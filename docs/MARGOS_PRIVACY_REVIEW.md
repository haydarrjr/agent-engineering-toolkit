# MARGOS Context Governor privacy review

Status: PASS for the portable experimental metadata-only / bounded-context design in Issue #10 Phases 1-4. This is a design-and-fixture review, not an approval to send arbitrary proprietary payloads to a remote provider.

## Scope

This review covers Context Reflex remote projection, frozen benchmark fixtures, child-context receipts, optional host-compaction proposals, logs/CI, and credential handling.

## Data minimization boundary

The portable remote Context Reflex projection is limited to bounded task fields and candidate metadata needed for the three typed judgments. It does not include raw context payloads by default.

Allowed default projection fields include:
- bounded task objective / verification obligation;
- batch-local candidate key rather than canonical local item ID;
- tool name and bounded locator;
- result status / content version;
- size metadata;
- deterministic evidence flags;
- replayability and supersession metadata;
- recency;
- Policy-admissible context actions.

Raw file contents, tool-result payloads, full private transcripts, auth headers, environment secrets, credentials, bearer tokens, private keys, and unrelated repository content are not default remote input.

## Credential boundary

`TYPESAFE_API_KEY` is runtime-only. It is not represented in Context Item metadata, receipts, benchmark fixtures, CI configuration, or host-compaction contracts. Merely having the variable in the environment does not enable live Context Reflex; provider selection is explicit.

## CI and fixtures

Committed Phase 4 benchmark fixtures are synthetic. `benchmark_margos_context.py` performs a static high-risk secret-pattern scan before strict promotion gates can pass. CI uses only `--mode fixture`; it does not set a TypeSafe key and does not execute live Jev.

Benchmark output may contain synthetic fixture metadata and aggregate metrics. It must not become a sink for raw production transcripts.

## Receipts

Context and child-context receipts record selection decisions, hashes, stable references, counts, provider status/usage, and rehydration metadata. They are not an evidence store and must not be used to smuggle secrets or complete proprietary payloads.

## Rehydration

Rehydration occurs at the parent/runtime boundary. Safe content-addressed recovery verifies SHA-256. Replay methods that can recompute/refetch state remain subject to current authority/freshness checks. No rehydration contract may silently repeat an external mutation.

## Optional root compaction

The portable host-compaction contract contains hashes and character counts only. It never contains the root transcript. `OFFER_DERIVED_VIEW` is a proposal available only after explicit experimental opt-in plus proven host hook capability. Applying the view remains an external host-adapter responsibility.

## Threats explicitly covered

- environment/API-key leakage into committed fixtures;
- provider auto-enablement merely because a key exists;
- full raw payload sent to Context Reflex by default;
- canonical item IDs leaking into the Jev candidate projection;
- child requesting hidden context by guessing an item ID;
- silent replay of mutable/external effects;
- root transcript interception becoming mandatory;
- CI contacting the live provider;
- compaction receipts being misrepresented as truth or execution evidence.

## Residual risks

A deployment-specific adapter can still violate these boundaries if it deliberately adds proprietary payloads or secrets. Organizations must separately approve such an adapter and its provider/data-retention terms. Live-provider calibration and privacy evaluation must be bound to the exact deployed model, endpoint, question set, projection, and organizational policy.

## Conclusion

The portable AET implementation is approved for experimental Context Reflex research with minimized metadata and synthetic offline CI. Full proprietary payload transfer remains opt-in/outside the default contract, and no live calibration or production privacy claim is made by fixture CI.

## JEV v2 semantic capsule boundary

Remote semantic capsules are disabled unless the Context View explicitly enables them. When enabled, MARGOS locally verifies the exact payload hash, extracts only bounded exact excerpts using the versioned evidence extractor (maximum 512 characters), records excerpt and provenance hashes, and screens the complete canonical payload before projection. Any secret-pattern match suppresses the capsule and labels the result `SUPPRESSED_SECRET`; no fabricated summary is sent. The provider projection still replaces canonical local item IDs with batch-local keys and never receives the full payload by default. A no-match selection is explicitly labeled `EXACT_PREFIX_FALLBACK`.

Redacted trace evaluation is local/offline in CI. The committed trace fixture is synthetic, requires `redacted=true`, and is secret-scanned. Real Codex traces are operator-supplied local inputs and are not repository artifacts.
