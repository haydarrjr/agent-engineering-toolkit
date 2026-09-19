#!/usr/bin/env python3
"""MARGOS deterministic Context Policy plus optional typed Context Reflex."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol

import margos_decide as routing_core

CONTEXT_POLICY_VERSION = "margos-context-policy/v1"
ITEM_VERSION = "margos-context-item/v1"
STATE_VERSION = "margos-context-state/v1"
DECISION_VERSION = "margos-context-decision/v1"
RECEIPT_VERSION = "margos-context-receipt/v1"
VIEW_VERSION = "margos-context-view/v1"
CONTEXT_REFLEX_REQUEST_VERSION = "margos-context-reflex-request/v1"
CONTEXT_REFLEX_RESULT_VERSION = "margos-context-reflex-result/v1"

ROOT = Path(__file__).resolve().parents[1]
QUESTION_DOC = json.loads((ROOT / "contracts/context-question-set-v1.json").read_text(encoding="utf-8"))
THRESHOLD_DOC = json.loads((ROOT / "contracts/context-threshold-policy-v1.json").read_text(encoding="utf-8"))
QUESTION_SET_VERSION = QUESTION_DOC["version"]
THRESHOLD_POLICY_VERSION = THRESHOLD_DOC["version"]
QUESTION_SET = tuple(QUESTION_DOC["questions"])
THRESHOLDS = {
    key: THRESHOLD_DOC[key]
    for key in (
        "full_threshold",
        "awareness_threshold",
        "replay_risk_threshold",
        "abstain_band",
        "max_items_per_batch",
        "max_projection_chars",
        "max_semantic_capsule_chars",
        "provider_failure_action",
    )
}


class ContextAction(str, Enum):
    PIN = "PIN"
    KEEP_FULL = "KEEP_FULL"
    KEEP_REF = "KEEP_REF"
    KEEP_HEAD = "KEEP_HEAD"
    OMIT_REHYDRATABLE = "OMIT_REHYDRATABLE"


class ProtectionClass(str, Enum):
    PINNED = "PINNED"
    ELIGIBLE = "ELIGIBLE"
    NO_REMOTE_EVAL = "NO_REMOTE_EVAL"
    NON_REPLAYABLE = "NON_REPLAYABLE"
    STALE_BUT_REQUIRED = "STALE_BUT_REQUIRED"
    SUPERSEDED = "SUPERSEDED"


class RehydrationMethod(str, Enum):
    READ_FILE = "READ_FILE"
    REPEAT_REPO_SEARCH = "REPEAT_REPO_SEARCH"
    READ_EVIDENCE_ARTIFACT = "READ_EVIDENCE_ARTIFACT"
    REPEAT_TEST = "REPEAT_TEST"
    REPEAT_BUILD = "REPEAT_BUILD"
    REFETCH_PUBLIC_DOC = "REFETCH_PUBLIC_DOC"
    READ_CHILD_RESULT_STORE = "READ_CHILD_RESULT_STORE"
    HOST_TRANSCRIPT_HANDLE = "HOST_TRANSCRIPT_HANDLE"
    UNAVAILABLE = "UNAVAILABLE"


class Rehydrator(Protocol):
    def recover(self, contract: Mapping[str, Any]) -> str: ...


@dataclass(frozen=True)
class FixtureContextReflexProvider:
    """Offline fixture provider implementing the existing ReflexProvider protocol."""

    answers: Mapping[str, Mapping[str, Any]]
    provider_id: str = "fixture-context"

    def evaluate(
        self,
        request: Mapping[str, Any],
        questions: tuple[dict[str, Any], ...],
    ) -> Mapping[str, Any]:
        del questions
        candidates = request.get("candidates", [])
        selected = {}
        for candidate in candidates:
            item_id = candidate["item_id"]
            if item_id not in self.answers:
                raise ValueError(f"missing fixture context answer for {item_id}")
            selected[item_id] = copy.deepcopy(dict(self.answers[item_id]))
        return {
            "schema_version": CONTEXT_REFLEX_RESULT_VERSION,
            "provider": {
                "kind": self.provider_id,
                "status": "AVAILABLE",
                "calibration_status": "UNCALIBRATED",
                "network_request_count": 0,
            },
            "question_set_sha256": question_set_sha256(),
            "answers": selected,
        }


AUTHORITY_FLAGS = (
    "contains_user_constraint",
    "contains_task_objective",
    "contains_permission_state",
    "contains_write_ownership",
    "contains_protected_path",
    "contains_explicit_model_provider_constraint",
    "contains_unresolved_external_effect",
    "contains_pending_confirmation",
    "contains_active_verification_obligation",
    "contains_unresolved_verification_failure",
    "contains_latest_route_decision",
)
EVIDENCE_FLAGS = (
    "proof_bound",
    "freshness_bound",
    "contradiction_open",
    "supports_claimed_pass",
)
COMPACT_ACTIONS = ["KEEP_FULL", "KEEP_REF", "KEEP_HEAD", "OMIT_REHYDRATABLE"]
SAFE_METHODS = {m.value for m in RehydrationMethod if m is not RehydrationMethod.UNAVAILABLE}
POLICY_DETAILS = {
    "MARGOS-CTX-POL-001": "Binding authority or obligation state is pinned.",
    "MARGOS-CTX-POL-002": "Active evidence, freshness, contradiction, or PASS support is pinned.",
    "MARGOS-CTX-POL-003": "Unknown or non-replayable evidence remains full.",
    "MARGOS-CTX-POL-004": "Explicitly superseded replayable evidence may leave the derived view.",
    "MARGOS-CTX-POL-005": "Current replayable unprotected evidence keeps a structured reference.",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bTYPESAFE_API_KEY\s*="),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def _canon(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def question_set_sha256() -> str:
    return _hash_json(QUESTION_DOC)


def threshold_policy_sha256() -> str:
    return _hash_json(THRESHOLD_DOC)


def _clip(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit]


def _obj(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _flags(value: Any, names: tuple[str, ...]) -> dict[str, bool]:
    obj = _obj(value or {}, "flags")
    result = {}
    for name in names:
        flag = obj.get(name, False)
        if not isinstance(flag, bool):
            raise ValueError(f"{name} must be boolean")
        result[name] = flag
    return result


def normalize_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    raw = _obj(raw, "context item")
    if raw.get("schema_version", ITEM_VERSION) != ITEM_VERSION:
        raise ValueError("unsupported context item schema")
    item_id = str(raw.get("item_id", "")).strip()
    if not item_id:
        raise ValueError("item_id is required")
    digest = str(raw.get("content_sha256", ""))
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("content_sha256 must be a lowercase SHA-256 digest")

    source = _obj(raw.get("source", {}), "source")
    size = _obj(raw.get("size", {}), "size")
    chars = int(size.get("chars", 0))
    tokens = size.get("tokens_estimated")
    if chars < 0 or (tokens is not None and int(tokens) < 0):
        raise ValueError("size values must be non-negative")

    evidence_raw = _obj(raw.get("evidence", {}), "evidence")
    evidence = _flags(evidence_raw, EVIDENCE_FLAGS)
    for key in ("proof_ids", "freshness_ids"):
        values = evidence_raw.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(x, str) or not x for x in values
        ):
            raise ValueError(f"{key} must be non-empty strings")
        evidence[key] = list(dict.fromkeys(values))
    route_id = evidence_raw.get("route_receipt_id")
    if route_id is not None and not isinstance(route_id, str):
        raise ValueError("route_receipt_id must be a string or null")
    evidence["route_receipt_id"] = route_id

    replay = _obj(raw.get("replay", {}), "replay")
    status = str(replay.get("status", "UNKNOWN")).upper()
    method = str(replay.get("method", "UNAVAILABLE")).upper()
    locator = replay.get("locator")
    if status not in {"REPLAYABLE", "NON_REPLAYABLE", "UNKNOWN"}:
        raise ValueError("unsupported replay status")
    if method not in {x.value for x in RehydrationMethod}:
        raise ValueError("unsupported rehydration method")
    locator = None if locator is None else str(locator)
    if status == "REPLAYABLE" and (method == "UNAVAILABLE" or not locator):
        raise ValueError("replayable item requires method and locator")
    if status != "REPLAYABLE" and method != "UNAVAILABLE":
        raise ValueError("non-replayable/unknown item must use UNAVAILABLE")

    supersession = _obj(raw.get("supersession", {}), "supersession")
    supersession_status = str(supersession.get("status", "CURRENT")).upper()
    superseded_by = supersession.get("superseded_by")
    superseded_by = None if superseded_by is None else str(superseded_by)
    if supersession_status not in {"CURRENT", "SUPERSEDED"}:
        raise ValueError("unsupported supersession status")
    if supersession_status == "SUPERSEDED" and (
        not superseded_by or superseded_by == item_id
    ):
        raise ValueError("superseded item requires distinct superseded_by")

    recency = _obj(raw.get("recency", {}), "recency")
    return {
        "schema_version": ITEM_VERSION,
        "item_id": item_id,
        "kind": str(raw.get("kind", "OTHER")).upper(),
        "source": {
            "tool": str(source.get("tool", "")),
            "locator": str(source.get("locator", "")),
            "result_status": str(source.get("result_status", "UNKNOWN")).upper(),
            "content_version": (
                None
                if source.get("content_version") is None
                else str(source.get("content_version"))
            ),
        },
        "content_sha256": digest,
        "size": {
            "chars": chars,
            "tokens_estimated": None if tokens is None else int(tokens),
        },
        "authority": _flags(raw.get("authority", {}), AUTHORITY_FLAGS),
        "evidence": evidence,
        "replay": {"status": status, "method": method, "locator": locator},
        "supersession": {
            "status": supersession_status,
            "superseded_by": superseded_by,
        },
        "recency": {"turn_distance": max(0, int(recency.get("turn_distance", 0)))},
    }


def normalize_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    raw = _obj(raw, "context state")
    if raw.get("schema_version", STATE_VERSION) != STATE_VERSION:
        raise ValueError("unsupported context state schema")
    values = raw.get("items", [])
    if not isinstance(values, list):
        raise ValueError("items must be an array")
    items = [normalize_item(x) for x in values]
    ids = [x["item_id"] for x in items]
    if len(ids) != len(set(ids)):
        raise ValueError("item_id values must be unique")
    known = set(ids)
    for item in items:
        successor = item["supersession"]["superseded_by"]
        if successor and successor not in known:
            raise ValueError("superseded_by must reference an item in the same state")
    task = _obj(raw.get("task", {}), "task")
    view = _obj(raw.get("view", {}), "view")
    head_chars = int(view.get("head_chars", 512))
    if head_chars <= 0:
        raise ValueError("head_chars must be positive")
    remote_capsule = view.get("remote_semantic_capsule_allowed", False)
    if not isinstance(remote_capsule, bool):
        raise ValueError("remote_semantic_capsule_allowed must be boolean")
    capsule_chars = int(view.get("semantic_capsule_chars", 0))
    max_capsule = int(THRESHOLDS["max_semantic_capsule_chars"])
    if capsule_chars < 0 or capsule_chars > max_capsule:
        raise ValueError("semantic_capsule_chars exceeds deterministic policy budget")
    if capsule_chars and not remote_capsule:
        raise ValueError("semantic_capsule_chars requires remote_semantic_capsule_allowed")
    return {
        "schema_version": STATE_VERSION,
        "task": {
            key: str(task.get(key, ""))
            for key in ("task_id", "objective", "verification_obligation")
        },
        "items": items,
        "view": {
            "head_chars": head_chars,
            "remote_semantic_capsule_allowed": remote_capsule,
            "semantic_capsule_chars": capsule_chars,
        },
    }


def rehydration_contract(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    item = normalize_item(raw_item)
    replay = item["replay"]
    available = replay["status"] == "REPLAYABLE"
    return {
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "method": replay["method"],
        "locator": replay["locator"],
        "content_sha256": item["content_sha256"],
        "may_repeat_external_effect": False,
        "authority_recheck_required": replay["method"]
        in {"REPEAT_TEST", "REPEAT_BUILD", "REFETCH_PUBLIC_DOC"},
    }


def _reflex_metadata(
    status: str,
    *,
    keep_awareness: float | None = None,
    keep_full: float | None = None,
    replay_needed: float | None = None,
    abstained: bool = True,
) -> dict[str, Any]:
    return {
        "status": status,
        "keep_awareness": keep_awareness,
        "keep_full": keep_full,
        "replay_needed": replay_needed,
        "abstained": abstained,
    }


def decide_item(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic Phase-1 baseline and Policy admissibility."""
    item = normalize_item(raw_item)
    if any(item["authority"].values()):
        cls, action, allowed, rule, source = (
            "PINNED",
            "PIN",
            ["PIN"],
            "MARGOS-CTX-POL-001",
            "DETERMINISTIC_POLICY",
        )
    elif any(item["evidence"][key] for key in EVIDENCE_FLAGS):
        cls, action, allowed, rule, source = (
            "PINNED",
            "PIN",
            ["PIN"],
            "MARGOS-CTX-POL-002",
            "DETERMINISTIC_POLICY",
        )
    elif item["replay"]["status"] != "REPLAYABLE":
        cls, action, allowed, rule, source = (
            "NON_REPLAYABLE",
            "KEEP_FULL",
            ["KEEP_FULL"],
            "MARGOS-CTX-POL-003",
            "DETERMINISTIC_POLICY",
        )
    elif item["supersession"]["status"] == "SUPERSEDED":
        cls, action, allowed, rule, source = (
            "SUPERSEDED",
            "OMIT_REHYDRATABLE",
            COMPACT_ACTIONS,
            "MARGOS-CTX-POL-004",
            "DETERMINISTIC_BASELINE",
        )
    else:
        cls, action, allowed, rule, source = (
            "ELIGIBLE",
            "KEEP_REF",
            COMPACT_ACTIONS,
            "MARGOS-CTX-POL-005",
            "DETERMINISTIC_BASELINE",
        )
    return {
        "schema_version": DECISION_VERSION,
        "item_id": item["item_id"],
        "protection_class": cls,
        "action": action,
        "admissible_actions": list(allowed),
        "policy_rules_applied": [
            {"rule_id": rule, "detail": POLICY_DETAILS[rule]}
        ],
        "rehydration": rehydration_contract(item),
        "superseded_by": item["supersession"]["superseded_by"],
        "decision_source": source,
        "reflex": _reflex_metadata(
            "NOT_ELIGIBLE" if source == "DETERMINISTIC_POLICY" else "DISABLED"
        ),
    }


def rehydrate_item(
    raw_item: Mapping[str, Any], rehydrator: Rehydrator
) -> str:
    item = normalize_item(raw_item)
    contract = rehydration_contract(item)
    if (
        contract["status"] != "AVAILABLE"
        or contract["method"] not in SAFE_METHODS
    ):
        raise ValueError("item has no safe deterministic rehydration path")
    content = rehydrator.recover(copy.deepcopy(contract))
    if not isinstance(content, str):
        raise ValueError("rehydrator must return text")
    if _hash_text(content) != item["content_sha256"]:
        raise ValueError("rehydrated content hash mismatch")
    return content


def _semantic_capsule(
    item: Mapping[str, Any],
    state: Mapping[str, Any],
    payloads: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    view = state["view"]
    if (
        not view["remote_semantic_capsule_allowed"]
        or int(view["semantic_capsule_chars"]) <= 0
        or payloads is None
    ):
        return None
    payload = _exact_payload(item, payloads)
    text = payload[: int(view["semantic_capsule_chars"])]
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return None
    return {
        "kind": "EXACT_PREFIX",
        "text": text,
        "characters": len(text),
        "sha256": _hash_text(text),
    }


def _candidate_projection(
    item: Mapping[str, Any],
    decision: Mapping[str, Any],
    state: Mapping[str, Any],
    payloads: Mapping[str, str] | None,
) -> dict[str, Any]:
    projected = {
        "item_id": item["item_id"],
        "kind": item["kind"],
        "source": {
            "tool": _clip(item["source"]["tool"], 128),
            "locator": _clip(item["source"]["locator"], 512),
            "result_status": item["source"]["result_status"],
            "content_version": (
                None
                if item["source"]["content_version"] is None
                else _clip(item["source"]["content_version"], 128)
            ),
        },
        "size": copy.deepcopy(item["size"]),
        "evidence": {
            key: bool(item["evidence"][key]) for key in EVIDENCE_FLAGS
        },
        "replay": copy.deepcopy(item["replay"]),
        "supersession": copy.deepcopy(item["supersession"]),
        "recency": copy.deepcopy(item["recency"]),
        "admissible_actions": list(decision["admissible_actions"]),
    }
    capsule = _semantic_capsule(item, state, payloads)
    if capsule is not None:
        projected["semantic_capsule"] = capsule
    return projected


def build_context_reflex_request(
    state: Mapping[str, Any],
    candidates: list[tuple[Mapping[str, Any], Mapping[str, Any]]],
    payloads: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CONTEXT_REFLEX_REQUEST_VERSION,
        "task": {
            "objective": _clip(state["task"]["objective"], 3000),
            "verification_obligation": _clip(
                state["task"]["verification_obligation"], 2000
            ),
        },
        "candidates": [
            _candidate_projection(item, decision, state, payloads)
            for item, decision in candidates
        ],
        "question_set_sha256": question_set_sha256(),
        "threshold_policy_sha256": threshold_policy_sha256(),
    }


def _candidate_batches(
    state: Mapping[str, Any],
    candidates: list[tuple[Mapping[str, Any], Mapping[str, Any]]],
    payloads: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    max_items = int(THRESHOLDS["max_items_per_batch"])
    max_chars = int(THRESHOLDS["max_projection_chars"])
    if max_items < 1 or max_chars < 1:
        raise ValueError("invalid Context Reflex batch budget")
    batches: list[dict[str, Any]] = []
    current: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for pair in candidates:
        trial = current + [pair]
        request = build_context_reflex_request(state, trial, payloads)
        exceeds = len(trial) > max_items or len(_canon(request)) > max_chars
        if current and exceeds:
            batches.append(build_context_reflex_request(state, current, payloads))
            current = [pair]
        else:
            current = trial
    if current:
        batches.append(build_context_reflex_request(state, current, payloads))
    return batches

def _probability(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} probability must be numeric")
    result = float(value)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} probability must be in [0,1]")
    return result


def validate_context_reflex_result(
    result: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        not isinstance(result, Mapping)
        or result.get("schema_version") != CONTEXT_REFLEX_RESULT_VERSION
    ):
        raise ValueError("invalid Context Reflex result schema")
    if result.get("question_set_sha256") != question_set_sha256():
        raise ValueError("wrong Context Reflex question set")
    provider = result.get("provider", {})
    if not isinstance(provider, Mapping) or provider.get("status") != "AVAILABLE":
        raise ValueError("Context Reflex provider unavailable")
    answers = result.get("answers", {})
    if not isinstance(answers, Mapping):
        raise ValueError("Context Reflex answers must be an object")
    expected = {candidate["item_id"] for candidate in request["candidates"]}
    if set(answers) != expected:
        raise ValueError("Context Reflex answers must cover the candidate batch")
    validated = {}
    question_ids = {q["id"] for q in QUESTION_SET}
    for item_id in expected:
        item_answers = answers[item_id]
        if not isinstance(item_answers, Mapping):
            raise ValueError(f"invalid answers for {item_id}")
        if set(item_answers) != question_ids:
            raise ValueError(f"incomplete Context Reflex answers for {item_id}")
        validated[item_id] = {}
        for qid in question_ids:
            raw = item_answers[qid]
            if not isinstance(raw, Mapping):
                raise ValueError(f"invalid {qid} for {item_id}")
            validated[item_id][qid] = {
                "probability": _probability(raw.get("probability"), qid)
            }
    return {
        "schema_version": CONTEXT_REFLEX_RESULT_VERSION,
        "provider": dict(provider),
        "question_set_sha256": result["question_set_sha256"],
        "answers": validated,
    }


def _aggregate_usage(
    target: dict[str, int], provider_meta: Mapping[str, Any]
) -> None:
    usage = provider_meta.get("usage")
    if not isinstance(usage, Mapping):
        return
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            target[key] = target.get(key, 0) + value


def evaluate_context_reflex(
    state: Mapping[str, Any],
    baseline_decisions: list[Mapping[str, Any]],
    provider: routing_core.ReflexProvider | None,
    payloads: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    item_by_id = {item["item_id"]: item for item in state["items"]}
    candidates = [
        (item_by_id[decision["item_id"]], decision)
        for decision in baseline_decisions
        if decision["protection_class"] in {"ELIGIBLE", "SUPERSEDED"}
    ]
    if provider is None:
        return {}, {
            "kind": "none",
            "status": "DISABLED",
            "calibration_status": "UNKNOWN",
            "request_count": 0,
            "network_request_count": 0,
            "items_evaluated": 0,
        }
    if not candidates:
        return {}, {
            "kind": "none",
            "status": "NOT_NEEDED",
            "calibration_status": "UNKNOWN",
            "request_count": 0,
            "network_request_count": 0,
            "items_evaluated": 0,
        }

    batches = _candidate_batches(state, candidates, payloads)
    all_answers: dict[str, Any] = {}
    aggregate_usage: dict[str, int] = {}
    request_count = 0
    network_request_count = 0
    provider_meta: dict[str, Any] = {
        "kind": type(provider).__name__,
        "status": "ERROR",
        "calibration_status": "UNKNOWN",
    }
    for request in batches:
        request_count += 1
        try:
            raw = provider.evaluate(request, QUESTION_SET)
        except Exception as exc:  # bounded provider boundary
            provider_meta = {
                "kind": type(provider).__name__,
                "status": "ERROR",
                "calibration_status": "UNKNOWN",
                "error": f"{type(exc).__name__}: {exc}",
            }
            break

        if isinstance(raw, Mapping) and isinstance(raw.get("provider"), Mapping):
            provider_meta = dict(raw["provider"])
        status = provider_meta.get("status")
        network_value = provider_meta.get("network_request_count", 0)
        if (
            isinstance(network_value, int)
            and not isinstance(network_value, bool)
            and network_value >= 0
        ):
            network_request_count += network_value
        _aggregate_usage(aggregate_usage, provider_meta)

        if status == "NOT_CONFIGURED":
            all_answers = {}
            break
        if status == "ERROR":
            all_answers = {}
            break
        if status != "AVAILABLE":
            provider_meta = {
                **provider_meta,
                "status": "ERROR",
                "error": f"unsupported provider status: {status}",
            }
            all_answers = {}
            break
        try:
            validated = validate_context_reflex_result(raw, request)
        except (TypeError, ValueError, KeyError) as exc:
            provider_meta = {
                **provider_meta,
                "status": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
            all_answers = {}
            break
        all_answers.update(validated["answers"])

    provider_meta = {
        **provider_meta,
        "request_count": request_count,
        "network_request_count": network_request_count,
        "items_evaluated": len(all_answers),
        "batch_count": len(batches),
    }
    if aggregate_usage:
        provider_meta["usage"] = aggregate_usage
    return all_answers, provider_meta


def _near_threshold(value: float, threshold: float) -> bool:
    return abs(value - threshold) <= float(THRESHOLDS["abstain_band"])


def compose_context_decision(
    baseline: Mapping[str, Any],
    answer: Mapping[str, Any] | None,
    provider_status: str,
) -> dict[str, Any]:
    decision = copy.deepcopy(dict(baseline))
    if baseline["protection_class"] not in {"ELIGIBLE", "SUPERSEDED"}:
        return decision

    if provider_status in {"DISABLED", "NOT_NEEDED"}:
        decision["reflex"] = _reflex_metadata(provider_status)
        return decision

    if provider_status != "AVAILABLE" or answer is None:
        fallback = str(THRESHOLDS["provider_failure_action"])
        if fallback not in baseline["admissible_actions"]:
            fallback = "KEEP_FULL"
        decision["action"] = fallback
        decision["decision_source"] = "REFLEX_CONSERVATIVE_FALLBACK"
        decision["reflex"] = _reflex_metadata(provider_status)
        return decision

    keep_awareness = _probability(
        answer["keep_awareness"]["probability"], "keep_awareness"
    )
    keep_full = _probability(answer["keep_full"]["probability"], "keep_full")
    replay_needed = _probability(
        answer["replay_needed"]["probability"], "replay_needed"
    )
    full_threshold = float(THRESHOLDS["full_threshold"])
    awareness_threshold = float(THRESHOLDS["awareness_threshold"])
    replay_threshold = float(THRESHOLDS["replay_risk_threshold"])
    abstained = any(
        (
            _near_threshold(keep_full, full_threshold),
            _near_threshold(keep_awareness, awareness_threshold),
            _near_threshold(replay_needed, replay_threshold),
        )
    )
    if abstained:
        action = "KEEP_REF"
        source = "REFLEX_CONSERVATIVE_FALLBACK"
    elif keep_full >= full_threshold:
        action = "KEEP_FULL"
        source = "REFLEX_ASSISTED"
    elif (
        keep_awareness >= awareness_threshold
        or replay_needed >= replay_threshold
    ):
        action = "KEEP_REF"
        source = "REFLEX_ASSISTED"
    else:
        action = "OMIT_REHYDRATABLE"
        source = "REFLEX_ASSISTED"

    if action not in baseline["admissible_actions"]:
        action = "KEEP_REF" if "KEEP_REF" in baseline["admissible_actions"] else "KEEP_FULL"
        source = "REFLEX_CONSERVATIVE_FALLBACK"
        abstained = True
    decision["action"] = action
    decision["decision_source"] = source
    decision["reflex"] = _reflex_metadata(
        "AVAILABLE",
        keep_awareness=keep_awareness,
        keep_full=keep_full,
        replay_needed=replay_needed,
        abstained=abstained,
    )
    return decision


def decide_context(
    raw_state: Mapping[str, Any],
    provider: routing_core.ReflexProvider | None = None,
    payloads: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    state = normalize_state(raw_state)
    baseline = [decide_item(item) for item in state["items"]]
    answers, provider_meta = evaluate_context_reflex(state, baseline, provider, payloads)
    decisions = [
        compose_context_decision(
            decision,
            answers.get(decision["item_id"]),
            str(provider_meta["status"]),
        )
        for decision in baseline
    ]
    return state, decisions, provider_meta


def _reference(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": copy.deepcopy(item["source"]),
        "content_sha256": item["content_sha256"],
        "size": copy.deepcopy(item["size"]),
        "replay": copy.deepcopy(item["replay"]),
        "evidence": {
            key: copy.deepcopy(item["evidence"][key])
            for key in ("proof_ids", "freshness_ids", "route_receipt_id")
        },
    }


def _exact_payload(
    item: Mapping[str, Any], payloads: Mapping[str, str]
) -> str:
    payload = payloads.get(item["item_id"])
    if not isinstance(payload, str):
        raise ValueError(f"missing exact payload for {item['item_id']}")
    if len(payload) != item["size"]["chars"]:
        raise ValueError(f"payload size mismatch for {item['item_id']}")
    if _hash_text(payload) != item["content_sha256"]:
        raise ValueError(f"payload hash mismatch for {item['item_id']}")
    return payload


def materialize_context_view(
    raw_state: Mapping[str, Any],
    payloads: Mapping[str, str],
    provider: routing_core.ReflexProvider | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payloads, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str)
        for k, v in payloads.items()
    ):
        raise ValueError("payloads must map item_id to exact text")
    state, decisions, provider_meta = decide_context(raw_state, provider, payloads)
    state_hash = _hash_json(state)
    by_id = {d["item_id"]: d for d in decisions}
    active, rehydration_index = [], []
    counts = {action.value: 0 for action in ContextAction}

    for item in state["items"]:
        decision = by_id[item["item_id"]]
        action = decision["action"]
        counts[action] += 1
        ref = _reference(item)
        if action in {"PIN", "KEEP_FULL"}:
            active.append(
                {
                    "item_id": item["item_id"],
                    "kind": item["kind"],
                    "action": action,
                    "content": _exact_payload(item, payloads),
                    "reference": ref,
                }
            )
        elif action == "KEEP_HEAD":
            content = _exact_payload(item, payloads)
            active.append(
                {
                    "item_id": item["item_id"],
                    "kind": item["kind"],
                    "action": action,
                    "head": content[: state["view"]["head_chars"]],
                    "reference": ref,
                }
            )
            rehydration_index.append(
                {
                    "item_id": item["item_id"],
                    **copy.deepcopy(decision["rehydration"]),
                }
            )
        elif action == "KEEP_REF":
            active.append(
                {
                    "item_id": item["item_id"],
                    "kind": item["kind"],
                    "action": action,
                    "reference": ref,
                }
            )
            rehydration_index.append(
                {
                    "item_id": item["item_id"],
                    **copy.deepcopy(decision["rehydration"]),
                }
            )
        elif action == "OMIT_REHYDRATABLE":
            if decision["rehydration"]["status"] != "AVAILABLE":
                raise ValueError("Policy attempted omission without rehydration")
            rehydration_index.append(
                {
                    "item_id": item["item_id"],
                    **copy.deepcopy(decision["rehydration"]),
                }
            )
        else:
            raise ValueError(f"unsupported context action: {action}")

    view = {
        "schema_version": VIEW_VERSION,
        "authority": "DERIVED_VIEW",
        "state_sha256": state_hash,
        "items": active,
        "rehydration_index": rehydration_index,
    }
    receipt = {
        "schema_version": RECEIPT_VERSION,
        "authority": "DERIVED_VIEW",
        "state_sha256": state_hash,
        "policy_version": CONTEXT_POLICY_VERSION,
        "question_set_version": QUESTION_SET_VERSION,
        "question_set_sha256": question_set_sha256(),
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "threshold_policy_sha256": threshold_policy_sha256(),
        "provider": provider_meta,
        "input": {
            "items": len(state["items"]),
            "characters": sum(x["size"]["chars"] for x in state["items"]),
        },
        "actions": decisions,
        "output": {
            "items_active": len(active),
            "characters_serialized": len(_canon(view)),
            "action_counts": counts,
        },
        "context_view_sha256": _hash_json(view),
        "canonical_source_mutated": False,
        "rehydration_available": all(
            d["rehydration"]["status"] == "AVAILABLE"
            for d in decisions
            if d["action"] in {"KEEP_REF", "KEEP_HEAD", "OMIT_REHYDRATABLE"}
        ),
    }
    return view, receipt


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--payloads", type=Path, required=True)
    parser.add_argument(
        "--reflex-provider",
        choices=("none", "jev"),
        default="none",
        help="Live provider is explicit opt-in; API key presence alone never enables it.",
    )
    parser.add_argument("--fixture-reflex", type=Path)
    parser.add_argument("--jev-model")
    parser.add_argument("--calibration-binding", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.fixture_reflex and args.reflex_provider != "none":
        parser.error("--fixture-reflex cannot be combined with a live provider")
    if args.jev_model and args.reflex_provider != "jev":
        parser.error("--jev-model requires --reflex-provider jev")
    if args.calibration_binding and args.reflex_provider != "jev":
        parser.error("--calibration-binding requires --reflex-provider jev")
    if args.calibration_binding and not args.jev_model:
        parser.error("--calibration-binding requires an explicit --jev-model")

    provider: routing_core.ReflexProvider | None = None
    if args.fixture_reflex:
        fixture = _read(args.fixture_reflex)
        answers = fixture.get("answers", fixture)
        provider = FixtureContextReflexProvider(answers)
    elif args.reflex_provider == "jev":
        import margos_reflex_jev

        binding = _read(args.calibration_binding) if args.calibration_binding else None
        provider = margos_reflex_jev.JevReflexProvider(
            model=args.jev_model, calibration_binding=binding
        )

    view, receipt = materialize_context_view(
        _read(args.state), _read(args.payloads), provider
    )
    rendered = (
        json.dumps(
            {"view": view, "receipt": receipt},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
