#!/usr/bin/env python3
"""Optional TypeSafe Jev Reflex adapter for MARGOS vNext.

This module is deliberately outside the deterministic Policy kernel. It uses only
Python stdlib, never logs API keys, and degrades to a typed unavailable/error
result so MARGOS can fall back safely.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import margos_decide as core

DEFAULT_BASE_URL="https://api.typesafe.ai"
DEFAULT_MODEL="jev-latest"
Transport=Callable[[str,str,Mapping[str,Any],float],Mapping[str,Any]]

_COORDINATION={
    "DIRECT":"Keep the obligation on the root/integration session.",
    "TRANSFER":"Use one bounded child for one self-contained obligation.",
    "DELEGATED":"Use multiple independent children with disjoint scopes.",
    "SERIALIZED":"Use children sequentially because state or ownership is shared.",
}
_COMPUTE={
    "ECONOMY_READ":"Bounded low-ambiguity read-only work.",
    "BALANCED_EXEC":"Ordinary implementation, debugging, or verification.",
    "FRONTIER_REASONING":"Contradiction-heavy, verification-failed, high-impact, or hard synthesis.",
}
_SCORE_LEVELS={
    "task_ambiguity":[
        "Low: the obligation and success criteria are clear.",
        "Moderate: some interpretation is needed but the route is still bounded.",
        "High: unresolved ambiguity could materially change implementation or verification.",
        "Severe: the obligation cannot be safely resolved without stronger reasoning or clarification.",
    ],
    "verification_risk":[
        "Low: the selected route has direct, bounded verification.",
        "Medium: verification is available but has meaningful uncertainty.",
        "High: the selected route may fail to close the declared verification obligation.",
        "Critical: incorrect routing could leave a high-impact claim or mutation inadequately verified.",
    ],
}

class JevAdapterError(ValueError):
    pass

def _clip(value: Any, limit: int=6000) -> str:
    text=str(value or "")
    return text if len(text)<=limit else text[:limit]+"…"

def project_reflex_state(request: Mapping[str,Any]) -> dict[str,Any]:
    if request.get("schema_version")!=core.REFLEX_REQUEST_VERSION:
        raise JevAdapterError("unsupported Reflex request schema")
    state=request.get("routing_state")
    admissible=request.get("admissible")
    if not isinstance(state,Mapping) or not isinstance(admissible,Mapping):
        raise JevAdapterError("invalid Reflex request")
    task=state["task"]; host=state["host"]; auth=state["authority"]
    return {
        "task":{
            "objective":_clip(task.get("objective")),
            "task_kind":_clip(task.get("task_kind"),256),
            "mutation_kind":task.get("mutation_kind"),
            "requested_outcome":_clip(task.get("requested_outcome")),
            "verification_obligation":_clip(task.get("verification_obligation")),
        },
        "host_capabilities":{
            "subagents_proven":bool(host.get("subagents_proven")),
            "per_child_model_control_proven":bool(host.get("per_child_model_control_proven")),
            "reasoning_control_proven":bool(host.get("reasoning_control_proven")),
            "concurrency_proven":bool(host.get("concurrency_proven")),
            "isolation_proven":bool(host.get("isolation_proven")),
        },
        "authority":{
            "explicit_model_provider_constraint_present":bool(auth.get("explicit_model_provider_constraint")),
            "remote_write_authorized":bool(auth.get("remote_write_authorized")),
            "destructive_or_production_authorized":bool(auth.get("destructive_or_production_authorized")),
            "unresolved_external_effect":bool(auth.get("unresolved_external_effect")),
        },
        "work_shape":dict(state["work_shape"]),
        "evidence":dict(state["evidence"]),
        "budget":dict(state["budget"]),
        "admissible":{
            "coordination":list(admissible.get("coordination",[])),
            "compute":list(admissible.get("compute",[])),
        },
    }

def _choice_question(question: Mapping[str,Any], admissible: list[str]) -> dict[str,Any] | None:
    options=[x for x in question["choices"] if x in admissible]
    if len(options)<=1: return None
    descriptions=_COORDINATION if question["id"]=="coordination_preference" else _COMPUTE
    return {"type":"choice","instructions":question["criterion"],"criteria":{x:descriptions[x] for x in options}}

def build_jev_payload(request: Mapping[str,Any], questions: tuple[dict[str,Any],...], model: str=DEFAULT_MODEL) -> dict[str,Any]:
    state=project_reflex_state(request)
    payload_questions={}
    for q in questions:
        qid=q["id"]
        if q["kind"]=="choice":
            allowed=state["admissible"]["coordination" if qid=="coordination_preference" else "compute"]
            item=_choice_question(q,allowed)
            if item is not None: payload_questions[qid]=item
        elif q["kind"]=="score":
            payload_questions[qid]={"type":"score","instructions":q["criterion"],"criteria":_SCORE_LEVELS[qid]}
        elif q["kind"]=="noul":
            payload_questions[qid]={"type":"noul","instructions":q["criterion"]}
        else:
            raise JevAdapterError(f"unsupported question kind: {q['kind']}")
    return {"model":model,"state":state,"questions":payload_questions}

def _http_transport(base_url: str, api_key: str, payload: Mapping[str,Any], timeout: float) -> Mapping[str,Any]:
    if not base_url.startswith("https://"):
        raise JevAdapterError("TypeSafe base URL must use HTTPS")
    endpoint=base_url.rstrip("/")+"/v1/systemone"
    request=urllib.request.Request(
        endpoint,
        data=json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode("utf-8"),
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","User-Agent":"agent-engineering-toolkit/margos-vnext"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            decoded=json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JevAdapterError(f"TypeSafe HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise JevAdapterError(f"TypeSafe transport error: {type(exc.reason).__name__}") from None
    except TimeoutError:
        raise JevAdapterError("TypeSafe request timed out") from None
    except json.JSONDecodeError:
        raise JevAdapterError("TypeSafe returned invalid JSON") from None
    if not isinstance(decoded,Mapping):
        raise JevAdapterError("TypeSafe response must be an object")
    return decoded

def _choice_answer(raw: Mapping[str,Any], options: list[str]) -> dict[str,Any]:
    choice=raw.get("choice")
    probs=raw.get("probabilities")
    if choice not in options or not isinstance(probs,Mapping):
        raise JevAdapterError("invalid Jev Choice answer")
    mapped={x:float(probs[x]) for x in options}
    return {"value":choice,"probabilities":mapped}

def _score_answer(raw: Mapping[str,Any], levels: list[str]) -> dict[str,Any]:
    probs=raw.get("probabilities")
    if not isinstance(probs,Mapping):
        raise JevAdapterError("invalid Jev Score answer")
    mapped={}
    for index,level in enumerate(levels):
        key=str(index)
        if key not in probs: raise JevAdapterError("Jev Score distribution does not match rubric")
        mapped[level]=float(probs[key])
    value=max(mapped,key=mapped.get)
    return {"value":value,"probabilities":mapped}

def _noul_answer(raw: Mapping[str,Any]) -> dict[str,Any]:
    value=raw.get("noul",raw.get("probability"))
    if not isinstance(value,(int,float)) or isinstance(value,bool):
        raise JevAdapterError("invalid Jev Noul answer")
    return {"probability":float(value)}

def to_reflex_result(raw: Mapping[str,Any], request: Mapping[str,Any], questions: tuple[dict[str,Any],...], model: str) -> dict[str,Any]:
    answers_raw=raw.get("answers")
    if not isinstance(answers_raw,Mapping):
        raise JevAdapterError("TypeSafe response missing answers")
    admissible=request["admissible"]; answers={}
    for q in questions:
        qid=q["id"]
        if q["kind"]=="choice":
            options=[x for x in q["choices"] if x in admissible["coordination" if qid=="coordination_preference" else "compute"]]
            all_options=list(q["choices"])
            if len(options)==1:
                answers[qid]={"value":options[0],"probabilities":{x:(1.0 if x==options[0] else 0.0) for x in all_options}}
            else:
                item=answers_raw.get(qid)
                if not isinstance(item,Mapping): raise JevAdapterError(f"missing Jev answer: {qid}")
                local=_choice_answer(item,options)
                answers[qid]={"value":local["value"],"probabilities":{x:local["probabilities"].get(x,0.0) for x in all_options}}
        elif q["kind"]=="score":
            item=answers_raw.get(qid)
            if not isinstance(item,Mapping): raise JevAdapterError(f"missing Jev answer: {qid}")
            answers[qid]=_score_answer(item,list(q["levels"]))
        else:
            item=answers_raw.get(qid)
            if not isinstance(item,Mapping): raise JevAdapterError(f"missing Jev answer: {qid}")
            answers[qid]=_noul_answer(item)
    provider={"kind":"typesafe-jev","status":"AVAILABLE","calibration_status":"UNCALIBRATED","requested_model":model}
    if isinstance(raw.get("model"),str): provider["response_model"]=raw["model"]
    if isinstance(raw.get("usage"),Mapping): provider["usage"]=dict(raw["usage"])
    return {"schema_version":"margos-reflex-result/v1","provider":provider,"question_set_sha256":core.question_set_sha256(),"answers":answers}

@dataclass
class JevReflexProvider:
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: float = 15.0
    transport: Transport | None = None

    def evaluate(self, request: Mapping[str,Any], questions: tuple[dict[str,Any],...]) -> Mapping[str,Any]:
        key=os.environ.get("TYPESAFE_API_KEY","") if self.api_key is None else self.api_key
        base=self.base_url or os.environ.get("TYPESAFE_BASE_URL",DEFAULT_BASE_URL)
        model=self.model or os.environ.get("TYPESAFE_DEFAULT_MODEL",DEFAULT_MODEL)
        if not key:
            return {"schema_version":"margos-reflex-result/v1","provider":{"kind":"typesafe-jev","status":"NOT_CONFIGURED","calibration_status":"UNKNOWN"},"question_set_sha256":core.question_set_sha256(),"answers":{}}
        try:
            payload=build_jev_payload(request,questions,model)
            raw=(self.transport or _http_transport)(base,key,payload,float(self.timeout))
            return to_reflex_result(raw,request,questions,model)
        except (JevAdapterError,KeyError,TypeError,ValueError) as exc:
            return {"schema_version":"margos-reflex-result/v1","provider":{"kind":"typesafe-jev","status":"ERROR","calibration_status":"UNKNOWN","error":f"{type(exc).__name__}: {exc}"},"question_set_sha256":core.question_set_sha256(),"answers":{}}
