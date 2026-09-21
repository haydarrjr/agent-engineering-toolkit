#!/usr/bin/env python3
"""Stable runtime/source identity for MARGOS receipts and benchmark reports."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[3]


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(_canon(value).encode("utf-8"))


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def source_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if value:
            return value
    except (OSError, subprocess.SubprocessError):
        pass
    return "UNKNOWN"


def toolkit_version() -> str:
    for relative in ("plugin.json", "pyproject.toml"):
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if relative.endswith("json"):
            value = json.loads(text).get("version")
        else:
            value = next(
                (line.split("=", 1)[1].strip().strip('"')
                 for line in text.splitlines() if line.startswith("version = ")),
                None,
            )
        if isinstance(value, str):
            return value
    return "UNKNOWN"


def build_fingerprint(
    *,
    requested_model: str | None,
    response_model: str | None,
    benchmark_protocol: str,
    corpus_sha256: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    files = {
        "policy": ROOT / "skills/margos/scripts/margos_decide.py",
        "routing_questions": ROOT / "skills/margos/contracts/question-set-v2.json",
        "thresholds": ROOT / "skills/margos/contracts/threshold-policy-v2.json",
        "context_questions": ROOT / "skills/margos/contracts/context-question-set-v2.json",
        "context_thresholds": ROOT / "skills/margos/contracts/context-threshold-policy-v2.json",
        "projection": ROOT / "skills/margos/scripts/margos_reflex_jev.py",
        "extractor": ROOT / "skills/margos/scripts/margos_evidence_capsule.py",
    }
    fingerprint = {
        "fingerprint_version": "margos-runtime-fingerprint/v1",
        "toolkit_version": toolkit_version(),
        "source_sha": source_sha(),
        "contracts": {key: file_sha256(path) for key, path in files.items()},
        "requested_model": requested_model,
        "response_model": response_model,
        "benchmark_protocol": benchmark_protocol,
        "corpus_sha256": corpus_sha256,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": sys.platform,
        },
    }
    if extra:
        fingerprint["extra"] = dict(extra)
    fingerprint["fingerprint_sha256"] = sha256_json(fingerprint)
    return fingerprint


def fingerprint_mismatches(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> list[str]:
    """Compare only identity fields that gate reuse of benchmark/calibration data."""
    fields = (
        "toolkit_version",
        "source_sha",
        "contracts",
        "requested_model",
        "response_model",
        "benchmark_protocol",
        "corpus_sha256",
    )
    return [field for field in fields if expected.get(field) != observed.get(field)]
