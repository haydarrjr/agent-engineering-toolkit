#!/usr/bin/env python3
"""Optional TypeSafe Jev Reflex adapter for both MARGOS Reflex decision families.

One transport/auth/error boundary serves Routing Reflex and Context Reflex.
The adapter is opt-in, stdlib-only, never logs API keys, and never performs
network I/O when TYPESAFE_API_KEY is absent.
"""
from __future__ import annotations

import hashlib
import json
import os
import copy
import http.client
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import margos_decide as core
import margos_verification as verification

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
PINNED_MODEL = "jev-1.13.0"
CONTEXT_REQUEST_VERSION = "margos-context-reflex-request/v2"
CONTEXT_RESULT_VERSION = "margos-context-reflex-result/v2"
RETRIEVAL_REQUEST_VERSION = "margos-retrieval-reflex-request/v1"
RETRIEVAL_RESULT_VERSION = "margos-retrieval-reflex-result/v1"
VERIFICATION_REQUEST_VERSION = verification.REQUEST_VERSION
VERIFICATION_RESULT_VERSION = verification.RESULT_VERSION
ROUTING_PROJECTION_VERSION = "margos-jev-routing-projection/v2"
CONTEXT_PROJECTION_VERSION = "margos-jev-context-projection/v3"
VERIFICATION_PROJECTION_VERSION = verification.PROJECTION_VERSION
CALIBRATION_BINDING_VERSION = "margos-jev-calibration/v2"
Transport = Callable[[str, str, Mapping[str, Any], float], Mapping[str, Any]]
RUNTIME_RECEIPT_VERSION = "margos-jev-runtime-receipt/v1"


def _environment_api_key() -> str:
    return os.environ.get("TYPESAFE_API_KEY", "")

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


@dataclass
class JevRuntime:
    """Session-scoped transport/runtime with pooled HTTPS and request telemetry."""

    base_url: str
    api_key: str
    transport: Transport | None = None
    _connection: http.client.HTTPSConnection | None = field(default=None, init=False, repr=False)
    _connection_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _pooled_request(self, payload: Mapping[str, Any], timeout: float) -> tuple[Mapping[str, Any], float]:
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise JevAdapterError("TypeSafe base URL must use HTTPS")
        path = (parsed.path.rstrip("/") or "") + "/v1/systemone"
        started = time.perf_counter()
        with self._connection_lock:
            try:
                if self._connection is None:
                    self._connection = http.client.HTTPSConnection(
                        parsed.hostname,
                        parsed.port or 443,
                        timeout=timeout,
                    )
                self._connection.timeout = timeout
                self._connection.request(
                    "POST",
                    path,
                    body=json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "agent-engineering-toolkit/margos-vnext",
                        "Connection": "keep-alive",
                    },
                )
                response = self._connection.getresponse()
                data = response.read()
                if response.status >= 400:
                    raise JevAdapterError(f"TypeSafe HTTP {response.status}")
                decoded = json.loads(data.decode("utf-8"))
            except JevAdapterError:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None
                raise
            except (OSError, http.client.HTTPException) as exc:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None
                raise JevAdapterError(f"TypeSafe pooled transport error: {type(exc).__name__}") from None
            except json.JSONDecodeError:
                raise JevAdapterError("TypeSafe returned invalid JSON") from None
        if not isinstance(decoded, Mapping):
            raise JevAdapterError("TypeSafe response must be an object")
        return decoded, (time.perf_counter() - started) * 1000.0

    def request(self, payload: Mapping[str, Any], timeout: float) -> tuple[Mapping[str, Any], float]:
        started = time.perf_counter()
        if self.transport is not None:
            decoded = self.transport(self.base_url, self.api_key, payload, timeout)
            if not isinstance(decoded, Mapping):
                raise JevAdapterError("TypeSafe response must be an object")
            return decoded, (time.perf_counter() - started) * 1000.0
        return self._pooled_request(payload, timeout)

    def close(self) -> None:
        with self._connection_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


def _clip(value: Any, limit: int = 6000) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _projection_version(request: Mapping[str, Any]) -> str:
    if request.get("schema_version") == VERIFICATION_REQUEST_VERSION:
        return VERIFICATION_PROJECTION_VERSION
    if request.get("schema_version") == CONTEXT_REQUEST_VERSION:
        return CONTEXT_PROJECTION_VERSION
    if request.get("schema_version") == core.REFLEX_REQUEST_VERSION:
        return ROUTING_PROJECTION_VERSION
    if request.get("schema_version") == RETRIEVAL_REQUEST_VERSION:
        return "margos-jev-retrieval-projection/v1"
    raise JevAdapterError("unsupported Reflex request schema")


def _threshold_hash_for_request(request: Mapping[str, Any]) -> str:
    value = request.get("threshold_policy_sha256")
    if isinstance(value, str) and len(value) == 64:
        return value
    if request.get("schema_version") == core.REFLEX_REQUEST_VERSION:
        return core.threshold_policy_sha256()
    if request.get("schema_version") == RETRIEVAL_REQUEST_VERSION:
        value = request.get("threshold_policy_sha256")
        if isinstance(value, str) and len(value) == 64:
            return value
    raise JevAdapterError("Reflex request missing threshold-policy hash")


def _calibration_metadata(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    model: str,
    binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    meta = {"calibration_status": "UNCALIBRATED"}
    if binding is None:
        return meta
    meta["calibration_binding_sha256"] = _hash_json(binding)
    response_model = raw.get("model")
    effective_model = response_model if isinstance(response_model, str) else model
    required = {
        "version": CALIBRATION_BINDING_VERSION,
        "provider": "typesafe-jev",
        "model": effective_model,
        "question_set_sha256": _question_hash_for_request(request),
        "threshold_policy_sha256": _threshold_hash_for_request(request),
        "projection_version": _projection_version(request),
        "evaluation_status": "PASSED",
    }
    corpus = binding.get("corpus_sha256")
    pinned = effective_model == PINNED_MODEL
    matches = all(binding.get(k) == v for k, v in required.items())
    valid_corpus = isinstance(corpus, str) and len(corpus) == 64 and all(ch in "0123456789abcdef" for ch in corpus)
    response_matches = not isinstance(response_model, str) or response_model == effective_model
    meta["calibration_status"] = (
        "CALIBRATED_FOR_FROZEN_SUITE"
        if pinned and matches and valid_corpus and response_matches
        else "STALE"
    )
    return meta


def _question_hash_for_request(request: Mapping[str, Any]) -> str:
    if request.get("schema_version") == VERIFICATION_REQUEST_VERSION:
        value = request.get("question_set_sha256")
        if not isinstance(value, str):
            raise JevAdapterError("Verification Reflex request missing question-set hash")
        return value
    if request.get("schema_version") in {CONTEXT_REQUEST_VERSION, RETRIEVAL_REQUEST_VERSION}:
        value = request.get("question_set_sha256")
        if not isinstance(value, str):
            raise JevAdapterError("Context Reflex request missing question-set hash")
        return value
    return core.question_set_sha256()


def _result_version_for_request(request: Mapping[str, Any]) -> str:
    if request.get("schema_version") == VERIFICATION_REQUEST_VERSION:
        return VERIFICATION_RESULT_VERSION
    if request.get("schema_version") == CONTEXT_REQUEST_VERSION:
        return CONTEXT_RESULT_VERSION
    if request.get("schema_version") == core.REFLEX_REQUEST_VERSION:
        return core.REFLEX_RESULT_VERSION
    if request.get("schema_version") == RETRIEVAL_REQUEST_VERSION:
        return RETRIEVAL_RESULT_VERSION
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
    projected = {
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
    opportunity = request.get("execution_opportunity") or state.get("execution_opportunity")
    if isinstance(opportunity, Mapping):
        projected["execution_opportunity"] = {
            "opportunity_id": _clip(opportunity.get("opportunity_id"), 128),
            "fallback_operation_id": _clip(opportunity.get("fallback_operation_id"), 128),
            "critical_path": bool(opportunity.get("critical_path")),
            "host_can_exploit_result": bool(opportunity.get("host_can_exploit_result")),
            "jev_latency_budget_ms": float(opportunity.get("jev_latency_budget_ms", 0.0)),
            "cost_model_version": _clip(opportunity.get("cost_model_version"), 64),
            "candidates": [
                {
                    "operation_id": _clip(candidate.get("operation_id"), 128),
                    "coordination": _clip(candidate.get("coordination"), 32),
                    "compute": _clip(candidate.get("compute"), 64),
                    "role": _clip(candidate.get("role"), 64),
                    "host_capability_proof": _clip(candidate.get("host_capability_proof"), 128),
                    "cost": dict(candidate.get("cost", {})),
                }
                for candidate in opportunity.get("candidates", [])
                if isinstance(candidate, Mapping)
            ],
        }
    return projected


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
        projected_candidate = {
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
        capsule = candidate.get("semantic_capsule")
        if isinstance(capsule, Mapping):
            projected_candidate["semantic_capsule"] = {
                "status": _clip(capsule.get("status"), 32),
                "extractor_version": _clip(capsule.get("extractor_version"), 64),
                "extractor_kind": _clip(capsule.get("extractor_kind"), 64),
                "payload_sha256": _clip(capsule.get("payload_sha256"), 64),
                "text": _clip(capsule.get("text"), 512),
                "exact_excerpts": [
                    _clip(value, 512)
                    for value in capsule.get("exact_excerpts", [])
                    if isinstance(value, str)
                ],
                "excerpt_sha256s": [
                    _clip(value, 64)
                    for value in capsule.get("excerpt_sha256s", [])
                    if isinstance(value, str)
                ],
                "characters": int(capsule.get("characters", 0)),
                "capsule_sha256": _clip(capsule.get("capsule_sha256"), 64),
                "provenance": dict(capsule.get("provenance", {})),
            }
        projected["candidates"].append(projected_candidate)
    return projected, mapping


def project_retrieval_state(request: Mapping[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Project metadata-only retrieval candidates; payload text is not accepted."""
    if request.get("schema_version") != RETRIEVAL_REQUEST_VERSION:
        raise JevAdapterError("unsupported retrieval Reflex request schema")
    task = request.get("task")
    candidates = request.get("candidates")
    if not isinstance(task, Mapping) or not isinstance(candidates, list):
        raise JevAdapterError("invalid retrieval Reflex request")
    projected = {
        "task": {"objective": _clip(task.get("objective"), 3000), "verification_obligation": _clip(task.get("verification_obligation"), 2000)},
        "candidates": [],
    }
    mapping: list[tuple[str, str]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise JevAdapterError("invalid retrieval candidate")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise JevAdapterError("retrieval candidate missing candidate_id")
        if "content" in candidate or "payload" in candidate:
            raise JevAdapterError("raw payload is forbidden in retrieval projection")
        key = f"c{index:03d}"
        mapping.append((key, candidate_id))
        projected["candidates"].append({
            "candidate_key": key,
            "kind": _clip(candidate.get("kind"), 128),
            "source": dict(candidate.get("source", {})),
            "estimated_size": dict(candidate.get("estimated_size", {})),
            "estimated_fetch_latency_ms": float(candidate.get("estimated_fetch_latency_ms", 0.0)),
            "fetch_cost_class": _clip(candidate.get("fetch_cost_class"), 64),
            "cache_locality": _clip(candidate.get("cache_locality"), 32),
            "mandatory_by_policy": bool(candidate.get("mandatory_by_policy")),
            "replay": dict(candidate.get("replay", {})),
        })
    return projected, mapping


def _choice_question(
    question: Mapping[str, Any], admissible: list[str]
) -> dict[str, Any] | None:
    options = [x for x in question["choices"] if x in admissible]
    if len(options) <= 1:
        return None
    descriptions = question.get("criteria") or (
        _COORDINATION
        if question["id"] == "coordination_preference"
        else _COMPUTE
    )
    return {
        "type": "choice",
        "instructions": question.get("instructions", question["criterion"]),
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
                "instructions": question.get("instructions", question["criterion"]),
                "criteria": question.get("criteria") or _SCORE_LEVELS[qid],
            }
        elif question["kind"] == "noul":
            payload_questions[qid] = {
                "type": "noul",
                "instructions": question.get("instructions", question["criterion"]),
                "criteria": {
                    "true": question.get("true", "The proposition is true."),
                    "false": question.get("false", "The proposition is false."),
                },
            }
        else:
            raise JevAdapterError(
                f"unsupported question kind: {question['kind']}"
            )
    opportunity = state.get("execution_opportunity")
    if isinstance(opportunity, Mapping):
        for candidate in opportunity.get("candidates", []):
            if not isinstance(candidate, Mapping):
                continue
            operation_id = str(candidate.get("operation_id", ""))
            if not operation_id:
                continue
            payload_questions[f"route_{operation_id}_sufficient"] = {
                "type": "noul",
                "instructions": f"Can the executable operation `{operation_id}` close `task.verification_obligation` with the declared evidence and host capability proof?",
                "criteria": {
                    "true": "The concrete operation is semantically sufficient to close the obligation.",
                    "false": "The concrete operation is not sufficient or would leave verification open.",
                },
            }
    return {"model": model, "state": state, "questions": payload_questions}


def _build_context_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    state, mapping = project_context_reflex_state(request)
    payload_questions = {}
    for index, (candidate_key, _) in enumerate(mapping):
        # TypeSafe structured paths are resolved relative to the request's
        # top-level `state` object.  The path must therefore start at
        # `candidates`, not at `state.candidates`.
        candidate_path = f"candidates[{index}]"
        for question in questions:
            if question.get("kind") != "noul":
                raise JevAdapterError("Context Reflex supports atomic Noul questions only")
            qid = question["id"]
            instructions = str(question.get("instructions", question["criterion"]))
            instructions = instructions.replace("candidates[current]", candidate_path)
            payload_questions[f"{candidate_key}_{qid}"] = {
                "type": "noul",
                "instructions": (
                    f"Evaluate {candidate_path} against `task`. "
                    f"{instructions}"
                ),
                "criteria": {
                    "true": question.get("true"),
                    "false": question.get("false"),
                },
            }
    return {"model": model, "state": state, "questions": payload_questions}


def _build_retrieval_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    state, mapping = project_retrieval_state(request)
    payload_questions = {}
    for candidate_key, _ in mapping:
        candidate_path = f"candidates[{int(candidate_key[1:])}]"
        for question in questions:
            if question.get("kind") != "noul":
                raise JevAdapterError("retrieval Reflex supports Noul questions only")
            qid = str(question["id"])
            payload_questions[f"{candidate_key}_{qid}"] = {
                "type": "noul",
                "instructions": f"Evaluate `{candidate_path}` against `task`: determine whether this candidate is needed for the next obligation.",
                "criteria": {
                    "true": "The metadata indicates the candidate is needed to close or verify the declared obligation.",
                    "false": "The candidate is not needed; omitting it is safe under the metadata and Policy floor.",
                },
            }
    return {"model": model, "state": state, "questions": payload_questions}


def _build_verification_payload(
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
) -> dict[str, Any]:
    """Build the dedicated one-batched-request Verification Reflex payload."""
    if request.get("schema_version") != VERIFICATION_REQUEST_VERSION:
        raise JevAdapterError("unsupported Verification Reflex request schema")
    candidates = request.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise JevAdapterError("Verification Reflex requires optional candidates")
    if len(questions) != len(candidates):
        raise JevAdapterError("Verification Reflex requires one question per optional candidate")
    state = {
        "task_objective": _clip(request.get("task_objective"), 2000),
        "candidates": [],
    }
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise JevAdapterError("invalid Verification candidate projection")
        summary = _clip(candidate.get("claim_summary"), 600)
        if any(marker in summary for marker in ("Bearer ", "PRIVATE KEY", "TYPESAFE_API_KEY", "gh" + "p_")):
            raise JevAdapterError("Verification claim summary failed privacy screening")
        state["candidates"].append({
            "candidate_id": _clip(candidate.get("candidate_id"), 128),
            "claim_summary": summary,
            "evidence_state": _clip(candidate.get("evidence_state"), 32),
            "evidence_kind": _clip(candidate.get("evidence_kind"), 64),
            "policy_priority_rank": int(candidate.get("policy_priority_rank", 0)),
            "verifier": dict(candidate.get("verifier", {})),
        })
    payload_questions: dict[str, Any] = {}
    for index, question in enumerate(questions):
        if question.get("kind") != "noul":
            raise JevAdapterError("Verification Reflex supports Noul questions only")
        instructions = str(question.get("instructions", ""))
        expected_path = f"`candidates[{index}]`"
        if expected_path not in instructions:
            raise JevAdapterError("Verification question must reference its exact candidate path")
        payload_questions[str(question["id"])] = {
            "type": "noul",
            "instructions": instructions,
            "criteria": {"true": question.get("true"), "false": question.get("false")},
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
    if schema == RETRIEVAL_REQUEST_VERSION:
        return _build_retrieval_payload(request, questions, model)
    if schema == VERIFICATION_REQUEST_VERSION:
        return _build_verification_payload(request, questions, model)
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


def resolve_available_models(
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 15.0,
) -> list[str]:
    """Resolve provider model IDs at run time without exposing credentials."""
    key = api_key if api_key is not None else _environment_api_key()
    if not key:
        return []
    base = base_url or os.environ.get("TYPESAFE_BASE_URL", DEFAULT_BASE_URL)
    if not base.startswith("https://"):
        raise JevAdapterError("TypeSafe base URL must use HTTPS")
    request = urllib.request.Request(
        base.rstrip("/") + "/v1/models",
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": "agent-engineering-toolkit/margos-vnext",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JevAdapterError(f"TypeSafe model-list HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise JevAdapterError(
            f"TypeSafe model-list transport error: {type(exc.reason).__name__}"
        ) from None
    except TimeoutError:
        raise JevAdapterError("TypeSafe model-list request timed out") from None
    except json.JSONDecodeError:
        raise JevAdapterError("TypeSafe model-list returned invalid JSON") from None
    if isinstance(decoded, Mapping):
        values = decoded.get("data", decoded.get("models", []))
    else:
        values = decoded
    if not isinstance(values, list):
        raise JevAdapterError("TypeSafe model-list response must contain an array")
    result = []
    for value in values:
        if isinstance(value, Mapping):
            # TypeSafe currently exposes model identifiers as ``name`` while
            # OpenAI-compatible listings commonly use ``id``.  Accept both
            # without weakening the explicit model/fingerprint checks below.
            model_id = value.get("id") or value.get("name")
        else:
            model_id = value
        if isinstance(model_id, str) and model_id:
            result.append(model_id)
    return list(dict.fromkeys(result))


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
    request: Mapping[str, Any],
    model: str,
    binding: Mapping[str, Any] | None,
    *,
    network_request_count: int,
) -> dict[str, Any]:
    provider = {
        "kind": "typesafe-jev",
        "status": "AVAILABLE",
        "requested_model": model,
        "projection_version": _projection_version(request),
        "network_request_count": network_request_count,
        **_calibration_metadata(raw, request, model, binding),
    }
    if isinstance(raw.get("model"), str):
        provider["response_model"] = raw["model"]
    for key in ("id", "request_id", "response_id"):
        if isinstance(raw.get(key), str) and raw[key]:
            provider["response_id" if key == "id" else key] = raw[key]
    if isinstance(raw.get("usage"), Mapping):
        provider["usage"] = dict(raw["usage"])
    return provider


def _to_routing_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
    binding: Mapping[str, Any] | None,
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
    projected_state = project_reflex_state(request)
    opportunity = projected_state.get("execution_opportunity")
    if isinstance(opportunity, Mapping):
        for candidate in opportunity.get("candidates", []):
            operation_id = str(candidate.get("operation_id", ""))
            key = f"route_{operation_id}_sufficient"
            item = answers_raw.get(key)
            if not isinstance(item, Mapping):
                raise JevAdapterError(f"missing Jev answer: {key}")
            answers[key] = _noul_answer(item)
    return {
        "schema_version": core.REFLEX_RESULT_VERSION,
        "provider": _provider_meta(raw, request, model, binding, network_request_count=1),
        "question_set_sha256": core.question_set_sha256(),
        "answers": answers,
    }


def _to_context_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
    binding: Mapping[str, Any] | None,
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
        "provider": _provider_meta(raw, request, model, binding, network_request_count=1),
        "question_set_sha256": _question_hash_for_request(request),
        "answers": answers,
    }


def _to_retrieval_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
    binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    answers_raw = raw.get("answers")
    if not isinstance(answers_raw, Mapping):
        raise JevAdapterError("TypeSafe response missing answers")
    _, mapping = project_retrieval_state(request)
    answers: dict[str, Any] = {}
    for candidate_key, candidate_id in mapping:
        answers[candidate_id] = {}
        for question in questions:
            raw_answer = answers_raw.get(f"{candidate_key}_{question['id']}")
            if not isinstance(raw_answer, Mapping):
                raise JevAdapterError(f"missing Jev retrieval answer: {candidate_key}_{question['id']}")
            answers[candidate_id][question["id"]] = _noul_answer(raw_answer)
    return {
        "schema_version": RETRIEVAL_RESULT_VERSION,
        "provider": _provider_meta(raw, request, model, binding, network_request_count=1),
        "question_set_sha256": _question_hash_for_request(request),
        "answers": answers,
    }


def _to_verification_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
    binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    answers_raw = raw.get("answers")
    candidates = request.get("candidates")
    if not isinstance(answers_raw, Mapping) or not isinstance(candidates, list):
        raise JevAdapterError("TypeSafe Verification response is incomplete")
    if len(questions) != len(candidates):
        raise JevAdapterError("Verification question/candidate count mismatch")
    answers: dict[str, Any] = {}
    for index, candidate in enumerate(candidates):
        candidate_id = candidate.get("candidate_id")
        qid = str(questions[index]["id"])
        item = answers_raw.get(qid)
        if not isinstance(candidate_id, str) or not isinstance(item, Mapping):
            raise JevAdapterError(f"missing Verification answer: {qid}")
        answers[candidate_id] = _noul_answer(item)
    return {
        "schema_version": VERIFICATION_RESULT_VERSION,
        "provider": _provider_meta(raw, request, model, binding, network_request_count=1),
        "question_set_sha256": _question_hash_for_request(request),
        "answers": answers,
    }


def to_reflex_result(
    raw: Mapping[str, Any],
    request: Mapping[str, Any],
    questions: tuple[dict[str, Any], ...],
    model: str,
    binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    schema = request.get("schema_version")
    if schema == core.REFLEX_REQUEST_VERSION:
        return _to_routing_result(raw, request, questions, model, binding)
    if schema == CONTEXT_REQUEST_VERSION:
        return _to_context_result(raw, request, questions, model, binding)
    if schema == RETRIEVAL_REQUEST_VERSION:
        return _to_retrieval_result(raw, request, questions, model, binding)
    if schema == VERIFICATION_REQUEST_VERSION:
        return _to_verification_result(raw, request, questions, model, binding)
    raise JevAdapterError("unsupported Reflex request schema")


def _validate_result_contract(result: Mapping[str, Any], questions: tuple[dict[str, Any], ...]) -> None:
    """Reject malformed provider distributions before they reach composition."""
    answers = result.get("answers")
    if not isinstance(answers, Mapping):
        raise JevAdapterError("TypeSafe response missing answers")
    for question in questions:
        if question["kind"] not in {"choice", "score"}:
            continue
        question_id = question["id"]
        answer = answers.get(question_id)
        options = question.get("choices") or question.get("levels") or []
        probabilities = answer.get("probabilities") if isinstance(answer, Mapping) else None
        if not isinstance(probabilities, Mapping) or set(probabilities) != set(options):
            raise JevAdapterError(f"{question_id} probabilities must cover the closed set")
        values = [float(probabilities[option]) for option in options]
        if any(value < 0 or value > 1 for value in values) or abs(sum(values) - 1.0) > 1e-6:
            raise JevAdapterError(f"invalid distribution for {question_id}")


@dataclass
class JevReflexProvider:
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: float = 15.0
    max_attempts: int = 3
    transport: Transport | None = None
    calibration_binding: Mapping[str, Any] | None = None
    runtime: JevRuntime | None = field(default=None, init=False, repr=False)
    _cache: dict[str, Mapping[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _inflight: dict[str, threading.Event] = field(default_factory=dict, init=False, repr=False)
    _cache_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def value_model_calibration_status(self) -> str:
        if self.calibration_binding is None:
            return "UNCALIBRATED"
        if self.calibration_binding.get("evaluation_status") != "PASSED":
            return "STALE"
        if self.calibration_binding.get("model") not in {None, PINNED_MODEL}:
            return "STALE"
        return "CALIBRATED_FOR_FROZEN_SUITE"

    def _get_runtime(self, base: str, key: str) -> JevRuntime:
        if self.runtime is None or self.runtime.base_url != base or self.runtime.api_key != key:
            if self.runtime is not None:
                self.runtime.close()
            self.runtime = JevRuntime(base, key, self.transport)
        return self.runtime

    def close(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
            self.runtime = None

    def _cache_key(self, request: Mapping[str, Any], payload: Mapping[str, Any], model: str) -> str:
        return _hash_json({
            "provider": "typesafe-jev",
            "concrete_or_requested_model": model,
            "question_set_sha256": _question_hash_for_request(request),
            "threshold_policy_sha256": _threshold_hash_for_request(request),
            "projection_version": _projection_version(request),
            "cost_model_version": request.get("cost_model_version", "unknown"),
            "host_capability_mapping_version": request.get("host_capability_mapping_version", "unknown"),
            "calibration_binding_sha256": _hash_json(self.calibration_binding) if self.calibration_binding is not None else None,
            "payload": payload,
        })

    def _runtime_meta(
        self,
        result: Mapping[str, Any],
        request: Mapping[str, Any],
        model: str,
        request_sha: str,
        *,
        cache_hit: bool,
        coalesced: bool,
        network_request_count: int,
        latency_ms: float,
        transport_latency_ms: float,
    ) -> dict[str, Any]:
        provider = dict(result.get("provider", {}))
        provider.update({
            "network_request_count": network_request_count,
            "retry_count": int(provider.get("retry_count", max(0, network_request_count - 1)) or 0),
            "cache_hit": cache_hit,
            "coalesced": coalesced,
            "runtime_receipt": {
                "schema_version": RUNTIME_RECEIPT_VERSION,
                "requested_model": model,
                "response_model": provider.get("response_model"),
                "question_set_sha256": _question_hash_for_request(request),
                "threshold_policy_sha256": _threshold_hash_for_request(request),
                "projection_version": _projection_version(request),
                "request_sha256": request_sha,
                "cache_hit": cache_hit,
                "coalesced": coalesced,
                "network_request_count": network_request_count,
                "retry_count": int(provider.get("retry_count", 0) or 0),
                "latency_ms": round(latency_ms, 3),
                "transport_latency_ms": round(transport_latency_ms, 3),
                "calibration_status": provider.get("calibration_status", "UNKNOWN"),
            },
        })
        return provider

    def _runtime_key(self) -> str:
        return (
            _environment_api_key()
            if self.api_key is None
            else self.api_key
        )

    def is_configured(self) -> bool:
        return bool(self._runtime_key())

    def evaluate(
        self,
        request: Mapping[str, Any],
        questions: tuple[dict[str, Any], ...],
    ) -> Mapping[str, Any]:
        key = self._runtime_key()
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

        payload = build_jev_payload(request, questions, model)
        request_sha = _hash_json(payload)
        with self._cache_lock:
            cached = self._cache.get(request_sha)
            if cached is not None:
                result = copy.deepcopy(dict(cached))
                result["provider"] = self._runtime_meta(
                    result, request, model, request_sha, cache_hit=True, coalesced=False,
                    network_request_count=0, latency_ms=0.0, transport_latency_ms=0.0,
                )
                return result
            waiter = self._inflight.get(request_sha)
            if waiter is None:
                waiter = threading.Event()
                self._inflight[request_sha] = waiter
                leader = True
            else:
                leader = False
        if not leader:
            deadline = time.monotonic() + float(self.timeout)
            waiter.wait(max(0.0, deadline - time.monotonic()))
            with self._cache_lock:
                cached = self._cache.get(request_sha)
            if cached is not None:
                result = copy.deepcopy(dict(cached))
                result["provider"] = self._runtime_meta(
                    result, request, model, request_sha, cache_hit=False, coalesced=True,
                    network_request_count=0, latency_ms=0.0, transport_latency_ms=0.0,
                )
                return result
            return {
                "schema_version": result_version,
                "provider": {"kind": "typesafe-jev", "status": "ERROR", "calibration_status": "UNKNOWN", "network_request_count": 0, "error": "singleflight deadline expired"},
                "question_set_sha256": question_hash,
                "answers": {},
            }
        started = time.perf_counter()
        transport_latency = 0.0
        try:
            attempts = max(1, int(self.max_attempts))
            errors: list[str] = []
            runtime = self._get_runtime(base, key)
            deadline_ms = request.get("jev_deadline_ms")
            deadline = time.monotonic() + min(
                float(self.timeout),
                max(0.001, float(deadline_ms) / 1000.0) if isinstance(deadline_ms, (int, float)) else float(self.timeout),
            )
            for attempt in range(1, attempts + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    errors.append("ValueOfCall deadline expired")
                    break
                try:
                    raw, transport_ms = runtime.request(payload, remaining)
                    transport_latency += transport_ms
                    result = to_reflex_result(raw, request, questions, model, self.calibration_binding)
                    _validate_result_contract(result, questions)
                    provider = dict(result.get("provider", {}))
                    provider["network_request_count"] = attempt
                    if attempt > 1:
                        provider["retry_count"] = attempt - 1
                        provider["retry_errors"] = list(errors)
                    provider.update({"request_sha256": request_sha})
                    result["provider"] = provider
                    result["provider"] = self._runtime_meta(
                        result, request, model, request_sha, cache_hit=False, coalesced=False,
                        network_request_count=attempt,
                        latency_ms=(time.perf_counter() - started) * 1000.0,
                        transport_latency_ms=transport_latency,
                    )
                    with self._cache_lock:
                        self._cache[request_sha] = copy.deepcopy(result)
                    return result
                except (JevAdapterError, KeyError, TypeError, ValueError) as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")
            return {
                "schema_version": result_version,
                "provider": {
                    "kind": "typesafe-jev", "status": "ERROR", "calibration_status": "UNKNOWN",
                    "network_request_count": len(errors), "retry_count": max(0, len(errors) - 1),
                    "retry_errors": list(errors[:-1]), "error": errors[-1] if errors else "request deadline expired",
                    "request_sha256": request_sha,
                    "runtime_receipt": {
                        "schema_version": RUNTIME_RECEIPT_VERSION, "requested_model": model, "response_model": None,
                        "question_set_sha256": question_hash, "threshold_policy_sha256": _threshold_hash_for_request(request),
                        "projection_version": _projection_version(request), "request_sha256": request_sha,
                        "cache_hit": False, "coalesced": False, "network_request_count": len(errors),
                        "retry_count": max(0, len(errors) - 1), "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
                        "transport_latency_ms": round(transport_latency, 3), "calibration_status": "UNKNOWN",
                    },
                },
                "question_set_sha256": question_hash,
                "answers": {},
            }
        finally:
            with self._cache_lock:
                event = self._inflight.pop(request_sha, None)
                if event is not None:
                    event.set()
