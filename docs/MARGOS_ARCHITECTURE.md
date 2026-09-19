# MARGOS vNext architecture

Issue #6 evolves MARGOS from instruction-only routing into a three-layer decision system while preserving AET's skills-first, provider-agnostic, host-native architecture.

```text
Task + host observations + authority
              |
              v
      deterministic Policy
   admissibility / veto / halt
              |
              v
        optional Reflex
  typed probabilities, no authority
              |
              v
   deterministic composition
      and final Policy veto
              |
              v
       host-native Execution
              |
              v
      verification/readback
```

## Layer 1: Policy

Policy is local and authoritative. It filters unsafe/impossible coordination and compute choices, preserves explicit user constraints, differentiates direct fallback from halt, and prevents unresolved external effects from being retried blindly.

## Layer 2: Reflex

Reflex is optional and non-authoritative. A provider receives a minimized routing projection plus only Policy-admissible choices. It returns typed judgments and probabilities. Low margin, malformed output, missing configuration, or provider failure falls back to deterministic behavior.

The first experimental adapter is inspired by TypeSafe AI's Jev/System One interface. It is optional, stdlib-only, and not part of the default offline dependency surface. See `skills/margos/references/reflex-provider.md`.

## Layer 3: Execution

Execution remains host-native. Codex uses native subagents when proven available; Copilot/VS Code maps roles to the shipped hidden `margos-*` leaf agents. A route receipt is still only `PROPOSED` until the host supplies runtime evidence.

## Evaluation

The frozen routing suite and benchmark harness live under:
- `tests/fixtures/margos/routing-cases-v1.json`
- `scripts/benchmark_margos_routing.py`
- `docs/MARGOS_EVALUATION.md`

CI runs the deterministic fixture benchmark. Live provider evaluation is opt-in and never required for installation, source validation, or CI.

## Authority rule

> Probabilistic routing may choose among allowed paths; only deterministic Policy defines the allowed paths.

The optional Reflex layer can improve route selection, but it cannot create credentials, permissions, host capabilities, execution facts, or verification evidence.


## Issue #10: evidence-aware Context Governor

MARGOS keeps the same three layers. Reflex gains a second decision family for context allocation, but Context Governor is not a fourth authority layer.

Policy deterministically defines which context may be reduced. Context Reflex may later estimate usefulness only inside that admissible set. Execution materializes a derived Context View. Canonical repository/file state, tool evidence, Proof/Freshness artifacts, route receipts, and external readback remain authoritative outside the view.

Phase 1 is deliberately offline and provider-free. The implementation adds versioned context item/state/decision/receipt schemas, deterministic protection and replayability rules, explicit supersession metadata, the PIN / KEEP_FULL / KEEP_REF / KEEP_HEAD / OMIT_REHYDRATABLE action model, content-addressed rehydration contracts, and a safe context materializer in skills/margos/scripts/margos_context.py.

The deterministic baseline pins binding authority/evidence, keeps non-replayable items full, keeps structured references for current replayable eligible items, and permits omission only for replayable items that are explicitly superseded. No Phase 1 path deletes canonical evidence or repeats an external mutation.
