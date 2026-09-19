# MARGOS Reflex layer

Reflex is optional, typed, probabilistic, and non-authoritative. It exists only when Policy leaves more than one safe route.

The v1 question set contains atomic judgments:
- coordination preference;
- compute preference;
- task ambiguity;
- verification risk;
- probability that escalation is needed;
- probability that an independent critic is needed;
- probability that one bounded transfer is sufficient.

Choice/score answers must include complete closed-set probability distributions. Boolean-like judgments use probabilities in `[0,1]`. A provider may choose only Policy-admissible coordination and compute values.

Low-margin choices abstain to a deterministic safe fallback. Invalid, malformed, unavailable, or wrong-question-set provider responses also fall back rather than inventing a route.

Phase 2 contains only a provider `Protocol` plus a deterministic fixture provider. No external model/API client is included.


## Context Reflex boundary

MARGOS Reflex has two decision families: Routing Reflex and Context Reflex.

Issue #10 Phase 2 adds three atomic Context Reflex Noul judgments for Policy-eligible replayable items:
- `keep_awareness`;
- `keep_full`;
- `replay_needed`.

Deterministic composition applies versioned thresholds and an abstention band. Low-margin, malformed, unavailable, or missing-key provider outcomes prefer `KEEP_REF` over omission. Protected/non-replayable items never enter the provider candidate set.

Context Reflex reuses the existing `ReflexProvider` contract and TypeSafe/Jev transport. It cannot decide replayability, permission, authorization, evidence truth, protected-item status, external-effect replay, or canonical deletion.
