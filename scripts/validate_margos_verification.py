#!/usr/bin/env python3
"""Validate the Issue #24 Verification Governor boundary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARGOS = ROOT / "skills/margos"
errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


required = [
    MARGOS / "scripts/margos_verification.py",
    MARGOS / "contracts/verification-question-set-v1.json",
    MARGOS / "contracts/verification-threshold-policy-v1.json",
    MARGOS / "schemas/verification-candidate-v1.schema.json",
    MARGOS / "schemas/verification-opportunity-v1.schema.json",
    MARGOS / "schemas/verification-plan-v1.schema.json",
    MARGOS / "schemas/verification-receipt-v1.schema.json",
    MARGOS / "schemas/verification-reflex-request-v1.schema.json",
    MARGOS / "schemas/verification-reflex-result-v1.schema.json",
    ROOT / "scripts/benchmark_margos_jev_verification.py",
    ROOT / "tests/fixtures/margos/verification-governor-v1.json",
    ROOT / "tests/test_margos_verification.py",
]
for path in required:
    check(path.is_file(), f"missing Issue #24 artifact: {path.relative_to(ROOT)}")

documents = {}
for path in required:
    if path.suffix == ".json" and path.is_file():
        try:
            documents[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

question_doc = documents.get("verification-question-set-v1.json", {})
threshold_doc = documents.get("verification-threshold-policy-v1.json", {})
fixture = documents.get("verification-governor-v1.json", {})
check(question_doc.get("version") == "margos-verification-questions/v1", "verification question contract drift")
check(threshold_doc.get("selection") == "CALIBRATION_SET_ONLY", "verification thresholds must be calibration-only")
check(int(threshold_doc.get("max_provider_requests_per_planning_round", 0)) == 1, "verification governor must cap production requests at one")
check("Noul" == question_doc.get("primitive"), "verification Reflex must use Noul")
template = json.dumps(question_doc.get("question_template", {}))
for token in ("candidates[INDEX]", "materially changes", "safely deferring"):
    check(token in template, f"verification question missing self-contained criterion: {token}")
check(fixture.get("provenance") in {"SYNTHETIC", "REDACTED_REAL_CODEX", "DERIVED_COUNTERFACTUAL"}, "fixture provenance must be explicit")
check(not set(fixture.get("calibration_partition", [])).intersection(fixture.get("holdout_partition", [])), "calibration and holdout partitions overlap")

source = (MARGOS / "scripts/margos_verification.py").read_text(encoding="utf-8") if (MARGOS / "scripts/margos_verification.py").is_file() else ""
for token in ("FindingLedger", "validate_verifier_readback", "SKIP_HOST_CANNOT_EXPLOIT_RESULT", "SKIP_STALE_CALIBRATION", "provider_request_count", "final_finding_order"):
    check(token in source, f"verification governor missing boundary: {token}")
check("coordination_preference" not in source, "dedicated Verification Reflex must not reuse generic routing questions")
check("route_" not in source, "dedicated Verification Reflex must not generate route sufficiency questions")
check("VERIFIED" in source and "cannot enter optional" in source, "verified-finding protection missing")

benchmark = ROOT / "scripts/benchmark_margos_jev_verification.py"
if benchmark.is_file():
    result = subprocess.run([sys.executable, str(benchmark), "--mode", "fixture", "--strict"], cwd=ROOT, capture_output=True, text=True)
    check(result.returncode == 0, f"strict Verification Governor fixture failed: {result.stderr[-500:]}")
    benchmark_text = benchmark.read_text(encoding="utf-8")
    for token in ("verified_finding_recall_at_1", "verified_finding_recall_at_3", "optional_verified_recall", "false_deescalation_count", "false_escalation_count", "gross_verifier_work_saved_ms", "optional_verification_cost_units_dispatched", "calibration_brier", "jev_overhead_ms", "end_to_end_latency_ms", "net_wall_saved_ms", "safety_violations", "response_models"):
        check(token in benchmark_text, f"Verification benchmark missing raw outcome/economics metric: {token}")

if errors:
    print("MARGOS Verification Governor validation: FAIL")
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)

print("MARGOS Verification Governor validation: PASS")
