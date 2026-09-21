#!/usr/bin/env python3
"""Deterministic, exact, bounded evidence selection for Context Reflex."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

EXTRACTOR_VERSION = "margos-evidence-extractor/v1"
MAX_DEFAULT_CHARS = 512
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bTYPESAFE_API_KEY\s*="),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b" + "gh" + r"p_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _terms(task: Mapping[str, Any]) -> list[str]:
    text = " ".join(str(task.get(key, "")) for key in ("objective", "verification_obligation"))
    return list(dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)))


def _line_ranges(payload: str, predicates: list[re.Pattern[str]], limit: int) -> list[tuple[int, int]]:
    lines = payload.splitlines(keepends=True)
    hits = []
    for index, line in enumerate(lines):
        if any(pattern.search(line) for pattern in predicates):
            start = max(0, index - 2)
            end = min(len(lines), index + 3)
            hits.append((sum(len(x) for x in lines[:start]), sum(len(x) for x in lines[:end])))
    return hits[:limit]


def _term_ranges(payload: str, terms: list[str], limit: int) -> list[tuple[int, int]]:
    ranges = []
    for term in terms:
        for match in re.finditer(re.escape(term), payload, re.IGNORECASE):
            start = max(0, payload.rfind("\n", 0, max(0, match.start() - 240)) + 1)
            end_marker = payload.find("\n", min(len(payload), match.end() + 240))
            end = len(payload) if end_marker < 0 else end_marker
            ranges.append((start, end))
            if len(ranges) >= limit:
                return ranges
    return ranges


def _merge_ranges(ranges: list[tuple[int, int]], budget: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    selected: list[tuple[int, int]] = []
    used = 0
    for start, end in merged:
        take = min(end - start, budget - used)
        if take <= 0:
            break
        selected.append((start, start + take))
        used += take
    return selected


def _kind(item: Mapping[str, Any]) -> str:
    raw = str(item.get("kind", "OTHER")).upper()
    source = str(item.get("source", {}).get("tool", "")).lower()
    if raw in {"CODE", "SOURCE", "DIFF"} or source in {"read_file", "git_diff", "apply_patch"}:
        return "SOURCE"
    if raw in {"TEST", "LOG", "TRACEBACK", "TEST_OUTPUT"} or "test" in source or "log" in source:
        return "TEST_LOG"
    if raw in {"SEARCH", "SEARCH_RESULT"} or "search" in source:
        return "SEARCH"
    if raw in {"DOCUMENT", "DOC"} or "doc" in source:
        return "DOCUMENT"
    if raw in {"STRUCTURED", "TOOL_RESULT"}:
        return "STRUCTURED_TOOL_RESULT"
    return raw


def extract_evidence_capsule(
    item: Mapping[str, Any],
    exact_payload: str,
    task: Mapping[str, Any] | None = None,
    budget: int = MAX_DEFAULT_CHARS,
) -> dict[str, Any]:
    """Return only verbatim excerpts bound to the canonical payload hash."""
    if not isinstance(exact_payload, str):
        raise TypeError("exact_payload must be text")
    if not isinstance(budget, int) or budget <= 0:
        raise ValueError("budget must be a positive integer")
    task = task or {}
    payload_hash = _sha(exact_payload)
    kind = _kind(item)
    terms = _terms(task)
    # Screen the canonical payload before any projection. A secret that happens
    # to fall outside a selected excerpt must still suppress the capsule.
    if any(pattern.search(exact_payload) for pattern in SECRET_PATTERNS):
        return {
            "extractor_version": EXTRACTOR_VERSION,
            "extractor_kind": _kind(item),
            "status": "SUPPRESSED_SECRET",
            "suppression_reason": "SECRET_PATTERN_MATCH",
            "payload_sha256": payload_hash,
            "exact_excerpts": [],
            "excerpt_sha256s": [],
            "total_characters": 0,
        }
    ranges: list[tuple[int, int]] = []
    if kind == "SOURCE":
        ranges.extend(_line_ranges(exact_payload, [re.compile(r"^\s*(?:def|class)\s+\w+"), re.compile(r"^@@")], 4))
        ranges.extend(_term_ranges(exact_payload, terms, 4))
    elif kind == "TEST_LOG":
        ranges.extend(_line_ranges(exact_payload, [re.compile(r"Traceback \(most recent call last\)"), re.compile(r"(?:FAILED|ERROR|AssertionError|E\s+)"), re.compile(r"={3,}")], 6))
    elif kind in {"SEARCH", "DOCUMENT"}:
        ranges.extend(_term_ranges(exact_payload, terms, 6))
    elif kind == "STRUCTURED_TOOL_RESULT":
        ranges.extend(_term_ranges(exact_payload, terms, 4))
    selected = _merge_ranges(ranges, min(budget, MAX_DEFAULT_CHARS))
    extractor_kind = kind
    if not selected:
        # The fallback is still exact, but it is explicitly not semantic selection.
        head = min(len(exact_payload), min(budget, MAX_DEFAULT_CHARS) // 2)
        tail = min(len(exact_payload) - head, min(budget, MAX_DEFAULT_CHARS) - head)
        selected = [(0, head)]
        if tail > 0:
            selected.append((len(exact_payload) - tail, len(exact_payload)))
        extractor_kind = "EXACT_PREFIX_FALLBACK"

    excerpts = [exact_payload[start:end] for start, end in selected]
    # Separators are part of the remote projection budget too.
    remaining = min(budget, MAX_DEFAULT_CHARS)
    bounded: list[str] = []
    for excerpt in excerpts:
        take = max(0, remaining - (1 if bounded else 0))
        if take <= 0:
            break
        bounded.append(excerpt[:take])
        remaining -= len(bounded[-1]) + (1 if len(bounded) > 1 else 0)
    excerpts = bounded
    joined = "\n".join(excerpts)
    return {
        "extractor_version": EXTRACTOR_VERSION,
        "extractor_kind": extractor_kind,
        "status": "AVAILABLE",
        "payload_sha256": payload_hash,
        "exact_excerpts": excerpts,
        "excerpt_sha256s": [_sha(value) for value in excerpts],
        "total_characters": len(joined),
        "capsule_sha256": _sha(_canon(excerpts)),
    }
