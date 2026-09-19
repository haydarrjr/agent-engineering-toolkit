#!/usr/bin/env python3
"""Privacy-safe benchmark for redacted Codex/MARGOS routing and context traces."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))
import margos_context as ctx
import margos_decide as core

DEFAULT_FIXTURE = ROOT / "tests/fixtures/margos/trace-benchmark-v1.json"
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bTYPESAFE_API_KEY\s*="),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def scan_text(text: str) -> list[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def _brier(probs: Mapping[str, Any], gold: str) -> float:
    return sum(
        (float(probability) - (1.0 if label == gold else 0.0)) ** 2
        for label, probability in probs.items()
    )


def _ece(points: list[tuple[float, bool]], bins: int = 5) -> float | None:
    if not points:
        return None
    total = len(points)
    error = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [
            (confidence, correct)
            for confidence, correct in points
            if (low <= confidence < high) or (index == bins - 1 and confidence == 1.0)
        ]
        if not bucket:
            continue
        avg_conf = sum(x[0] for x in bucket) / len(bucket)
        avg_acc = sum(1.0 if x[1] else 0.0 for x in bucket) / len(bucket)
        error += len(bucket) / total * abs(avg_conf - avg_acc)
    return error


def _routing_case(case: Mapping[str, Any]) -> tuple[dict[str, Any], list[tuple[float, bool]], list[float]]:
    provider = core.FixtureReflexProvider(case["answers"])
    receipt = core.decide(case["state"], provider)
    selected = receipt["selected"]
    gold = case["gold_route"]
    passed = all(selected.get(key) == value for key, value in gold.items())
    hard_violation = selected["disposition"] != "HALT" and (
        selected["coordination"] not in receipt["admissible"]["coordination"]
        or selected["compute"] not in receipt["admissible"]["compute"]
        or selected["role"] not in receipt["admissible"]["roles"]
    )
    points: list[tuple[float, bool]] = []
    briers: list[float] = []
    for question, gold_key in (
        ("coordination_preference", "coordination"),
        ("compute_preference", "compute"),
    ):
        answer = receipt["reflex"]["answers"].get(question)
        if not answer:
            continue
        probs = answer["probabilities"]
        confidence = max(float(x) for x in probs.values())
        points.append((confidence, answer["value"] == gold[gold_key]))
        briers.append(_brier(probs, gold[gold_key]))
    return {
        "id": case["id"],
        "kind": "routing",
        "pass": passed,
        "hard_violation": hard_violation,
        "abstained": bool(selected.get("abstained")),
        "selected": selected,
        "gold": gold,
    }, points, briers


def _context_case(case: Mapping[str, Any]) -> dict[str, Any]:
    provider = ctx.FixtureContextReflexProvider(case["answers"])
    view, receipt = ctx.materialize_context_view(
        case["state"], case["payloads"], provider
    )
    actions = {entry["item_id"]: entry["action"] for entry in receipt["actions"]}
    gold = case["gold_actions"]
    passed = actions == gold and receipt["canonical_source_mutated"] is False
    before = sum(len(value) for value in case["payloads"].values())
    after = int(receipt["output"]["characters_serialized"])
    return {
        "id": case["id"],
        "kind": "context",
        "pass": passed,
        "harmful_omission": not passed,
        "rehydration_count": 0,
        "characters_before": before,
        "characters_after": after,
        "reduction_ratio": 0.0 if before == 0 else (before - after) / before,
        "actions": actions,
        "gold": gold,
        "context_view_sha256": receipt["context_view_sha256"],
        "view_items": len(view["items"]),
    }


def evaluate_corpus(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("version") != "margos-trace-benchmark/v1":
        raise ValueError("unsupported trace benchmark version")
    if document.get("redacted") is not True:
        raise ValueError("trace benchmark input must declare redacted=true")
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False)
    secret_hits = scan_text(encoded)
    results = []
    points: list[tuple[float, bool]] = []
    briers: list[float] = []
    for case in document.get("cases", []):
        kind = case.get("kind")
        if kind == "routing":
            result, case_points, case_briers = _routing_case(case)
            points.extend(case_points)
            briers.extend(case_briers)
        elif kind == "context":
            result = _context_case(case)
        else:
            raise ValueError(f"unsupported trace case kind: {kind}")
        results.append(result)
    routing = [x for x in results if x["kind"] == "routing"]
    context = [x for x in results if x["kind"] == "context"]
    context_before = sum(int(x["characters_before"]) for x in context)
    context_after = sum(int(x["characters_after"]) for x in context)
    aggregate = {
        "cases": len(results),
        "passed": sum(1 for x in results if x["pass"]),
        "routing_success_rate": (
            sum(1 for x in routing if x["pass"]) / len(routing) if routing else None
        ),
        "context_success_rate": (
            sum(1 for x in context if x["pass"]) / len(context) if context else None
        ),
        "abstentions": sum(1 for x in routing if x["abstained"]),
        "hard_boundary_violations": sum(1 for x in routing if x["hard_violation"]),
        "harmful_omission_cases": sum(1 for x in context if x["harmful_omission"]),
        "rehydration_count": sum(int(x["rehydration_count"]) for x in context),
        "context_reduction_ratio": (
            0.0
            if context_before == 0
            else (context_before - context_after) / context_before
        ),
        "brier_mean": sum(briers) / len(briers) if briers else None,
        "ece_5_bin": _ece(points),
        "calibration_observations": len(points),
        "secret_pattern_hits": secret_hits,
    }
    aggregate["pass"] = (
        aggregate["passed"] == aggregate["cases"]
        and aggregate["hard_boundary_violations"] == 0
        and aggregate["harmful_omission_cases"] == 0
        and not secret_hits
    )
    return {
        "schema_version": "margos-trace-benchmark-report/v1",
        "input_version": document["version"],
        "authority": "REDACTED_EVALUATION_ONLY",
        "aggregate": aggregate,
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    report = evaluate_corpus(document)
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if args.strict and not report["aggregate"]["pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
