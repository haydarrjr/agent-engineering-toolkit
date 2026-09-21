#!/usr/bin/env python3
"""Forced-arm benchmark for the Issue #24 Verification Governor."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))

import margos_reflex_jev as jev
import margos_verification as governor

FIXTURE = ROOT / "tests/fixtures/margos/verification-governor-v1.json"
ARMS = ("A_POLICY_ONLY_BASELINE", "B_JEV_SHADOW", "C_JEV_ACTIVE_COLD", "D_JEV_ACTIVE_WARM")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _candidate(candidate_id: str, rank: int, group: str, p95: float) -> dict[str, Any]:
    return {
        "schema_version": governor.CANDIDATE_VERSION,
        "candidate_id": candidate_id,
        "claim_fingerprint": hashlib.sha256(candidate_id.encode()).hexdigest(),
        "claim_summary": f"Bounded synthetic audit hypothesis: {candidate_id}.",
        "evidence_state": "UNVERIFIED",
        "evidence_kind": "HYPOTHESIS",
        "policy_priority_rank": rank,
        "mandatory_by_policy": False,
        "remote_semantic_allowed": True,
        "verifier": {
            "operation_id": f"verify-{candidate_id}",
            "kind": "synthetic-verifier",
            "host_capability_proof": "fixture-selective-dispatch-v1",
            "parallel_group": group,
            "cost": {"latency_ms_p50": p95 * 0.5, "latency_ms_p95": p95, "model_tokens": 100, "money_microunits": 10, "verification_cost_units": 1},
        },
        "discovery_provenance": {
            "provenance_kind": "SYNTHETIC",
            "source_sha256": hashlib.sha256(f"source:{candidate_id}".encode()).hexdigest(),
            "extractor_version": "fixture-extractor/v1",
            "locator": f"fixture://{candidate_id}",
        },
    }


def opportunity() -> dict[str, Any]:
    return {
        "schema_version": governor.OPPORTUNITY_VERSION,
        "opportunity_id": "verification-opportunity-holdout-001",
        "task_objective": "audit a repository and close the highest-impact unresolved claims",
        "budget": {"max_optional_candidates": 1, "max_verification_cost_units": 8, "max_wall_clock_ms": 500},
        "mandatory_candidate_ids": ["mandatory-policy-snapshot"],
        "optional_candidates": [
            _candidate("upstream-contract", 0, "g-upstream", 120),
            _candidate("deployment-drift", 1, "g-post", 180),
            _candidate("adapter-capability", 2, "g-post", 160),
        ],
        "host_selective_dispatch_proof": "fixture-selective-dispatch-v1",
        "critical_path_model_version": "critical-path/v1",
        "jev_latency_budget_ms": 50,
        "cost_model_version": "fixture-cost/v1",
        "cache_lookup_status": "MISS",
        "calibration_binding_hash": "c" * 64,
        "optimization_objective": "LATENCY_AND_COST",
    }


def baseline_plan(raw: Mapping[str, Any]) -> dict[str, Any]:
    normalized = governor.normalize_verification_opportunity(raw)
    ids = [item["candidate_id"] for item in normalized["optional_candidates"]]
    return {
        "schema_version": governor.PLAN_VERSION,
        "opportunity_id": normalized["opportunity_id"],
        "mandatory_candidate_ids": list(normalized["mandatory_candidate_ids"]),
        "selected_optional_candidate_ids": ids,
        "skipped_optional_candidate_ids": [],
        "fallback_used": True,
        "fallback_reason": "POLICY_BASELINE_ALL_OPTIONAL",
        "composer_version": governor.COMPOSER_VERSION,
        "selection_scores": {},
    }


class FixtureProvider:
    def __init__(self, probabilities: Mapping[str, float], *, warm: bool = False):
        self.probabilities = dict(probabilities)
        self.calls = 0
        self.warm = warm

    def evaluate(self, request: Mapping[str, Any], questions: tuple[dict[str, Any], ...]) -> Mapping[str, Any]:
        self.calls += 1
        answers = {candidate["candidate_id"]: {"probability": self.probabilities[candidate["candidate_id"]]} for candidate in request["candidates"]}
        return {
            "schema_version": governor.RESULT_VERSION,
            "provider": {"kind": "fixture", "status": "AVAILABLE", "calibration_status": "CALIBRATED_FOR_FROZEN_SUITE", "network_request_count": 0 if self.warm else 1, "cache_hit": self.warm},
            "question_set_sha256": governor.question_set_sha256(),
            "answers": answers,
        }


def _live_binding(fixture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": jev.CALIBRATION_BINDING_VERSION,
        "provider": "typesafe-jev",
        "model": jev.PINNED_MODEL,
        "question_set_sha256": governor.question_set_sha256(),
        "threshold_policy_sha256": governor.threshold_policy_sha256(),
        "projection_version": governor.PROJECTION_VERSION,
        "corpus_sha256": _hash(fixture),
        "evaluation_status": "PASSED",
    }


def _source_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("AET_SOURCE_SHA", "UNSET")


class FixtureDispatcher:
    def __init__(self, raw: Mapping[str, Any], gold: Mapping[str, str]):
        self.raw = governor.normalize_verification_opportunity(raw)
        self.gold = dict(gold)
        self.receipts: list[dict[str, Any]] = []

    def dispatch_selected(self, *, candidate_ids, operation_ids, plan):
        start = time.perf_counter()
        by_id = {item["candidate_id"]: item for item in self.raw["optional_candidates"]}
        latencies = []
        outcomes = {}
        for candidate_id in candidate_ids:
            if candidate_id in by_id:
                latencies.append(float(by_id[candidate_id]["verifier"]["cost"]["latency_ms_p95"]))
                outcomes[candidate_id] = self.gold.get(candidate_id, "INCONCLUSIVE")
            else:
                latencies.append(80.0)
                outcomes[candidate_id] = "VERIFIED"
        receipt = {
            "dispatched_operation_ids": list(operation_ids),
            "candidate_ids": list(candidate_ids),
            "outcomes": outcomes,
            "per_verifier_latency_ms": {candidate_id: latencies[index] for index, candidate_id in enumerate(candidate_ids)},
            "critical_path_ms": governor._critical_path([by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in by_id]) + (80.0 if "mandatory-policy-snapshot" in candidate_ids else 0.0),
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
        }
        self.receipts.append(receipt)
        return receipt


def _findings(raw: Mapping[str, Any], dispatch: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    states = {"verified-provenance-defect": "VERIFIED"}
    for candidate_id in ("upstream-contract", "deployment-drift", "adapter-capability"):
        states[candidate_id] = "UNVERIFIED"
    if dispatch:
        states.update({key: value for key, value in dispatch.get("outcomes", {}).items() if key in states})
    return governor.final_finding_order([
        {"finding_id": key, "evidence_state": value, "policy_priority_rank": 0 if key == "verified-provenance-defect" else index + 1}
        for index, (key, value) in enumerate(states.items())
    ])


def _metrics(raw: Mapping[str, Any], plan: Mapping[str, Any], receipt: Mapping[str, Any], findings: list[Mapping[str, Any]], baseline_critical_path: float, gold: Mapping[str, str]) -> dict[str, Any]:
    verified_ids = {item["finding_id"] for item in findings if item["evidence_state"] == "VERIFIED"}
    gold_verified = {"verified-provenance-defect"} | {key for key, value in gold.items() if value == "VERIFIED"}
    ranks = {item["finding_id"]: index + 1 for index, item in enumerate(findings) if item["evidence_state"] == "VERIFIED"}
    top1 = {key for key, rank in ranks.items() if rank <= 1}
    top3 = {key for key, rank in ranks.items() if rank <= 3}
    topk = {key for key, rank in ranks.items() if rank <= len(findings)}
    protected = "verified-provenance-defect" in top3
    dispatch = receipt.get("dispatch", {})
    outcomes = dispatch.get("outcomes", {}) if isinstance(dispatch, Mapping) else {}
    provider = receipt.get("provider", {})
    runtime = provider.get("runtime_receipt", {}) if isinstance(provider, Mapping) else {}
    jev_latency = float(runtime.get("latency_ms", 0.0) or 0.0)
    critical_path = float(dispatch.get("critical_path_ms", 0.0) or 0.0)
    execution_affected = bool(receipt.get("execution_affected_by_reflex", False))
    recovered_optional = {key for key in outcomes if key in gold and outcomes[key] == "VERIFIED"}
    optional_gold = {key for key, value in gold.items() if value == "VERIFIED"}
    scores = plan.get("selection_scores", {})
    brier = None
    if scores:
        brier = sum((float(scores[key]) - (1.0 if gold.get(key) == "VERIFIED" else 0.0)) ** 2 for key in scores) / len(scores)
    by_candidate = {item["candidate_id"]: item for item in raw["optional_candidates"]}
    optional_dispatched_ids = set(plan["selected_optional_candidate_ids"])
    optional_available_cost = sum(float(item["verifier"]["cost"]["verification_cost_units"]) for item in raw["optional_candidates"])
    optional_dispatched_cost = sum(float(by_candidate[key]["verifier"]["cost"]["verification_cost_units"]) for key in optional_dispatched_ids)
    return {
        "verified_finding_recall_at_1": len(gold_verified & top1) / len(gold_verified),
        "verified_finding_recall_at_3": len(gold_verified & top3) / len(gold_verified),
        "verified_finding_recall_at_k": len(gold_verified & topk) / len(gold_verified),
        "protected_retention": 1.0 if protected else 0.0,
        "hypothesis_above_verified": any(item["evidence_state"] != "VERIFIED" for item in findings[:1]),
        "mandatory_retention": 1.0 if "mandatory-policy-snapshot" in receipt.get("dispatch", {}).get("candidate_ids", []) else 0.0,
        "optional_available": len(raw["optional_candidates"]),
        "optional_selected": len(plan["selected_optional_candidate_ids"]),
        "optional_dispatched": len(plan["selected_optional_candidate_ids"]),
        "optional_skipped": len(plan["skipped_optional_candidate_ids"]),
        "provider_request_count": receipt.get("provider_request_count", 0),
        "dispatched_operation_ids": receipt.get("dispatched_operation_ids", []),
        "critical_path_ms": critical_path,
        "baseline_critical_path_ms": baseline_critical_path,
        "gross_verifier_work_saved_ms": max(0.0, baseline_critical_path - critical_path),
        "jev_overhead_ms": jev_latency,
        "end_to_end_latency_ms": critical_path + (jev_latency if execution_affected else 0.0),
        "net_wall_saved_ms": baseline_critical_path - critical_path - (jev_latency if execution_affected else 0.0),
        "optional_verified_recall": len(recovered_optional) / len(optional_gold) if optional_gold else 1.0,
        "optional_hit_rate": len(recovered_optional) / len(optional_gold) if optional_gold else 1.0,
        "false_deescalation_count": len(optional_gold - recovered_optional),
        "false_escalation_count": sum(1 for key in optional_dispatched_ids if gold.get(key) != "VERIFIED"),
        "recovered_count": sum(1 for key, value in outcomes.items() if key in gold and value == "VERIFIED"),
        "falsified_count": sum(1 for key, value in outcomes.items() if key in gold and value == "FALSIFIED"),
        "inconclusive_count": sum(1 for key, value in outcomes.items() if key in gold and value == "INCONCLUSIVE"),
        "verification_error_count": sum(1 for key, value in outcomes.items() if key in gold and value == "ERROR"),
        "optional_verification_cost_units_available": optional_available_cost,
        "optional_verification_cost_units_dispatched": optional_dispatched_cost,
        "calibration_brier": brier,
        "calibration_status": provider.get("calibration_status", "NOT_REQUESTED") if isinstance(provider, Mapping) else "NOT_REQUESTED",
        "context_reduction_ratio": 0.0,
        "rehydration_count": 0,
        "safety_violations": {"protected_loss": 0 if protected else 1, "mandatory_loss": 0 if "mandatory-policy-snapshot" in receipt.get("dispatch", {}).get("candidate_ids", []) else 1, "report_rank_violation": 0 if not any(item["evidence_state"] != "VERIFIED" for item in findings[:1]) else 1},
        "verified_ids": sorted(verified_ids),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = opportunity()
    normalized = governor.normalize_verification_opportunity(raw)
    baseline = baseline_plan(raw)
    gold = fixture["cases"][0]["gold_outcomes"]
    baseline_dispatcher = FixtureDispatcher(raw, gold)
    baseline_dispatch = governor.dispatch_verification_plan(baseline, raw, baseline_dispatcher)
    baseline_path = float(baseline_dispatch["critical_path_ms"])
    probabilities = {"upstream-contract": 0.95, "deployment-drift": 0.85, "adapter-capability": 0.80}
    available_models: list[str] = []
    model_resolution_error = None
    if args.mode == "live":
        try:
            available_models = jev.resolve_available_models(api_key=os.environ["TYPESAFE_API_KEY"])
        except Exception as exc:
            model_resolution_error = f"{type(exc).__name__}: {exc}"
    arms: dict[str, Any] = {}
    for arm in ARMS:
        provider = None
        provider_result = None
        if arm in {"B_JEV_SHADOW", "C_JEV_ACTIVE_COLD", "D_JEV_ACTIVE_WARM"}:
            if args.mode == "live":
                provider = jev.JevReflexProvider(
                    api_key=os.environ.get("TYPESAFE_API_KEY", ""),
                    model=args.model or jev.DEFAULT_MODEL,
                    max_attempts=1,
                    calibration_binding=_live_binding(fixture),
                )
            else:
                provider = FixtureProvider(probabilities, warm=arm == "D_JEV_ACTIVE_WARM")
            if arm == "D_JEV_ACTIVE_WARM":
                provider.evaluate(governor.build_verification_request(raw), governor.verification_questions(len(normalized["optional_candidates"])))
            provider_result = provider.evaluate(governor.build_verification_request(raw), governor.verification_questions(len(normalized["optional_candidates"])))
        admission = governor.evaluate_verification_value_of_call(raw, calibration_status="CALIBRATED_FOR_FROZEN_SUITE")
        if arm in {"A_POLICY_ONLY_BASELINE", "B_JEV_SHADOW"}:
            plan = copy.deepcopy(baseline)
        elif provider_result is not None:
            try:
                scores = governor.validate_verification_result(provider_result, raw)
                plan = governor.compose_verification_plan(raw, scores)
            except governor.VerificationContractError:
                plan = governor.deterministic_verification_plan(raw, "INVALID_REFLEX_RESULT")
        else:
            plan = governor.deterministic_verification_plan(raw, "NO_PROVIDER")
        dispatcher = FixtureDispatcher(raw, gold)
        dispatch = governor.dispatch_verification_plan(plan, raw, dispatcher)
        provider_meta = dict(provider_result.get("provider", {}) if provider_result else {})
        receipt = governor.make_verification_receipt(raw, plan, admission, provider_request_count=int(provider_meta.get("network_request_count", 0) or 0), dispatch_receipt=dispatch, provider=provider_meta)
        receipt["dispatch"] = dispatch
        receipt["execution_affected_by_reflex"] = arm in {"C_JEV_ACTIVE_COLD", "D_JEV_ACTIVE_WARM"}
        findings = _findings(raw, dispatch)
        metrics = _metrics(normalized, plan, receipt, findings, baseline_path, gold)
        metrics["execution_affected_by_reflex"] = receipt["execution_affected_by_reflex"]
        arms[arm] = {"plan": plan, "receipt": receipt, "findings": findings, "metrics": metrics}
        if provider is not None:
            provider_result["provider"]["calls"] = getattr(provider, "calls", provider_result["provider"].get("network_request_count", 0))
            if hasattr(provider, "close"):
                provider.close()
    report = {
        "schema_version": "margos-jev-verification-benchmark/v1",
        "mode": args.mode,
        "arms": arms,
        "arm_contract_hash": _hash({"opportunity": normalized, "fixture": fixture["version"]}),
        "partition_isolation": not set(fixture["calibration_partition"]).intersection(fixture["holdout_partition"]),
        "gold_labels_are_external_to_jev": True,
        "forced_arms": True,
        "max_production_provider_requests_per_round": 1,
        "runtime_fingerprint": {"toolkit_version": "1.4.0", "source_sha": _source_sha(), "requested_model": args.model or jev.DEFAULT_MODEL, "response_models": sorted({arm["receipt"].get("provider", {}).get("response_model") for arm in arms.values() if arm["receipt"].get("provider", {}).get("response_model")}), "available_models": available_models, "model_resolution_error": model_resolution_error, "benchmark_protocol": "margos-jev-verification/v1", "corpus_sha256": _hash(fixture)},
        "promotion_status": "JEV_RESEARCH_ONLY",
    }
    baseline_recall = float(arms["A_POLICY_ONLY_BASELINE"]["metrics"]["verified_finding_recall_at_3"])
    active = [arms[name]["metrics"] for name in ("C_JEV_ACTIVE_COLD", "D_JEV_ACTIVE_WARM")]
    report["promotion_gates"] = {
        "protected_retention": all(item["protected_retention"] == 1.0 for item in active),
        "mandatory_retention": all(item["mandatory_retention"] == 1.0 for item in active),
        "quality_noninferior_to_policy_baseline": all(item["verified_finding_recall_at_3"] >= baseline_recall for item in active),
        "optional_verified_recall": {name: arms[name]["metrics"]["optional_verified_recall"] for name in ("A_POLICY_ONLY_BASELINE", "B_JEV_SHADOW", "C_JEV_ACTIVE_COLD", "D_JEV_ACTIVE_WARM")},
        "material_optional_work_reduction": any(item["optional_skipped"] > 0 for item in active),
        "end_to_end_latency_nonregression": all(item["end_to_end_latency_ms"] <= item["baseline_critical_path_ms"] for item in active),
        "provider_errors": sum(item["verification_error_count"] for item in active),
    }
    if args.strict:
        _strict(report, fixture)
    return report


def _strict(report: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    assert report["forced_arms"] and report["partition_isolation"] and report["gold_labels_are_external_to_jev"]
    for arm_name, arm in report["arms"].items():
        assert arm["receipt"]["report_protection"]["jev_did_not_rank_findings"]
        assert arm["metrics"]["mandatory_retention"] == 1.0
        assert not arm["metrics"]["hypothesis_above_verified"]
        assert arm["receipt"]["provider_request_count"] <= 1
        assert set(arm["receipt"]["dispatched_operation_ids"]) == set(arm["receipt"]["dispatch"].get("dispatched_operation_ids", []))
    assert report["arms"]["A_POLICY_ONLY_BASELINE"]["receipt"]["provider_request_count"] == 0
    assert report["arms"]["B_JEV_SHADOW"]["metrics"]["execution_affected_by_reflex"] is False
    assert report["arms"]["C_JEV_ACTIVE_COLD"]["metrics"]["execution_affected_by_reflex"] is True
    assert report["arms"]["C_JEV_ACTIVE_COLD"]["metrics"]["optional_dispatched"] <= report["arms"]["A_POLICY_ONLY_BASELINE"]["metrics"]["optional_dispatched"]
    assert report["promotion_gates"]["quality_noninferior_to_policy_baseline"]
    assert report["promotion_gates"]["end_to_end_latency_nonregression"]
    assert fixture["strict_gates"]["protected_retention"] == 1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--model", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "live" and not os.environ.get("TYPESAFE_API_KEY"):
        print(json.dumps({"status": "NOT_RUN", "reason": "TYPESAFE_API_KEY is unavailable"}, indent=2))
        return 2
    report = run(args)
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
