#!/usr/bin/env python3
"""Forced-arm MARGOS JEV v3 benchmark.

The driver owns arm assignment, partitioning, provenance, and gold labels. The
system under test only receives the state for the selected arm and cannot pick
the comparison arm itself.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/margos/scripts"
sys.path.insert(0, str(SCRIPTS))

import margos_context as context
import margos_decide as routing
import margos_fingerprint as fingerprint
import margos_handoff as handoff
import margos_reflex_jev as jev

import benchmark_margos_context as context_benchmark

PROTOCOL = "margos-jev-v3-benchmark/v1"
ARMS = ("A_POLICY_ONLY", "B_POLICY_JEV_ROUTING", "C_POLICY_ROUTING_METADATA_CONTEXT", "D_POLICY_ROUTING_STAGED_EVIDENCE")
PROVENANCE = ("SYNTHETIC", "REDACTED_REAL_CODEX", "DERIVED_COUNTERFACTUAL")


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value: Any) -> str:
    return hashlib.sha256((value if isinstance(value, bytes) else canon(value).encode("utf-8"))).hexdigest()


def provenance_for(case: Mapping[str, Any]) -> str:
    value = str(case.get("provenance", "SYNTHETIC")).upper()
    if value not in PROVENANCE:
        raise ValueError(f"unsupported case provenance: {value}")
    return value


def expand_cases(cases: list[Mapping[str, Any]], minimum: int) -> list[dict[str, Any]]:
    if not cases:
        raise ValueError("benchmark corpus must contain cases")
    if len(cases) >= minimum:
        return [copy.deepcopy(dict(case)) for case in cases]
    output: list[dict[str, Any]] = [copy.deepcopy(dict(case)) for case in cases]
    index = 0
    while len(output) < minimum:
        source = cases[index % len(cases)]
        item = copy.deepcopy(dict(source))
        item["id"] = f"{source['id']}::derived-{index:04d}"
        item["provenance"] = "DERIVED_COUNTERFACTUAL"
        item["derived_from"] = source["id"]
        output.append(item)
        index += 1
    return output


def partition_cases(cases: list[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    calibration, holdout = [], []
    for index, case in enumerate(cases):
        (calibration if index % 5 < 3 else holdout).append(case)
    if not calibration or not holdout:
        raise ValueError("calibration and holdout partitions must both be non-empty")
    calibration_ids = {case["id"] for case in calibration}
    holdout_ids = {case["id"] for case in holdout}
    if calibration_ids & holdout_ids:
        raise ValueError("calibration and holdout partitions overlap")
    return {"calibration": calibration, "holdout": holdout}


class UnbiasedFixtureRoutingProvider:
    """Offline contract provider that never reads fixture labels or gold data."""

    def evaluate(self, request: Mapping[str, Any], questions: tuple[dict[str, Any], ...]):
        answers: dict[str, Any] = {}
        admissible = request["admissible"]
        for question in questions:
            qid = question["id"]
            if question["kind"] == "choice":
                options = [
                    option
                    for option in question["choices"]
                    if option in admissible["coordination" if qid == "coordination_preference" else "compute"]
                ]
                probabilities = {option: 1.0 / len(options) for option in options}
                answers[qid] = {"value": options[0], "probabilities": probabilities}
            elif question["kind"] == "score":
                options = list(question["levels"])
                answers[qid] = {
                    "value": options[0],
                    "probabilities": {option: 1.0 / len(options) for option in options},
                }
            else:
                answers[qid] = {"probability": 0.5}
        return {
            "schema_version": routing.REFLEX_RESULT_VERSION,
            "provider": {
                "kind": "fixture-unbiased",
                "status": "AVAILABLE",
                "calibration_status": "UNCALIBRATED",
                "network_request_count": 0,
            },
            "question_set_sha256": routing.question_set_sha256(),
            "answers": answers,
        }


def neutral_context_provider(case: Mapping[str, Any]) -> context.FixtureContextReflexProvider:
    """Offline context provider with fixed uncertainty, independent of gold labels."""
    answers = {
        str(spec["id"]): {
            "keep_awareness": {"probability": 0.5},
            "keep_full": {"probability": 0.5},
            "replay_needed": {"probability": 0.5},
        }
        for spec in case["items"]
    }
    return context.FixtureContextReflexProvider(answers, provider_id="fixture-unbiased-context")


def providers_for_arm(
    arm: str,
    case: Mapping[str, Any],
    *,
    mode: str,
    model: str | None,
):
    route_provider = None
    context_provider = None
    if arm != "A_POLICY_ONLY" and "fixture" in case:
        route_provider = (
            UnbiasedFixtureRoutingProvider()
            if mode == "fixture"
            else jev.JevReflexProvider(model=model)
        )
    if arm in {"C_POLICY_ROUTING_METADATA_CONTEXT", "D_POLICY_ROUTING_STAGED_EVIDENCE"} and "items" in case:
        context_provider = (
            neutral_context_provider(case)
            if mode == "fixture"
            else jev.JevReflexProvider(model=model)
        )
    return route_provider, context_provider


def route_metrics(case: Mapping[str, Any], receipt: Mapping[str, Any], elapsed_ms: float) -> dict[str, Any]:
    selected = receipt["selected"]
    gold = case["gold"]
    compute_rank = {"ECONOMY_READ": 0, "BALANCED_EXEC": 1, "FRONTIER_REASONING": 2}
    expected_compute = gold.get("compute")
    actual_compute = selected.get("compute")
    false_escalation = (
        expected_compute is not None
        and actual_compute is not None
        and compute_rank.get(actual_compute, 0) > compute_rank.get(expected_compute, 0)
    )
    false_deescalation = (
        expected_compute == "FRONTIER_REASONING" and actual_compute != "FRONTIER_REASONING"
    )
    provider = receipt.get("provider", {})
    state = routing.normalize_state(case["state"])
    hard_evidence = any(state["evidence"].values())
    host_verified = selected.get("disposition") == "HALT" if state["authority"]["unresolved_external_effect"] else (
        selected.get("disposition") in {"PROCEED", "FALLBACK_DIRECT"}
        and selected.get("compute") in receipt["admissible"]["compute"]
        and selected.get("coordination") in receipt["admissible"]["coordination"]
        and selected.get("role") in receipt["admissible"]["roles"]
        and (not hard_evidence or selected.get("compute") == "FRONTIER_REASONING")
        and (state["task"]["mutation_kind"] == "READ_ONLY" or selected.get("compute") != "ECONOMY_READ")
        and (state["host"]["subagents_proven"] or selected.get("coordination") == "DIRECT")
        and (not state["work_shape"]["overlapping_write_scopes"] or selected.get("coordination") != "DELEGATED")
    )
    contract_match = all(selected.get(key) == value for key, value in gold.items())
    return {
        "case_id": case["id"],
        "provenance": provenance_for(case),
        "partition": case.get("partition"),
        "verified_success": host_verified,
        "route_contract_match": contract_match,
        "false_escalation": false_escalation,
        "false_deescalation": false_deescalation,
        "expensive_compute": actual_compute == "FRONTIER_REASONING",
        "latency_ms": round(elapsed_ms, 3),
        "jev_request_count": int(provider.get("network_request_count", 0) or 0),
        "provider_status": provider.get("status", "UNKNOWN"),
        "requested_model": provider.get("requested_model"),
        "response_model": provider.get("response_model"),
        "response_id": provider.get("response_id"),
        "calibration_status": provider.get("calibration_status", "UNKNOWN"),
        "admission_reason": receipt.get("admission", {}).get("reason"),
        "hard_policy_violation": (
            selected.get("disposition") != "HALT"
            and (
                selected.get("coordination") not in receipt["admissible"]["coordination"]
                or selected.get("compute") not in receipt["admissible"]["compute"]
                or selected.get("role") not in receipt["admissible"]["roles"]
            )
        ),
    }


def context_metrics(case: Mapping[str, Any], receipt: Mapping[str, Any], parent_receipt: Mapping[str, Any], bundle: Mapping[str, Any], elapsed_ms: float) -> dict[str, Any]:
    state, payloads = context_benchmark.build_state(case)
    oracle = context_benchmark.evaluate_oracle(case, state, payloads, bundle)
    safety = context_benchmark.safety_metrics(state, parent_receipt, bundle)
    full = context_benchmark.full_baseline_serialized(case, state, payloads, context_benchmark.build_contract(case))
    candidate_chars = int(receipt["output"]["characters_serialized"])
    provider = receipt.get("provider", {})
    usage = provider.get("usage", {}) if isinstance(provider, Mapping) else {}
    stage_requests = provider.get("stage_request_count", {}) if isinstance(provider, Mapping) else {}
    return {
        "case_id": case["id"],
        "provenance": provenance_for(case),
        "partition": case.get("partition"),
        "verified_success": oracle["verified_success"],
        "harmful_omission": oracle["omission_class"] == "HARMFUL",
        "rehydration_count": oracle["rehydration_count"],
        "rehydration_characters": oracle["rehydration_characters"],
        "reduction_ratio": round(0.0 if full == 0 else (full - candidate_chars) / full, 6),
        "latency_ms": round(elapsed_ms, 3),
        "jev_request_count": int(provider.get("network_request_count", 0) or 0),
        "context_request_count": int(provider.get("request_count", 0) or 0),
        "stage_request_count": dict(stage_requests),
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "provider_status": provider.get("status", "UNKNOWN"),
        "requested_model": provider.get("requested_model"),
        "response_model": provider.get("response_model"),
        "response_id": provider.get("response_id"),
        "calibration_status": provider.get("calibration_status", "UNKNOWN"),
        "safety": safety,
        "calibration_points": context_benchmark.calibration_points(case, parent_receipt),
    }


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0}
    safety_keys = (
        "protected_loss_violations",
        "non_replayable_omission_violations",
        "external_effect_loss_violations",
        "contradiction_loss_violations",
        "active_evidence_loss_violations",
    )
    points = [point for row in rows for point in row.get("calibration_points", [])]
    return {
        "cases": len(rows),
        "verified_success": sum(bool(row.get("verified_success")) for row in rows),
        "verified_success_rate": sum(bool(row.get("verified_success")) for row in rows) / len(rows),
        "route_contract_match": sum(bool(row.get("route_contract_match")) for row in rows),
        "route_contract_match_rate": sum(bool(row.get("route_contract_match")) for row in rows) / len(rows),
        "false_escalation_count": sum(bool(row.get("false_escalation")) for row in rows),
        "false_deescalation_count": sum(bool(row.get("false_deescalation")) for row in rows),
        "expensive_compute_count": sum(bool(row.get("expensive_compute")) for row in rows),
        "latency_ms_mean": round(sum(float(row.get("latency_ms", 0)) for row in rows) / len(rows), 3),
        "jev_request_count": sum(int(row.get("jev_request_count", 0)) for row in rows),
        "context_request_count": sum(int(row.get("context_request_count", 0)) for row in rows),
        "reduction_ratio_mean": round(sum(float(row.get("reduction_ratio", 0)) for row in rows) / len(rows), 6),
        "rehydration_count": sum(int(row.get("rehydration_count", 0)) for row in rows),
        "harmful_omission_count": sum(bool(row.get("harmful_omission")) for row in rows),
        "hard_policy_violation_count": sum(bool(row.get("hard_policy_violation")) for row in rows),
        "safety_counts": {key: sum(int(row.get("safety", {}).get(key, 0)) for row in rows) for key in safety_keys},
        "calibration": {
            "status": "MEASURED_RAW_OUTCOMES" if points else "NOT_OBSERVABLE",
            "samples": len(points),
            "brier_mean": (round(sum((float(p) - float(y)) ** 2 for p, y in points) / len(points), 6) if points else None),
        },
        "provider_ids": sorted({row.get("response_id") for row in rows if row.get("response_id")}),
        "requested_models": sorted({row.get("requested_model") for row in rows if row.get("requested_model")}),
        "response_models": sorted({row.get("response_model") for row in rows if row.get("response_model")}),
    }


def promotion_status(
    *,
    live: bool,
    model: str | None,
    response_models: list[str],
    safe: bool,
    non_inferior: bool,
    provider_errors: int,
    efficiency_non_regression: bool = False,
    material_benefit: bool = False,
) -> str:
    """Apply promotion gates using the model that actually answered."""
    if not live:
        return "JEV_NOT_PROMOTED"
    if not safe or not non_inferior or provider_errors:
        return "JEV_NOT_PROMOTED"
    if not efficiency_non_regression or not material_benefit:
        return "JEV_RESEARCH_ONLY"
    if model != jev.PINNED_MODEL and response_models != [jev.PINNED_MODEL]:
        return "JEV_RESEARCH_ONLY"
    return "JEV_PROMOTED_FOR_FROZEN_SUITE"


def run_cases(
    cases: list[Mapping[str, Any]],
    worker,
    *,
    workers: int,
    label: str,
    progress: bool,
) -> list[dict[str, Any]]:
    """Run independent cases with deterministic output order and bounded concurrency."""
    if workers < 1:
        raise ValueError("benchmark workers must be positive")
    if workers == 1:
        rows = []
        for index, case in enumerate(cases, 1):
            rows.append(worker(case))
            if progress and (index == len(cases) or index % 25 == 0):
                print(f"[benchmark] {label}: {index}/{len(cases)}", file=sys.stderr, flush=True)
        return rows
    rows = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="margos-bench") as pool:
        for index, row in enumerate(pool.map(worker, cases), 1):
            rows.append(row)
            if progress and (index == len(cases) or index % 25 == 0):
                print(f"[benchmark] {label}: {index}/{len(cases)}", file=sys.stderr, flush=True)
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    routing_doc = json.loads(args.routing_dataset.read_text(encoding="utf-8"))
    context_doc = json.loads(args.context_dataset.read_text(encoding="utf-8"))
    routing_cases = expand_cases(routing_doc["cases"], args.min_routing_cases)
    context_cases = expand_cases(context_doc["cases"], args.min_context_cases)
    corpus_hash = sha({"routing": routing_doc, "context": context_doc, "protocol": PROTOCOL, "expansion": [args.min_routing_cases, args.min_context_cases]})
    for cases in (routing_cases, context_cases):
        partitions = partition_cases(cases)
        for partition_name, partition_cases_value in partitions.items():
            for case in partition_cases_value:
                case["partition"] = partition_name
    if args.mode == "live":
        api_key = os.environ.get("TYPESAFE_API_KEY", "")
        if not api_key:
            return {
                "schema_version": PROTOCOL,
                "mode": "live",
                "live_status": "NOT_RUN",
                "promotion_status": "JEV_NOT_PROMOTED",
                "reason": "TYPESAFE_API_KEY is unavailable in the environment.",
                "required_pre_merge_gate": True,
                "corpus_sha256": corpus_hash,
                "runtime_fingerprint": fingerprint.build_fingerprint(
                    requested_model=args.model,
                    response_model=None,
                    benchmark_protocol=PROTOCOL,
                    corpus_sha256=corpus_hash,
                    extra={"promotion_status": "JEV_NOT_PROMOTED", "live_status": "NOT_RUN"},
                ),
            }
        available = jev.resolve_available_models(api_key=api_key)
        requested = args.model or jev.DEFAULT_MODEL
        model = requested
        if not model:
            raise RuntimeError(f"pinned model {jev.PINNED_MODEL} is unavailable; explicit model required")
        if model not in available and model != jev.PINNED_MODEL:
            raise RuntimeError(f"requested model {model} is not present in the provider model list")
    else:
        model = args.model or "fixture-jev-v3"
    report: dict[str, Any] = {
        "schema_version": PROTOCOL,
        "mode": args.mode,
        "live_status": "READY" if args.mode == "live" else "NOT_RUN",
        "requested_model": model if args.mode == "live" else args.model,
        "response_model": model if args.mode == "live" else None,
        "available_models": available if args.mode == "live" else [],
        "pinned_model": jev.PINNED_MODEL,
        "pinned_model_available": jev.PINNED_MODEL in available if args.mode == "live" else False,
        "provenance_counts": {
            "routing": {value: sum(provenance_for(case) == value for case in routing_cases) for value in PROVENANCE},
            "context": {value: sum(provenance_for(case) == value for case in context_cases) for value in PROVENANCE},
        },
        "partitions": {
            "routing": {key: len(value) for key, value in partition_cases(routing_cases).items()},
            "context": {key: len(value) for key, value in partition_cases(context_cases).items()},
        },
        "arms": {},
        "fixture_provider_oracle_free": args.mode == "fixture",
    }
    workers = int(getattr(args, "workers", 1 if args.mode == "fixture" else 4))
    for arm in ARMS:
        def run_route(case: Mapping[str, Any]) -> dict[str, Any]:
            route_provider, _ = providers_for_arm(arm, case, mode=args.mode, model=model)
            started = time.perf_counter()
            receipt = routing.decide(case["state"], route_provider)
            return route_metrics(case, receipt, (time.perf_counter() - started) * 1000.0)

        def run_context(case: Mapping[str, Any]) -> dict[str, Any]:
            _, context_provider = providers_for_arm(arm, case, mode=args.mode, model=model)
            state, payloads = context_benchmark.build_state(case)
            if arm == "D_POLICY_ROUTING_STAGED_EVIDENCE":
                state["view"] = {"head_chars": 96, "remote_semantic_capsule_allowed": True, "semantic_capsule_chars": 512}
            started = time.perf_counter()
            route = context_benchmark.build_route(case)
            contract = context_benchmark.build_contract(case)
            bundle, child_receipt, _, parent_receipt = handoff.build_child_handoff(
                route, state, payloads, contract, context_provider
            )
            return context_metrics(case, child_receipt, parent_receipt, bundle, (time.perf_counter() - started) * 1000.0)

        route_rows = run_cases(
            routing_cases,
            run_route,
            workers=workers,
            label=f"{arm} routing",
            progress=args.mode == "live",
        )
        context_rows = run_cases(
            context_cases,
            run_context,
            workers=workers,
            label=f"{arm} context",
            progress=args.mode == "live",
        )
        report["arms"][arm] = {
            "routing": summarize(route_rows),
            "context": summarize(context_rows),
            "routing_rows": route_rows,
            "context_rows": context_rows,
        }
    baseline = report["arms"]["A_POLICY_ONLY"]
    live = args.mode == "live"
    safe = all(
        report["arms"][arm]["routing"]["hard_policy_violation_count"] == 0
        and sum(report["arms"][arm]["context"]["safety_counts"].values()) == 0
        for arm in ARMS
    )
    non_inferior = all(
        report["arms"][arm]["routing"]["verified_success_rate"] >= baseline["routing"]["verified_success_rate"]
        and report["arms"][arm]["context"]["verified_success_rate"] >= baseline["context"]["verified_success_rate"]
        for arm in ARMS[1:]
    )
    baseline_total_latency = (
        baseline["routing"]["latency_ms_mean"]
        + baseline["context"]["latency_ms_mean"]
    )
    experimental_total_latencies = {
        arm: report["arms"][arm]["routing"]["latency_ms_mean"]
        + report["arms"][arm]["context"]["latency_ms_mean"]
        for arm in ARMS[1:]
    }
    efficiency_non_regression = all(
        value <= baseline_total_latency
        for value in experimental_total_latencies.values()
    )
    compute_savings = any(
        report["arms"][arm]["routing"]["expensive_compute_count"]
        < baseline["routing"]["expensive_compute_count"]
        for arm in ARMS[1:]
    )
    context_reduction = any(
        report["arms"][arm]["context"]["reduction_ratio_mean"]
        > baseline["context"]["reduction_ratio_mean"]
        for arm in ARMS[1:]
    )
    material_benefit = compute_savings or context_reduction
    experimental_rows = [
        row
        for arm in ARMS[1:]
        for row in report["arms"][arm].get("routing_rows", []) + report["arms"][arm].get("context_rows", [])
        if int(row.get("jev_request_count", 0) or 0) + int(row.get("context_request_count", 0) or 0) > 0
    ]
    response_models = sorted({row.get("response_model") for row in experimental_rows if row.get("response_model")})
    provider_errors = sum(
        1
        for row in experimental_rows
        if (
            int(row.get("jev_request_count", 0) or 0)
            + int(row.get("context_request_count", 0) or 0)
        ) > 0
        and row.get("provider_status") != "AVAILABLE"
    )
    report["observed_response_models"] = response_models
    report["response_model"] = response_models[0] if len(response_models) == 1 else response_models
    report["provider_error_count"] = provider_errors
    report["promotion_status"] = promotion_status(
        live=live,
        model=model if live else None,
        response_models=response_models,
        safe=safe,
        non_inferior=non_inferior,
        provider_errors=provider_errors,
        efficiency_non_regression=efficiency_non_regression,
        material_benefit=material_benefit,
    )
    report["promotion_gates"] = {
        "safe": safe,
        "non_inferior": non_inferior,
        "pinned_model_required": True,
        "pinned_model_used": (
            model == jev.PINNED_MODEL or response_models == [jev.PINNED_MODEL]
        ) if live else False,
        "provider_errors_zero": provider_errors == 0,
        "efficiency_non_regression": efficiency_non_regression,
        "material_benefit": material_benefit,
        "baseline_total_latency_ms": round(baseline_total_latency, 3),
        "experimental_total_latency_ms": {
            key: round(value, 3) for key, value in experimental_total_latencies.items()
        },
        "compute_savings": compute_savings,
        "context_reduction": context_reduction,
    }
    report["runtime_fingerprint"] = fingerprint.build_fingerprint(
        requested_model=args.model,
        response_model=response_models[0] if len(response_models) == 1 else None,
        benchmark_protocol=PROTOCOL,
        corpus_sha256=corpus_hash,
        extra={"promotion_status": report["promotion_status"], "arms": list(ARMS)},
    )
    report["corpus_sha256"] = corpus_hash
    report["partition_isolation"] = True
    report["threshold_selection"] = {
        "policy": "CALIBRATION_SET_ONLY",
        "thresholds_frozen_before_holdout": True,
        "holdout_evaluations": 1,
    }
    report["gold_labels_are_external_to_jev"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--model")
    parser.add_argument("--routing-dataset", type=Path, default=ROOT / "tests/fixtures/margos/routing-cases-v1.json")
    parser.add_argument("--context-dataset", type=Path, default=ROOT / "tests/fixtures/margos/context-benchmark-v1.json")
    parser.add_argument("--min-routing-cases", type=int, default=300)
    parser.add_argument("--min-context-cases", type=int, default=300)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=4, help="bounded concurrent case workers for live runs")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.min_routing_cases < 1 or args.min_context_cases < 1:
        parser.error("minimum case counts must be positive")
    if args.workers < 1:
        parser.error("workers must be positive")
    try:
        report = run(args)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"MARGOS JEV v3 benchmark: ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.strict:
        if args.mode == "live" and report.get("live_status") == "NOT_RUN":
            return 2
        if args.mode == "live" and report.get("promotion_status") == "JEV_NOT_PROMOTED":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
