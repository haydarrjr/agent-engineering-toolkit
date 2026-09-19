# Context retention policy

Context Policy runs before any future Context Reflex judgment. Binding state is protected by meaning, not recency.

## Deterministic rules

MARGOS-CTX-POL-001 pins active user constraints, objective, permission state, write ownership, protected paths, explicit model/provider constraints, unresolved external effects, pending confirmation, active verification obligations, unresolved verification failures, and the latest finalized route decision.

MARGOS-CTX-POL-002 pins active proof/freshness bindings, open contradictions, and evidence currently supporting a claimed PASS.

MARGOS-CTX-POL-003 keeps unknown or non-replayable items in full. Replayability is deterministic metadata, never a probabilistic guess.

MARGOS-CTX-POL-004 allows OMIT_REHYDRATABLE only when an item is replayable and explicitly SUPERSEDED with a successor present in the same normalized state.

MARGOS-CTX-POL-005 uses KEEP_REF for current replayable unprotected items in the deterministic baseline.

An old binding constraint remains protected until deterministic state says it is resolved or superseded.

## Actions

- PIN: exact protected content stays active.
- KEEP_FULL: exact content stays active because safe recovery is unavailable or unknown.
- KEEP_REF: retain structured source/hash/replay/evidence references.
- KEEP_HEAD: retain an exact bounded prefix plus a structured reference. Phase 1 exposes the contract but does not automatically choose it.
- OMIT_REHYDRATABLE: omit payload from the derived view only and preserve a verified recovery path.

There is no DELETE action. Canonical evidence is outside the Context Governor mutation surface.
