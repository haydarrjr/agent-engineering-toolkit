---
name: margos
description: "Use only when the user explicitly requests MARGOS to coordinate host-native subagents, choose compute tiers, or govern delegation and runtime boundaries."
---

# MARGOS

MARGOS is an explicit, model/provider-agnostic orchestrator for optional computation. Keep the root session as the integration owner, but do not assume the root model should execute every subtask. Use only host-native subagents and model controls that the current client actually exposes; MARGOS never requires an MCP server, daemon, or global model change.

## Orchestrate

1. Bind the requested outcome, write ownership, and hard authority boundaries.
2. Inspect the effective host surface before delegation. Missing subagent or per-child model capability falls back to direct execution; never claim a child or model ran without host evidence.
3. Choose the smallest sufficient compute class. A bounded read-only research, review, or mapping task may transfer to a cheaper child even when it is the only subtask. Ordinary implementation uses balanced execution. Escalate only when ambiguity, failed verification, conflicting evidence, cross-system impact, or another hard obligation justifies deeper reasoning.
4. Treat the root model selected in the UI as the parent session, not as a blanket child-model constraint. Obey an explicit user instruction that all work, or a named subtask, must use a specific model/provider.
5. Keep one compute class for an active subtask. Re-evaluate at a real handoff boundary instead of oscillating models mid-task.
6. Integrate child results at the root, run the verification needed for the requested outcome, and reconcile unknown external effects before retrying.

Load only the reference that owns the current decision:

- [decision model](references/decision-model.md) for direct, transfer, delegation, serialization, and ownership choices.
- [model routing](references/model-routing.md) for compute classes and escalation/de-escalation signals.
- [Codex host adapter](references/host-codex.md) when Codex native subagents are available.
- [Copilot/VS Code host adapter](references/host-copilot.md) when GitHub Copilot custom agents or VS Code subagents are available.
- [host boundaries](references/host-boundaries.md) for capability evidence, explicit model constraints, or profile changes.
- [external effects](references/external-effects.md) for destructive, production, credentialed, or irreversible mutations.

Finish with the requested result, host evidence for delegated work, and unresolved capability or reconciliation state. MARGOS remains explicit-only for ordinary engineering work.
