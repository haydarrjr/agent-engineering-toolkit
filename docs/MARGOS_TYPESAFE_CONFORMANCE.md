# MARGOS TypeSafe/Jev conformance

Issue #21 uses two deliberately separate planes:

```text
design-time Codex skill -> question/API/calibration design guidance
runtime MARGOS          -> provider-neutral contracts and deterministic authority
```

The official TypeSafe skill is not vendored into this repository and is not a
runtime dependency. Runtime authority remains:

```text
Policy -> ExecutionOpportunity/RetrievalCandidate -> ValueOfCall
       -> optional typed Jev judgments -> deterministic composition
       -> final Policy veto -> host-native execution -> verification/readback
```

## Freshness binding

The Issue #21 implementation was designed against the following current sources:

| Source | Binding |
|---|---|
| Official skill | `typesafe-ai/skills` `skills/typesafe-ai/SKILL.md`, blob `0109513f9656917dc93cbc5ecddfca465a53ce66` |
| Documentation index | https://docs.typesafe.ai/llms.txt |
| Primitive guidance | https://docs.typesafe.ai/primitives.md |
| Confidence guidance | https://docs.typesafe.ai/confidence.md |
| API contract | https://docs.typesafe.ai/api.md |
| Model lifecycle | https://docs.typesafe.ai/models.md |
| Jev 1.13 jaggedness | https://docs.typesafe.ai/model-jaggedness/jev-1.13.md |
| Requested model policy | Resolve `jev-latest` at benchmark time; bind calibration to the concrete response model |
| Known observed model | `jev-1.13.0` in the prior authorized live evidence; fixture runs do not claim a live response model |

The exact machine-readable binding is in
`provenance/typesafe-jev-design.json`. A change to these sources or to any
question, projection, threshold, extractor, model, corpus, or runtime contract
invalidates the corresponding calibration/fingerprint and requires a new
calibration or research run.

## Design-conformance checklist

Before merging a Jev contract, verify:

- [ ] Each question is one narrow semantic judgment; deterministic rules and arithmetic remain in code.
- [ ] Choice candidates are complete and Policy-admissible; no omitted option can be selected.
- [ ] Independent same-state questions are sent in one batched request when the token budget permits.
- [ ] A second request exists only when the first answer creates/fetches genuinely new state.
- [ ] Instructions and criteria are self-contained; structured paths are backticked and relative to the actual state object.
- [ ] Noul values are used as probability that the proposition is true, not as intensity or generic confidence.
- [ ] Score levels describe standalone ordered situations and are not used as a disguised Choice.
- [ ] Thresholds are frozen from calibration data and evaluated once on a disjoint holdout.
- [ ] Raw judgments remain separate from deterministic composition, final Policy veto, execution, and verification.
- [ ] Provider, missing-evidence, code, and service failures have distinct receipts and conservative fallbacks.
- [ ] Typed output is never treated as authorization, proof, or ground truth.

The repository validators and `tests/test_margos_jev_v4.py` cover the
mechanically testable subset. Human review must still inspect semantic question
meaning and the concrete host operation being replaced.

## Shadow-first rollout

The runtime supports a shadow mode for domain calibration:

```text
Policy makes the real decision
Jev receives the admitted state
Jev judgment is recorded
Jev does not alter execution
downstream outcome is observed
calibration/value telemetry is accumulated
```

Call `margos_decide.decide(state, provider, shadow=True)` to record the admitted
Reflex result while keeping the selected operation on the deterministic Policy
fallback. Shadow mode does not expand authority and is not a promotion claim.
Active execution-affecting Jev requires a matching concrete-model calibration
binding and a passing cold disjoint holdout.

## Effective-in-Codex acceptance

The official skill being available is not sufficient. The integration is
effective only when the implementation demonstrates zero-call deterministic
cases, one batched request for independent same-state judgments, true
dependency-only Stage 2, pre-retrieval loader/byte reduction, realized routing
work avoidance, verification non-inferiority on a cold holdout, warm replay
savings, and clean Policy-only fallback when the skill/provider is absent.
