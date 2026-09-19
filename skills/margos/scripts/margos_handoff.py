#!/usr/bin/env python3
"""Role-aware MARGOS child-context handoff and safe rehydration planning."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import margos_context as context_core
import margos_decide as routing_core

CHILD_CONTRACT_VERSION = "margos-child-contract/v1"
CHILD_BUNDLE_VERSION = "margos-child-context-bundle/v1"
CHILD_RECEIPT_VERSION = "margos-child-context-receipt/v1"
CHILD_RESULT_VERSION = "margos-child-result/v1"
REHYDRATION_PLAN_VERSION = "margos-child-rehydration-plan/v1"
REHYDRATION_RESULT_VERSION = "margos-child-rehydration-result/v1"
ROUTE_RECEIPT_VERSION = "margos-route-receipt/v1"

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_POLICY_DOC = json.loads(
    (ROOT / "contracts/child-handoff-policy-v1.json").read_text(encoding="utf-8")
)
HANDOFF_POLICY_VERSION = HANDOFF_POLICY_DOC["version"]
ROLE_POLICY = HANDOFF_POLICY_DOC["roles"]

CHILD_ROLES = {"SCOUT", "WORKER", "VERIFIER", "INDEPENDENT_CRITIC"}
CHILD_COORDINATIONS = {"TRANSFER", "DELEGATED", "SERIALIZED"}
SAFE_ROUTE_STATUSES = {"PENDING", "OBSERVED", "UNKNOWN", "FAILED"}


def _canon(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _obj(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    result = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"{name} must contain non-empty strings")
        cleaned = entry.strip()
        if cleaned not in result:
            result.append(cleaned)
    return result


def _normalized_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    path = path.rstrip("/")
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError("owned_paths must be relative repository paths")
    return path


def _path_owned(locator: str, owned_paths: list[str]) -> bool:
    path = locator.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    for owned in owned_paths:
        if path == owned or path.startswith(owned + "/"):
            return True
    return False


def normalize_route_receipt(raw: Mapping[str, Any]) -> dict[str, Any]:
    route = copy.deepcopy(dict(_obj(raw, "route receipt")))
    if route.get("schema_version") != ROUTE_RECEIPT_VERSION:
        raise ValueError("unsupported route receipt schema")
    if "context_binding" in route:
        raise ValueError("route receipt is already context-bound")
    selected = _obj(route.get("selected"), "route selected")
    disposition = selected.get("disposition")
    coordination = selected.get("coordination")
    role = selected.get("role")
    compute = selected.get("compute")
    if disposition != "PROCEED":
        raise ValueError("child handoff requires a PROCEED route")
    if coordination not in CHILD_COORDINATIONS:
        raise ValueError("child handoff requires TRANSFER, DELEGATED, or SERIALIZED")
    if role not in CHILD_ROLES:
        raise ValueError("route selected role is not a child role")
    if compute not in {x.value for x in routing_core.ComputeTier}:
        raise ValueError("route selected compute tier is invalid")
    host_execution = _obj(route.get("host_execution"), "host_execution")
    if host_execution.get("status") not in SAFE_ROUTE_STATUSES:
        raise ValueError("unsupported host execution status")
    return route


def normalize_child_contract(
    raw: Mapping[str, Any], route: Mapping[str, Any]
) -> dict[str, Any]:
    raw = _obj(raw, "child contract")
    if raw.get("schema_version") != CHILD_CONTRACT_VERSION:
        raise ValueError("unsupported child contract schema")
    child_id = str(raw.get("child_id", "")).strip()
    role = str(raw.get("role", "")).upper()
    objective = str(raw.get("objective", "")).strip()
    output_contract = str(raw.get("output_contract", "")).strip()
    verification_obligation = str(raw.get("verification_obligation", "")).strip()
    if not child_id or not objective or not output_contract:
        raise ValueError("child_id, objective, and output_contract are required")
    if role not in CHILD_ROLES:
        raise ValueError("unsupported child role")
    if role != route["selected"]["role"]:
        raise ValueError("child role must match the finalized route role")

    owned_paths = [_normalized_path(x) for x in _string_list(raw.get("owned_paths", []), "owned_paths")]
    required_context_ids = _string_list(raw.get("required_context_ids", []), "required_context_ids")
    required_full_ids = _string_list(raw.get("required_full_ids", []), "required_full_ids")
    implementation_result_ids = _string_list(
        raw.get("implementation_result_ids", []), "implementation_result_ids"
    )
    verification_evidence_ids = _string_list(
        raw.get("verification_evidence_ids", []), "verification_evidence_ids"
    )
    fresh_evidence_ids = _string_list(
        raw.get("fresh_evidence_ids", []), "fresh_evidence_ids"
    )
    budget = _obj(raw.get("budget"), "budget")
    max_optional_items = int(budget.get("max_optional_items", 0))
    max_optional_payload_chars = int(budget.get("max_optional_payload_chars", 0))
    if not 0 <= max_optional_items <= 64:
        raise ValueError("max_optional_items must be in [0,64]")
    if max_optional_payload_chars < 0:
        raise ValueError("max_optional_payload_chars must be non-negative")

    if role == "WORKER" and not owned_paths:
        raise ValueError("WORKER child contract requires owned_paths")
    if role == "VERIFIER":
        if not verification_obligation:
            raise ValueError("VERIFIER requires a verification_obligation")
        if not implementation_result_ids:
            raise ValueError("VERIFIER requires implementation_result_ids")
    if role == "INDEPENDENT_CRITIC":
        if not implementation_result_ids:
            raise ValueError("INDEPENDENT_CRITIC requires implementation_result_ids")
        if not fresh_evidence_ids:
            raise ValueError("INDEPENDENT_CRITIC requires fresh_evidence_ids")

    return {
        "schema_version": CHILD_CONTRACT_VERSION,
        "child_id": child_id,
        "role": role,
        "objective": objective,
        "owned_paths": owned_paths,
        "required_context_ids": required_context_ids,
        "required_full_ids": required_full_ids,
        "implementation_result_ids": implementation_result_ids,
        "verification_evidence_ids": verification_evidence_ids,
        "fresh_evidence_ids": fresh_evidence_ids,
        "verification_obligation": verification_obligation,
        "output_contract": output_contract,
        "budget": {
            "max_optional_items": max_optional_items,
            "max_optional_payload_chars": max_optional_payload_chars,
        },
    }


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


def _exact_payload(item: Mapping[str, Any], payloads: Mapping[str, str]) -> str:
    payload = payloads.get(item["item_id"])
    if not isinstance(payload, str):
        raise ValueError(f"missing exact payload for {item['item_id']}")
    if len(payload) != item["size"]["chars"]:
        raise ValueError(f"payload size mismatch for {item['item_id']}")
    if _hash_text(payload) != item["content_sha256"]:
        raise ValueError(f"payload hash mismatch for {item['item_id']}")
    return payload


def _required_ids(contract: Mapping[str, Any]) -> list[str]:
    ordered: list[str] = []
    for key in (
        "required_context_ids",
        "required_full_ids",
        "implementation_result_ids",
        "verification_evidence_ids",
        "fresh_evidence_ids",
    ):
        for item_id in contract[key]:
            if item_id not in ordered:
                ordered.append(item_id)
    return ordered


def _selection_reasons(
    item: Mapping[str, Any],
    decision: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[str]:
    item_id = item["item_id"]
    reasons: list[str] = []
    if decision["protection_class"] in {"PINNED", "NON_REPLAYABLE"}:
        reasons.append("POLICY_PROTECTED")
    if item_id in contract["required_context_ids"]:
        reasons.append("EXPLICIT_REQUIRED")
    if item_id in contract["required_full_ids"]:
        reasons.append("EXPLICIT_FULL")
    if item_id in contract["implementation_result_ids"]:
        reasons.append("IMPLEMENTATION_RESULT")
    if item_id in contract["verification_evidence_ids"]:
        reasons.append("VERIFICATION_EVIDENCE")
    if item_id in contract["fresh_evidence_ids"]:
        reasons.append("FRESH_EVIDENCE")
    if contract["role"] == "WORKER" and _path_owned(
        item["source"]["locator"], contract["owned_paths"]
    ):
        reasons.append("OWNED_PATH")
    return reasons


def _optional_role_candidate(
    item: Mapping[str, Any],
    decision: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> bool:
    if decision["action"] == "OMIT_REHYDRATABLE":
        return False
    role = contract["role"]
    profile = ROLE_POLICY[role]
    if not profile["inherit_optional"]:
        return False
    match = profile["optional_match"]
    if match == "OWNED_PATH":
        return _path_owned(item["source"]["locator"], contract["owned_paths"])
    if match == "TOOL_SIGNAL":
        tool = item["source"]["tool"].lower()
        return any(token in tool for token in profile["optional_tool_signals"])
    return False


def _desired_action(
    item: Mapping[str, Any],
    decision: Mapping[str, Any],
    contract: Mapping[str, Any],
    reasons: list[str],
    *,
    optional: bool,
) -> str:
    if "POLICY_PROTECTED" in reasons:
        return decision["action"]
    role = contract["role"]
    profile = ROLE_POLICY[role]
    if any(reason in profile["exact_reasons"] for reason in reasons):
        return "KEEP_FULL"
    if (
        "FRESH_EVIDENCE" in reasons
        and profile.get("fresh_evidence_action") == "KEEP_HEAD"
    ):
        return "KEEP_HEAD"

    action = decision["action"]
    if action == "OMIT_REHYDRATABLE":
        action = "KEEP_REF"
    if action == "KEEP_FULL":
        action = (
            profile["optional_full_cap"]
            if optional
            else profile["ordinary_full_cap"]
        )
    if action not in {"PIN", "KEEP_FULL", "KEEP_REF", "KEEP_HEAD"}:
        action = "KEEP_REF"
    return action


def _materialize_child_item(
    item: Mapping[str, Any],
    decision: Mapping[str, Any],
    contract: Mapping[str, Any],
    reasons: list[str],
    payloads: Mapping[str, str],
    head_chars: int,
    *,
    optional: bool,
) -> tuple[dict[str, Any], int]:
    action = _desired_action(
        item, decision, contract, reasons, optional=optional
    )
    entry = {
        "item_id": item["item_id"],
        "kind": item["kind"],
        "action": action,
        "selection_reasons": reasons,
        "reference": _reference(item),
    }
    payload_chars = 0
    if action in {"PIN", "KEEP_FULL"}:
        content = _exact_payload(item, payloads)
        entry["content"] = content
        payload_chars = len(content)
    elif action == "KEEP_HEAD":
        content = _exact_payload(item, payloads)
        entry["head"] = content[:head_chars]
        payload_chars = len(entry["head"])
    return entry, payload_chars


def _rehydration_entry(
    item: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any] | None:
    if decision["rehydration"]["status"] != "AVAILABLE":
        return None
    return {
        "item_id": item["item_id"],
        **copy.deepcopy(decision["rehydration"]),
    }


def build_child_handoff(
    route_receipt: Mapping[str, Any],
    raw_context_state: Mapping[str, Any],
    payloads: Mapping[str, str],
    child_contract: Mapping[str, Any],
    context_provider: routing_core.ReflexProvider | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(payloads, Mapping):
        raise ValueError("payloads must be an object")

    route = normalize_route_receipt(route_receipt)
    contract = normalize_child_contract(child_contract, route)
    state = context_core.normalize_state(raw_context_state)
    _, parent_receipt = context_core.materialize_context_view(
        raw_context_state, payloads, context_provider
    )
    decisions_by_id = {
        entry["item_id"]: entry for entry in parent_receipt["actions"]
    }
    provider_meta = copy.deepcopy(parent_receipt["provider"])

    items_by_id = {item["item_id"]: item for item in state["items"]}
    required_ids = _required_ids(contract)
    unknown = [item_id for item_id in required_ids if item_id not in items_by_id]
    if unknown:
        raise ValueError(f"child contract references unknown context IDs: {unknown}")

    selected_ids: list[str] = []
    reasons_by_id: dict[str, list[str]] = {}

    # Policy-protected state always crosses a child handoff.
    for item in state["items"]:
        decision = decisions_by_id[item["item_id"]]
        reasons = _selection_reasons(item, decision, contract)
        if "POLICY_PROTECTED" in reasons:
            selected_ids.append(item["item_id"])
            reasons_by_id[item["item_id"]] = reasons

    # Explicit role requirements cannot be silently dropped by optional budgets.
    for item_id in required_ids:
        item = items_by_id[item_id]
        reasons = _selection_reasons(item, decisions_by_id[item_id], contract)
        if item_id not in selected_ids:
            selected_ids.append(item_id)
        reasons_by_id[item_id] = list(
            dict.fromkeys(reasons_by_id.get(item_id, []) + reasons)
        )

    max_optional_items = contract["budget"]["max_optional_items"]
    max_optional_payload_chars = contract["budget"]["max_optional_payload_chars"]
    optional_items_used = 0
    optional_payload_chars_used = 0
    optional_ids: set[str] = set()

    # Optional role context is newest-first and strictly budgeted.
    candidates = sorted(
        state["items"],
        key=lambda item: (
            item["recency"]["turn_distance"],
            item["item_id"],
        ),
    )
    for item in candidates:
        item_id = item["item_id"]
        if item_id in selected_ids:
            continue
        decision = decisions_by_id[item_id]
        if not _optional_role_candidate(item, decision, contract):
            continue
        if optional_items_used >= max_optional_items:
            break
        reasons = _selection_reasons(item, decision, contract)
        role_reason = {
            "SCOUT": "ROLE_SEARCH_EVIDENCE",
            "WORKER": "ROLE_OWNED_PATH_CONTEXT",
            "VERIFIER": "ROLE_VERIFICATION_CONTEXT",
        }.get(contract["role"])
        if role_reason:
            reasons.append(role_reason)
        selected_ids.append(item_id)
        optional_ids.add(item_id)
        reasons_by_id[item_id] = list(dict.fromkeys(reasons))
        optional_items_used += 1

    bundle_items = []
    rehydration_index = []
    output_payload_chars = 0
    optional_payload_emitted = 0
    for item in state["items"]:
        item_id = item["item_id"]
        if item_id not in selected_ids:
            continue
        decision = decisions_by_id[item_id]
        reasons = reasons_by_id[item_id]
        entry, payload_chars = _materialize_child_item(
            item,
            decision,
            contract,
            reasons,
            payloads,
            state["view"]["head_chars"],
            optional=item_id in optional_ids,
        )
        if (
            item_id in optional_ids
            and optional_payload_emitted + payload_chars
            > max_optional_payload_chars
        ):
            entry.pop("content", None)
            entry.pop("head", None)
            entry["action"] = "KEEP_REF"
            payload_chars = 0
        bundle_items.append(entry)
        output_payload_chars += payload_chars
        if item_id in optional_ids:
            optional_payload_emitted += payload_chars
        if entry["action"] in {"KEEP_REF", "KEEP_HEAD"}:
            rh = _rehydration_entry(item, decision)
            if rh is not None:
                rehydration_index.append(rh)

    route_sha = _hash_json(route)
    parent_receipt_sha = _hash_json(parent_receipt)
    bundle = {
        "schema_version": CHILD_BUNDLE_VERSION,
        "authority": "DERIVED_VIEW",
        "handoff_policy_version": HANDOFF_POLICY_VERSION,
        "child_id": contract["child_id"],
        "role": contract["role"],
        "route": {
            "coordination": route["selected"]["coordination"],
            "compute": route["selected"]["compute"],
            "role": route["selected"]["role"],
            "model_provider_constraint": route["selected"].get(
                "model_provider_constraint"
            ),
        },
        "task": {
            "objective": contract["objective"],
            "owned_paths": copy.deepcopy(contract["owned_paths"]),
            "verification_obligation": contract["verification_obligation"],
            "output_contract": contract["output_contract"],
        },
        "items": bundle_items,
        "rehydration_index": rehydration_index,
        "binding": {
            "route_receipt_sha256": route_sha,
            "parent_context_receipt_sha256": parent_receipt_sha,
            "parent_context_view_sha256": parent_receipt["context_view_sha256"],
        },
        "budget": {
            "max_optional_items": max_optional_items,
            "max_optional_payload_chars": max_optional_payload_chars,
            "optional_items_used": optional_items_used,
            "optional_payload_chars_used": optional_payload_emitted,
        },
    }
    bundle_sha = _hash_json(bundle)
    selected_set = set(selected_ids)
    state_ids = [item["item_id"] for item in state["items"]]
    required_set = set(required_ids)
    selected_set_for_coverage = {entry["item_id"] for entry in bundle_items}
    coverage = (
        1.0
        if not required_set
        else len(required_set & selected_set_for_coverage) / len(required_set)
    )
    receipt = {
        "schema_version": CHILD_RECEIPT_VERSION,
        "authority": "DERIVED_VIEW",
        "handoff_policy_version": HANDOFF_POLICY_VERSION,
        "child_id": contract["child_id"],
        "role": contract["role"],
        "route_receipt_sha256": route_sha,
        "parent_context_receipt_sha256": parent_receipt_sha,
        "parent_context_view_sha256": parent_receipt["context_view_sha256"],
        "bundle_sha256": bundle_sha,
        "required_item_ids": required_ids,
        "selected_item_ids": [x for x in state_ids if x in selected_set],
        "omitted_item_ids": [x for x in state_ids if x not in selected_set],
        "required_coverage": coverage,
        "input": copy.deepcopy(parent_receipt["input"]),
        "output": {
            "items": len(bundle_items),
            "characters_serialized": len(_canon(bundle)),
            "payload_characters": output_payload_chars,
        },
        "provider": copy.deepcopy(provider_meta),
        "canonical_source_mutated": False,
        "rehydration_available": all(
            entry.get("status") == "AVAILABLE" for entry in rehydration_index
        ),
    }
    bound_route = bind_route_context(route, receipt)
    return bundle, receipt, bound_route, parent_receipt


def bind_route_context(
    route_receipt: Mapping[str, Any],
    child_context_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    route = normalize_route_receipt(route_receipt)
    receipt = _obj(child_context_receipt, "child context receipt")
    if receipt.get("schema_version") != CHILD_RECEIPT_VERSION:
        raise ValueError("unsupported child context receipt schema")
    route_sha = _hash_json(route)
    if receipt.get("route_receipt_sha256") != route_sha:
        raise ValueError("child context receipt is not bound to this route")
    if receipt.get("role") != route["selected"]["role"]:
        raise ValueError("child context receipt role does not match route")
    bound = copy.deepcopy(route)
    bound["context_binding"] = {
        "status": "BOUND",
        "child_id": receipt["child_id"],
        "role": receipt["role"],
        "context_receipt_schema_version": CHILD_RECEIPT_VERSION,
        "context_receipt_sha256": _hash_json(receipt),
        "context_bundle_sha256": receipt["bundle_sha256"],
        "parent_context_receipt_sha256": receipt[
            "parent_context_receipt_sha256"
        ],
    }
    return bound


def normalize_child_result(
    raw: Mapping[str, Any], bundle: Mapping[str, Any]
) -> dict[str, Any]:
    raw = _obj(raw, "child result")
    if raw.get("schema_version") != CHILD_RESULT_VERSION:
        raise ValueError("unsupported child result schema")
    child_id = str(raw.get("child_id", "")).strip()
    role = str(raw.get("role", "")).upper()
    status = str(raw.get("status", "")).upper()
    if child_id != bundle.get("child_id") or role != bundle.get("role"):
        raise ValueError("child result identity does not match bundle")
    if status not in {"COMPLETE", "PASS", "FAIL", "UNVERIFIED", "ESCALATE"}:
        raise ValueError("unsupported child result status")
    requests_raw = raw.get("rehydration_requests", [])
    if not isinstance(requests_raw, list):
        raise ValueError("rehydration_requests must be an array")
    requests = []
    seen = set()
    for entry in requests_raw:
        entry = _obj(entry, "rehydration request")
        item_id = str(entry.get("item_id", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if not item_id or not reason:
            raise ValueError("rehydration request requires item_id and reason")
        if item_id in seen:
            continue
        seen.add(item_id)
        requests.append({"item_id": item_id, "reason": reason})
    return {
        "schema_version": CHILD_RESULT_VERSION,
        "child_id": child_id,
        "role": role,
        "status": status,
        "rehydration_requests": requests,
    }


def plan_child_rehydration(
    child_result: Mapping[str, Any], bundle: Mapping[str, Any]
) -> dict[str, Any]:
    bundle = copy.deepcopy(dict(_obj(bundle, "child context bundle")))
    if bundle.get("schema_version") != CHILD_BUNDLE_VERSION:
        raise ValueError("unsupported child context bundle schema")
    result = normalize_child_result(child_result, bundle)
    exposed = {
        entry["item_id"]: entry
        for entry in bundle.get("rehydration_index", [])
        if isinstance(entry, Mapping) and isinstance(entry.get("item_id"), str)
    }
    requests = []
    for request in result["rehydration_requests"]:
        item_id = request["item_id"]
        contract = exposed.get(item_id)
        if contract is None:
            status = "REJECTED_NOT_EXPOSED"
            copied_contract = None
        elif contract.get("status") != "AVAILABLE":
            status = "REJECTED_UNAVAILABLE"
            copied_contract = copy.deepcopy(dict(contract))
        elif contract.get("may_repeat_external_effect") is not False:
            status = "REJECTED_UNAVAILABLE"
            copied_contract = copy.deepcopy(dict(contract))
        elif contract.get("authority_recheck_required"):
            status = "PENDING_AUTHORITY_RECHECK"
            copied_contract = copy.deepcopy(dict(contract))
        else:
            status = "READY"
            copied_contract = copy.deepcopy(dict(contract))
        requests.append(
            {
                "item_id": item_id,
                "reason": request["reason"],
                "status": status,
                "contract": copied_contract,
            }
        )
    return {
        "schema_version": REHYDRATION_PLAN_VERSION,
        "authority": "REQUEST_ONLY",
        "child_id": result["child_id"],
        "role": result["role"],
        "bundle_sha256": _hash_json(bundle),
        "requests": requests,
        "canonical_source_mutated": False,
    }


def resolve_child_rehydration(
    plan: Mapping[str, Any],
    raw_context_state: Mapping[str, Any],
    rehydrator: context_core.Rehydrator,
    *,
    authority_recheck: bool = False,
) -> dict[str, Any]:
    plan = copy.deepcopy(dict(_obj(plan, "rehydration plan")))
    if plan.get("schema_version") != REHYDRATION_PLAN_VERSION:
        raise ValueError("unsupported rehydration plan schema")
    state = context_core.normalize_state(raw_context_state)
    items = {item["item_id"]: item for item in state["items"]}
    output = []
    for request in plan.get("requests", []):
        request = _obj(request, "rehydration plan request")
        item_id = request["item_id"]
        status = request["status"]
        if status in {"REJECTED_NOT_EXPOSED", "REJECTED_UNAVAILABLE"}:
            output.append({"item_id": item_id, "status": status})
            continue
        if status == "PENDING_AUTHORITY_RECHECK" and not authority_recheck:
            output.append(
                {"item_id": item_id, "status": "PENDING_AUTHORITY_RECHECK"}
            )
            continue
        if item_id not in items:
            output.append({"item_id": item_id, "status": "REJECTED_UNAVAILABLE"})
            continue
        content = context_core.rehydrate_item(items[item_id], rehydrator)
        output.append(
            {
                "item_id": item_id,
                "status": "REHYDRATED",
                "content": content,
                "content_sha256": _hash_text(content),
            }
        )
    return {
        "schema_version": REHYDRATION_RESULT_VERSION,
        "authority": "DERIVED_VIEW",
        "child_id": plan["child_id"],
        "role": plan["role"],
        "items": output,
        "canonical_source_mutated": False,
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def _write_or_print(value: Mapping[str, Any], output: Path | None) -> None:
    rendered = json.dumps(
        value, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--route", type=Path, required=True)
    build.add_argument("--state", type=Path, required=True)
    build.add_argument("--payloads", type=Path, required=True)
    build.add_argument("--contract", type=Path, required=True)
    build.add_argument(
        "--context-reflex-provider",
        choices=("none", "jev"),
        default="none",
    )
    build.add_argument("--output", type=Path)

    plan = sub.add_parser("plan-rehydration")
    plan.add_argument("--bundle", type=Path, required=True)
    plan.add_argument("--result", type=Path, required=True)
    plan.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "build":
        provider: routing_core.ReflexProvider | None = None
        if args.context_reflex_provider == "jev":
            import margos_reflex_jev

            provider = margos_reflex_jev.JevReflexProvider()
        bundle, receipt, bound_route, parent_receipt = build_child_handoff(
            _read(args.route),
            _read(args.state),
            _read(args.payloads),
            _read(args.contract),
            provider,
        )
        _write_or_print(
            {
                "bundle": bundle,
                "child_context_receipt": receipt,
                "bound_route_receipt": bound_route,
                "parent_context_receipt": parent_receipt,
            },
            args.output,
        )
        return 0

    rehydration_plan = plan_child_rehydration(
        _read(args.result), _read(args.bundle)
    )
    _write_or_print(rehydration_plan, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
