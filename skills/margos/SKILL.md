---
name: margos
description: "Use only when the user explicitly requests MARGOS to coordinate host-native subagents, choose compute tiers, or govern delegation and runtime boundaries."
---

# MARGOS

MARGOS is an explicit, model/provider-agnostic orchestrator for optional computation. Keep the root session as integration owner, but do not assume the root model should execute every subtask. MARGOS uses three layers: deterministic Policy defines what is allowed, optional typed Reflex judgment chooses among allowed paths, and host-native Execution maps the abstract route to capabilities the current client can actually prove. Policy always outranks Reflex.

## Orchestrate

1. Bind the requested outcome, write ownership, verification obligation, and hard authority boundaries.
2. Inspect the effective host surface before delegation. Missing subagent or per-child model capability falls back to direct execution; never claim a child or model ran without host evidence.
3. Apply deterministic Policy first. External-effect uncertainty, missing authority, overlapping writes, or unproven host capabilities may remove routes or halt execution before any Reflex evaluation.
4. When more than one safe route remains, use the smallest sufficient compute tier. Reflex judgment may rank only Policy-admissible routes and never expands permission, evidence strength, or host capability.
5. Treat the root model selected in the UI as the parent session, not as a blanket child-model constraint. Obey an explicit user instruction that all work, or a named subtask, must use a specific model/provider.
6. Integrate child results at the root, run the verification needed for the requested outcome, and reconcile unknown external effects before retrying.
7. When context allocation matters, build the smallest evidence-sufficient derived Context View. Never omit Policy-protected constraints, unresolved effects, contradictions, or active verification evidence; canonical evidence remains unchanged.

Load only the reference that owns the current decision:

- [decision model](references/decision-model.md) for coordination shape, disposition, role, and ownership choices.
- [policy layer](references/policy-layer.md) for deterministic admission, hard vetoes, and safe fallback.
- [reflex layer](references/reflex-layer.md) for typed judgments, abstention, and provider-neutral contracts.
- [context governor](references/context-governor.md) when active context allocation, replayability, or rehydration matters.
- [reflex confidence](references/reflex-confidence.md) for probability/calibration boundaries.
- [optional Reflex provider](references/reflex-provider.md) only when an external Reflex backend is explicitly configured or evaluated.
- [execution layer](references/execution-layer.md) for abstract-route to host-native execution mapping.
- [value-of-call and retrieval contracts](references/value-of-call.md) for concrete executable opportunities, deterministic semantic admission, metadata-first lazy retrieval, and conservative fallback.
- [model routing](references/model-routing.md) for compute tiers and escalation/de-escalation signals.
- [Codex host adapter](references/host-codex.md) when Codex native subagents are available.
- [Copilot/VS Code host adapter](references/host-copilot.md) when GitHub Copilot custom agents or VS Code subagents are available.
- [host boundaries](references/host-boundaries.md) for capability evidence, explicit model constraints, or profile changes.
- [external effects](references/external-effects.md) for destructive, production, credentialed, or irreversible mutations.

The default contract helper is [margos_decide.py](scripts/margos_decide.py). Its deterministic/provider-neutral path is offline by default; an external Reflex adapter is used only when the caller explicitly selects one and passes the deterministic Reflex Admission gate. The offline context helper is [margos_context.py](scripts/margos_context.py); it materializes derived Context Views without mutating canonical evidence. Evidence capsules are locally extracted, exact, hash-bound, budgeted, and secret-screened. External providers are optional, fail closed, and are never required for ordinary MARGOS use. Finish with the requested result, host evidence for delegated work, and unresolved capability or reconciliation state. MARGOS remains explicit-only for ordinary engineering work.

Issue #21 adds `margos_value.py` for deterministic value-of-call admission,
`margos_retrieval.py` for metadata-only planning followed by lazy payload
materialization, and the executable counterfactual benchmark for forced
counterfactual arms. `decide(..., shadow=True)` records a typed judgment while
preserving the Policy fallback for first-stage domain calibration.
