# MARGOS Execution layer

Execution consumes a finalized abstract route after Policy has revalidated it and maps coordination, disposition, compute tier, role, explicit model/provider constraints, and role-aware derived context to host-native mechanisms.

Execution cannot infer a child/model switch from configuration text. Missing runtime capability uses the Policy fallback; approval, sandbox, credentials, connectors, and mutation authority remain unchanged.

## Context materialization

`margos_context.py` produces a `DERIVED_VIEW`; canonical evidence remains authoritative. Exact payloads are hash-checked, references retain rehydration metadata, and rehydration cannot widen permission or silently repeat an external mutation.

## Phase 3 child handoff

Before `TRANSFER`, `DELEGATED`, or `SERIALIZED` child execution, use `margos_handoff.py` to build a role-aware child bundle and child-context receipt.

Portable order:
1. consume the finalized proposed route;
2. materialize one parent Context View/receipt;
3. validate a child contract whose role matches the route;
4. build the smallest role-aware evidence-sufficient child bundle;
5. create a child-context receipt bound to route/context hashes;
6. create a derived route-receipt copy with `context_binding`;
7. invoke the host-native child;
8. consume runtime evidence and structured rehydration requests;
9. reconcile and verify at the root.

A `DIRECT` / `PRIMARY` route does not create a child bundle. Load [role-aware child context](child-context.md) for role policy, bindings, and rehydration.

Route/context receipts remain proposed/derived artifacts; they do not prove a child or exact model actually ran.
