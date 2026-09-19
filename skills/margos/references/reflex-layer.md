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

MARGOS Reflex now has two decision families: Routing Reflex and Context Reflex. Issue #10 Phase 1 implements only deterministic Context Policy and the derived-view materializer. It makes no Context Reflex provider call.

A later Context Reflex may estimate keep-awareness, keep-full, and replay-needed only for Policy-eligible items. It cannot decide replayability, permission, authorization, evidence truth, or canonical deletion.
