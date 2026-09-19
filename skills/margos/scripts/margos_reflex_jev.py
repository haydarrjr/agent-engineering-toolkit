#!/usr/bin/env python3
"""Optional TypeSafe Jev Reflex adapter for both MARGOS Reflex decision families.

One transport/auth/error boundary serves Routing Reflex and Context Reflex.
The adapter is opt-in, stdlib-only, never logs API keys, and never performs
network I/O when TYPESAFE_API_KEY is absent.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import margos_decide as core

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
CONTEXT_REQUEST_VERSION = "margos-context-reflex-request/v1"
CONTEXT_RESULT_VERSION = "margos-context-reflex-result/v1"
Transport = Callable[[str, str, Mapping[str, Any], float], Mapping[str, Any]]

_COORDINATION = {
    "DIRECT": "Keep the obligation on the root/integration session.",
    "TRANSFER": "Use one bounded child for one self-contained obligation.",
    "DELEGATED": "Use multiple independent children with disjoint scopes.",
    "SERIALIZED": "Use children sequentially because state or ownership is shared.",
}
_COMPUTE = {
    "ECONOMY_READ": "Bounded low-ambiguity read-only work.",
    "BALANCED_EXEC": "Ordinary implementation, debugging, or verification.",
    "FRONTIER_REASONING": "Contradiction-heavy, verification-failed, high-impact, or hard synthesis.",
}
_SCORE_LEVELS = {
    "task_ambiguity": [
        "Low: the obligation and success criteria are clear.",
        "Moderate: some interpretation is needed but the route is still bounded.",
        "High: unresolved ambiguity could materially change implementation or verification.",
        "Severe: the obligation cannot be safely resolved without stronger reasoning or clarification.",
    ],
    "verification_risk": [
        "Low: the selected route has direct, bounded verification.",
        "Medium: verification is available but has meaningful uncertainty.",
        "High: the selected route may fail to close the declared verification obligation.",
        "Critical: incorrect routing could leave a high-impact claim or mutation inadequately verified.",
    ],
}


class JevAdapterError(ValueError):
    pass


def _clip(value: Any, limit: int = 6000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


def _question_hash_for_request(request: Mapping[str, Any]) -> str:
    if request.get("schema_version") == CONTEXT_REQUEST_VERSION:
        value = request.get("question_set_sha256")
        if not isinstance(value, str):
            raise JevAdapterError("Context Reflex request missing question-set hash")
        return value
    return core.question_set_sha256()


def _result_version_for_request(request: Mapping[str, Any]) -> str:
    if request.get("schema_version") == CONTEXT_REQUEST_VERSION:
        return CONTEXT_RESULT_VERSION
    if request.get("schema_version") == core.REFLEX_REQUEST_VERSION:
        return "margos-reflex-result/v1"
    raise JevAdapterError("unsupported Reflex request schema")


def project_reflex_state(request: Mapping[str, Any]) -> dict[str, Any]:
    """Minimized Routing Reflex state projection."""
    if request.get("schema_version") != core.REFLEX_REQUEST_VERSION:
        raise JevAdapterError("unsupported Routing Reflex request schema")
    state = request.get("routing_state")
    admissible = request.get("admissible")
    if not isinstance(state, Mapping) or not isinstance(admissible, Mapping):
        raise JevAdapterError("invalid Routing Reflex request")
    task = state["task"]
    host = state["host"]
    auth = state["authority"]
    return {
        "task": {
            "objective": _clip(task.get("objective")),
            "task_kind": _clip(task.get("task_kind"), 256),
            "mutation_kind": task.get("mutation_kind"),
            "requested_outcome": _clip(task.get("requested_outcome")),
            "verification_obligation": _clip(task.get("verification_obligation")),
        },
        "host_capabilities": {
            "subagents_proven": bool(host.get("subagents_proven")),
            "per_child_model_control_proven": bool(
                host.get("per_child_model_control_proven")
            ),
            "reasoning_control_proven": bool(host.get("reasoning_control_proven")),
            "concurrency_proven": bool(host.get("concurrency_proven")),
            "isolation_proven": bool(host.get("isolation_proven")),
        },
        "authority": {
            "explicit_model_provider_constraint_present": bool(
                auth.get("explicit_model_provider_constraint")
            ),
            "remote_write_authorized": bool(auth.get("remote_write_authorized")),
            "destructive_or_production_authorized": bool(
                auth.get("destructive_or_production_authorized")
            ),
            "unresolved_external_effect": bool(
                auth.get("unresolved_external_effect")
            ),
        },
        "work_shape": dict(state["work_shape"]),
        "evidence": dict(state["evidence"]),
        "budget": dict(state["budget"]),
        "admissible": {
            "coordination": list(admissible.get("coordination", [])),
            "compute": list(admissible.get("compute", [])),
        },
    }


def project_context_reflex_state(
    request: Mapping[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Minimize Context Reflex input and replace local item IDs with batch keys."""
    if request.get("schema_version") != CONTEXT_REQUEST_VERSION:
        raise JevAdapterError("unsupported Context Reflex request schema")
    task = request.get("task")
    candidates = request.get("candidates")
    if not isinstance(task, Mapping) or not isinstance(candidates, list):
        raise JevAdapterError("invalid Context Reflex request")
    projected = {
        "task": {
            "objective": _clip(task.get("objective"), 3000),
            "verification_obligation": _clip(
                task.get("verification_obligation"), 2000
            ),
        },
        "candidates": [],
    }
    mapping: list[tuple[str, str]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise JevAdapterError("invalid Context Reflex candidate")
        item_id = candidate.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise JevAdapterError("Context Reflex candidate missing item_id")
        key = f"c{index:03d}"
        mapping.append((key, item_id))
        source = candidate.get("source", {})
        if not isinstance(source, Mapping):
            raise JevAdapterError("invalid Context Reflex source metadata")
        projected["candidates"].append(
            {
                "candidate_key": key,
                "kind": _clip(candidate.get("kind"), 128),
                "source": {
                    "tool": _clip(source.get("tool"), 128),
                    "locator": _clip(source.get("locator"), 512),
                    "result_status": _clip(source.get("result_status"), 64),
                    "content_version": _clip(
                        source.get("content_version"), 128
                    ),
                },
                "size": dict(candidate.get("size", {})),
                "evidence": dict(candidate.get("evidence", {})),
                "replay": dict(candidate.get("replay", {})),
                "supersession": dict(candidate.get("supersession", {})),
                "recency": dict(candidate.get("recency", {})),
                "admissible_actions": list(
                    candidate.get("admissible_actions", [])
                ),
            }
        )
    return projected, mapping


def _choice_question(
    question: Mapping[str, Any], admissible: list[str]
) -> dict[str, Any] | None:
    options = [x for x in question["choices"] if x in admissible]
    if len(options) <= 1:
        return None
    descriptions = (
        _COORDINATION
        if question["id"] == "coordination_preference"
        else _COMPUTE
    )
    return {
        "type": "choice",
        "instructions": question["criterion"],
        "criteria": {x: descriptions[x] for x in options},
    }


def _build_routing_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    state = project_reflex_state(request)
    payload_questions = {}
    for question in questions:
        qid = question["id"]
        if question["kind"] == "choice":
            allowed = state["admissible"][
                "coordination"
                if qid == "coordination_preference"
                else "compute"
            ]
            item = _choice_question(question, allowed)
            if item is not None:
                payload_questions[qid] = item
        elif question["kind"] == "score":
            payload_questions[qid] = {
                "type": "score",
                "instructions": question["criterion"],
                "criteria": _SCORE_LEVELS[qid],
            }
        elif question["kind"] == "noul":
            payload_questions[qid] = {
                "type": "noul",
                "instructions": question["criterion"],
            }
        else:
            raise JevAdapterError(
                f"unsupported question kind: {question['kind']}"
            )
    return {"model": model, "state": state, "questions": payload_questions}


def _build_context_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    state, mapping = project_context_reflex_state(request)
    payload_questions = {}
    for candidate_key, _ in mapping:
        for question in questions:
            if question.get("kind") != "noul":
                raise JevAdapterError(
                    "Context Reflex v1 supports atomic Noul questions only"
                )
            qid = question["id"]
            payload_questions[f"{candidate_key}_{qid}"] = {
                "type": "noul",
                "instructions": (
                    f"For candidate {candidate_key}: {question['criterion']}"
                ),
                "criteria": {
                    "true": question.get("true"),
                    "false": question.get("false"),
                },
            }
    return {"model": model, "state": state, "questions": payload_questions}


def build_jev_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    schema = request.get("schema_version")
    if schema == core.REFLEX_REQUEST_VERSION:
        return _build_routing_payload(request, questions, model)
    if schema == CONTEXT_REQUEST_VERSION:
        return _build_context_payload(request, questions, model)
    raise JevAdapterError("unsupported Reflex request schema")


def _http_transport(
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout: float,
) -> Mapping[str, Any]:
    if not base_url.startswith("https://"):
        raise JevAdapterError("TypeSafe base URL must use HTTPS")
    endpoint = base_url.rstrip("/") + "/v1/systemone"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            payload, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-engineering-toolkit/margos-vnext",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JevAdapterError(f"TypeSafe HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise JevAdapterError(
            f"TypeSafe transport error: {type(exc.reason).__name__}"
        ) from None
    except TimeoutError:
        raise JevAdapterError("TypeSafe request timed out") from None
    except json.JSONDecodeError:
        raise JevAdapterError("TypeSafe returned invalid JSON") from None
    if not isinstance(decoded, Mapping):
        raise JevAdapterError("TypeSafe response must be an object")
    return decoded


def _choice_answer(
    raw: Mapping[str, Any], options: list[str]
) -> dict[str, Any]:
    choice = raw.get("choice")
    probs = raw.get("probabilities")
    if choice not in options or not isinstance(probs, Mapping):
        raise JevAdapterError("invalid Jev Choice answer")
    mapped = {x: float(probs[x]) for x in options}
    return {"value": choice, "probabilities": mapped}


def _score_answer(
    raw: Mapping[str, Any], levels: list[str]
) -> dict[str, Any]:
    probs = raw.get("probabilities")
    if not isinstance(probs, Mapping):
        raise JevAdapterError("invalid Jev Score answer")
    mapped = {}
    for index, level in enumerate(levels):
        key = str(index)
        if key not in probs:
            raise JevAdapterError(
                "Jev Score distribution does not match rubric"
            )
        mapped[level] = float(probs[key])
    value = max(mapped, key=mapped.get)
    return {"value": value, "probabilities": mapped}


def _noul_answer(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = raw.get("noul", raw.get("probability"))
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= float(value) <= 1
    ):
        raise JevAdapterError("invalid Jev Noul answer")
    return {"probability": float(value)}


def _provider_meta(
    raw: Mapping[str, Any],
    model: str,
    *,
    network_request_count: int,
) -> dict[str, Any]:
    provider = {
        "kind": "typesafe-jev",
        "status": "AVAILABLE",
        "calibration_status": "UNCALIBRATED",
        "requested_model": model,
        "network_request_count": network_request_count,
    }
    if isinstance(raw.get("model"), str):
        provider["response_model"] = raw["model"]
    if isinstance(raw.get("usage"), Mapping):
        provider["usage"] = dict(raw["usage"])
    return provider


def _to_routing_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    answers_raw = raw.get("answers")
    if not isinstance(answers_raw, Mapping):
        raise JevAdapterError("TypeSafe response missing answers")
    admissible = request["admissible"]
    answers = {}
    for question in questions:
        qid = question["id"]
        if question["kind"] == "choice":
            options = [
                x
                for x in question["choices"]
                if x
                in admissible[
                    "coordination"
                    if qid == "coordination_preference"
                    else "compute"
                ]
            ]
            all_options = list(question["choices"])
            if len(options) == 1:
                answers[qid] = {
                    "value": options[0],
                    "probabilities": {
                        x: (1.0 if x == options[0] else 0.0)
                        for x in all_options
                    },
                }
            else:
                item = answers_raw.get(qid)
                if not isinstance(item, Mapping):
                    raise JevAdapterError(f"missing Jev answer: {qid}")
                local = _choice_answer(item, options)
                answers[qid] = {
                    "value": local["value"],
                    "probabilities": {
                        x: local["probabilities"].get(x, 0.0)
                        for x in all_options
                    },
                }
        elif question["kind"] == "score":
            item = answers_raw.get(qid)
            if not isinstance(item, Mapping):
                raise JevAdapterError(f"missing Jev answer: {qid}")
            answers[qid] = _score_answer(item, list(question["levels"]))
        else:
            item = answers_raw.get(qid)
            if not isinstance(item, Mapping):
                raise JevAdapterError(f"missing Jev answer: {qid}")
            answers[qid] = _noul_answer(item)
    return {
        "schema_version": "margos-reflex-result/v1",
        "provider": _provider_meta(raw, model, network_request_count=1),
        "question_set_sha256": core.question_set_sha256(),
        "answers": answers,
    }


def _to_context_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    answers_raw = raw.get("answers")
    if not isinstance(answers_raw, Mapping):
        raise JevAdapterError("TypeSafe response missing answers")
    _, mapping = project_context_reflex_state(request)
    answers = {}
    for candidate_key, item_id in mapping:
        answers[item_id] = {}
        for question in questions:
            qid = question["id"]
            raw_answer = answers_raw.get(f"{candidate_key}_{qid}")
            if not isinstance(raw_answer, Mapping):
                raise JevAdapterError(
                    f"missing Jev Context answer: {candidate_key}_{qid}"
                )
            answers[item_id][qid] = _noul_answer(raw_answer)
    return {
        "schema_version": CONTEXT_RESULT_VERSION,
        "provider": _provider_meta(raw, model, network_request_count=1),
        "question_set_sha256": _question_hash_for_request(request),
        "answers": answers,
    }


def to_reflex_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    schema = request.get("schema_version")
    if schema == core.REFLEX_REQUEST_VERSION:
        return _to_routing_result(raw, request, questions, model)
    if schema == CONTEXT_REQUEST_VERSION:
        return _to_context_result(raw, request, questions, model)
    raise JevAdapterError("unsupported Reflex request schema")


@dataclass
class JevReflexProvider:
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: float = 15.0
    transport: Transport | None = None

    def evaluate(
        self,
        request: Mapping[str, Any],
        questions: tuple[dict[str, Any], ...],
    ) -> Mapping[str, Any]:
        key = (
            os.environ.get("TYPESAFE_API_KEY", "")
            if self.api_key is None
            else self.api_key
        )
        base = self.base_url or os.environ.get(
            "TYPESAFE_BASE_URL", DEFAULT_BASE_URL
        )
        model = self.model or os.environ.get(
            "TYPESAFE_DEFAULT_MODEL", DEFAULT_MODEL
        )
        result_version = _result_version_for_request(request)
        question_hash = _question_hash_for_request(request)
        if not key:
            return {
                "schema_version": result_version,
                "provider": {
                    "kind": "typesafe-jev",
                    "status": "NOT_CONFIGURED",
                    "calibration_status": "UNKNOWN",
                    "network_request_count": 0,
                },
                "question_set_sha256": question_hash,
                "answers": {},
            }

        attempted_network = False
        try:
            payload = build_jev_payload(request, questions, model)
            attempted_network = True
            raw = (self.transport or _http_transport)(
                base, key, payload, float(self.timeout)
            )
            return to_reflex_result(raw, request, questions, model)
        except (JevAdapterError, KeyError, TypeError, ValueError) as exc:
            return {
                "schema_version": result_version,
                "provider": {
                    "kind": "typesafe-jev",
                    "status": "ERROR",
                    "calibration_status": "UNKNOWN",
                    "network_request_count": 1 if attempted_network else 0,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                "question_set_sha256": question_hash,
                "answers": {},
            }
