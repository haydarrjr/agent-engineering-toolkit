---
name: margos
description: "Use only when the user explicitly requests MARGOS coordination, optional delegation, host-capability decisions, or bounded runtime/profile changes."
---

# MARGOS

MARGOS is an explicit decision aid for optional computation. It does not replace the host, grant permission, or turn a plan into execution. Prefer the native direct path unless the requested work has an independent obligation that benefits from coordination.

## Decide

1. State the requested outcome and the single owner of each write scope.
2. Prefer direct work when the task is small, sequential, or already clear.
3. Consider delegation only for independent work with disjoint scopes and a useful handoff boundary. A host must prove child capability; a profile declaration or model name is not proof.
4. Keep the root model, permissions, sandbox, connectors, credentials, and user authority unchanged unless explicitly authorized.
5. Preserve verification, reconciliation, and completion capacity before optional work. Unknown results stop the branch and require reconciliation.

## Runtime and external effects

For a profile/runtime change, inspect effective host state, plan, obtain any required exact authority immediately before mutation, apply only the owned scope, verify the result, and reconcile drift. Never claim a child ran from configuration alone.

Load a reference only when the matching decision is material:

- [decision model](references/decision-model.md)
- [host boundaries](references/host-boundaries.md)
- [external effects](references/external-effects.md)

MARGOS is never selected implicitly for ordinary engineering work.
