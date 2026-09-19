#!/usr/bin/env python3
"""Deterministic MARGOS Context Policy and derived Context View materializer."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol

CONTEXT_POLICY_VERSION = "margos-context-policy/v1"
ITEM_VERSION = "margos-context-item/v1"
STATE_VERSION = "margos-context-state/v1"
DECISION_VERSION = "margos-context-decision/v1"
RECEIPT_VERSION = "margos-context-receipt/v1"
VIEW_VERSION = "margos-context-view/v1"


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


AUTHORITY_FLAGS = (
    "contains_user_constraint", "contains_task_objective", "contains_permission_state",
    "contains_write_ownership", "contains_protected_path",
    "contains_explicit_model_provider_constraint", "contains_unresolved_external_effect",
    "contains_pending_confirmation", "contains_active_verification_obligation",
    "contains_unresolved_verification_failure", "contains_latest_route_decision",
)
EVIDENCE_FLAGS = ("proof_bound", "freshness_bound", "contradiction_open", "supports_claimed_pass")
COMPACT_ACTIONS = ["KEEP_FULL", "KEEP_REF", "KEEP_HEAD", "OMIT_REHYDRATABLE"]
SAFE_METHODS = {m.value for m in RehydrationMethod if m is not RehydrationMethod.UNAVAILABLE}
POLICY_DETAILS = {
    "MARGOS-CTX-POL-001": "Binding authority or obligation state is pinned.",
    "MARGOS-CTX-POL-002": "Active evidence, freshness, contradiction, or PASS support is pinned.",
    "MARGOS-CTX-POL-003": "Unknown or non-replayable evidence remains full.",
    "MARGOS-CTX-POL-004": "Explicitly superseded replayable evidence may leave the derived view.",
    "MARGOS-CTX-POL-005": "Current replayable unprotected evidence keeps a structured reference.",
}


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


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
        if not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values):
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
    if supersession_status == "SUPERSEDED" and (not superseded_by or superseded_by == item_id):
        raise ValueError("superseded item requires distinct superseded_by")

    recency = _obj(raw.get("recency", {}), "recency")
    return {
        "schema_version": ITEM_VERSION,
        "item_id": item_id,
        "kind": str(raw.get("kind", "OTHER")).upper(),
        "source": {
            "tool": str(source.get("tool", "")), "locator": str(source.get("locator", "")),
            "result_status": str(source.get("result_status", "UNKNOWN")).upper(),
            "content_version": None if source.get("content_version") is None else str(source.get("content_version")),
        },
        "content_sha256": digest,
        "size": {"chars": chars, "tokens_estimated": None if tokens is None else int(tokens)},
        "authority": _flags(raw.get("authority", {}), AUTHORITY_FLAGS),
        "evidence": evidence,
        "replay": {"status": status, "method": method, "locator": locator},
        "supersession": {"status": supersession_status, "superseded_by": superseded_by},
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
    return {
        "schema_version": STATE_VERSION,
        "task": {k: str(task.get(k, "")) for k in ("task_id", "objective", "verification_obligation")},
        "items": items,
        "view": {"head_chars": head_chars},
    }


def rehydration_contract(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    item = normalize_item(raw_item)
    replay = item["replay"]
    available = replay["status"] == "REPLAYABLE"
    return {
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "method": replay["method"], "locator": replay["locator"],
        "content_sha256": item["content_sha256"],
        "may_repeat_external_effect": False,
        "authority_recheck_required": replay["method"] in {"REPEAT_TEST", "REPEAT_BUILD", "REFETCH_PUBLIC_DOC"},
    }


def decide_item(raw_item: Mapping[str, Any]) -> dict[str, Any]:
    item = normalize_item(raw_item)
    if any(item["authority"].values()):
        cls, action, allowed, rule = "PINNED", "PIN", ["PIN"], "MARGOS-CTX-POL-001"
    elif any(item["evidence"][key] for key in EVIDENCE_FLAGS):
        cls, action, allowed, rule = "PINNED", "PIN", ["PIN"], "MARGOS-CTX-POL-002"
    elif item["replay"]["status"] != "REPLAYABLE":
        cls, action, allowed, rule = "NON_REPLAYABLE", "KEEP_FULL", ["KEEP_FULL"], "MARGOS-CTX-POL-003"
    elif item["supersession"]["status"] == "SUPERSEDED":
        cls, action, allowed, rule = "SUPERSEDED", "OMIT_REHYDRATABLE", COMPACT_ACTIONS, "MARGOS-CTX-POL-004"
    else:
        cls, action, allowed, rule = "ELIGIBLE", "KEEP_REF", COMPACT_ACTIONS, "MARGOS-CTX-POL-005"
    return {
        "schema_version": DECISION_VERSION, "item_id": item["item_id"],
        "protection_class": cls, "action": action, "admissible_actions": list(allowed),
        "policy_rules_applied": [{"rule_id": rule, "detail": POLICY_DETAILS[rule]}],
        "rehydration": rehydration_contract(item),
        "superseded_by": item["supersession"]["superseded_by"],
    }


def rehydrate_item(raw_item: Mapping[str, Any], rehydrator: Rehydrator) -> str:
    item = normalize_item(raw_item)
    contract = rehydration_contract(item)
    if contract["status"] != "AVAILABLE" or contract["method"] not in SAFE_METHODS:
        raise ValueError("item has no safe deterministic rehydration path")
    content = rehydrator.recover(copy.deepcopy(contract))
    if not isinstance(content, str):
        raise ValueError("rehydrator must return text")
    if _hash_text(content) != item["content_sha256"]:
        raise ValueError("rehydrated content hash mismatch")
    return content


def _reference(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": copy.deepcopy(item["source"]), "content_sha256": item["content_sha256"],
        "size": copy.deepcopy(item["size"]), "replay": copy.deepcopy(item["replay"]),
        "evidence": {k: copy.deepcopy(item["evidence"][k]) for k in ("proof_ids", "freshness_ids", "route_receipt_id")},
    }


def _exact_payload(item: Mapping[str, Any], payloads: Mapping[str, str]) -> str:
    payload = payloads.get(item["item_id"])
    if not isinstance(payload, str):
        raise ValueError(f"missing exact payload for {item['item_id']}")
    if len(payload) != item["size"]["chars"]:
        raise ValueError(f"payload size mismatch for {item['item_id']}")
    if _hash_text(payload) != item["content_sha256"]:
        raise ValueError(f"payload hash mismatch for {item['item_id']}")
    return payload


def materialize_context_view(raw_state: Mapping[str, Any], payloads: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payloads, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in payloads.items()):
        raise ValueError("payloads must map item_id to exact text")
    state = normalize_state(raw_state)
    state_hash = _hash_json(state)
    decisions = [decide_item(item) for item in state["items"]]
    by_id = {d["item_id"]: d for d in decisions}
    active, rehydration_index = [], []
    counts = {action.value: 0 for action in ContextAction}

    for item in state["items"]:
        decision = by_id[item["item_id"]]
        action = decision["action"]
        counts[action] += 1
        ref = _reference(item)
        if action in {"PIN", "KEEP_FULL"}:
            active.append({"item_id": item["item_id"], "kind": item["kind"], "action": action,
                           "content": _exact_payload(item, payloads), "reference": ref})
        elif action == "KEEP_HEAD":
            content = _exact_payload(item, payloads)
            active.append({"item_id": item["item_id"], "kind": item["kind"], "action": action,
                           "head": content[:state["view"]["head_chars"]], "reference": ref})
            rehydration_index.append({"item_id": item["item_id"], **copy.deepcopy(decision["rehydration"])})
        elif action == "KEEP_REF":
            active.append({"item_id": item["item_id"], "kind": item["kind"], "action": action, "reference": ref})
            rehydration_index.append({"item_id": item["item_id"], **copy.deepcopy(decision["rehydration"])})
        elif action == "OMIT_REHYDRATABLE":
            if decision["rehydration"]["status"] != "AVAILABLE":
                raise ValueError("Policy attempted omission without rehydration")
            rehydration_index.append({"item_id": item["item_id"], **copy.deepcopy(decision["rehydration"])})
        else:
            raise ValueError(f"unsupported context action: {action}")

    view = {"schema_version": VIEW_VERSION, "authority": "DERIVED_VIEW", "state_sha256": state_hash,
            "items": active, "rehydration_index": rehydration_index}
    receipt = {
        "schema_version": RECEIPT_VERSION, "authority": "DERIVED_VIEW", "state_sha256": state_hash,
        "policy_version": CONTEXT_POLICY_VERSION,
        "provider": {"kind": "none", "status": "NOT_CONFIGURED"},
        "input": {"items": len(state["items"]), "characters": sum(x["size"]["chars"] for x in state["items"])},
        "actions": decisions,
        "output": {"items_active": len(active), "characters_serialized": len(_canon(view)), "action_counts": counts},
        "context_view_sha256": _hash_json(view), "canonical_source_mutated": False,
        "rehydration_available": all(
            d["rehydration"]["status"] == "AVAILABLE" for d in decisions
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    view, receipt = materialize_context_view(_read(args.state), _read(args.payloads))
    rendered = json.dumps({"view": view, "receipt": receipt}, indent=2, sort_keys=True, ensure_ascii=False) + "
"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
