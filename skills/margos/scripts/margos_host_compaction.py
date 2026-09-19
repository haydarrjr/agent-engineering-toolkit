#!/usr/bin/env python3
"""Host-neutral proposal contract for optional MARGOS root-context compaction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads(
    (ROOT / "contracts/host-compaction-policy-v1.json").read_text(encoding="utf-8")
)
POLICY_VERSION = POLICY["version"]
REQUEST_VERSION = "margos-host-compaction-request/v1"
RESULT_VERSION = "margos-host-compaction-result/v1"


def _obj(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def normalize_request(raw: Mapping[str, Any]) -> dict[str, Any]:
    raw = _obj(raw, "host compaction request")
    if raw.get("schema_version") != REQUEST_VERSION:
        raise ValueError("unsupported host compaction request schema")
    host = _obj(raw.get("host"), "host")
    context = _obj(raw.get("context"), "context")
    host_id = str(host.get("host_id", "")).strip()
    if not host_id:
        raise ValueError("host_id is required")
    for key in ("root_compaction_hook_proven", "native_compaction_proven"):
        if not isinstance(host.get(key), bool):
            raise ValueError(f"{key} must be boolean")
    if not isinstance(raw.get("experimental_adapter_enabled"), bool):
        raise ValueError("experimental_adapter_enabled must be boolean")
    if context.get("authority") != "DERIVED_VIEW":
        raise ValueError("host compaction accepts DERIVED_VIEW authority only")
    if context.get("canonical_source_mutated") is not False:
        raise ValueError("canonical source must remain unchanged")
    digest = str(context.get("context_view_sha256", ""))
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("context_view_sha256 must be a lowercase SHA-256 digest")
    input_chars = int(context.get("input_characters", 0))
    output_chars = int(context.get("output_characters", 0))
    if input_chars < 0 or output_chars < 0:
        raise ValueError("context character counts must be non-negative")
    return {
        "schema_version": REQUEST_VERSION,
        "host": {
            "host_id": host_id,
            "root_compaction_hook_proven": host["root_compaction_hook_proven"],
            "native_compaction_proven": host["native_compaction_proven"],
        },
        "experimental_adapter_enabled": raw["experimental_adapter_enabled"],
        "context": {
            "authority": "DERIVED_VIEW",
            "canonical_source_mutated": False,
            "context_view_sha256": digest,
            "input_characters": input_chars,
            "output_characters": output_chars,
        },
    }


def decide_host_compaction(raw: Mapping[str, Any]) -> dict[str, Any]:
    request = normalize_request(raw)
    host = request["host"]
    context = request["context"]
    before = context["input_characters"]
    after = context["output_characters"]
    reduction = 0.0 if before == 0 else (before - after) / before
    minimum = float(POLICY["minimum_serialized_reduction_ratio"])

    if not request["experimental_adapter_enabled"]:
        action = "NO_AET_INTERCEPTION"
        reason = "Experimental host compaction adapter is not explicitly enabled."
        execution = "NOT_APPLICABLE"
        view_sha = None
    elif not host["root_compaction_hook_proven"]:
        if host["native_compaction_proven"]:
            action = "DEFER_HOST_NATIVE"
            reason = "No proven AET root hook; defer to the host-native compaction path."
        else:
            action = "NO_AET_INTERCEPTION"
            reason = "No proven root hook or native compaction capability."
        execution = "NOT_APPLICABLE"
        view_sha = None
    elif reduction < minimum:
        if host["native_compaction_proven"]:
            action = "DEFER_HOST_NATIVE"
            reason = "Derived-view reduction is below the experimental threshold."
        else:
            action = "NO_AET_INTERCEPTION"
            reason = "Derived-view reduction is below the experimental threshold."
        execution = "NOT_APPLICABLE"
        view_sha = None
    else:
        action = "OFFER_DERIVED_VIEW"
        reason = "Explicit opt-in and proven root hook permit a derived-view proposal."
        execution = "PENDING"
        view_sha = context["context_view_sha256"]

    return {
        "schema_version": RESULT_VERSION,
        "decision_authority": "PROPOSED",
        "policy_version": POLICY_VERSION,
        "action": action,
        "reason": reason,
        "reduction_ratio": round(reduction, 6),
        "context_view_sha256": view_sha,
        "host_execution": {"status": execution},
        "canonical_source_mutated": False,
    }


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request JSON must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = decide_host_compaction(_read(args.request))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
