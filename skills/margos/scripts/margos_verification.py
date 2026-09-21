#!/usr/bin/env python3
"""Deterministic Verification Governor for MARGOS.

This module is deliberately separate from ``margos_value`` and the routing
question set.  Execution opportunities describe interchangeable routes.  A
verification opportunity describes independent unresolved claims whose
expensive verifiers may be selectively dispatched.  Jev can help choose the
latter, but it never owns evidence state, Policy priority, or final report
ordering.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

ROOT = Path(__file__).resolve().parents[1]
QUESTION_DOC = json.loads((ROOT / "contracts/verification-question-set-v1.json").read_text(encoding="utf-8"))
THRESHOLD_DOC = json.loads((ROOT / "contracts/verification-threshold-policy-v1.json").read_text(encoding="utf-8"))

CANDIDATE_VERSION = "margos-verification-candidate/v1"
OPPORTUNITY_VERSION = "margos-verification-opportunity/v1"
PLAN_VERSION = "margos-verification-plan/v1"
RECEIPT_VERSION = "margos-verification-receipt/v1"
REQUEST_VERSION = "margos-verification-reflex-request/v1"
RESULT_VERSION = "margos-verification-reflex-result/v1"
COMPOSER_VERSION = "margos-verification-composer/v1"
PROJECTION_VERSION = "margos-jev-verification-projection/v1"
UNRESOLVED_STATES = frozenset({"UNVERIFIED", "INCONCLUSIVE"})
FINAL_FINDING_STATES = frozenset({"VERIFIED", "UNVERIFIED", "FALSIFIED", "INCONCLUSIVE"})
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bTYPESAFE_API_KEY\s*="),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}"),
)


class VerificationContractError(ValueError):
    """Raised when a verification contract would weaken a safety boundary."""


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def question_set_sha256() -> str:
    return sha256(QUESTION_DOC)


def threshold_policy_sha256() -> str:
    return sha256(THRESHOLD_DOC)


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationContractError(f"{name} must be a non-empty string")
    value = value.strip()
    if len(value) > limit:
        raise VerificationContractError(f"{name} exceeds {limit} characters")
    return value


def _hash(value: Any, name: str) -> str:
    value = _text(value, name, 128)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise VerificationContractError(f"{name} must be a lowercase SHA-256")
    return value


def _nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise VerificationContractError(f"{name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise VerificationContractError(f"{name} must be numeric") from None
    if number < 0:
        raise VerificationContractError(f"{name} must be non-negative")
    return number


def _safe_summary(value: Any) -> str:
    summary = _text(value, "claim_summary", 600)
    if any(pattern.search(summary) for pattern in _SECRET_PATTERNS):
        raise VerificationContractError("claim_summary is suppressed by secret screening")
    return summary


def _cost(raw: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise VerificationContractError("verifier.cost must be an object")
    return {
        "latency_ms_p50": _nonnegative(raw.get("latency_ms_p50", 0), "latency_ms_p50"),
        "latency_ms_p95": _nonnegative(raw.get("latency_ms_p95", 0), "latency_ms_p95"),
        "model_tokens": _nonnegative(raw.get("model_tokens", 0), "model_tokens"),
        "money_microunits": _nonnegative(raw.get("money_microunits", 0), "money_microunits"),
        "verification_cost_units": _nonnegative(raw.get("verification_cost_units", 0), "verification_cost_units"),
    }


def normalize_verification_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise VerificationContractError("verification candidate must be an object")
    state = raw.get("evidence_state")
    if state == "VERIFIED":
        raise VerificationContractError("VERIFIED findings cannot enter optional VerificationOpportunity")
    if state not in UNRESOLVED_STATES:
        raise VerificationContractError("verification candidate must be unresolved")
    verifier = raw.get("verifier")
    provenance = raw.get("discovery_provenance")
    if not isinstance(verifier, Mapping) or not isinstance(provenance, Mapping):
        raise VerificationContractError("candidate verifier and discovery_provenance are required")
    mandatory = raw.get("mandatory_by_policy", False)
    remote_allowed = raw.get("remote_semantic_allowed", False)
    if not isinstance(mandatory, bool) or not isinstance(remote_allowed, bool):
        raise VerificationContractError("candidate policy flags must be boolean")
    return {
        "schema_version": CANDIDATE_VERSION,
        "candidate_id": _text(raw.get("candidate_id"), "candidate_id", 128),
        "claim_fingerprint": _hash(raw.get("claim_fingerprint"), "claim_fingerprint"),
        "claim_summary": _safe_summary(raw.get("claim_summary")),
        "evidence_state": state,
        "evidence_kind": _text(raw.get("evidence_kind"), "evidence_kind", 64),
        "policy_priority_rank": int(raw.get("policy_priority_rank", 0)),
        "mandatory_by_policy": mandatory,
        "remote_semantic_allowed": remote_allowed,
        "verifier": {
            "operation_id": _text(verifier.get("operation_id"), "verifier.operation_id", 128),
            "kind": _text(verifier.get("kind"), "verifier.kind", 128),
            "host_capability_proof": _text(verifier.get("host_capability_proof"), "verifier.host_capability_proof", 512),
            "parallel_group": _text(verifier.get("parallel_group"), "verifier.parallel_group", 64),
            "cost": _cost(verifier.get("cost", {})),
        },
        "discovery_provenance": {
            "provenance_kind": _text(provenance.get("provenance_kind"), "discovery_provenance.provenance_kind", 128),
            "source_sha256": _hash(provenance.get("source_sha256"), "discovery_provenance.source_sha256"),
            "extractor_version": _text(provenance.get("extractor_version"), "discovery_provenance.extractor_version", 128),
            **({"locator": _text(provenance["locator"], "discovery_provenance.locator", 512)} if provenance.get("locator") else {}),
        },
    }


def _proof_available(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {"false", "none", "unproven"}


def normalize_verification_opportunity(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise VerificationContractError("verification opportunity must be an object")
    candidates_raw = raw.get("optional_candidates", [])
    mandatory = raw.get("mandatory_candidate_ids", [])
    budget = raw.get("budget", {})
    if not isinstance(candidates_raw, list) or not isinstance(mandatory, list) or not isinstance(budget, Mapping):
        raise VerificationContractError("verification opportunity has invalid collections")
    if any(not isinstance(value, str) or not value for value in mandatory) or len(set(mandatory)) != len(mandatory):
        raise VerificationContractError("mandatory_candidate_ids must be unique strings")
    candidates = [normalize_verification_candidate(item) for item in candidates_raw]
    ids = [item["candidate_id"] for item in candidates]
    if len(ids) != len(set(ids)):
        raise VerificationContractError("optional candidate IDs must be unique")
    overlap = set(ids).intersection(mandatory)
    if overlap:
        raise VerificationContractError(f"mandatory candidates cannot be optional: {sorted(overlap)}")
    if any(item["mandatory_by_policy"] for item in candidates):
        raise VerificationContractError("mandatory_by_policy candidates belong in mandatory_candidate_ids, not optional_candidates")
    if any(not item["remote_semantic_allowed"] for item in candidates):
        raise VerificationContractError("remote-semantic-disabled candidates cannot enter the JEV optional projection")
    return {
        "schema_version": OPPORTUNITY_VERSION,
        "opportunity_id": _text(raw.get("opportunity_id"), "opportunity_id", 128),
        "task_objective": _text(raw.get("task_objective"), "task_objective", 2000),
        "budget": {
            "max_optional_candidates": max(0, int(budget.get("max_optional_candidates", 0))),
            "max_verification_cost_units": _nonnegative(budget.get("max_verification_cost_units", 0), "max_verification_cost_units"),
            "max_wall_clock_ms": _nonnegative(budget.get("max_wall_clock_ms", 0), "max_wall_clock_ms"),
        },
        "mandatory_candidate_ids": list(mandatory),
        "optional_candidates": candidates,
        "host_selective_dispatch_proof": raw.get("host_selective_dispatch_proof", ""),
        "critical_path_model_version": _text(raw.get("critical_path_model_version"), "critical_path_model_version", 128),
        "jev_latency_budget_ms": _nonnegative(raw.get("jev_latency_budget_ms", 0), "jev_latency_budget_ms"),
        "cost_model_version": _text(raw.get("cost_model_version"), "cost_model_version", 128),
        "cache_lookup_status": raw.get("cache_lookup_status", "NOT_CHECKED"),
        "calibration_binding_hash": _hash(raw.get("calibration_binding_hash"), "calibration_binding_hash"),
        "optimization_objective": raw.get("optimization_objective", "LATENCY_AND_COST"),
    }


def _critical_path(candidates: Sequence[Mapping[str, Any]]) -> float:
    groups: dict[str, float] = {}
    for candidate in candidates:
        verifier = candidate["verifier"]
        group = str(verifier["parallel_group"])
        groups[group] = max(groups.get(group, 0.0), float(verifier["cost"]["latency_ms_p95"]))
    return sum(groups.values())


def _cost_units(candidates: Sequence[Mapping[str, Any]]) -> float:
    return sum(float(item["verifier"]["cost"]["verification_cost_units"]) for item in candidates)


@dataclass(frozen=True)
class VerificationValueDecision:
    decision: str
    reason: str
    detail: str
    opportunity_id: str
    optional_candidate_ids: tuple[str, ...]
    avoidable_critical_path_ms: float
    avoidable_cost_units: float
    jev_latency_budget_ms: float
    host_can_exploit_result: bool
    calibration_status: str

    @property
    def admitted(self) -> bool:
        return self.decision == "CALL_REFLEX"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "margos-verification-value-of-call/v1",
            "decision": self.decision,
            "reason": self.reason,
            "detail": self.detail,
            "opportunity_id": self.opportunity_id,
            "optional_candidate_ids": list(self.optional_candidate_ids),
            "avoidable_critical_path_ms": self.avoidable_critical_path_ms,
            "avoidable_cost_units": self.avoidable_cost_units,
            "jev_latency_budget_ms": self.jev_latency_budget_ms,
            "host_can_exploit_result": self.host_can_exploit_result,
            "calibration_status": self.calibration_status,
        }


def evaluate_verification_value_of_call(
    opportunity: Mapping[str, Any],
    *,
    policy_forced: bool = False,
    provider_enabled: bool = True,
    calibration_status: str = "CALIBRATED_FOR_FROZEN_SUITE",
) -> VerificationValueDecision:
    normalized = normalize_verification_opportunity(opportunity)
    optional = normalized["optional_candidates"]
    ids = tuple(item["candidate_id"] for item in optional)
    base = dict(
        opportunity_id=normalized["opportunity_id"],
        optional_candidate_ids=ids,
        avoidable_critical_path_ms=0.0,
        avoidable_cost_units=0.0,
        jev_latency_budget_ms=normalized["jev_latency_budget_ms"],
        host_can_exploit_result=_proof_available(normalized["host_selective_dispatch_proof"]),
        calibration_status=calibration_status,
    )
    if not provider_enabled:
        return VerificationValueDecision("SKIP", "SKIP_DISABLED", "Verification Reflex is disabled or not configured.", **base)
    if policy_forced:
        return VerificationValueDecision("SKIP", "SKIP_POLICY_SUFFICIENT", "Policy fixed the mandatory verification set.", **base)
    if not optional:
        return VerificationValueDecision("SKIP", "SKIP_NO_MATERIAL_ROUTE_DELTA", "No unresolved optional verification candidate exists.", **base)
    if not base["host_can_exploit_result"]:
        return VerificationValueDecision("SKIP", "SKIP_HOST_CANNOT_EXPLOIT_RESULT", "Host has not proven selective verifier dispatch.", **base)
    if normalized["cache_lookup_status"] == "HIT":
        return VerificationValueDecision("SKIP", "SKIP_CACHE_HIT", "A validated verification plan is already cached.", **base)
    if calibration_status in {"STALE", "UNCALIBRATED", "UNKNOWN"}:
        return VerificationValueDecision("SKIP", "SKIP_STALE_CALIBRATION", "Active optimization requires a current calibration binding.", **base)
    capacity = normalized["budget"]["max_optional_candidates"]
    if capacity <= 0 or normalized["budget"]["max_verification_cost_units"] <= 0 or normalized["jev_latency_budget_ms"] <= 0:
        return VerificationValueDecision("SKIP", "SKIP_BUDGET", "The declared bounded verification or Reflex budget is empty.", **base)
    if capacity >= len(optional):
        return VerificationValueDecision("SKIP", "SKIP_NO_MATERIAL_ROUTE_DELTA", "No optional verifier can be avoided under the declared capacity.", **base)
    ordered = sorted(optional, key=lambda item: (int(item["policy_priority_rank"]), item["candidate_id"]))
    kept = ordered[:capacity]
    skipped = ordered[capacity:]
    avoidable_path = max(0.0, _critical_path(optional) - _critical_path(kept))
    avoidable_cost = _cost_units(skipped)
    base.update(avoidable_critical_path_ms=avoidable_path, avoidable_cost_units=avoidable_cost)
    if avoidable_path <= normalized["jev_latency_budget_ms"] and avoidable_cost <= 0:
        return VerificationValueDecision("SKIP", "SKIP_BUDGET", "Avoidable critical-path work cannot pay the Reflex budget.", **base)
    return VerificationValueDecision("CALL_REFLEX", "CALL_REFLEX", "Selective dispatch can avoid material verifier work on the critical path.", **base)


def verification_questions(candidate_count: int) -> tuple[dict[str, Any], ...]:
    if candidate_count <= 0:
        return ()
    template = QUESTION_DOC["question_template"]
    return tuple({
        "id": f"verification_{index:03d}",
        "kind": "noul",
        "candidate_index": index,
        "instructions": template["instructions"].replace("INDEX", str(index)),
        "true": template["criteria"]["true"],
        "false": template["criteria"]["false"],
    } for index in range(candidate_count))


def build_verification_request(opportunity: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_verification_opportunity(opportunity)
    return {
        "schema_version": REQUEST_VERSION,
        "task_objective": normalized["task_objective"],
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "claim_summary": item["claim_summary"],
                "evidence_state": item["evidence_state"],
                "evidence_kind": item["evidence_kind"],
                "policy_priority_rank": item["policy_priority_rank"],
                "verifier": {"kind": item["verifier"]["kind"], "parallel_group": item["verifier"]["parallel_group"]},
            }
            for item in normalized["optional_candidates"]
        ],
        "question_set_sha256": question_set_sha256(),
        "threshold_policy_sha256": threshold_policy_sha256(),
        "projection_version": PROJECTION_VERSION,
        "calibration_binding_hash": normalized["calibration_binding_hash"],
    }


def deterministic_verification_plan(opportunity: Mapping[str, Any], reason: str = "DETERMINISTIC_FALLBACK") -> dict[str, Any]:
    normalized = normalize_verification_opportunity(opportunity)
    capacity = normalized["budget"]["max_optional_candidates"]
    ordered = sorted(normalized["optional_candidates"], key=lambda item: (int(item["policy_priority_rank"]), item["candidate_id"]))
    selected = [item["candidate_id"] for item in ordered[:capacity]]
    skipped = [item["candidate_id"] for item in ordered[capacity:]]
    return {
        "schema_version": PLAN_VERSION,
        "opportunity_id": normalized["opportunity_id"],
        "mandatory_candidate_ids": list(normalized["mandatory_candidate_ids"]),
        "selected_optional_candidate_ids": selected,
        "skipped_optional_candidate_ids": skipped,
        "fallback_used": True,
        "fallback_reason": reason,
        "composer_version": COMPOSER_VERSION,
        "selection_scores": {},
    }


def validate_verification_result(result: Mapping[str, Any], opportunity: Mapping[str, Any]) -> dict[str, float]:
    normalized = normalize_verification_opportunity(opportunity)
    if not isinstance(result, Mapping) or result.get("schema_version") != RESULT_VERSION:
        raise VerificationContractError("invalid Verification Reflex result schema")
    provider = result.get("provider", {})
    if not isinstance(provider, Mapping) or provider.get("status") == "ERROR":
        raise VerificationContractError("Verification Reflex provider failed")
    if result.get("question_set_sha256") != question_set_sha256():
        raise VerificationContractError("Verification question-set hash mismatch")
    answers = result.get("answers")
    if not isinstance(answers, Mapping):
        raise VerificationContractError("Verification Reflex result has no answers")
    ids = [item["candidate_id"] for item in normalized["optional_candidates"]]
    if set(answers) != set(ids):
        raise VerificationContractError("Verification Reflex answers must cover exactly optional candidates")
    values: dict[str, float] = {}
    for candidate_id in ids:
        answer = answers[candidate_id]
        raw = answer.get("probability") if isinstance(answer, Mapping) else None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not 0 <= float(raw) <= 1:
            raise VerificationContractError(f"invalid verification probability for {candidate_id}")
        values[candidate_id] = float(raw)
    return values


def compose_verification_plan(
    opportunity: Mapping[str, Any],
    probabilities: Mapping[str, float] | None = None,
    *,
    fallback_reason: str = "DETERMINISTIC_FALLBACK",
) -> dict[str, Any]:
    normalized = normalize_verification_opportunity(opportunity)
    if probabilities is None:
        return deterministic_verification_plan(normalized, fallback_reason)
    optional = normalized["optional_candidates"]
    ids = {item["candidate_id"] for item in optional}
    if set(probabilities) != ids:
        return deterministic_verification_plan(normalized, "INVALID_REFLEX_RESULT")
    threshold = float(THRESHOLD_DOC["noul_selection_threshold"])
    for candidate_id, probability in probabilities.items():
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 <= float(probability) <= 1:
            return deterministic_verification_plan(normalized, "INVALID_REFLEX_RESULT")
    ordered = sorted(
        (item for item in optional if float(probabilities[item["candidate_id"]]) >= threshold),
        key=lambda item: (int(item["policy_priority_rank"]), -float(probabilities[item["candidate_id"]]), item["candidate_id"]),
    )
    capacity = normalized["budget"]["max_optional_candidates"]
    selected = [item["candidate_id"] for item in ordered[:capacity]]
    skipped = [item["candidate_id"] for item in optional if item["candidate_id"] not in selected]
    return {
        "schema_version": PLAN_VERSION,
        "opportunity_id": normalized["opportunity_id"],
        "mandatory_candidate_ids": list(normalized["mandatory_candidate_ids"]),
        "selected_optional_candidate_ids": selected,
        "skipped_optional_candidate_ids": skipped,
        "fallback_used": False,
        "composer_version": COMPOSER_VERSION,
        "selection_scores": {key: float(value) for key, value in probabilities.items()},
    }


def _operation_ids(plan: Mapping[str, Any], opportunity: Mapping[str, Any]) -> list[str]:
    by_candidate = {item["candidate_id"]: item["verifier"]["operation_id"] for item in opportunity["optional_candidates"]}
    candidate_ids = list(plan["mandatory_candidate_ids"]) + list(plan["selected_optional_candidate_ids"])
    return [by_candidate.get(candidate_id, candidate_id) for candidate_id in candidate_ids]


class VerificationDispatcher(Protocol):
    def dispatch_selected(self, *, candidate_ids: Sequence[str], operation_ids: Sequence[str], plan: Mapping[str, Any]) -> Mapping[str, Any]: ...


def validate_dispatch_receipt(plan: Mapping[str, Any], opportunity: Mapping[str, Any], dispatch_receipt: Mapping[str, Any]) -> None:
    expected = set(_operation_ids(plan, opportunity))
    actual = dispatch_receipt.get("dispatched_operation_ids", dispatch_receipt.get("operation_ids"))
    if not isinstance(actual, list) or set(actual) != expected or len(actual) != len(expected):
        raise VerificationContractError("host dispatch does not equal VerificationPlan selected IDs")
    if any(item not in actual for item in [*plan["mandatory_candidate_ids"]]):
        # Mandatory candidate IDs may be mapped by a host; the set comparison above
        # is authoritative. This branch only rejects an impossible empty receipt.
        if not actual:
            raise VerificationContractError("mandatory verification was not dispatched")


def dispatch_verification_plan(
    plan: Mapping[str, Any], opportunity: Mapping[str, Any], dispatcher: VerificationDispatcher
) -> dict[str, Any]:
    operation_ids = _operation_ids(plan, opportunity)
    candidate_ids = list(plan["mandatory_candidate_ids"]) + list(plan["selected_optional_candidate_ids"])
    raw = dispatcher.dispatch_selected(candidate_ids=candidate_ids, operation_ids=operation_ids, plan=plan)
    if not isinstance(raw, Mapping):
        raise VerificationContractError("VerificationDispatcher must return a receipt object")
    validate_dispatch_receipt(plan, opportunity, raw)
    return dict(raw)


def validate_verifier_readback(candidate: Mapping[str, Any], readback: Mapping[str, Any]) -> dict[str, Any]:
    """Accept a verifier transition only with an identity-bound proof."""
    normalized = normalize_verification_candidate(candidate)
    if not isinstance(readback, Mapping):
        raise VerificationContractError("verifier readback must be an object")
    operation_id = readback.get("verifier_operation_id")
    state = readback.get("evidence_state")
    proof_hash = readback.get("proof_hash")
    evidence_refs = readback.get("evidence_refs")
    if operation_id != normalized["verifier"]["operation_id"]:
        raise VerificationContractError("verifier readback operation identity mismatch")
    if state not in {"VERIFIED", "FALSIFIED", "INCONCLUSIVE"}:
        raise VerificationContractError("verifier readback has invalid evidence state")
    _hash(proof_hash, "proof_hash")
    if not isinstance(evidence_refs, list) or not evidence_refs or any(not isinstance(item, str) or not item for item in evidence_refs):
        raise VerificationContractError("verifier readback requires evidence references")
    updated = dict(normalized)
    updated["evidence_state"] = state
    updated["verification"] = {
        "verifier_operation_id": operation_id,
        "proof_hash": proof_hash,
        "evidence_refs": list(evidence_refs),
    }
    return updated


class FindingLedger:
    """Small deterministic evidence ledger; Jev has no write access to it."""

    def __init__(self, findings: Sequence[Mapping[str, Any]] = ()):
        self._findings: dict[str, dict[str, Any]] = {}
        for finding in findings:
            self.add(finding)

    def add(self, finding: Mapping[str, Any]) -> None:
        if not isinstance(finding, Mapping):
            raise VerificationContractError("finding must be an object")
        finding_id = _text(finding.get("finding_id"), "finding_id", 128)
        state = finding.get("evidence_state")
        if state not in FINAL_FINDING_STATES:
            raise VerificationContractError("finding has invalid evidence state")
        if finding_id in self._findings:
            raise VerificationContractError("finding IDs are immutable and unique")
        self._findings[finding_id] = dict(finding)

    def apply_readback(self, candidate: Mapping[str, Any], readback: Mapping[str, Any]) -> dict[str, Any]:
        updated = validate_verifier_readback(candidate, readback)
        finding_id = updated["candidate_id"]
        existing = self._findings.get(finding_id)
        if existing is not None and existing.get("evidence_state") == "VERIFIED":
            raise VerificationContractError("a verified finding cannot be demoted by verifier readback")
        record = dict(existing or {})
        record.update({
            "finding_id": finding_id,
            "evidence_state": updated["evidence_state"],
            "policy_priority_rank": updated["policy_priority_rank"],
            "claim_fingerprint": updated["claim_fingerprint"],
            "evidence_refs": list(updated["verification"]["evidence_refs"]),
            "proof_hash": updated["verification"]["proof_hash"],
            "provenance": dict(updated["discovery_provenance"]),
        })
        self._findings[finding_id] = record
        return dict(record)

    def final_report(self) -> list[dict[str, Any]]:
        return final_finding_order(list(self._findings.values()))


def govern_verification(
    opportunity: Mapping[str, Any],
    provider: Any = None,
    *,
    provider_enabled: bool = True,
    calibration_status: str = "CALIBRATED_FOR_FROZEN_SUITE",
    policy_forced: bool = False,
    shadow: bool = False,
) -> dict[str, Any]:
    """Run one bounded planning round; dispatch remains an explicit host step."""
    normalized = normalize_verification_opportunity(opportunity)
    enabled = provider_enabled and provider is not None
    admission = evaluate_verification_value_of_call(
        normalized,
        policy_forced=policy_forced,
        provider_enabled=enabled,
        calibration_status=calibration_status,
    )
    plan = deterministic_verification_plan(normalized, admission.reason)
    provider_result: Mapping[str, Any] | None = None
    provider_count = 0
    if admission.admitted:
        request = build_verification_request(normalized)
        questions = verification_questions(len(normalized["optional_candidates"]))
        try:
            provider_result = provider.evaluate(request, questions)
            provider_meta = provider_result.get("provider", {}) if isinstance(provider_result, Mapping) else {}
            provider_count = int(provider_meta.get("network_request_count", 1) or 0) if isinstance(provider_meta, Mapping) else 1
            if provider_count > 1:
                raise VerificationContractError("provider exceeded one request per planning round")
            scores = validate_verification_result(provider_result, normalized)
            if not shadow:
                plan = compose_verification_plan(normalized, scores)
        except Exception as exc:
            plan = deterministic_verification_plan(normalized, f"{type(exc).__name__}: {exc}")
    receipt = make_verification_receipt(
        normalized,
        plan,
        admission,
        provider_request_count=provider_count,
        provider=(provider_result.get("provider", {}) if isinstance(provider_result, Mapping) else {}),
    )
    return {"opportunity": normalized, "admission": admission.as_dict(), "plan": plan, "receipt": receipt, "reflex_result": provider_result}


def make_verification_receipt(
    opportunity: Mapping[str, Any],
    plan: Mapping[str, Any],
    admission: VerificationValueDecision,
    *,
    provider_request_count: int = 0,
    dispatch_receipt: Mapping[str, Any] | None = None,
    provider: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_verification_opportunity(opportunity)
    if provider_request_count not in {0, 1}:
        raise VerificationContractError("at most one Verification Reflex request is allowed per planning round")
    dispatched = list((dispatch_receipt or {}).get("dispatched_operation_ids", []))
    if dispatch_receipt is not None:
        validate_dispatch_receipt(plan, normalized, dispatch_receipt)
    return {
        "schema_version": RECEIPT_VERSION,
        "opportunity_id": normalized["opportunity_id"],
        "admission": {"decision": admission.decision, "reason": admission.reason, "detail": admission.detail},
        "mandatory_candidate_ids": list(plan["mandatory_candidate_ids"]),
        "selected_optional_candidate_ids": list(plan["selected_optional_candidate_ids"]),
        "skipped_optional_candidate_ids": list(plan["skipped_optional_candidate_ids"]),
        "dispatched_operation_ids": dispatched,
        "provider_request_count": provider_request_count,
        "dispatch_matches_plan": dispatch_receipt is not None,
        "provider": dict(provider or {}),
        "report_protection": {"verified_candidates_excluded_from_optional": True, "jev_did_not_rank_findings": True},
        "fingerprints": {
            "question_set_sha256": question_set_sha256(),
            "threshold_policy_sha256": threshold_policy_sha256(),
            "projection_version": PROJECTION_VERSION,
            "calibration_binding_hash": normalized["calibration_binding_hash"],
            "cost_model_version": normalized["cost_model_version"],
        },
    }


def final_finding_order(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Order the final report without consulting Jev probabilities."""
    normalized = []
    for finding in findings:
        if not isinstance(finding, Mapping) or finding.get("evidence_state") not in FINAL_FINDING_STATES:
            raise VerificationContractError("invalid final finding state")
        normalized.append(dict(finding))
    return sorted(
        normalized,
        key=lambda item: (
            0 if item["evidence_state"] == "VERIFIED" else 1 if item["evidence_state"] == "INCONCLUSIVE" else 2 if item["evidence_state"] == "UNVERIFIED" else 3,
            int(item.get("policy_priority_rank", 0)),
            str(item.get("finding_id", "")),
        ),
    )
