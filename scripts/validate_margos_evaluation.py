#!/usr/bin/env python3
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MARGOS = ROOT / "skills/margos"
errors = []


def check(condition, message):
    if not condition:
        errors.append(message)


required = (
    ROOT / "scripts/benchmark_margos_context.py",
    ROOT / "tests/fixtures/margos/context-benchmark-v1.json",
    ROOT / "docs/MARGOS_PRIVACY_REVIEW.md",
    ROOT / "tests/test_margos_context_evaluation.py",
    MARGOS / "contracts/host-compaction-policy-v1.json",
    MARGOS / "schemas/host-compaction-request-v1.schema.json",
    MARGOS / "schemas/host-compaction-result-v1.schema.json",
    MARGOS / "schemas/context-benchmark-report-v1.schema.json",
    MARGOS / "scripts/margos_host_compaction.py",
    MARGOS / "references/host-compaction.md",
)
for path in required:
    check(path.is_file(), f"missing Phase 4 artifact: {path.relative_to(ROOT)}")

fixture = {}
fixture_path = ROOT / "tests/fixtures/margos/context-benchmark-v1.json"
if fixture_path.is_file():
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid context benchmark fixture: {exc}")
check(fixture.get("version") == "margos-context-benchmark/v1", "context benchmark fixture version drift")
check(len(fixture.get("cases", [])) >= 10, "context benchmark must contain representative frozen cases")
gates = fixture.get("strict_gates", {})
check(float(gates.get("minimum_candidate_verified_success_rate", 0)) == 1.0, "verified-success gate must remain 100% for frozen corpus")
check(float(gates.get("maximum_harmful_omission_rate", 1)) == 0.0, "harmful omission gate must remain zero")
for key in (
    "maximum_protected_loss_violations",
    "maximum_non_replayable_omission_violations",
    "maximum_external_effect_loss_violations",
    "maximum_contradiction_loss_violations",
    "maximum_forbidden_context_violations",
):
    check(int(gates.get(key, 1)) == 0, f"hard safety gate must remain zero: {key}")
check(float(gates.get("minimum_aggregate_serialized_reduction_ratio", 0)) >= 0.40, "context reduction gate must remain meaningful")

fixture_text = fixture_path.read_text(encoding="utf-8") if fixture_path.is_file() else ""
secret_patterns = (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}",
    r"\bTYPESAFE_API_KEY\s*=",
    r"\bsk-[A-Za-z0-9_-]{16,}",
    r"\b" + "gh" + r"p_[A-Za-z0-9]{20,}",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",
)
for pattern in secret_patterns:
    check(re.search(pattern, fixture_text) is None, f"possible secret in committed context fixture: {pattern}")

benchmark = ROOT / "scripts/benchmark_margos_context.py"
if benchmark.is_file():
    text = benchmark.read_text(encoding="utf-8")
    for token in (
        "full_baseline_serialized",
        "evaluate_oracle",
        "harmful_omission_rate",
        "rehydration_count",
        "brier_score",
        "ece_5_bin",
        "NOT_OBSERVABLE_IN_PORTABLE_CI",
        "TYPESAFE_API_KEY",
    ):
        check(token in text, f"context benchmark missing metric/boundary: {token}")
    check("--mode" in text and "fixture" in text and "jev" in text, "context benchmark must expose policy/fixture/live research modes")

for name in (
    "host-compaction-policy-v1.json",
    "host-compaction-request-v1.schema.json",
    "host-compaction-result-v1.schema.json",
    "context-benchmark-report-v1.schema.json",
):
    path = (MARGOS / "contracts" / name) if name.endswith("policy-v1.json") else (MARGOS / "schemas" / name)
    if path.is_file():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid Phase 4 JSON {name}: {exc}")

compaction = MARGOS / "scripts/margos_host_compaction.py"
if compaction.is_file():
    text = compaction.read_text(encoding="utf-8").lower()
    for token in ("no_aet_interception", "defer_host_native", "offer_derived_view", "experimental_adapter_enabled", "root_compaction_hook_proven", "decision_authority"):
        check(token in text, f"host compaction contract missing {token}")
    for forbidden in ("import requests", "import httpx", "urllib.request", "import claude", "session.compact"):
        check(forbidden not in text, f"portable host compaction core must not bind a host/network runtime: {forbidden}")

privacy = ROOT / "docs/MARGOS_PRIVACY_REVIEW.md"
if privacy.is_file():
    text = privacy.read_text(encoding="utf-8")
    for token in ("TYPESAFE_API_KEY", "full private transcripts", "runtime-only", "synthetic", "canonical AET evidence"):
        check(token in text, f"privacy review missing boundary: {token}")

execution = MARGOS / "references/execution-layer.md"
if execution.is_file():
    text = execution.read_text(encoding="utf-8")
    check("host-compaction.md" in text, "execution layer must progressively disclose optional host compaction")

ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
check("MARGOS evaluation/privacy contract" in ci, "CI must run Phase 4 evaluation/privacy validator")
check("MARGOS frozen context benchmark (policy)" in ci, "CI must run deterministic policy context benchmark")
check("MARGOS frozen context benchmark (fixture)" in ci, "CI must run fixture Context Reflex benchmark")
check("--mode jev" not in ci, "CI must never run live Jev context benchmark")
check("TYPESAFE_API_KEY" not in ci, "CI must not inject TypeSafe credentials")

if errors:
    print("MARGOS evaluation/privacy validation: FAIL")
    for error in errors:
        print("ERROR:", error)
    raise SystemExit(1)

print("MARGOS evaluation/privacy validation: PASS")
print("Phase 4 boundary: frozen counterfactual CI + explicit live research + optional host-neutral compaction proposal")
