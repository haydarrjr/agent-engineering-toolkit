#!/usr/bin/env python3
"""Frozen/counterfactual MARGOS context benchmark with optional live Jev research mode."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
MARGOS_SCRIPTS = ROOT / "skills/margos/scripts"
sys.path.insert(0, str(MARGOS_SCRIPTS))

import margos_context as ctx
import margos_handoff as handoff
import margos_reflex_jev as jev

FIXTURE = ROOT / "tests/fixtures/margos/context-benchmark-v1.json"
BENCHMARK_VERSION = "margos-context-benchmark-report/v1"
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bTYPESAFE_API_KEY\s*="),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b" + "gh" + r"p_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def canon(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def estimated_tokens(characters: int) -> int:
    return int(math.ceil(max(0, characters) / 4.0))


def payload_for(spec: Mapping[str, Any]) -> str:
    length = int(spec["chars"])
    fill = str(spec.get("fill") or spec["id"] or "X")
    if length <= 0:
        return ""
    repeated = (fill * ((length // len(fill)) + 1))[:length]
    return repeated


def replay_contract(spec: Mapping[str, Any], locator: str) -> dict[str, Any]:
    status = str(spec.get("replay", "REPLAYABLE")).upper()
    if status == "REPLAYABLE":
        method = str(spec.get("replay_method", "READ_FILE")).upper()
        return {"status": status, "method": method, "locator": locator}
    return {"status": status, "method": "UNAVAILABLE", "locator": None}


def build_item(spec: Mapping[str, Any], payload: str) -> dict[str, Any]:
    authority = {name: True for name in spec.get("authority", [])}
    evidence = {name: True for name in spec.get("evidence", [])}
    locator = str(spec.get("locator") or f"fixture/{spec['id']}")
    return {
        "schema_version": "margos-context-item/v1",
        "item_id": str(spec["id"]),
        "kind": str(spec.get("kind", "TOOL_RESULT")).upper(),
        "source": {
            "tool": str(spec.get("tool", "read_file")),
            "locator": locator,
            "result_status": str(spec.get("result_status", "OK")).upper(),
            "content_version": str(spec.get("content_version", "fixture-v1")),
        },
        "content_sha256": sha_text(payload),
        "size": {
            "chars": len(payload),
            "tokens_estimated": estimated_tokens(len(payload)),
        },
        "authority": authority,
        "evidence": evidence,
        "replay": replay_contract(spec, locator),
        "supersession": {
            "status": "SUPERSEDED" if spec.get("superseded_by") else "CURRENT",
            "superseded_by": spec.get("superseded_by"),
        },
        "recency": {"turn_distance": max(0, int(spec.get("turn_distance", 3)))},
    }


def build_state(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    payloads = {}
    items = []
    for spec in case["items"]:
        payload = payload_for(spec)
        payloads[str(spec["id"])] = payload
        items.append(build_item(spec, payload))
    return {
        "schema_version": "margos-context-state/v1",
        "task": {
            "task_id": str(case["id"]),
            "objective": f"Frozen context benchmark: {case['id']}",
            "verification_obligation": str(
                case["contract"].get("verification_obligation", "")
            ),
        },
        "items": items,
        "view": {"head_chars": 96},
    }, payloads


def build_route(case: Mapping[str, Any]) -> dict[str, Any]:
    role = str(case["role"])
    compute = "ECONOMY_READ" if role == "SCOUT" else "BALANCED_EXEC"
    if role == "INDEPENDENT_CRITIC":
        compute = "FRONTIER_REASONING"
    return {
        "schema_version": "margos-route-receipt/v1",
        "decision_authority": "PROPOSED",
        "state_sha256": "a" * 64,
        "policy_version": "margos-policy/v1",
        "question_set_version": "margos-questions/v1",
        "question_set_sha256": "b" * 64,
        "threshold_policy_version": "margos-thresholds/v1",
        "provider": {"kind": "benchmark", "status": "AVAILABLE"},
        "admissible": {},
        "blocked": [],
        "policy_rules_applied": [],
        "reflex": {},
        "selected": {
            "disposition": "PROCEED",
            "coordination": str(case["coordination"]),
            "compute": compute,
            "role": role,
            "source": "DETERMINISTIC_POLICY",
            "abstained": False,
            "model_provider_constraint": None,
        },
        "host_execution": {"status": "PENDING"},
    }


def build_contract(case: Mapping[str, Any]) -> dict[str, Any]:
    source = case["contract"]
    return {
        "schema_version": "margos-child-contract/v1",
        "child_id": f"benchmark-{case['id']}",
        "role": str(case["role"]),
        "objective": f"Close frozen obligation {case['id']}.",
        "owned_paths": list(source.get("owned_paths", [])),
        "required_context_ids": list(source.get("required_context_ids", [])),
        "required_full_ids": list(source.get("required_full_ids", [])),
        "implementation_result_ids": list(
            source.get("implementation_result_ids", [])
        ),
        "verification_evidence_ids": list(
            source.get("verification_evidence_ids", [])
        ),
        "fresh_evidence_ids": list(source.get("fresh_evidence_ids", [])),
        "verification_obligation": str(
            source.get("verification_obligation", "")
        ),
        "output_contract": str(source["output_contract"]),
        "budget": {
            "max_optional_items": int(case["budget"]["max_optional_items"]),
            "max_optional_payload_chars": int(
                case["budget"]["max_optional_payload_chars"]
            ),
        },
    }


def fixture_provider(case: Mapping[str, Any]) -> ctx.FixtureContextReflexProvider:
    answers = {}
    for spec in case["items"]:
        gold = spec.get("gold", {})
        answers[str(spec["id"])] = {
            "keep_awareness": {
                "probability": 0.90 if gold.get("keep_awareness") else 0.05
            },
            "keep_full": {
                "probability": 0.90 if gold.get("keep_full") else 0.05
            },
            "replay_needed": {
                "probability": 0.85 if gold.get("replay_needed") else 0.05
            },
        }
    return ctx.FixtureContextReflexProvider(answers, provider_id="fixture-context-eval")


def provider_for_mode(mode: str, case: Mapping[str, Any]):
    if mode == "policy":
        return None
    if mode == "fixture":
        return fixture_provider(case)
    if mode == "jev":
        return jev.JevReflexProvider()
    raise ValueError(f"unsupported benchmark mode: {mode}")


def full_baseline_serialized(
    case: Mapping[str, Any],
    state: Mapping[str, Any],
    payloads: Mapping[str, str],
    contract: Mapping[str, Any],
) -> int:
    value = {
        "schema_version": "margos-full-context-baseline/v1",
        "case_id": case["id"],
        "role": case["role"],
        "task": contract,
        "items": [
            {
                "item_id": item["item_id"],
                "kind": item["kind"],
                "source": item["source"],
                "content_sha256": item["content_sha256"],
                "content": payloads[item["item_id"]],
            }
            for item in state["items"]
        ],
    }
    return len(canon(value))


class FixtureResolver:
    def __init__(self, state: Mapping[str, Any], payloads: Mapping[str, str]):
        self.by_locator = {
            item["replay"]["locator"]: payloads[item["item_id"]]
            for item in state["items"]
            if item["replay"]["locator"]
        }

    def recover(self, contract: Mapping[str, Any]) -> str:
        locator = contract.get("locator")
        if locator not in self.by_locator:
            raise ValueError("fixture rehydration locator missing")
        return self.by_locator[locator]


def evaluate_oracle(
    case: Mapping[str, Any],
    state: Mapping[str, Any],
    payloads: Mapping[str, str],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    oracle = case["oracle"]
    required_awareness = set(oracle.get("required_awareness_ids", []))
    required_exact = set(oracle.get("required_exact_ids", []))
    forbidden = set(oracle.get("forbidden_ids", []))
    entries = {entry["item_id"]: entry for entry in bundle["items"]}
    selected = set(entries)

    missing_awareness = sorted(required_awareness - selected)
    exact_satisfied = {
        item_id
        for item_id in required_exact
        if item_id in entries
        and entries[item_id].get("content") == payloads[item_id]
    }
    needs_rehydration = sorted(
        item_id
        for item_id in (required_exact - exact_satisfied)
        if item_id in selected
    )

    rehydration_count = 0
    rehydration_chars = 0
    rehydration_latency_ms = 0.0
    rehydration_failures = []
    if needs_rehydration:
        result = {
            "schema_version": "margos-child-result/v1",
            "child_id": bundle["child_id"],
            "role": bundle["role"],
            "status": "ESCALATE",
            "rehydration_requests": [
                {
                    "item_id": item_id,
                    "reason": "Frozen oracle requires exact evidence.",
                }
                for item_id in needs_rehydration
            ],
        }
        plan = handoff.plan_child_rehydration(result, bundle)
        start = time.perf_counter()
        resolved = handoff.resolve_child_rehydration(
            plan,
            state,
            FixtureResolver(state, payloads),
            authority_recheck=True,
        )
        rehydration_latency_ms = (time.perf_counter() - start) * 1000.0
        for entry in resolved["items"]:
            if (
                entry["status"] == "REHYDRATED"
                and entry.get("content") == payloads.get(entry["item_id"])
            ):
                exact_satisfied.add(entry["item_id"])
                rehydration_count += 1
                rehydration_chars += len(entry["content"])
            else:
                rehydration_failures.append(
                    {"item_id": entry["item_id"], "status": entry["status"]}
                )

    missing_exact = sorted(required_exact - exact_satisfied)
    forbidden_retained = sorted(forbidden & selected)
    verified_success = not missing_awareness and not missing_exact

    if not verified_success:
        omission_class = "HARMFUL"
    elif rehydration_count:
        omission_class = "COSTLY"
    else:
        omission_class = "HARMLESS"

    return {
        "verified_success": verified_success,
        "omission_class": omission_class,
        "missing_awareness_ids": missing_awareness,
        "missing_exact_ids": missing_exact,
        "forbidden_retained_ids": forbidden_retained,
        "rehydration_count": rehydration_count,
        "rehydration_characters": rehydration_chars,
        "rehydration_latency_ms": round(rehydration_latency_ms, 3),
        "rehydration_failures": rehydration_failures,
    }


def safety_metrics(
    state: Mapping[str, Any],
    parent_receipt: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> dict[str, int]:
    state = ctx.normalize_state(state)
    selected = {entry["item_id"] for entry in bundle["items"]}
    decisions = {entry["item_id"]: entry for entry in parent_receipt["actions"]}
    protected_loss = 0
    non_replayable_omission = 0
    external_effect_loss = 0
    contradiction_loss = 0
    active_evidence_loss = 0
    for item in state["items"]:
        item_id = item["item_id"]
        decision = decisions[item_id]
        if (
            decision["protection_class"] in {"PINNED", "NON_REPLAYABLE"}
            and item_id not in selected
        ):
            protected_loss += 1
        if item["replay"]["status"] != "REPLAYABLE" and item_id not in selected:
            non_replayable_omission += 1
        if (
            item["authority"]["contains_unresolved_external_effect"]
            and item_id not in selected
        ):
            external_effect_loss += 1
        if item["evidence"]["contradiction_open"] and item_id not in selected:
            contradiction_loss += 1
        if (
            any(
                item["evidence"][key]
                for key in (
                    "proof_bound",
                    "freshness_bound",
                    "supports_claimed_pass",
                )
            )
            and item_id not in selected
        ):
            active_evidence_loss += 1
    return {
        "protected_loss_violations": protected_loss,
        "non_replayable_omission_violations": non_replayable_omission,
        "external_effect_loss_violations": external_effect_loss,
        "contradiction_loss_violations": contradiction_loss,
        "active_evidence_loss_violations": active_evidence_loss,
    }


def calibration_points(
    case: Mapping[str, Any],
    parent_receipt: Mapping[str, Any],
) -> list[tuple[float, int]]:
    gold_by_id = {str(spec["id"]): spec.get("gold", {}) for spec in case["items"]}
    points = []
    for decision in parent_receipt["actions"]:
        reflex = decision.get("reflex", {})
        if reflex.get("status") != "AVAILABLE":
            continue
        gold = gold_by_id.get(decision["item_id"], {})
        for question in ("keep_awareness", "keep_full", "replay_needed"):
            probability = reflex.get(question)
            if probability is None or question not in gold:
                continue
            points.append((float(probability), 1 if gold[question] else 0))
    return points


def brier(points: list[tuple[float, int]]) -> float | None:
    if not points:
        return None
    return sum((p - y) ** 2 for p, y in points) / len(points)


def ece(points: list[tuple[float, int]], bins: int = 5) -> float | None:
    if not points:
        return None
    total = len(points)
    error = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        bucket = [
            (p, y)
            for p, y in points
            if (low <= p < high) or (index == bins - 1 and p == 1.0)
        ]
        if not bucket:
            continue
        confidence = sum(p for p, _ in bucket) / len(bucket)
        accuracy = sum(y for _, y in bucket) / len(bucket)
        error += (len(bucket) / total) * abs(confidence - accuracy)
    return error


def evaluate_case(case: Mapping[str, Any], mode: str) -> dict[str, Any]:
    state, payloads = build_state(case)
    route = build_route(case)
    contract = build_contract(case)
    provider = provider_for_mode(mode, case)

    full_chars = full_baseline_serialized(case, state, payloads, contract)
    start = time.perf_counter()
    bundle, receipt, _, parent_receipt = handoff.build_child_handoff(
        route, state, payloads, contract, provider
    )
    compaction_latency_ms = (time.perf_counter() - start) * 1000.0
    oracle = evaluate_oracle(case, state, payloads, bundle)
    safety = safety_metrics(state, parent_receipt, bundle)
    candidate_chars = int(receipt["output"]["characters_serialized"])
    reduction = (
        0.0 if full_chars == 0 else max(-1.0, (full_chars - candidate_chars) / full_chars)
    )

    required_exact = set(case["oracle"].get("required_exact_ids", []))
    full_selected = {
        entry["item_id"]
        for entry in bundle["items"]
        if entry["action"] in {"PIN", "KEEP_FULL"}
    }
    protected = {
        entry["item_id"]
        for entry in parent_receipt["actions"]
        if entry["protection_class"] in {"PINNED", "NON_REPLAYABLE"}
    }
    false_keep_full = len(full_selected - required_exact - protected)

    provider_meta = parent_receipt["provider"]
    usage = provider_meta.get("usage", {}) if isinstance(provider_meta, Mapping) else {}
    return {
        "case_id": case["id"],
        "role": case["role"],
        "coordination": case["coordination"],
        "mode": mode,
        "full_context": {
            "characters_serialized": full_chars,
            "tokens_estimated": estimated_tokens(full_chars),
            "verified_success": True,
        },
        "candidate": {
            "characters_serialized": candidate_chars,
            "tokens_estimated": estimated_tokens(candidate_chars),
            "payload_characters": receipt["output"]["payload_characters"],
            "reduction_ratio": round(reduction, 6),
            "compaction_latency_ms": round(compaction_latency_ms, 3),
            "provider_request_count": int(provider_meta.get("request_count", 0)),
            "provider_network_request_count": int(
                provider_meta.get("network_request_count", 0)
            ),
            "provider_input_tokens": int(usage.get("input_tokens", 0) or 0),
            "provider_output_tokens": int(usage.get("output_tokens", 0) or 0),
            "provider_status": provider_meta.get("status", "UNKNOWN"),
            "verified_success": oracle["verified_success"],
        },
        "oracle": oracle,
        "safety": safety,
        "false_keep_full_count": false_keep_full,
        "calibration_points": calibration_points(case, parent_receipt),
        "required_coverage": receipt["required_coverage"],
        "canonical_source_mutated": receipt["canonical_source_mutated"],
    }


def aggregate(results: list[Mapping[str, Any]]) -> dict[str, Any]:
    full_chars = sum(x["full_context"]["characters_serialized"] for x in results)
    candidate_chars = sum(x["candidate"]["characters_serialized"] for x in results)
    required_events = sum(
        len(x["oracle"]["missing_awareness_ids"])
        + len(x["oracle"]["missing_exact_ids"])
        + (
            1
            if x["oracle"]["verified_success"]
            else 0
        )
        for x in results
    )
    harmful = sum(1 for x in results if x["oracle"]["omission_class"] == "HARMFUL")
    costly = sum(1 for x in results if x["oracle"]["omission_class"] == "COSTLY")
    points = [
        point
        for result in results
        for point in result.get("calibration_points", [])
    ]
    verified = sum(1 for x in results if x["candidate"]["verified_success"])
    forbidden = sum(len(x["oracle"]["forbidden_retained_ids"]) for x in results)
    safety_keys = (
        "protected_loss_violations",
        "non_replayable_omission_violations",
        "external_effect_loss_violations",
        "contradiction_loss_violations",
        "active_evidence_loss_violations",
    )
    safety = {
        key: sum(int(x["safety"][key]) for x in results) for key in safety_keys
    }
    return {
        "cases": len(results),
        "verified_success_rate": verified / len(results) if results else 0.0,
        "full_verified_success_rate": 1.0 if results else 0.0,
        "verified_success_delta": (
            verified / len(results) - 1.0 if results else -1.0
        ),
        "characters_before": full_chars,
        "characters_after": candidate_chars,
        "tokens_before_estimated": estimated_tokens(full_chars),
        "tokens_after_estimated": estimated_tokens(candidate_chars),
        "serialized_reduction_ratio": (
            (full_chars - candidate_chars) / full_chars if full_chars else 0.0
        ),
        "harmful_omission_cases": harmful,
        "harmful_omission_rate": harmful / len(results) if results else 0.0,
        "costly_omission_cases": costly,
        "rehydration_count": sum(
            int(x["oracle"]["rehydration_count"]) for x in results
        ),
        "rehydration_characters": sum(
            int(x["oracle"]["rehydration_characters"]) for x in results
        ),
        "rehydration_latency_ms": round(
            sum(float(x["oracle"]["rehydration_latency_ms"]) for x in results), 3
        ),
        "forbidden_context_violations": forbidden,
        "false_keep_full_count": sum(int(x["false_keep_full_count"]) for x in results),
        "provider_request_count": sum(
            int(x["candidate"]["provider_request_count"]) for x in results
        ),
        "provider_network_request_count": sum(
            int(x["candidate"]["provider_network_request_count"]) for x in results
        ),
        "provider_input_tokens": sum(
            int(x["candidate"]["provider_input_tokens"]) for x in results
        ),
        "provider_output_tokens": sum(
            int(x["candidate"]["provider_output_tokens"]) for x in results
        ),
        "compaction_latency_ms": round(
            sum(float(x["candidate"]["compaction_latency_ms"]) for x in results), 3
        ),
        **safety,
        "brier_score": None if brier(points) is None else round(brier(points), 6),
        "ece_5_bin": None if ece(points) is None else round(ece(points), 6),
        "calibration_observations": len(points),
        "required_event_proxy": required_events,
    }


def scan_fixture_for_secrets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def strict_gate(
    aggregate_result: Mapping[str, Any],
    fixture: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    gates = fixture["strict_gates"]
    failures = []
    checks = (
        (
            aggregate_result["cases"] >= int(gates["minimum_cases"]),
            "minimum_cases",
        ),
        (
            aggregate_result["verified_success_rate"]
            >= float(gates["minimum_candidate_verified_success_rate"]),
            "candidate_verified_success_rate",
        ),
        (
            aggregate_result["serialized_reduction_ratio"]
            >= float(gates["minimum_aggregate_serialized_reduction_ratio"]),
            "serialized_reduction_ratio",
        ),
        (
            aggregate_result["harmful_omission_rate"]
            <= float(gates["maximum_harmful_omission_rate"]),
            "harmful_omission_rate",
        ),
        (
            aggregate_result["protected_loss_violations"]
            <= int(gates["maximum_protected_loss_violations"]),
            "protected_loss_violations",
        ),
        (
            aggregate_result["non_replayable_omission_violations"]
            <= int(gates["maximum_non_replayable_omission_violations"]),
            "non_replayable_omission_violations",
        ),
        (
            aggregate_result["external_effect_loss_violations"]
            <= int(gates["maximum_external_effect_loss_violations"]),
            "external_effect_loss_violations",
        ),
        (
            aggregate_result["contradiction_loss_violations"]
            <= int(gates["maximum_contradiction_loss_violations"]),
            "contradiction_loss_violations",
        ),
        (
            aggregate_result["forbidden_context_violations"]
            <= int(gates["maximum_forbidden_context_violations"]),
            "forbidden_context_violations",
        ),
    )
    for ok, name in checks:
        if not ok:
            failures.append(name)
    return not failures, failures


def evaluate_mode(fixture: Mapping[str, Any], mode: str) -> dict[str, Any]:
    results = [evaluate_case(case, mode) for case in fixture["cases"]]
    return {"mode": mode, "cases": results, "aggregate": aggregate(results)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("policy", "fixture", "jev"), default="fixture")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture.get("version") != "margos-context-benchmark/v1":
        raise ValueError("unsupported context benchmark fixture version")

    secret_hits = scan_fixture_for_secrets(args.fixture)
    policy = evaluate_mode(fixture, "policy")
    candidate = policy if args.mode == "policy" else evaluate_mode(fixture, args.mode)
    gate_ok, gate_failures = strict_gate(candidate["aggregate"], fixture)
    if secret_hits:
        gate_ok = False
        gate_failures.append("fixture_secret_scan")

    live_status = "NOT_REQUESTED"
    if args.mode == "jev":
        if not os.environ.get("TYPESAFE_API_KEY"):
            live_status = "NOT_CONFIGURED"
        else:
            statuses = {
                case["candidate"]["provider_status"] for case in candidate["cases"]
            }
            live_status = "AVAILABLE" if statuses == {"AVAILABLE"} else ",".join(sorted(statuses))

    report = {
        "schema_version": BENCHMARK_VERSION,
        "fixture_version": fixture["version"],
        "mode": args.mode,
        "estimator": fixture["estimator"],
        "baselines": {
            "A_full_context": {
                "verified_success_rate": candidate["aggregate"]["full_verified_success_rate"],
                "characters": candidate["aggregate"]["characters_before"],
            },
            "B_deterministic_policy": policy["aggregate"],
            "C_host_native_compaction": {
                "status": "NOT_OBSERVABLE_IN_PORTABLE_CI"
            },
        },
        "candidate": candidate,
        "live_jev_research": {
            "status": live_status,
            "calibration_claim": False,
            "note": (
                "Live Jev is explicit opt-in and never required by CI. "
                "Fixture probabilities are evaluator tests, not live calibration evidence."
            ),
        },
        "privacy": {
            "fixture_secret_scan": "PASS" if not secret_hits else "FAIL",
            "secret_pattern_hits": secret_hits,
            "remote_full_payload_default": False,
        },
        "promotion_gate": {
            "status": "PASS" if gate_ok else "FAIL",
            "failures": gate_failures,
            "scope": "FROZEN_FIXTURE_ONLY",
        },
    }
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.strict and not gate_ok:
        return 1
    if args.mode == "jev" and live_status == "NOT_CONFIGURED":
        return 2 if args.strict else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
