#!/usr/bin/env python3
"""Deterministic value-of-call admission for MARGOS Reflex decisions."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

VERSION = "margos-value-of-call/v1"
RECEIPT_VERSION = "margos-value-of-call-receipt/v1"
OPPORTUNITY_VERSION = "margos-execution-opportunity/v1"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValueOfCallDecision:
    decision: str
    reason: str
    detail: str
    opportunity_id: str
    operation_that_can_be_avoided: str | None
    fallback_operation_id: str | None
    candidate_operation_ids: tuple[str, ...]
    max_possible_saving: Mapping[str, float]
    jev_latency_budget_ms: float
    host_can_exploit_result: bool
    critical_path: bool
    cache_lookup_status: str
    policy_fallback: str
    calibration_status: str

    @property
    def admitted(self) -> bool:
        return self.decision == "CALL_REFLEX"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECEIPT_VERSION,
            "decision": self.decision,
            "reason": self.reason,
            "detail": self.detail,
            "opportunity_id": self.opportunity_id,
            "operation_that_can_be_avoided": self.operation_that_can_be_avoided,
            "fallback_operation_id": self.fallback_operation_id,
            "candidate_operation_ids": list(self.candidate_operation_ids),
            "max_possible_saving": dict(self.max_possible_saving),
            "jev_latency_budget_ms": self.jev_latency_budget_ms,
            "host_can_exploit_result": self.host_can_exploit_result,
            "critical_path": self.critical_path,
            "cache_lookup_status": self.cache_lookup_status,
            "policy_fallback": self.policy_fallback,
            "calibration_status": self.calibration_status,
        }


def _cost(candidate: Mapping[str, Any]) -> Mapping[str, float]:
    raw = candidate.get("cost", {})
    return {key: float(raw.get(key, 0.0)) for key in (
        "latency_ms_p50", "latency_ms_p95", "model_tokens", "money_microunits", "retrieval_bytes", "verification_cost_units"
    )}


def normalize_opportunity(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("execution opportunity must be an object")
    candidates = raw.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("execution opportunity candidates must be a list")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("execution opportunity candidate must be an object")
        operation_id = str(candidate.get("operation_id", "")).strip()
        if not operation_id or operation_id in ids:
            raise ValueError("execution opportunity operation IDs must be unique")
        ids.add(operation_id)
        cost = _cost(candidate)
        normalized.append({
            "operation_id": operation_id,
            "coordination": str(candidate.get("coordination", "DIRECT")),
            "compute": str(candidate.get("compute", "BALANCED_EXEC")),
            "role": candidate.get("role"),
            "host_capability_proof": str(candidate.get("host_capability_proof", "")),
            "cost": cost,
        })
    opportunity_id = str(raw.get("opportunity_id", "")).strip()
    fallback = str(raw.get("fallback_operation_id", "")).strip()
    if not opportunity_id or not fallback:
        raise ValueError("execution opportunity requires IDs")
    if fallback not in ids:
        raise ValueError("fallback_operation_id must identify a candidate")
    return {
        "schema_version": OPPORTUNITY_VERSION,
        "opportunity_id": opportunity_id,
        "fallback_operation_id": fallback,
        "candidates": normalized,
        "critical_path": bool(raw.get("critical_path", True)),
        "host_can_exploit_result": bool(raw.get("host_can_exploit_result", False)),
        "jev_latency_budget_ms": max(0.0, float(raw.get("jev_latency_budget_ms", 0.0))),
        "jev_cost_budget_microunits": max(0.0, float(raw.get("jev_cost_budget_microunits", 0.0))),
        "cost_model_version": str(raw.get("cost_model_version", "margos-cost/v1")),
        "cache_lookup_status": str(raw.get("cache_lookup_status", "NOT_CHECKED")),
    }


def evaluate_value_of_call(
    opportunity: Mapping[str, Any] | None,
    *,
    policy_sufficient: bool = False,
    provider_enabled: bool = True,
    calibration_status: str = "UNKNOWN",
) -> ValueOfCallDecision:
    if not provider_enabled:
        reason, detail = "SKIP_DISABLED", "Reflex provider is disabled or not configured."
    elif policy_sufficient:
        reason, detail = "SKIP_POLICY_SUFFICIENT", "Deterministic Policy fixes the route or execution must halt."
    elif opportunity is None:
        reason, detail = "SKIP_NO_AVOIDABLE_OPERATION", "No concrete not-yet-executed operation is bound to this decision."
    else:
        normalized = normalize_opportunity(opportunity)
        assert normalized is not None
        candidates = normalized["candidates"]
        fallback_id = normalized["fallback_operation_id"]
        fallback = next(item for item in candidates if item["operation_id"] == fallback_id)
        alternatives = [item for item in candidates if item["operation_id"] != fallback_id]
        if not normalized["host_can_exploit_result"]:
            reason, detail = "SKIP_HOST_CANNOT_EXPLOIT_RESULT", "Host capability proof does not show how the answer changes execution."
        elif not alternatives:
            reason, detail = "SKIP_NO_AVOIDABLE_OPERATION", "The opportunity has no alternate executable operation."
        else:
            best = min(alternatives, key=lambda item: item["cost"]["latency_ms_p95"])
            saving = {key: max(0.0, fallback["cost"][key] - best["cost"][key]) for key in fallback["cost"]}
            materially_different = any(value > 0 for value in saving.values())
            if not materially_different:
                reason, detail = "SKIP_NO_MATERIAL_VALUE_DELTA", "All executable candidates have equivalent cost vectors."
            elif normalized["cache_lookup_status"] == "HIT":
                reason, detail = "SKIP_CACHE_HIT", "A validated decision is already available for this canonical request."
            elif normalized["jev_latency_budget_ms"] <= 0 or saving["latency_ms_p95"] <= normalized["jev_latency_budget_ms"]:
                reason, detail = "SKIP_LATENCY_BUDGET", "The maximum latency saving cannot pay the declared JEV budget."
            elif calibration_status in {"STALE", "UNCALIBRATED"}:
                reason, detail = "SKIP_UNCALIBRATED_VALUE_MODEL", "No calibration is bound to this opportunity contract."
            else:
                reason, detail = "CALL_REFLEX", "A concrete executable alternative has calibrated material value-of-call."
            if reason == "CALL_REFLEX":
                return ValueOfCallDecision(
                    "CALL_REFLEX", reason, detail, normalized["opportunity_id"], fallback_id, fallback_id,
                    tuple(item["operation_id"] for item in alternatives), saving,
                    normalized["jev_latency_budget_ms"], True, normalized["critical_path"],
                    normalized["cache_lookup_status"], fallback_id, calibration_status,
                )
            return ValueOfCallDecision(
                "SKIP", reason, detail, normalized["opportunity_id"], fallback_id, fallback_id,
                tuple(item["operation_id"] for item in alternatives), saving,
                normalized["jev_latency_budget_ms"], normalized["host_can_exploit_result"], normalized["critical_path"],
                normalized["cache_lookup_status"], fallback_id, calibration_status,
            )
    if opportunity is None:
        return ValueOfCallDecision("SKIP", reason, detail, "UNBOUND", None, None, (), {}, 0.0, False, False, "NOT_CHECKED", "POLICY_FALLBACK", calibration_status)
    normalized = normalize_opportunity(opportunity)
    assert normalized is not None
    fallback_id = normalized["fallback_operation_id"]
    fallback = next(item for item in normalized["candidates"] if item["operation_id"] == fallback_id)
    return ValueOfCallDecision("SKIP", reason, detail, normalized["opportunity_id"], fallback_id, fallback_id, tuple(), {key: 0.0 for key in fallback["cost"]}, normalized["jev_latency_budget_ms"], normalized["host_can_exploit_result"], normalized["critical_path"], normalized["cache_lookup_status"], fallback_id, calibration_status)


def choose_sufficient_candidate(
    opportunity: Mapping[str, Any],
    probabilities: Mapping[str, float],
    threshold: float,
) -> dict[str, Any]:
    """Choose the cheapest candidate that clears a calibrated semantic threshold."""
    normalized = normalize_opportunity(opportunity)
    assert normalized is not None
    eligible = [
        item for item in normalized["candidates"]
        if float(probabilities.get(item["operation_id"], 0.0)) >= threshold
    ]
    if not eligible:
        eligible = [item for item in normalized["candidates"] if item["operation_id"] == normalized["fallback_operation_id"]]
    return min(eligible, key=lambda item: (item["cost"]["latency_ms_p95"], item["cost"]["model_tokens"], item["operation_id"]))
