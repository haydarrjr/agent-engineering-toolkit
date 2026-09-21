#!/usr/bin/env python3
"""Metadata-first Context retrieval planning and lazy payload materialization."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

RETRIEVAL_CANDIDATE_VERSION = "margos-retrieval-candidate/v1"
RETRIEVAL_PLAN_VERSION = "margos-context-retrieval-plan/v1"
PAYLOAD_ARTIFACT_VERSION = "margos-payload-artifact/v1"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PayloadArtifact:
    candidate_id: str
    content: str
    content_sha256: str
    size: Mapping[str, int]
    source: Mapping[str, Any]
    fetch: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PAYLOAD_ARTIFACT_VERSION,
            "candidate_id": self.candidate_id,
            "content": self.content,
            "content_sha256": self.content_sha256,
            "size": dict(self.size),
            "source": dict(self.source),
            "fetch": dict(self.fetch),
        }


class PayloadLoader(Protocol):
    def load_many(self, candidate_ids: Sequence[str]) -> Mapping[str, PayloadArtifact]: ...


class InMemoryPayloadLoader:
    """Deterministic fixture/host adapter for proving lazy loading semantics."""

    def __init__(self, payloads: Mapping[str, str], candidates: Mapping[str, Mapping[str, Any]] | None = None):
        self.payloads = dict(payloads)
        self.candidates = dict(candidates or {})
        self.loaded_ids: list[str] = []

    def load_many(self, candidate_ids: Sequence[str]) -> Mapping[str, PayloadArtifact]:
        started = time.perf_counter()
        result: dict[str, PayloadArtifact] = {}
        for candidate_id in candidate_ids:
            if candidate_id not in self.payloads:
                raise KeyError(f"payload not available for {candidate_id}")
            content = self.payloads[candidate_id]
            metadata = self.candidates.get(candidate_id, {})
            self.loaded_ids.append(candidate_id)
            result[candidate_id] = PayloadArtifact(
                candidate_id=candidate_id,
                content=content,
                content_sha256=_sha_text(content),
                size={"chars": len(content), "bytes": len(content.encode("utf-8")), "tokens_estimated": max(1, len(content) // 4)},
                source=dict(metadata.get("source", {})),
                fetch={"status": "AVAILABLE", "latency_ms": round((time.perf_counter() - started) * 1000.0, 3)},
            )
        return result


def normalize_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("retrieval candidate must be an object")
    candidate_id = str(raw.get("candidate_id", raw.get("item_id", ""))).strip()
    if not candidate_id:
        raise ValueError("retrieval candidate requires candidate_id")
    source = raw.get("source", {})
    if not isinstance(source, Mapping):
        raise ValueError("retrieval candidate source must be an object")
    size = raw.get("estimated_size", raw.get("size", {}))
    if not isinstance(size, Mapping):
        size = {}
    return {
        "schema_version": RETRIEVAL_CANDIDATE_VERSION,
        "candidate_id": candidate_id,
        "kind": str(raw.get("kind", "OTHER")),
        "source": {
            "tool": str(source.get("tool", "")),
            "locator": str(source.get("locator", "")),
            "content_version_if_known": source.get("content_version_if_known", source.get("content_version")),
        },
        "authority": dict(raw.get("authority", {})) if isinstance(raw.get("authority", {}), Mapping) else {},
        "evidence": dict(raw.get("evidence", {})) if isinstance(raw.get("evidence", {}), Mapping) else {},
        "estimated_size": {
            "bytes": max(0, int(size.get("bytes", size.get("chars", 0)))),
            "chars": max(0, int(size.get("chars", 0))),
            "tokens": max(0, int(size.get("tokens", size.get("tokens_estimated", 0)))),
        },
        "estimated_fetch_latency_ms": max(0.0, float(raw.get("estimated_fetch_latency_ms", 0.0))),
        "fetch_cost_class": str(raw.get("fetch_cost_class", "UNKNOWN")),
        "cache_locality": str(raw.get("cache_locality", "UNKNOWN")),
        "mandatory_by_policy": bool(raw.get("mandatory_by_policy", False)),
        "replay": dict(raw.get("replay", {})) if isinstance(raw.get("replay", {}), Mapping) else {},
    }


def build_metadata_state(
    task: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized = [normalize_candidate(candidate) for candidate in candidates]
    ids = [item["candidate_id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("retrieval candidate IDs must be unique")
    return {
        "schema_version": "margos-retrieval-state/v1",
        "task": {
            "objective": str(task.get("objective", "")),
            "verification_obligation": str(task.get("verification_obligation", "")),
        },
        "candidates": normalized,
    }


def _request(state: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "margos-retrieval-reflex-request/v1",
        "task": dict(state["task"]),
        "candidates": [dict(candidate) for candidate in candidates],
        "question_set_sha256": _sha_text("margos-retrieval-question-set/v1"),
        "threshold_policy_sha256": _sha_text("margos-retrieval-thresholds/v1"),
    }


def plan_context_retrieval(
    metadata_state: Mapping[str, Any],
    provider: Any = None,
    *,
    needed_threshold: float = 0.60,
    fallback_optional: bool = True,
    privacy_allowed: bool = True,
    host_can_select: bool = True,
    jev_latency_budget_ms: float = 100.0,
    calibration_status: str | None = None,
    minimum_avoidable_bytes: int = 0,
) -> dict[str, Any]:
    """Plan retrieval without reading payload text.

    Provider failures and uncertainty return the complete safe Policy fallback;
    only a validated AVAILABLE response may reduce optional retrieval.
    """
    candidates = [normalize_candidate(item) for item in metadata_state.get("candidates", [])]
    mandatory = [item["candidate_id"] for item in candidates if item["mandatory_by_policy"]]
    optional = [item["candidate_id"] for item in candidates if not item["mandatory_by_policy"]]
    fallback = list(dict.fromkeys(mandatory + (optional if fallback_optional else [])))
    selected = list(fallback)
    admission = {
        "decision": "SKIP",
        "reason": "SKIP_DISABLED",
        "detail": "No metadata Reflex provider was admitted.",
        "stage": "METADATA_ONLY",
    }
    telemetry = {
        "candidate_count": len(candidates),
        "mandatory_count": len(mandatory),
        "optional_count": len(optional),
        "bytes_available_to_avoid": sum(item["estimated_size"]["bytes"] for item in candidates if not item["mandatory_by_policy"]),
        "tokens_available_to_avoid": sum(item["estimated_size"]["tokens"] for item in candidates if not item["mandatory_by_policy"]),
        "estimated_fetch_ms_available_to_avoid": sum(item["estimated_fetch_latency_ms"] for item in candidates if not item["mandatory_by_policy"]),
        "selected_count": len(selected),
        "actual_fetch_count": 0,
        "actual_fetch_bytes": 0,
        "actual_fetch_ms": 0.0,
        "stage1_request_count": 0,
        "stage2_request_count": 0,
        "stage2_realized_value": False,
        "raw_payload_projected": False,
    }
    provider_meta: dict[str, Any] = {}
    value_calibration = calibration_status
    if value_calibration is None and provider is not None:
        value_calibration = getattr(provider, "value_model_calibration_status", None)
    if not optional:
        admission = {"decision": "SKIP", "reason": "SKIP_POLICY_SUFFICIENT", "detail": "All candidates are mandatory by Policy.", "stage": "METADATA_ONLY"}
    elif not privacy_allowed:
        admission = {"decision": "SKIP", "reason": "SKIP_PRIVACY_POLICY", "detail": "Metadata projection is not privacy-authorized.", "stage": "METADATA_ONLY"}
    elif not host_can_select:
        admission = {"decision": "SKIP", "reason": "SKIP_HOST_CANNOT_EXPLOIT_RESULT", "detail": "The host cannot selectively retrieve the metadata candidates.", "stage": "METADATA_ONLY"}
    elif all(item["cache_locality"].upper() in {"LOCAL", "HOT", "CACHED"} for item in candidates if not item["mandatory_by_policy"]):
        admission = {"decision": "SKIP", "reason": "SKIP_NO_MATERIAL_VALUE_DELTA", "detail": "All optional candidates are already local or cached.", "stage": "METADATA_ONLY"}
    elif telemetry["bytes_available_to_avoid"] <= max(0, int(minimum_avoidable_bytes)):
        admission = {"decision": "SKIP", "reason": "SKIP_NO_MATERIAL_VALUE_DELTA", "detail": "Optional retrieval is below the configured compaction floor.", "stage": "METADATA_ONLY"}
    elif value_calibration in {"STALE", "UNCALIBRATED"}:
        admission = {"decision": "SKIP", "reason": "SKIP_UNCALIBRATED_VALUE_MODEL", "detail": "Retrieval optimization has no current concrete-model calibration.", "stage": "METADATA_ONLY"}
    elif 0.0 < telemetry["estimated_fetch_ms_available_to_avoid"] <= max(0.0, float(jev_latency_budget_ms)):
        admission = {"decision": "SKIP", "reason": "SKIP_LATENCY_BUDGET", "detail": "The maximum retrieval saving cannot pay the declared Jev budget.", "stage": "METADATA_ONLY"}
    elif provider is not None:
        questions = (
            {"id": "needed_for_next_obligation", "kind": "noul"},
            {"id": "likely_needed_for_verification", "kind": "noul"},
        )
        request = _request(metadata_state, [item for item in candidates if not item["mandatory_by_policy"]])
        try:
            if callable(getattr(provider, "is_configured", None)) and not provider.is_configured():
                raise ValueError("provider not configured")
            raw = provider.evaluate(request, questions)
            telemetry["stage1_request_count"] = int(raw.get("provider", {}).get("network_request_count", 0) or 0) if isinstance(raw, Mapping) else 0
            if not isinstance(raw, Mapping) or not isinstance(raw.get("provider"), Mapping) or raw["provider"].get("status") != "AVAILABLE":
                raise ValueError("metadata provider unavailable")
            provider_meta = dict(raw["provider"])
            answers = raw.get("answers", {})
            reduced: list[str] = []
            for item in candidates:
                if item["mandatory_by_policy"]:
                    continue
                answer = answers.get(item["candidate_id"], answers.get(f"{item['candidate_id']}_needed_for_next_obligation"))
                probability = None
                if isinstance(answer, Mapping):
                    nested = answer.get("needed_for_next_obligation", answer)
                    if isinstance(nested, Mapping):
                        probability = nested.get("probability")
                    elif isinstance(nested, (int, float)):
                        probability = nested
                if not isinstance(probability, (int, float)) or not 0 <= float(probability) <= 1:
                    raise ValueError("incomplete metadata answer")
                if float(probability) >= float(needed_threshold):
                    reduced.append(item["candidate_id"])
            selected = list(dict.fromkeys(mandatory + reduced))
            admission = {"decision": "CALL_REFLEX", "reason": "CALL_REFLEX", "detail": "Validated metadata-only semantic need reduced optional retrieval.", "stage": "METADATA_ONLY"}
            telemetry["selected_count"] = len(selected)
        except Exception as exc:
            admission = {"decision": "SKIP", "reason": "SKIP_PROVIDER_FAILURE", "detail": f"Safe retrieval fallback: {type(exc).__name__}", "stage": "METADATA_ONLY"}
    return {
        "schema_version": RETRIEVAL_PLAN_VERSION,
        "candidate_ids": [item["candidate_id"] for item in candidates],
        "mandatory_ids": mandatory,
        "optional_ids": optional,
        "selected_ids": selected,
        "fallback_ids": fallback,
        "admission": admission,
        "telemetry": telemetry,
        "question_set_sha256": _sha_text("margos-retrieval-question-set/v1"),
        "threshold_policy_sha256": _sha_text(f"margos-retrieval-thresholds/v1:{needed_threshold}"),
        "provider": provider_meta,
        "value_of_call": {
            "schema_version": "margos-value-of-call-receipt/v1",
            "decision": admission["decision"],
            "reason": admission["reason"],
            "operation_that_can_be_avoided": "optional_payload_fetch" if optional else None,
            "max_possible_saving": {
                "retrieval_bytes": telemetry["bytes_available_to_avoid"],
                "retrieval_tokens": telemetry["tokens_available_to_avoid"],
                "retrieval_latency_ms": telemetry["estimated_fetch_ms_available_to_avoid"],
            },
            "calibration_status": value_calibration or "UNKNOWN",
            "host_can_exploit_result": bool(host_can_select),
        },
    }


def materialize_context_from_plan(plan: Mapping[str, Any], loader: PayloadLoader) -> dict[str, Any]:
    selected = [str(item) for item in plan.get("selected_ids", [])]
    started = time.perf_counter()
    loaded = loader.load_many(selected)
    artifacts: dict[str, dict[str, Any]] = {}
    fetched_bytes = 0
    for candidate_id in selected:
        if candidate_id not in loaded:
            raise ValueError(f"loader omitted selected candidate {candidate_id}")
        value = loaded[candidate_id]
        if isinstance(value, PayloadArtifact):
            artifact = value
        elif isinstance(value, Mapping):
            content = value.get("content")
            if not isinstance(content, str):
                raise ValueError("payload artifact content must be text")
            artifact = PayloadArtifact(candidate_id, content, _sha_text(content), {"chars": len(content), "bytes": len(content.encode("utf-8")), "tokens_estimated": max(1, len(content) // 4)}, value.get("source", {}), value.get("fetch", {"status": "AVAILABLE", "latency_ms": 0.0}))
        else:
            raise ValueError("loader returned unsupported payload artifact")
        if artifact.content_sha256 != _sha_text(artifact.content):
            raise ValueError(f"payload hash mismatch for {candidate_id}")
        artifacts[candidate_id] = artifact.as_dict()
        fetched_bytes += len(artifact.content.encode("utf-8"))
    telemetry = dict(plan.get("telemetry", {}))
    telemetry.update({
        "actual_fetch_count": len(artifacts),
        "actual_fetch_bytes": fetched_bytes,
        "actual_fetch_ms": round((time.perf_counter() - started) * 1000.0, 3),
    })
    return {"schema_version": "margos-context-materialization/v1", "plan": dict(plan), "artifacts": artifacts, "telemetry": telemetry}
