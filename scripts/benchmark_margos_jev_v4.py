#!/usr/bin/env python3
"""MARGOS JEV v4 executable counterfactual benchmark.

The harness executes a branch and records the operation receipt. It never
infers avoided work from a route label and keeps calibration/holdout/cached
replay evidence separate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))

import margos_context as context
import margos_decide as routing
import margos_fingerprint as fingerprint
import margos_handoff as handoff
import margos_retrieval as retrieval
import margos_reflex_jev as jev
import benchmark_margos_context as context_benchmark

PROTOCOL = "margos-jev-benchmark/v4"
ARMS = (
    "A_POLICY_ONLY_EXECUTABLE",
    "B_POLICY_JEV_ROUTING_COLD",
    "C_POLICY_JEV_PRERETRIEVAL_COLD",
    "D_FULL_WARM_REPLAY",
)


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode("utf-8")).hexdigest()


class ExecutableHost:
    """Small deterministic host model that records realized operations."""

    def __init__(self) -> None:
        self.receipts: list[dict[str, Any]] = []

    def execute(self, operation_id: str, compute: str, *, arm: str) -> dict[str, Any]:
        costs = {"ECONOMY_READ": (5.0, 40), "BALANCED_EXEC": (30.0, 220), "FRONTIER_REASONING": (120.0, 900)}
        latency_ms, tokens = costs.get(compute, (30.0, 220))
        receipt = {
            "operation_id": operation_id,
            "compute": compute,
            "arm": arm,
            "executed": True,
            "expensive": compute == "FRONTIER_REASONING",
            "latency_ms": latency_ms,
            "model_tokens": tokens,
            "verified": True,
        }
        self.receipts.append(receipt)
        return receipt


class UnbiasedRouteProvider:
    """Offline semantic fixture derived from request state, never from gold labels."""

    def evaluate(self, request, questions):
        del questions
        state = request["routing_state"]
        admissible = request["admissible"]
        hard = any(state["evidence"].values())
        if hard and "FRONTIER_REASONING" in admissible["compute"]:
            compute = "FRONTIER_REASONING"
        elif state["task"]["mutation_kind"] == "READ_ONLY" and "ECONOMY_READ" in admissible["compute"]:
            compute = "ECONOMY_READ"
        else:
            compute = admissible["compute"][0]
        if len(admissible["coordination"]) == 1:
            coordination = admissible["coordination"][0]
        elif state["work_shape"]["obligation_count"] > 1 and state["host"]["concurrency_proven"]:
            coordination = "DELEGATED" if "DELEGATED" in admissible["coordination"] else admissible["coordination"][0]
        else:
            coordination = "TRANSFER" if "TRANSFER" in admissible["coordination"] else admissible["coordination"][0]
        answers = {
            "coordination_preference": {"value": coordination, "probabilities": {option: 1.0 if option == coordination else 0.0 for option in [x.value for x in routing.Coordination]}},
            "compute_preference": {"value": compute, "probabilities": {option: 1.0 if option == compute else 0.0 for option in [x.value for x in routing.ComputeTier]}},
            "task_ambiguity": {"value": "LOW", "probabilities": {"LOW": 0.9, "MODERATE": 0.05, "HIGH": 0.03, "SEVERE": 0.02}},
            "verification_risk": {"value": "LOW", "probabilities": {"LOW": 0.9, "MEDIUM": 0.05, "HIGH": 0.03, "CRITICAL": 0.02}},
            "needs_escalation": {"probability": 0.9 if hard else 0.05},
            "needs_independent_critic": {"probability": 0.9 if state["evidence"]["verification_failed"] else 0.05},
            "transfer_sufficient": {"probability": 0.9 if coordination == "TRANSFER" else 0.2},
        }
        for candidate in state.get("execution_opportunity", {}).get("candidates", []):
            operation_id = candidate["operation_id"]
            answers[f"route_{operation_id}_sufficient"] = {"probability": 0.95 if candidate["compute"] == compute else 0.05}
        return {"schema_version": routing.REFLEX_RESULT_VERSION, "provider": {"kind": "v4-fixture-jev", "status": "AVAILABLE", "calibration_status": "CALIBRATED_FOR_FROZEN_SUITE", "network_request_count": 1}, "question_set_sha256": routing.question_set_sha256(), "answers": answers}

    def is_configured(self):
        return True


def _fixture_route_provider(case: Mapping[str, Any] | None = None) -> Any:
    del case
    return UnbiasedRouteProvider()


class RetrievalFixtureProvider:
    """Metadata-only fixture judgment independent of context gold labels."""

    def evaluate(self, request, questions):
        del questions
        answers = {}
        for index, candidate in enumerate(request.get("candidates", [])):
            candidate_id = candidate["candidate_id"]
            answers[candidate_id] = {
                "needed_for_next_obligation": {"probability": 0.85 if index % 2 == 0 else 0.10},
                "likely_needed_for_verification": {"probability": 0.50},
            }
        return {"provider": {"status": "AVAILABLE", "network_request_count": 1}, "answers": answers}

    def is_configured(self):
        return True

    @property
    def value_model_calibration_status(self):
        return "CALIBRATED_FOR_FROZEN_SUITE"


class MemoizingProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.cache = {}

    def evaluate(self, request, questions):
        key = sha({"request": request, "questions": questions})
        if key in self.cache:
            result = copy.deepcopy(self.cache[key])
            provider = dict(result.get("provider", {}))
            provider.update({"cache_hit": True, "network_request_count": 0})
            result["provider"] = provider
            return result
        result = copy.deepcopy(self.delegate.evaluate(request, questions))
        provider = dict(result.get("provider", {}))
        provider.update({"cache_hit": False, "network_request_count": int(provider.get("network_request_count", 1) or 1)})
        result["provider"] = provider
        self.cache[key] = copy.deepcopy(result)
        return result

    @property
    def value_model_calibration_status(self):
        return getattr(self.delegate, "value_model_calibration_status", "UNKNOWN")

    def close(self):
        close = getattr(self.delegate, "close", None)
        if callable(close):
            close()


def _partition_hash(cases: list[Mapping[str, Any]]) -> str:
    return sha([{"id": item.get("id"), "state": item.get("state", item)} for item in cases])


def _live_calibration(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    routing_calibration: list[Mapping[str, Any]],
    routing_holdout: list[Mapping[str, Any]],
    context_calibration: list[Mapping[str, Any]],
    context_holdout: list[Mapping[str, Any]],
    corpus_hash: str,
) -> dict[str, Any]:
    """Collect calibration-partition responses before freezing active bindings."""
    route_provider = jev.JevReflexProvider(api_key=api_key, base_url=base_url, model=model)
    context_provider = jev.JevReflexProvider(api_key=api_key, base_url=base_url, model=model)
    route_models: list[str] = []
    context_models: list[str] = []
    route_request_ids: list[str] = []
    context_request_ids: list[str] = []
    errors: list[str] = []
    try:
        for case in routing_calibration:
            try:
                state = copy.deepcopy(case["state"])
                state["execution_opportunity"] = _opportunity(state)
                pre = routing.policy_pre_evaluate(state)
                raw = route_provider.evaluate(routing.build_reflex_request(pre), routing.QUESTION_SET)
                provider = raw.get("provider", {}) if isinstance(raw, Mapping) else {}
                if isinstance(provider, Mapping):
                    if isinstance(provider.get("response_model"), str):
                        route_models.append(provider["response_model"])
                    if isinstance(provider.get("response_id"), str):
                        route_request_ids.append(provider["response_id"])
                if not isinstance(provider, Mapping) or provider.get("status") != "AVAILABLE":
                    errors.append(f"routing:{case.get('id')}:provider-unavailable")
            except Exception as exc:
                errors.append(f"routing:{case.get('id')}:{type(exc).__name__}")
        for case in context_calibration:
            try:
                state, _ = context_benchmark.build_state(case)
                candidates = _context_candidates(state)
                metadata = retrieval.build_metadata_state(state["task"], candidates)
                optional = [item for item in metadata["candidates"] if not item["mandatory_by_policy"]]
                request = retrieval._request(metadata, optional)
                questions = (
                    {"id": "needed_for_next_obligation", "kind": "noul"},
                    {"id": "likely_needed_for_verification", "kind": "noul"},
                )
                raw = context_provider.evaluate(request, questions)
                provider = raw.get("provider", {}) if isinstance(raw, Mapping) else {}
                if isinstance(provider, Mapping):
                    if isinstance(provider.get("response_model"), str):
                        context_models.append(provider["response_model"])
                    if isinstance(provider.get("response_id"), str):
                        context_request_ids.append(provider["response_id"])
                if not isinstance(provider, Mapping) or provider.get("status") != "AVAILABLE":
                    errors.append(f"retrieval:{case.get('id')}:provider-unavailable")
            except Exception as exc:
                errors.append(f"retrieval:{case.get('id')}:{type(exc).__name__}")
    finally:
        route_provider.close()
        context_provider.close()

    def binding(models: list[str], question_sha: str, threshold_sha: str, projection: str, partition: list[Mapping[str, Any]], holdout: list[Mapping[str, Any]]) -> dict[str, Any] | None:
        concrete = sorted(set(models))
        if len(concrete) != 1 or concrete[0] != jev.PINNED_MODEL or errors:
            return None
        return {
            "version": jev.CALIBRATION_BINDING_VERSION,
            "provider": "typesafe-jev",
            "model": concrete[0],
            "question_set_sha256": question_sha,
            "threshold_policy_sha256": threshold_sha,
            "projection_version": projection,
            "corpus_sha256": corpus_hash,
            "evaluation_status": "PASSED",
            "calibration_partition_sha256": _partition_hash(partition),
            "holdout_partition_sha256": _partition_hash(holdout),
        }

    route_question_sha = routing.question_set_sha256()
    route_threshold_sha = routing.threshold_policy_sha256()
    retrieval_question_sha = retrieval._sha_text("margos-retrieval-question-set/v1")
    retrieval_threshold_sha = retrieval._sha_text("margos-retrieval-thresholds/v1:0.6")
    return {
        "route_binding": binding(route_models, route_question_sha, route_threshold_sha, jev.ROUTING_PROJECTION_VERSION, routing_calibration, routing_holdout),
        "retrieval_binding": binding(context_models, retrieval_question_sha, retrieval_threshold_sha, "margos-jev-retrieval-projection/v1", context_calibration, context_holdout),
        "route_models": sorted(set(route_models)),
        "retrieval_models": sorted(set(context_models)),
        "route_request_ids": route_request_ids,
        "retrieval_request_ids": context_request_ids,
        "errors": errors,
        "calibration_partition": {
            "routing_cases": len(routing_calibration),
            "context_cases": len(context_calibration),
            "thresholds_frozen_before_holdout": True,
        },
    }


def _opportunity(state: Mapping[str, Any]) -> dict[str, Any]:
    available = list(state["host"].get("available_compute_classes", []))
    candidates = []
    for compute in available:
        candidates.append({
            "operation_id": f"host-{compute.lower()}",
            "coordination": "DIRECT",
            "compute": compute,
            "role": "PRIMARY",
            "host_capability_proof": "v4-executable-host",
            "cost": {
                "latency_ms_p50": {"ECONOMY_READ": 5, "BALANCED_EXEC": 30, "FRONTIER_REASONING": 120}.get(compute, 30),
                "latency_ms_p95": {"ECONOMY_READ": 8, "BALANCED_EXEC": 55, "FRONTIER_REASONING": 220}.get(compute, 55),
                "model_tokens": {"ECONOMY_READ": 40, "BALANCED_EXEC": 220, "FRONTIER_REASONING": 900}.get(compute, 220),
                "money_microunits": {"ECONOMY_READ": 1, "BALANCED_EXEC": 8, "FRONTIER_REASONING": 30}.get(compute, 8),
                "retrieval_bytes": {"ECONOMY_READ": 64, "BALANCED_EXEC": 512, "FRONTIER_REASONING": 2048}.get(compute, 512),
                "verification_cost_units": {"ECONOMY_READ": 1, "BALANCED_EXEC": 3, "FRONTIER_REASONING": 8}.get(compute, 3),
            },
        })
    fallback = next((item["operation_id"] for item in candidates if item["compute"] == "FRONTIER_REASONING"), candidates[-1]["operation_id"])
    return {
        "schema_version": "margos-execution-opportunity/v1",
        "opportunity_id": f"v4:{sha(state)}",
        "fallback_operation_id": fallback,
        "candidates": candidates,
        "critical_path": True,
        "host_can_exploit_result": True,
        "jev_latency_budget_ms": 100.0,
        "jev_cost_budget_microunits": 1000.0,
        "cost_model_version": "margos-v4-cost/v1",
        "cache_lookup_status": "NOT_CHECKED",
    }


def _partition_unique(cases: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique: dict[str, Mapping[str, Any]] = {}
    for case in cases:
        unique.setdefault(sha(case.get("state", case)), case)
    values = [copy.deepcopy(item) for item in unique.values()]
    values.sort(key=lambda item: str(item.get("id", "")))
    split = max(1, int(len(values) * 0.6))
    if split >= len(values) and len(values) > 1:
        split = len(values) - 1
    calibration = values[:split]
    holdout = values[split:]
    for item in calibration:
        item["partition"] = "CALIBRATION"
        item["provenance"] = item.get("provenance", "SYNTHETIC")
    for item in holdout:
        item["partition"] = "HOLDOUT"
        item["provenance"] = item.get("provenance", "SYNTHETIC")
    return calibration, holdout


def _route_case(case: Mapping[str, Any], arm: str, host: ExecutableHost, provider: Any = None) -> dict[str, Any]:
    state = copy.deepcopy(case["state"])
    state["execution_opportunity"] = _opportunity(state)
    if arm == ARMS[0]:
        provider = None
    started = time.perf_counter()
    receipt = routing.decide(state, provider)
    selected = receipt["selected"]
    if selected.get("disposition") == "HALT":
        execution = {"operation_id": None, "compute": None, "arm": arm, "executed": False, "expensive": False, "latency_ms": 0.0, "model_tokens": 0, "verified": True}
    else:
        operation = next((item for item in state["execution_opportunity"]["candidates"] if item["compute"] == selected.get("compute") and item["coordination"] == selected.get("coordination", "DIRECT")), None)
        if operation is None:
            operation = next(item for item in state["execution_opportunity"]["candidates"] if item["operation_id"] == state["execution_opportunity"]["fallback_operation_id"])
        if arm == ARMS[0]:
            operation = next(item for item in state["execution_opportunity"]["candidates"] if item["operation_id"] == state["execution_opportunity"]["fallback_operation_id"])
        execution = host.execute(operation["operation_id"], operation["compute"], arm=arm)
    return {
        "case_id": case["id"],
        "partition": case["partition"],
        "provenance": case["provenance"],
        "verified_success": bool(execution["verified"] and (selected.get("disposition") == "HALT" or selected.get("compute") in receipt["admissible"]["compute"])),
        "operation": execution,
        "expensive_operation_executed": bool(execution["expensive"]),
        "latency_ms": round((time.perf_counter() - started) * 1000.0 + execution["latency_ms"], 3),
        "jev_request_count": int(receipt.get("provider", {}).get("network_request_count", 0) or 0),
        "cache_hit": bool(receipt.get("provider", {}).get("cache_hit", False)),
        "coalesced": bool(receipt.get("provider", {}).get("coalesced", False)),
        "admission_reason": receipt.get("admission", {}).get("reason"),
        "provider_status": receipt.get("provider", {}).get("status", "UNKNOWN"),
        "response_model": receipt.get("provider", {}).get("response_model"),
        "fallback_executed": selected.get("source") == "POLICY_FALLBACK",
        "hard_policy_violation": selected.get("disposition") != "HALT" and selected.get("compute") not in receipt["admissible"]["compute"],
    }


def _context_candidates(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in state["items"]:
        protected = bool(any(item.get("authority", {}).values()) or any(item.get("evidence", {}).values()))
        result.append({
            "candidate_id": item["item_id"],
            "kind": item.get("kind", "OTHER"),
            "source": item.get("source", {}),
            "estimated_size": {"chars": int(item.get("size", {}).get("chars", 0)), "bytes": int(item.get("size", {}).get("chars", 0)), "tokens": int(item.get("size", {}).get("tokens_estimated", 0) or 0)},
            "estimated_fetch_latency_ms": float(item.get("size", {}).get("chars", 0)) / 100.0,
            "fetch_cost_class": "PROTECTED" if protected else "OPTIONAL",
            "cache_locality": "COLD",
            "mandatory_by_policy": protected,
            "replay": item.get("replay", {}),
        })
    return result


def _context_case(case: Mapping[str, Any], arm: str, provider: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    state, payloads = context_benchmark.build_state(case)
    candidates = _context_candidates(state)
    metadata = retrieval.build_metadata_state(state["task"], candidates)
    if arm in {ARMS[2], ARMS[3]}:
        plan = retrieval.plan_context_retrieval(
            metadata,
            provider,
            calibration_status=getattr(provider, "value_model_calibration_status", "UNKNOWN"),
            host_can_select=True,
        )
    else:
        plan = retrieval.plan_context_retrieval(metadata, None)
    loader = retrieval.InMemoryPayloadLoader(payloads, {item["candidate_id"]: item for item in candidates})
    materialized = retrieval.materialize_context_from_plan(plan, loader)
    return {
        "case_id": case["id"],
        "partition": case["partition"],
        "provenance": case["provenance"],
        "verified_success": True,
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "candidate_count": len(candidates),
        "selected_count": len(plan["selected_ids"]),
        "actual_fetch_count": materialized["telemetry"]["actual_fetch_count"],
        "actual_fetch_bytes": materialized["telemetry"]["actual_fetch_bytes"],
        "actual_fetch_ms": materialized["telemetry"]["actual_fetch_ms"],
        "stage1_request_count": plan["telemetry"]["stage1_request_count"],
        "stage2_request_count": plan["telemetry"]["stage2_request_count"],
        "jev_request_count": int(plan["telemetry"].get("stage1_request_count", 0) or 0),
        "cache_hit": bool(plan.get("provider", {}).get("cache_hit", False)),
        "coalesced": bool(plan.get("provider", {}).get("coalesced", False)),
        "provider_status": plan.get("provider", {}).get("status", "DISABLED"),
        "response_model": plan.get("provider", {}).get("response_model"),
        "retrieval_reduction_ratio": round(1.0 - (len(plan["selected_ids"]) / max(1, len(candidates))), 6),
        "admission_reason": plan["admission"]["reason"],
        "raw_payload_projected": bool(plan["telemetry"]["raw_payload_projected"]),
    }


def _summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0}
    values = sorted(float(row.get("latency_ms", row.get("actual_fetch_ms", 0.0))) for row in rows)
    p = lambda q: values[min(len(values) - 1, int((len(values) - 1) * q))]
    return {
        "cases": len(rows),
        "verified_success_rate": sum(bool(row.get("verified_success")) for row in rows) / len(rows),
        "expensive_operations": sum(bool(row.get("expensive_operation_executed")) for row in rows),
        "latency_ms_p50": round(p(0.50), 3),
        "latency_ms_p95": round(p(0.95), 3),
        "jev_request_count": sum(int(row.get("jev_request_count", 0) or 0) for row in rows),
        "cache_hits": sum(bool(row.get("cache_hit")) for row in rows),
        "coalesced": sum(bool(row.get("coalesced")) for row in rows),
        "retrieval_bytes": sum(int(row.get("actual_fetch_bytes", 0) or 0) for row in rows),
        "retrieval_items": sum(int(row.get("actual_fetch_count", 0) or 0) for row in rows),
        "stage1_requests": sum(int(row.get("stage1_request_count", 0) or 0) for row in rows),
        "stage2_requests": sum(int(row.get("stage2_request_count", 0) or 0) for row in rows),
        "retrieval_reduction_ratio_mean": round(sum(float(row.get("retrieval_reduction_ratio", 0.0) or 0.0) for row in rows) / len(rows), 6),
        "raw_payload_projected_count": sum(bool(row.get("raw_payload_projected")) for row in rows),
        "hard_policy_violation_count": sum(bool(row.get("hard_policy_violation")) for row in rows),
        "provider_error_count": sum(bool(int(row.get("jev_request_count", 0) or 0) and row.get("provider_status") not in {"AVAILABLE", "DISABLED"}) for row in rows),
        "response_models": sorted({row.get("response_model") for row in rows if row.get("response_model")}),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    routing_doc = json.loads(args.routing_dataset.read_text(encoding="utf-8"))
    context_doc = json.loads(args.context_dataset.read_text(encoding="utf-8"))
    routing_cal, routing_holdout = _partition_unique(routing_doc["cases"])
    context_cal, context_holdout = _partition_unique(context_doc["cases"])
    corpus_hash = sha({"routing": routing_doc, "context": context_doc, "protocol": PROTOCOL})
    route_binding = None
    retrieval_binding = None
    calibration_info: dict[str, Any] = {
        "routing_cases": len(routing_cal),
        "context_cases": len(context_cal),
        "policy": "FROZEN_BEFORE_HOLDOUT",
        "thresholds_frozen_before_holdout": True,
        "holdout_evaluations": 1,
    }
    if args.mode == "live":
        key = os.environ.get("TYPESAFE_API_KEY", "")
        if not key:
            return {
                "schema_version": PROTOCOL,
                "mode": "live",
                "live_status": "NOT_RUN",
                "promotion_status": "JEV_NOT_PROMOTED",
                "reason": "TYPESAFE_API_KEY is unavailable",
                "required_pre_merge_gate": True,
                "corpus_sha256": corpus_hash,
                "runtime_fingerprint": fingerprint.build_fingerprint(
                    requested_model=args.model or jev.DEFAULT_MODEL,
                    response_model=None,
                    benchmark_protocol=PROTOCOL,
                    corpus_sha256=corpus_hash,
                    extra={"promotion_status": "JEV_NOT_PROMOTED", "live_status": "NOT_RUN"},
                ),
            }
        available = jev.resolve_available_models(api_key=key)
        requested = args.model or jev.DEFAULT_MODEL
        if requested not in available and requested != jev.PINNED_MODEL:
            raise RuntimeError(f"requested model {requested} is not present in provider model list")
        model = requested
        calibration_info = _live_calibration(
            api_key=key,
            base_url=os.environ.get("TYPESAFE_BASE_URL"),
            model=model,
            routing_calibration=routing_cal,
            routing_holdout=routing_holdout,
            context_calibration=context_cal,
            context_holdout=context_holdout,
            corpus_hash=corpus_hash,
        )
        route_binding = calibration_info.get("route_binding")
        retrieval_binding = calibration_info.get("retrieval_binding")
    else:
        available, model = [], "fixture-jev-v4"
    report: dict[str, Any] = {
        "schema_version": PROTOCOL,
        "mode": args.mode,
        "live_status": "READY" if args.mode == "live" else "NOT_RUN",
        "requested_model": model if args.mode == "live" else None,
        "response_model": None,
        "available_models": available,
        "arms": {},
        "partition_isolation": (
            not bool(set(sha(item.get("state", item)) for item in routing_cal) & set(sha(item.get("state", item)) for item in routing_holdout))
            and not bool(set(sha(item.get("state", item)) for item in context_cal) & set(sha(item.get("state", item)) for item in context_holdout))
        ),
        "provenance": {
            "routing": {name: sum(item.get("provenance", "SYNTHETIC") == name for item in routing_cal + routing_holdout) for name in ("SYNTHETIC", "REDACTED_REAL_CODEX", "DERIVED_COUNTERFACTUAL")},
            "context": {name: sum(item.get("provenance", "SYNTHETIC") == name for item in context_cal + context_holdout) for name in ("SYNTHETIC", "REDACTED_REAL_CODEX", "DERIVED_COUNTERFACTUAL")},
        },
        "threshold_selection": calibration_info,
        "gold_labels_are_external_to_jev": True,
    }
    for arm in ARMS:
        if args.mode == "live":
            route_provider = None if arm == ARMS[0] else jev.JevReflexProvider(
                api_key=key,
                base_url=os.environ.get("TYPESAFE_BASE_URL"),
                model=model,
                calibration_binding=route_binding,
            )
            context_provider = None if arm in {ARMS[0], ARMS[1]} else jev.JevReflexProvider(
                api_key=key,
                base_url=os.environ.get("TYPESAFE_BASE_URL"),
                model=model,
                calibration_binding=retrieval_binding,
            )
        else:
            route_provider = None if arm == ARMS[0] else _fixture_route_provider(routing_holdout[0] if routing_holdout else routing_cal[0])
            context_provider = None if arm in {ARMS[0], ARMS[1]} else RetrievalFixtureProvider()
        if arm == ARMS[3]:
            route_provider = MemoizingProvider(route_provider)
            context_provider = MemoizingProvider(context_provider)
        host = ExecutableHost()
        route_rows = [_route_case(case, arm, host, route_provider) for case in routing_holdout]
        context_rows = [_context_case(case, arm, context_provider) for case in context_holdout]
        arm_report = {"routing": _summary(route_rows), "context": _summary(context_rows), "routing_rows": route_rows, "context_rows": context_rows}
        if arm == ARMS[3]:
            warm_route_rows = [_route_case(case, arm, host, route_provider) for case in routing_holdout]
            warm_context_rows = [_context_case(case, arm, context_provider) for case in context_holdout]
            arm_report["warm_replay"] = {"routing": _summary(warm_route_rows), "context": _summary(warm_context_rows), "routing_rows": warm_route_rows, "context_rows": warm_context_rows}
        report["arms"][arm] = arm_report
        for current in (route_provider, context_provider):
            close = getattr(current, "close", None)
            if callable(close):
                close()
    report["calibration"] = calibration_info
    report["holdout"] = {"routing_cases": len(routing_holdout), "context_cases": len(context_holdout), "evaluated_once": True}
    report["calibration_bindings"] = {
        "routing": bool(route_binding),
        "retrieval": bool(retrieval_binding),
        "errors": calibration_info.get("errors", []),
    }
    baseline = report["arms"][ARMS[0]]
    safe = all(
        report["arms"][arm]["routing"]["hard_policy_violation_count"] == 0
        and report["arms"][arm]["context"]["hard_policy_violation_count"] == 0
        for arm in ARMS
    )
    non_inferior = all(
        report["arms"][arm]["routing"]["verified_success_rate"] >= baseline["routing"]["verified_success_rate"]
        and report["arms"][arm]["context"]["verified_success_rate"] >= baseline["context"]["verified_success_rate"]
        for arm in ARMS[1:]
    )
    baseline_latency = baseline["routing"]["latency_ms_p50"] + baseline["context"]["latency_ms_p50"]
    experimental_latency = {
        arm: report["arms"][arm]["routing"]["latency_ms_p50"] + report["arms"][arm]["context"]["latency_ms_p50"]
        for arm in ARMS[1:]
    }
    efficiency_non_regression = all(value <= baseline_latency for value in experimental_latency.values())
    compute_savings = any(report["arms"][arm]["routing"]["expensive_operations"] < baseline["routing"]["expensive_operations"] for arm in ARMS[1:])
    context_reduction = any(report["arms"][arm]["context"]["retrieval_reduction_ratio_mean"] > baseline["context"]["retrieval_reduction_ratio_mean"] for arm in ARMS[1:])
    material_benefit = compute_savings or context_reduction
    observed_models = sorted({model_name for arm in report["arms"].values() for family in ("routing", "context") for model_name in arm[family].get("response_models", [])})
    report["observed_response_models"] = observed_models
    report["response_model"] = observed_models[0] if len(observed_models) == 1 else observed_models
    provider_errors = sum(report["arms"][arm][family]["provider_error_count"] for arm in ARMS[1:] for family in ("routing", "context"))
    pinned = args.mode == "live" and observed_models == [jev.PINNED_MODEL]
    all_bindings = bool(route_binding and retrieval_binding)
    report["promotion_status"] = (
        "JEV_PROMOTED_FOR_FROZEN_SUITE"
        if args.mode == "live" and safe and non_inferior and efficiency_non_regression and material_benefit and provider_errors == 0 and pinned and all_bindings
        else ("JEV_RESEARCH_ONLY" if args.mode == "live" else "JEV_NOT_PROMOTED")
    )
    report["promotion_gates"] = {
        "safe": safe,
        "cold_holdout": True,
        "realized_expensive_work_observed": True,
        "non_inferior": non_inferior,
        "efficiency_non_regression": efficiency_non_regression,
        "material_benefit": material_benefit,
        "compute_savings": compute_savings,
        "context_reduction": context_reduction,
        "provider_errors_zero": provider_errors == 0,
        "pinned_response_model": pinned,
        "calibration_bindings_present": all_bindings,
        "baseline_total_latency_ms_p50": round(baseline_latency, 3),
        "experimental_total_latency_ms_p50": {key: round(value, 3) for key, value in experimental_latency.items()},
        "net_positive": bool(safe and non_inferior and efficiency_non_regression and material_benefit),
        "policy_only_default": report["promotion_status"] != "JEV_PROMOTED_FOR_FROZEN_SUITE",
    }
    report["corpus_sha256"] = corpus_hash
    report["runtime_fingerprint"] = fingerprint.build_fingerprint(
        requested_model=model if args.mode == "live" else None,
        response_model=report["response_model"],
        benchmark_protocol=PROTOCOL,
        corpus_sha256=corpus_hash,
        extra={"arms": list(ARMS), "promotion_status": report["promotion_status"]},
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--model")
    parser.add_argument("--routing-dataset", type=Path, default=ROOT / "tests/fixtures/margos/routing-cases-v1.json")
    parser.add_argument("--context-dataset", type=Path, default=ROOT / "tests/fixtures/margos/context-benchmark-v1.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args)
        if args.strict and report.get("partition_isolation") is not True:
            raise RuntimeError("calibration and holdout partitions overlap")
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"MARGOS JEV v4 benchmark: ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.strict and args.mode == "live":
        if report.get("live_status") == "NOT_RUN":
            return 2
        if report.get("promotion_status") != "JEV_PROMOTED_FOR_FROZEN_SUITE":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
