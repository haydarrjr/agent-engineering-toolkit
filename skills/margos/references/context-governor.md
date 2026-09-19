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

Phase 2 may add typed Context Reflex judgments only for Policy-eligible items. Replayability, authorization, evidence truth, and permission remain deterministic Policy metadata.

## Attribution

Context Reflex was informed in part by the public fast-jev-compaction project by Tamara Tran, especially its separation of tool-call retention from full-result retention and its use of atomic Jev decisions for compaction.

Reference: https://github.com/tamaratran/fast-jev-compaction

This is conceptual attribution only. The AET implementation is independently designed around its own evidence, portability, privacy, and host-boundary requirements; no source from that project is copied.
