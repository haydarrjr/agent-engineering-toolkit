# MARGOS Context Governor

Issue #10 adds context allocation to the existing Policy -> Reflex -> Execution architecture. It is not a fourth authority layer.

Context optimization creates a derived Context View only. Repository state, files, tool evidence, Proof/Freshness artifacts, route receipts, and other canonical sources remain authoritative and are never deleted by Context Policy.

## Phase 1 contract

Phase 1 is deterministic and offline:

- context item/state/decision/receipt schemas are versioned from v1;
- Policy classifies protected, replayable, non-replayable, and superseded items;
- the action set is PIN, KEEP_FULL, KEEP_REF, KEEP_HEAD, OMIT_REHYDRATABLE;
- the materializer creates a hash-bound DERIVED_VIEW receipt without changing canonical evidence;
- every compacted item carries a rehydration contract;
- no Context Reflex provider or network call is used.

Load context-retention-policy.md for protection/action rules and context-rehydration.md for recovery semantics.

## Phase 2 contract

Phase 2 adds optional typed Context Reflex only for Policy-eligible replayable items.

The v1 Context Reflex question set is deliberately small:
- `keep_awareness`: does knowing the item/action existed still matter?
- `keep_full`: is the exact full payload needed now?
- `replay_needed`: is rehydration likely before the current obligation closes?

Thresholds and request budgets live in `contracts/context-threshold-policy-v1.json`, separate from the question wording. Low-margin judgments abstain to `KEEP_REF`. Provider failure or missing configuration also prefers `KEEP_REF` over omission.

Context Reflex uses the existing `ReflexProvider` protocol and the existing TypeSafe/Jev transport. There is no second client stack or credential path. A live provider is explicit opt-in: the presence of `TYPESAFE_API_KEY` alone never enables Context Reflex. With Jev selected but no key, the provider returns `NOT_CONFIGURED` and performs zero network requests.

Only minimized metadata is projected remotely: bounded task fields, bounded source locator/tool metadata, size, evidence flags, deterministic replay/supersession metadata, recency, and Policy-admissible context actions. Canonical item IDs are replaced with batch-local candidate keys and raw payloads are not sent.

Replayability, authorization, evidence truth, permission, protected-item classification, canonical deletion, and external-effect replay remain deterministic Policy concerns.

## Attribution

Context Reflex was informed in part by the public fast-jev-compaction project by Tamara Tran, especially its separation of tool-call retention from full-result retention and its use of atomic Jev decisions for compaction.

Reference: https://github.com/tamaratran/fast-jev-compaction

This is conceptual attribution only. The AET implementation is independently designed around its own evidence, portability, privacy, and host-boundary requirements; no source from that project is copied.
