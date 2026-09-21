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

POLICY_VERSION = "margos-policy/v2"
REFLEX_REQUEST_VERSION = "margos-reflex-request/v2"
REFLEX_RESULT_VERSION = "margos-reflex-result/v2"
ROUTE_RECEIPT_VERSION = "margos-route-receipt/v2"
ROOT = Path(__file__).resolve().parents[1]
QUESTION_DOC = json.loads((ROOT/"contracts/question-set-v2.json").read_text(encoding="utf-8"))
THRESHOLD_DOC = json.loads((ROOT/"contracts/threshold-policy-v2.json").read_text(encoding="utf-8"))
QUESTION_SET_VERSION = QUESTION_DOC["version"]
THRESHOLD_POLICY_VERSION = THRESHOLD_DOC["version"]
QUESTION_SET = tuple(QUESTION_DOC["questions"])
THRESHOLDS = {
    key: float(THRESHOLD_DOC[key])
    for key in (
        "choice_min_margin",
        "ambiguity_escalation",
        "verification_escalation",
        "direct_escalation",
        "independent_critic",
        "transfer_sufficient",
    )
}
ROUTING_THRESHOLD_KEYS = frozenset(THRESHOLDS)


def dead_thresholds() -> set[str]:
    """Return threshold fields present in the contract but unused by routing."""
    return set(THRESHOLD_DOC) - ROUTING_THRESHOLD_KEYS - {"version", "selection"}

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


class AdmissionReason(str, Enum):
    CALL_REFLEX = "CALL_REFLEX"
    SKIP_POLICY_SUFFICIENT = "SKIP_POLICY_SUFFICIENT"
    SKIP_NO_MATERIAL_ROUTE_DELTA = "SKIP_NO_MATERIAL_ROUTE_DELTA"
    SKIP_HOST_CANNOT_EXPLOIT_RESULT = "SKIP_HOST_CANNOT_EXPLOIT_RESULT"
    SKIP_BUDGET = "SKIP_BUDGET"
    SKIP_DISABLED = "SKIP_DISABLED"


@dataclass(frozen=True)
class ReflexAdmission:
    decision: str
    reason: str
    detail: str
    policy_state_sha256: str

    @property
    def admitted(self) -> bool:
        return self.decision == AdmissionReason.CALL_REFLEX.value

@dataclass(frozen=True)
class FixtureReflexProvider:
    answers: Mapping[str, Any]
    provider_id: str = "fixture"
    def evaluate(self, request, questions):
        del request, questions
        return {
            "schema_version":REFLEX_RESULT_VERSION,
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


def threshold_policy_sha256() -> str:
    return _hash(THRESHOLD_DOC)

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
      "schema_version":"margos-routing-state/v2",
      "task":{"objective":str(task.get("objective","")),"task_kind":str(task.get("task_kind","GENERAL")),"mutation_kind":mutation,"requested_outcome":str(task.get("requested_outcome","")),"verification_obligation":str(task.get("verification_obligation","")),"trivial":_bool(task,"trivial")},
      "host":{"host_id":str(host.get("host_id","UNKNOWN")),"subagents_proven":_bool(host,"subagents_proven"),"per_child_model_control_proven":_bool(host,"per_child_model_control_proven"),"reasoning_control_proven":_bool(host,"reasoning_control_proven"),"concurrency_proven":_bool(host,"concurrency_proven"),"isolation_proven":_bool(host,"isolation_proven"),"available_compute_classes":list(dict.fromkeys(available))},
      "authority":{"explicit_model_provider_constraint":constraint,"remote_write_authorized":_bool(auth,"remote_write_authorized"),"destructive_or_production_authorized":_bool(auth,"destructive_or_production_authorized"),"unresolved_external_effect":_bool(auth,"unresolved_external_effect")},
      "work_shape":{"obligation_count":max(0,int(work.get("obligation_count",1))),"overlapping_write_scopes":_bool(work,"overlapping_write_scopes"),"shared_state":_bool(work,"shared_state"),"parallel_safe":_bool(work,"parallel_safe"),"route_equivalent":_bool(work,"route_equivalent")},
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
    if state["task"]["trivial"]:
        rule("MARGOS-POL-011", "Explicitly trivial work uses the direct lowest safe route.")
        forced={"disposition":"PROCEED","coordination":"DIRECT","compute":_safe_compute(state,compute),"role":"PRIMARY"}
        return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,forced,False)
    if mutation!="READ_ONLY" and "ECONOMY_READ" in compute:
        compute.remove("ECONOMY_READ"); block("compute","ECONOMY_READ","MARGOS-POL-004"); rule("MARGOS-POL-004","ECONOMY_READ is read-only.")
    hard_evidence = any(
        state["evidence"][key]
        for key in (
            "verification_failed",
            "conflicting_sources",
            "unresolved_ambiguity",
            "cross_system_impact",
            "high_impact_correctness_or_security",
        )
    )
    if hard_evidence and "FRONTIER_REASONING" in compute:
        # These are deterministic Policy signals, not Reflex opinions.  JEV
        # may still propose coordination/role details for an admitted route,
        # but it cannot turn a failed or high-impact verification obligation
        # into a cheaper compute tier.
        for value in ("ECONOMY_READ", "BALANCED_EXEC"):
            if value in compute:
                compute.remove(value)
                block("compute", value, "MARGOS-POL-012")
        rule(
            "MARGOS-POL-012",
            "Hard verification evidence fixes the minimum compute tier at FRONTIER_REASONING.",
        )
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
    if hard_evidence:
        policy_coordination = (
            "TRANSFER"
            if "TRANSFER" in coordination and state["host"]["subagents_proven"]
            else "DIRECT"
        )
        policy_role = (
            "INDEPENDENT_CRITIC"
            if "INDEPENDENT_CRITIC" in roles and state["host"]["subagents_proven"]
            else "PRIMARY"
        )
        forced = {
            "disposition": "PROCEED",
            "coordination": policy_coordination,
            "compute": "FRONTIER_REASONING",
            "role": policy_role,
        }
        rule(
            "MARGOS-POL-013",
            "Hard verification evidence fixes the safe coordination and critic role deterministically.",
        )
        return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,forced,False)
    if len(coordination)==1 and len(compute)==1:
        forced={"disposition":"PROCEED","coordination":coordination[0],"compute":compute[0],"role":_default_role(state,coordination[0])}
        return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,forced,False)
    return _pre(state,"PROCEED",coordination,compute,roles,rules,blocked,None,True)

def _pre(state,disposition,coordination,compute,roles,rules,blocked,forced,reflex):
    return {"policy_version":POLICY_VERSION,"state":state,"state_sha256":_hash(state),"disposition":disposition,"admissible":{"coordination":coordination,"compute":compute,"roles":roles},"blocked":blocked,"rules":rules,"forced_route":forced,"reflex_useful":reflex}


def admit_reflex(
    pre: Mapping[str, Any],
    *,
    provider_enabled: bool = True,
) -> ReflexAdmission:
    """Decide locally whether a Reflex call can materially change a safe route."""
    if not provider_enabled:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_DISABLED.value,
            "Reflex provider is disabled or not configured.",
            pre["state_sha256"],
        )
    if pre["disposition"] == "HALT" or pre["forced_route"]:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_POLICY_SUFFICIENT.value,
            "Deterministic Policy already fixes the route or halts execution.",
            pre["state_sha256"],
        )
    state = pre["state"]
    if state["budget"]["max_escalations"] <= 0 or state["budget"]["max_children"] <= 0:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_BUDGET.value,
            "The declared budget cannot exploit an alternate Reflex route.",
            pre["state_sha256"],
        )
    host = state["host"]
    if not host["subagents_proven"]:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_HOST_CANNOT_EXPLOIT_RESULT.value,
            "The host has no proven subagent capability.",
            pre["state_sha256"],
        )
    if state["work_shape"]["route_equivalent"]:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_NO_MATERIAL_ROUTE_DELTA.value,
            "The caller marked the remaining routes as downstream-equivalent.",
            pre["state_sha256"],
        )
    hard_evidence = any(
        state["evidence"][key]
        for key in (
            "verification_failed",
            "conflicting_sources",
            "unresolved_ambiguity",
            "cross_system_impact",
            "high_impact_correctness_or_security",
        )
    )
    if hard_evidence and pre["admissible"]["compute"] == ["FRONTIER_REASONING"]:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_POLICY_SUFFICIENT.value,
            "Policy fixed the compute floor at FRONTIER_REASONING from hard verification evidence; Reflex cannot create a safe cheaper route.",
            pre["state_sha256"],
        )
    coordination = pre["admissible"]["coordination"]
    compute = pre["admissible"]["compute"]
    if len(coordination) <= 1 and len(compute) <= 1:
        return ReflexAdmission(
            "SKIP",
            AdmissionReason.SKIP_NO_MATERIAL_ROUTE_DELTA.value,
            "All Policy-admissible routes have the same downstream shape.",
            pre["state_sha256"],
        )
    if not host["per_child_model_control_proven"] and len(compute) > 1:
        # A provider cannot make a useful per-child compute choice when the host
        # cannot prove that it can apply one.
        meaningful_coordination = any(x != "DIRECT" for x in coordination)
        if not meaningful_coordination:
            return ReflexAdmission(
                "SKIP",
                AdmissionReason.SKIP_HOST_CANNOT_EXPLOIT_RESULT.value,
                "The host cannot exploit alternate compute choices and has no alternate coordination shape.",
                pre["state_sha256"],
            )
    return ReflexAdmission(
        "CALL_REFLEX",
        AdmissionReason.CALL_REFLEX.value,
        "Multiple Policy-admissible routes have a material downstream difference.",
        pre["state_sha256"],
    )

def build_reflex_request(pre: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": REFLEX_REQUEST_VERSION,
        "routing_state": pre["state"],
        "admissible": pre["admissible"],
        "threshold_policy_sha256": threshold_policy_sha256(),
    }

def _distribution(answer, options, qid):
    probs=answer.get("probabilities")
    if not isinstance(probs,Mapping) or set(probs)!=set(options): raise ValueError(f"{qid} probabilities must cover the closed set")
    vals=[float(probs[o]) for o in options]
    if any(v<0 or v>1 for v in vals) or abs(sum(vals)-1)>1e-6: raise ValueError(f"invalid distribution for {qid}")
    return {o:float(probs[o]) for o in options}

def validate_reflex_result(result: Mapping[str, Any], pre: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result,Mapping) or result.get("schema_version")!=REFLEX_RESULT_VERSION: raise ValueError("invalid Reflex schema")
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
    return {"schema_version":REFLEX_RESULT_VERSION,"provider":dict(provider),"question_set_sha256":result["question_set_sha256"],"answers":validated}

def _margin(answer):
    vals = sorted((float(v) for v in answer["probabilities"].values()), reverse=True)
    return vals[0] - vals[1] if len(vals) > 1 else 1.0


def _mass(answer: Mapping[str, Any], labels: tuple[str, ...]) -> float:
    probs = answer["probabilities"]
    return sum(float(probs[label]) for label in labels)


def reflex_signals(reflex: Mapping[str, Any] | None) -> dict[str, float]:
    if reflex is None:
        return {}
    a = reflex["answers"]
    ambiguity_high = _mass(a["task_ambiguity"], ("HIGH", "SEVERE"))
    verification_high = _mass(a["verification_risk"], ("HIGH", "CRITICAL"))
    needs_escalation = float(a["needs_escalation"]["probability"])
    return {
        "task_ambiguity_high_probability": ambiguity_high,
        "verification_risk_high_probability": verification_high,
        "needs_escalation_probability": needs_escalation,
        "ambiguity_escalates": ambiguity_high >= THRESHOLDS["ambiguity_escalation"],
        "verification_escalates": verification_high >= THRESHOLDS["verification_escalation"],
        "direct_escalates": needs_escalation >= THRESHOLDS["direct_escalation"],
        "frontier_required": (
            ambiguity_high >= THRESHOLDS["ambiguity_escalation"]
            or verification_high >= THRESHOLDS["verification_escalation"]
            or needs_escalation >= THRESHOLDS["direct_escalation"]
        ),
        "needs_independent_critic_probability": float(
            a["needs_independent_critic"]["probability"]
        ),
        "transfer_sufficient_probability": float(a["transfer_sufficient"]["probability"]),
    }


def compose_decision(pre, reflex=None):
    state = pre["state"]
    if pre["disposition"] == "HALT":
        return _final(
            pre,
            {
                "disposition": "HALT",
                "coordination": None,
                "compute": None,
                "role": None,
                "source": "DETERMINISTIC_POLICY",
                "abstained": True,
            },
        )
    if pre["forced_route"]:
        return _final(
            pre,
            {**pre["forced_route"], "source": "DETERMINISTIC_POLICY", "abstained": False},
        )
    if reflex is None:
        return _final(
            pre,
            {
                "disposition": "PROCEED",
                "coordination": "DIRECT",
                "compute": _safe_compute(state, pre["admissible"]["compute"]),
                "role": "PRIMARY",
                "source": "POLICY_FALLBACK",
                "abstained": True,
            },
        )
    a = reflex["answers"]
    ca = a["coordination_preference"]
    co = a["compute_preference"]
    if _margin(ca) < THRESHOLDS["choice_min_margin"] or _margin(co) < THRESHOLDS[
        "choice_min_margin"
    ]:
        return _final(
            pre,
            {
                "disposition": "FALLBACK_DIRECT",
                "coordination": "DIRECT",
                "compute": _safe_compute(state, pre["admissible"]["compute"]),
                "role": "PRIMARY",
                "source": "LOW_MARGIN_FALLBACK",
                "abstained": True,
            },
        )
    signals = reflex_signals(reflex)
    coordination = ca["value"]
    compute = co["value"]
    if signals["frontier_required"] and "FRONTIER_REASONING" in pre["admissible"]["compute"]:
        compute = "FRONTIER_REASONING"
    critic = (
        signals["needs_independent_critic_probability"]
        >= THRESHOLDS["independent_critic"]
    )
    if critic and "TRANSFER" in pre["admissible"]["coordination"]:
        coordination = "TRANSFER"
        role = "INDEPENDENT_CRITIC"
    else:
        if (
            coordination == "TRANSFER"
            and signals["transfer_sufficient_probability"] < THRESHOLDS["transfer_sufficient"]
        ):
            coordination = "DIRECT"
        role = _default_role(state, coordination)
    return _final(
        pre,
        {
            "disposition": "PROCEED",
            "coordination": coordination,
            "compute": compute,
            "role": role,
            "source": "REFLEX_ASSISTED",
            "abstained": False,
        },
    )


def _final(pre,candidate):
    state=pre["state"]
    if pre["disposition"]=="HALT":
        return {"disposition":"HALT","coordination":None,"compute":None,"role":None,"source":"DETERMINISTIC_POLICY","abstained":True,"model_provider_constraint":state["authority"]["explicit_model_provider_constraint"]}
    if candidate["coordination"] not in pre["admissible"]["coordination"]: raise ValueError("final coordination violates Policy")
    if candidate["compute"] not in pre["admissible"]["compute"]: raise ValueError("final compute violates Policy")
    if candidate["role"] not in pre["admissible"]["roles"]: raise ValueError("final role violates Policy")
    return {**candidate,"model_provider_constraint":state["authority"]["explicit_model_provider_constraint"]}


def _provider_enabled(provider: ReflexProvider | None) -> bool:
    if provider is None:
        return False
    probe = getattr(provider, "is_configured", None)
    if callable(probe):
        return bool(probe())
    return True

def decide(raw_state, provider: ReflexProvider | None = None):
    pre = policy_pre_evaluate(raw_state)
    reflex = None
    provider_meta = {"kind": "none", "status": "DISABLED", "calibration_status": "UNKNOWN"}
    admission = admit_reflex(pre, provider_enabled=_provider_enabled(provider))
    if provider is not None and not _provider_enabled(provider):
        provider_meta = {
            "kind": type(provider).__name__,
            "status": "NOT_CONFIGURED",
            "calibration_status": "UNKNOWN",
        }
    if admission.admitted:
        try:
            raw_reflex = provider.evaluate(build_reflex_request(pre), QUESTION_SET)
            if isinstance(raw_reflex, Mapping) and isinstance(raw_reflex.get("provider"), Mapping):
                provider_meta = dict(raw_reflex["provider"])
            status = provider_meta.get("status")
            if status == "AVAILABLE":
                reflex = validate_reflex_result(raw_reflex, pre)
                provider_meta = dict(reflex["provider"])
            elif status in {"NOT_CONFIGURED", "ERROR"}:
                reflex = None
            else:
                raise ValueError(f"unsupported provider status: {status}")
        except (TypeError, ValueError, KeyError) as exc:
            provider_meta = {
                **provider_meta,
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
    decision = compose_decision(pre, reflex)
    return {
        "schema_version": ROUTE_RECEIPT_VERSION,
        "decision_authority": "PROPOSED",
        "state_sha256": pre["state_sha256"],
        "policy_version": POLICY_VERSION,
        "question_set_version": QUESTION_SET_VERSION,
        "question_set_sha256": question_set_sha256(),
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "threshold_policy_sha256": threshold_policy_sha256(),
        "provider": provider_meta,
        "admission": {
            "decision": admission.decision,
            "reason": admission.reason,
            "detail": admission.detail,
            "policy_state_sha256": admission.policy_state_sha256,
        },
        "admissible": pre["admissible"],
        "blocked": pre["blocked"],
        "policy_rules_applied": pre["rules"],
        "reflex": {
            "answers": reflex["answers"] if reflex else {},
            "derived_signals": reflex_signals(reflex),
        },
        "selected": decision,
        "host_execution": {"status": "PENDING"},
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--fixture-reflex", type=Path)
    ap.add_argument(
        "--reflex-provider",
        choices=("none", "jev"),
        default="none",
        help="Live provider is explicit opt-in; API key presence alone never enables it.",
    )
    ap.add_argument("--jev-model")
    ap.add_argument("--calibration-binding", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.fixture_reflex and args.reflex_provider != "none":
        ap.error("--fixture-reflex cannot be combined with a live provider")
    if args.jev_model and args.reflex_provider != "jev":
        ap.error("--jev-model requires --reflex-provider jev")
    if args.calibration_binding and args.reflex_provider != "jev":
        ap.error("--calibration-binding requires --reflex-provider jev")
    if args.calibration_binding and not args.jev_model:
        ap.error("--calibration-binding requires an explicit --jev-model")
    provider: ReflexProvider | None = None
    if args.fixture_reflex:
        provider = FixtureReflexProvider(_read(args.fixture_reflex))
    elif args.reflex_provider == "jev":
        import margos_reflex_jev

        binding = _read(args.calibration_binding) if args.calibration_binding else None
        provider = margos_reflex_jev.JevReflexProvider(
            model=args.jev_model, calibration_binding=binding
        )
    rendered = json.dumps(
        decide(_read(args.state), provider),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
