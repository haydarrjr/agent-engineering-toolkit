#!/usr/bin/env python3
"""MARGOS vNext deterministic Policy and provider-neutral typed Reflex contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol

POLICY_VERSION = "margos-policy/v1"
REFLEX_REQUEST_VERSION = "margos-reflex-request/v1"
ROOT = Path(__file__).resolve().parents[1]
QUESTION_DOC = json.loads((ROOT/"contracts/question-set-v1.json").read_text(encoding="utf-8"))
THRESHOLD_DOC = json.loads((ROOT/"contracts/threshold-policy-v1.json").read_text(encoding="utf-8"))
QUESTION_SET_VERSION = QUESTION_DOC["version"]
THRESHOLD_POLICY_VERSION = THRESHOLD_DOC["version"]
QUESTION_SET = tuple(QUESTION_DOC["questions"])
THRESHOLDS = {k: float(THRESHOLD_DOC[k]) for k in ("choice_min_margin","needs_escalation","needs_independent_critic","transfer_sufficient")}

class Coordination(str, Enum):
    DIRECT="DIRECT"; TRANSFER="TRANSFER"; DELEGATED="DELEGATED"; SERIALIZED="SERIALIZED"

class Disposition(str, Enum):
    PROCEED="PROCEED"; FALLBACK_DIRECT="FALLBACK_DIRECT"; HALT="HALT"

class ComputeTier(str, Enum):
    ECONOMY_READ="ECONOMY_READ"; BALANCED_EXEC="BALANCED_EXEC"; FRONTIER_REASONING="FRONTIER_REASONING"

class Role(str, Enum):
    PRIMARY="PRIMARY"; SCOUT="SCOUT"; WORKER="WORKER"; VERIFIER="VERIFIER"; INDEPENDENT_CRITIC="INDEPENDENT_CRITIC"

class CalibrationStatus(str, Enum):
    UNKNOWN="UNKNOWN"; UNCALIBRATED="UNCALIBRATED"; CALIBRATED_FOR_FROZEN_SUITE="CALIBRATED_FOR_FROZEN_SUITE"; STALE="STALE"

class ReflexProvider(Protocol):
    def evaluate(self, request: Mapping[str, Any], questions: tuple[dict[str, Any], ...]) -> Mapping[str, Any]: ...

@dataclass(frozen=True)
class FixtureReflexProvider:
    answers: Mapping[str, Any]
    provider_id: str = "fixture"
    def evaluate(self, request, questions):
        del request, questions
        return {
            "schema_version":"margos-reflex-result/v1",
            "provider":{"kind":self.provider_id,"status":"AVAILABLE","calibration_status":"UNCALIBRATED"},
            "question_set_sha256":question_set_sha256(),
            "answers":dict(self.answers),
        }

def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)

def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()

def question_set_sha256() -> str:
    return _hash(QUESTION_DOC)

def _bool(obj, key, default=False):
    value=obj.get(key, default)
    if not isinstance(value,bool): raise ValueError(f"{key} must be boolean")
    return value

def normalize_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw,Mapping): raise ValueError("routing state must be an object")
    task,host,auth,work,ev,budget=(raw.get(k,{}) for k in ("task","host","authority","work_shape","evidence","budget"))
    for name,value in (("task",task),("host",host),("authority",auth),("work_shape",work),("evidence",ev),("budget",budget)):
        if not isinstance(value,Mapping): raise ValueError(f"{name} must be an object")
    mutation=str(task.get("mutation_kind","READ_ONLY")).upper()
    if mutation not in {"READ_ONLY","LOCAL_WRITE","REMOTE_WRITE","DESTRUCTIVE_OR_PRODUCTION"}: raise ValueError("unsupported mutation kind")
    available=host.get("available_compute_classes",[x.value for x in ComputeTier])
    if not isinstance(available,list) or not available or any(x not in {y.value for y in ComputeTier} for x in available):
        raise ValueError("invalid available_compute_classes")
    constraint=auth.get("explicit_model_provider_constraint")
    if constraint is not None and not isinstance(constraint,str): raise ValueError("invalid model/provider constraint")
    return {
      "schema_version":"margos-routing-state/v1",
      "task":{"objective":str(task.get("objective","")),"task_kind":str(task.get("task_kind","GENERAL")),"mutation_kind":mutation,"requested_outcome":str(task.get("requested_outcome","")),"verification_obligation":str(task.get("verification_obligation",""))},
      "host":{"host_id":str(host.get("host_id","UNKNOWN")),"subagents_proven":_bool(host,"subagents_proven"),"per_child_model_control_proven":_bool(host,"per_child_model_control_proven"),"reasoning_control_proven":_bool(host,"reasoning_control_proven"),"concurrency_proven":_bool(host,"concurrency_proven"),"isolation_proven":_bool(host,"isolation_proven"),"available_compute_classes":list(dict.fromkeys(available))},
      "authority":{"explicit_model_provider_constraint":constraint,"remote_write_authorized":_bool(auth,"remote_write_authorized"),"destructive_or_production_authorized":_bool(auth,"destructive_or_production_authorized"),"unresolved_external_effect":_bool(auth,"unresolved_external_effect")},
      "work_shape":{"obligation_count":max(0,int(work.get("obligation_count",1))),"overlapping_write_scopes":_bool(work,"overlapping_write_scopes"),"shared_state":_bool(work,"shared_state"),"parallel_safe":_bool(work,"parallel_safe")},
      "evidence":{"verification_failed":_bool(ev,"verification_failed"),"conflicting_sources":_bool(ev,"conflicting_sources"),"unresolved_ambiguity":_bool(ev,"unresolved_ambiguity"),"cross_system_impact":_bool(ev,"cross_system_impact"),"high_impact_correctness_or_security":_bool(ev,"high_impact_correctness_or_security")},
      "budget":{"max_children":max(0,int(budget.get("max_children",1))),"max_escalations":max(0,int(budget.get("max_escalations",1))),"cost_class":str(budget.get("cost_class","UNSPECIFIED")),"latency_class":str(budget.get("latency_class","UNSPECIFIED"))},
    }

def _safe_compute(state, admissible):
    evidence=state["evidence"]
    hard=any(evidence[k] for k in ("verification_failed","conflicting_sources","unresolved_ambiguity","cross_system_impact","high_impact_correctness_or_security"))
    if hard and "FRONTIER_REASONING" in admissible: return "FRONTIER_REASONING"
    if state["task"]["mutation_kind"]=="READ_ONLY" and "ECONOMY_READ" in admissible: return "ECONOMY_READ"
    if "BALANCED_EXEC" in admissible: return "BALANCED_EXEC"
    if "FRONTIER_REASONING" in admissible: return "FRONTIER_REASONING"
    if admissible: return admissible[0]
    raise ValueError("no admissible compute")

def _default_role(state, coordination):
    if coordination=="DIRECT": return "PRIMARY"
    kind=state["task"]["task_kind"].upper()
    if kind in {"VERIFY","VERIFICATION","REVIEW"}: return "VERIFIER"
    if state["task"]["mutation_kind"]=="READ_ONLY": return "SCOUT"
    return "WORKER"

def policy_pre_evaluate(raw: Mapping[str, Any]) -> dict[str, Any]:
    state=normalize_state(raw); rules=[]; blocked=[]
    coordination=[x.value for x in Coordination]
    compute=[x.value for x in ComputeTier if x.value in state["host"]["available_compute_classes"]]
    roles=[x.value for x in Role]
    def rule(i,d): rules.append({"rule_id":i,"detail":d})
    def block(k,v,i): blocked.append({"kind":k,"value":v,"rule_id":i})
    auth=state["authority"]; mutation=state["task"]["mutation_kind"]
    if auth["unresolved_external_effect"]:
        rule("MARGOS-POL-001","Unresolved external effect requires authoritative reconciliation.")
        return _pre(state,"HALT",coordination,compute,roles,rules,blocked,None,False)
    if mutation=="REMOTE_WRITE" and not auth["remote_write_authorized"]:
        rule("MARGOS-POL-002","Remote write is not authorized.")
        return _pre(state,"HALT",coordination,compute,roles,rules,blocked,None,False)
    if mutation=="DESTRUCTIVE_OR_PRODUCTION" and not auth["destructive_or_production_authorized"]:
        rule("MARGOS-POL-003","Destructive or production effect is not authorized.")
        return _pre(state,"HALT",coordination,compute,roles,rules,blocked,None,False)
    if mutation!="READ_ONLY" and "ECONOMY_READ" in compute:
        compute.remove("ECONOMY_READ"); block("compute","ECONOMY_READ","MARGOS-POL-004"); rule("MARGOS-POL-004","ECONOMY_READ is read-only.")
    if not state["host"]["subagents_proven"]:
        for value in list(coordination):
            if value!="DIRECT": coordination.remove(value); block("coordination",value,"MARGOS-POL-005")
        rule("MARGOS-POL-005","Subagent capability is not proven; fall back to the root.")
        forced={"disposition":"FALLBACK_DIRECT","coordination":"DIRECT","compute":_safe_compute(state,compute),"role":"PRIMARY"}
        return _pre(state,"FALLBACK_DIRECT",coordination,compute,roles,rules,blocked,forced,False)
    unsafe_parallel=state["work_shape"]["overlapping_write_scopes"] or state["work_shape"]["shared_state"] or not state["work_shape"]["parallel_safe"] or not state["host"]["concurrency_proven"] or state["work_shape"]["obligation_count"]<=1
    if unsafe_parallel and "DELEGATED" in coordination:
        coordination.remove("DELEGATED"); block("coordination","DELEGATED","MARGOS-POL-006"); rule("MARGOS-POL-006","Parallel delegation requires disjoint scopes, multiple obligations, parallel safety, and proven host concurrency.")
    if auth["explicit_model_provider_constraint"]: rule("MARGOS-POL-009","Explicit user model/provider constraint is preserved.")
    if not compute:
        rule("MARGOS-POL-010","No compute tier remains after deterministic filtering.")
        return _pre(state,"HALT",coordination,compute,roles,rules,blocked,None,False)
    if len(coordination)==1 and len(compute)==1:
        forced={"disposition":"PROCEED","coordination":coordination[0],"compute":compute[0],"role":_default_role(state,coordination[0])}
        return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,forced,False)
    return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,None,True)

def _pre(state,disposition,coordination,compute,roles,rules,blocked,forced,reflex):
    return {"policy_version":POLICY_VERSION,"state":state,"state_sha256":_hash(state),"disposition":disposition,"admissible":{"coordination":coordination,"compute":compute,"roles":roles},"blocked":blocked,"rules":rules,"forced_route":forced,"reflex_useful":reflex}

def build_reflex_request(pre: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version":REFLEX_REQUEST_VERSION,"routing_state":pre["state"],"admissible":pre["admissible"]}

def _distribution(answer, options, qid):
    probs=answer.get("probabilities")
    if not isinstance(probs,Mapping) or set(probs)!=set(options): raise ValueError(f"{qid} probabilities must cover the closed set")
    vals=[float(probs[o]) for o in options]
    if any(v<0 or v>1 for v in vals) or abs(sum(vals)-1)>1e-6: raise ValueError(f"invalid distribution for {qid}")
    return {o:float(probs[o]) for o in options}

def validate_reflex_result(result: Mapping[str, Any], pre: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result,Mapping) or result.get("schema_version")!="margos-reflex-result/v1": raise ValueError("invalid Reflex schema")
    if result.get("question_set_sha256")!=question_set_sha256(): raise ValueError("wrong question set")
    provider=result.get("provider",{})
    if not isinstance(provider,Mapping) or provider.get("status")!="AVAILABLE": raise ValueError("provider unavailable")
    answers=result.get("answers",{}); validated={}
    for q in QUESTION_SET:
        qid=q["id"]; a=answers.get(qid)
        if not isinstance(a,Mapping): raise ValueError(f"missing {qid}")
        if q["kind"] in {"choice","score"}:
            options=q.get("choices") or q.get("levels"); value=a.get("value")
            if value not in options: raise ValueError(f"invalid {qid}")
            probs=_distribution(a,options,qid)
            if qid=="coordination_preference" and value not in pre["admissible"]["coordination"]: raise ValueError("Policy-inadmissible coordination")
            if qid=="compute_preference" and value not in pre["admissible"]["compute"]: raise ValueError("Policy-inadmissible compute")
            validated[qid]={"value":value,"probabilities":probs}
        else:
            p=a.get("probability")
            if not isinstance(p,(int,float)) or isinstance(p,bool) or not 0<=float(p)<=1: raise ValueError(f"invalid {qid}")
            validated[qid]={"probability":float(p)}
    return {"schema_version":"margos-reflex-result/v1","provider":dict(provider),"question_set_sha256":result["question_set_sha256"],"answers":validated}

def _margin(answer):
    vals=sorted((float(v) for v in answer["probabilities"].values()),reverse=True)
    return vals[0]-vals[1] if len(vals)>1 else 1.0

def compose_decision(pre, reflex=None):
    state=pre["state"]
    if pre["disposition"]=="HALT": return _final(pre,{"disposition":"HALT","coordination":None,"compute":None,"role":None,"source":"DETERMINISTIC_POLICY","abstained":True})
    if pre["forced_route"]: return _final(pre,{**pre["forced_route"],"source":"DETERMINISTIC_POLICY","abstained":False})
    if reflex is None: return _final(pre,{"disposition":"PROCEED","coordination":"DIRECT","compute":_safe_compute(state,pre["admissible"]["compute"]),"role":"PRIMARY","source":"POLICY_FALLBACK","abstained":True})
    a=reflex["answers"]; ca=a["coordination_preference"]; co=a["compute_preference"]
    if _margin(ca)<THRESHOLDS["choice_min_margin"] or _margin(co)<THRESHOLDS["choice_min_margin"]:
        return _final(pre,{"disposition":"FALLBACK_DIRECT","coordination":"DIRECT","compute":_safe_compute(state,pre["admissible"]["compute"]),"role":"PRIMARY","source":"LOW_MARGIN_FALLBACK","abstained":True})
    coordination=ca["value"]; compute=co["value"]
    critic=a["needs_independent_critic"]["probability"]>=THRESHOLDS["needs_independent_critic"]
    if a["needs_escalation"]["probability"]>=THRESHOLDS["needs_escalation"] and "FRONTIER_REASONING" in pre["admissible"]["compute"]: compute="FRONTIER_REASONING"
    if critic and "TRANSFER" in pre["admissible"]["coordination"]:
        coordination="TRANSFER"; role="INDEPENDENT_CRITIC"
    else:
        if coordination=="TRANSFER" and a["transfer_sufficient"]["probability"]<THRESHOLDS["transfer_sufficient"]: coordination="DIRECT"
        role=_default_role(state,coordination)
    return _final(pre,{"disposition":"PROCEED","coordination":coordination,"compute":compute,"role":role,"source":"REFLEX_ASSISTED","abstained":False})

def _final(pre,candidate):
    state=pre["state"]
    if pre["disposition"]=="HALT":
        return {"disposition":"HALT","coordination":None,"compute":None,"role":None,"source":"DETERMINISTIC_POLICY","abstained":True,"model_provider_constraint":state["authority"]["explicit_model_provider_constraint"]}
    if candidate["coordination"] not in pre["admissible"]["coordination"]: raise ValueError("final coordination violates Policy")
    if candidate["compute"] not in pre["admissible"]["compute"]: raise ValueError("final compute violates Policy")
    if candidate["role"] not in pre["admissible"]["roles"]: raise ValueError("final role violates Policy")
    return {**candidate,"model_provider_constraint":state["authority"]["explicit_model_provider_constraint"]}

def decide(raw_state, provider: ReflexProvider|None=None):
    pre=policy_pre_evaluate(raw_state); reflex=None; raw_reflex=None
    provider_meta={"kind":"none","status":"DISABLED","calibration_status":"UNKNOWN"}
    if provider is not None and pre["reflex_useful"] and pre["disposition"]!="HALT":
        try:
            raw_reflex=provider.evaluate(build_reflex_request(pre),QUESTION_SET)
            if isinstance(raw_reflex,Mapping) and isinstance(raw_reflex.get("provider"),Mapping):
                provider_meta=dict(raw_reflex["provider"])
            status=provider_meta.get("status")
            if status=="AVAILABLE":
                reflex=validate_reflex_result(raw_reflex,pre)
                provider_meta=dict(reflex["provider"])
            elif status in {"NOT_CONFIGURED","ERROR"}:
                reflex=None
            else:
                raise ValueError(f"unsupported provider status: {status}")
        except (TypeError,ValueError,KeyError) as exc:
            provider_meta={**provider_meta,"status":"ERROR","error":f"{type(exc).__name__}: {exc}"}
    decision=compose_decision(pre,reflex)
    return {"schema_version":"margos-route-receipt/v1","decision_authority":"PROPOSED","state_sha256":pre["state_sha256"],"policy_version":POLICY_VERSION,"question_set_version":QUESTION_SET_VERSION,"question_set_sha256":question_set_sha256(),"threshold_policy_version":THRESHOLD_POLICY_VERSION,"provider":provider_meta,"admissible":pre["admissible"],"blocked":pre["blocked"],"policy_rules_applied":pre["rules"],"reflex":{"answers":reflex["answers"] if reflex else {}},"selected":decision,"host_execution":{"status":"PENDING"}}

def _read(path):
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValueError("JSON input must be an object")
    return value

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--state",type=Path,required=True); ap.add_argument("--fixture-reflex",type=Path); ap.add_argument("--output",type=Path)
    args=ap.parse_args(); provider=FixtureReflexProvider(_read(args.fixture_reflex)) if args.fixture_reflex else None
    rendered=json.dumps(decide(_read(args.state),provider),indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    if args.output: args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(rendered,encoding="utf-8")
    else: print(rendered,end="")
    return 0

if __name__=="__main__": raise SystemExit(main())
