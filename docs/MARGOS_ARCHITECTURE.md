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


## Context Reflex Phase 2

Phase 2 preserves the same three-layer architecture:

```text
deterministic Context Policy
          |
          v
 optional Context Reflex
 keep_awareness / keep_full / replay_needed
          |
          v
 deterministic composition
 thresholds / abstention / vetoes
          |
          v
 derived Context View materializer
```

Only replayable Policy-eligible items can be evaluated by Context Reflex. Protected constraints/evidence and non-replayable items never enter the remote candidate set.

The existing provider abstraction and TypeSafe/Jev transport are reused. Live Context Reflex is explicit opt-in; an API key in the environment does not activate it by itself. Missing key, malformed answer, or provider failure cannot authorize omission and falls back conservatively.

The remote Context Reflex projection excludes raw item payloads and replaces local item IDs with batch-local candidate keys. Batch size and projection-character budgets are deterministic local contracts. Context receipts bind the question-set hash, threshold-policy version, provider status, request/network counts, and per-item Reflex probabilities without claiming that retained content is true or omitted content is irrelevant.


## Role-aware child context Phase 3

Phase 3 connects Context Governor to actual MARGOS child execution without adding a new authority layer.

```text
route receipt
   -> parent Context View/receipt
   -> versioned child contract + role policy
   -> child bundle/receipt
   -> route context_binding
   -> host-native child
   -> optional parent-side rehydration
```

Scout, Worker, Verifier, and Independent Critic receive distinct bounded bundles. Policy-protected state always crosses the handoff. Required role evidence cannot be removed by optional budgets. Independent Critic inherits no optional implementation context.

The child-context receipt binds the unbound route receipt, parent context receipt/view, handoff-policy version, bundle hash, required coverage, and reduction metrics. Binding is derived and never mutates canonical evidence.

Child rehydration is request-only from the leaf agent. Exact recovery is performed at the parent boundary with the existing content-hash checks. Recompute/refetch methods that require authority review remain pending until that review occurs.


## Evaluation and optional compaction Phase 4

Phase 4 closes Issue #10 without changing the three-layer authority model.

```text
canonical evidence
      |
Policy -> optional Context Reflex
      |
derived Context View / child bundle
      |
counterfactual benchmark + rehydration oracle
      |
optional host-neutral compaction proposal
      |
host runtime evidence, if any
```

The frozen benchmark evaluates full-context vs deterministic Policy vs fixture Context Reflex on synthetic evidence-bound cases. Harmful omission, protected-state loss, non-replayable omission, unresolved external-effect loss, contradiction loss, verified-success, reduction, rehydration, provider usage, and probability metrics are recorded.

Optional root compaction remains outside the portable authority path. The core only proposes whether to leave context untouched, defer to a proven host-native compactor, or offer an already-derived view to an explicitly enabled/proven hook. It never claims application without host runtime evidence.

## Issue #16: JEV v2 Reflex control plane

Issue #16 completes the next production-shaped Reflex layer without changing authority ownership. Routing now exposes explicit live-provider selection from the normal CLI and composes all seven typed routing judgments: Choice winners plus probability mass from task ambiguity, verification risk, escalation need, critic need, and transfer sufficiency. Deterministic Policy still defines the admissible envelope.

Context Reflex can optionally add a privacy-bounded semantic capsule derived from a locally verified exact payload. Remote semantic content is opt-in, length-capped, secret-filtered, and never becomes canonical state. Jev questions reference concrete state paths such as `state.candidates[N]` to reduce indirection.

Calibration is version-aware: research may follow `jev-latest`, while calibrated operation requires a pinned model and an explicit binding to the question set, threshold policy, projection version, and frozen corpus. Drift becomes `STALE`. A separate redacted trace harness lets maintainers evaluate representative Codex routing/context traces locally without committing private transcripts.
