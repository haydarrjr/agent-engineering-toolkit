# MARGOS role-aware child context

Phase 3 binds a finalized child route to a bounded, role-aware derived context bundle before host-native child execution.

This remains Layer 3 Execution. It does not add authority and never mutates the canonical context source.

## Portable handoff flow

route receipt -> parent Context View/receipt -> role-aware child contract -> margos_handoff.py -> child bundle/receipt -> bound route receipt -> host child -> optional rehydration request

A child handoff is valid only for a `PROCEED` route using `TRANSFER`, `DELEGATED`, or `SERIALIZED` and a child role. `DIRECT` / `PRIMARY` does not create a child bundle.

The original route receipt and canonical context state are not modified in place. The child-context receipt stores hashes of the unbound route receipt and parent context receipt. A derived route-receipt copy gains `context_binding` with hashes of the child-context receipt and bundle.

## Child contract

`margos-child-contract/v1` carries child ID/role, objective, owned paths, required context IDs, explicit full IDs, implementation-result IDs, verification-evidence IDs, fresh-evidence IDs, verification obligation, output contract, and optional budgets. The role must match the finalized route.

## Versioned role policy

`contracts/child-handoff-policy-v1.json` owns deterministic role behavior.

- Scout receives Policy-protected state, explicit required context, and bounded search/find/grep evidence. Ordinary eligible full payloads are capped to exact `KEEP_HEAD` unless explicitly full.
- Worker receives Policy-protected state, task + owned paths, explicit requirements, and bounded owned-path context.
- Verifier receives Policy-protected state, exact implementation result(s), exact explicit verification evidence, the verification obligation, and bounded test/build/verify/check context.
- Independent Critic receives Policy-protected state, exact implementation result(s), and fresh evidence capped to `KEEP_HEAD` unless explicitly full. It inherits no optional implementation context.

Policy-protected and explicitly required items are never dropped by optional budgets. Optional context is newest-first, role-matched, and limited by item/payload budgets. If optional payload budget is exhausted, awareness may remain as `KEEP_REF`.

## Receipt and binding

The child-context receipt records required/selected/omitted IDs, required coverage, input/output characters, provider metadata inherited from the parent Context decision, hash bindings, and rehydration availability. `required_coverage` must remain 1.0 for an evidence-sufficient fixture handoff.

## Rehydration request protocol

A child may request exact content only for an item already exposed as `KEEP_REF` or `KEEP_HEAD`. The child emits `margos-child-result/v1` with `rehydration_requests`; it does not replay the source itself.

`margos_handoff.py plan-rehydration` maps requests to:
- `READY`: safe content-addressed replay may proceed;
- `PENDING_AUTHORITY_RECHECK`: replay needs an authority/freshness recheck;
- `REJECTED_NOT_EXPOSED`: the child requested context it was not given awareness of;
- `REJECTED_UNAVAILABLE`: no safe rehydration path exists.

Injected runtime rehydrators reuse the existing content-hash check. No rehydration contract may silently repeat an external mutation.

## Host boundary

The child bundle is the portable baseline. It does not claim control over a host's internal context window. Codex and Copilot pass the bounded bundle to the selected host-native child; exact model/provider execution still requires runtime evidence. Host-native root compaction remains Phase 4/optional work.
