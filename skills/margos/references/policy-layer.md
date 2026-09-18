# MARGOS Policy layer

Policy is deterministic, local, and authoritative over routing admissibility. It runs before Reflex and again after composition.

Policy may:
- remove delegation when subagent capability is not proven;
- remove parallel delegation when scopes overlap, mutable state is shared, or concurrency is unproven;
- remove `ECONOMY_READ` from mutation obligations;
- preserve explicit user model/provider constraints;
- force direct fallback when only the root is proven safe;
- halt when remote/destructive/production authority is missing;
- halt when an earlier external mutation has an unresolved outcome.

Policy must not infer capability from a profile, model label, prior success, or Reflex output. If one safe route remains, no probabilistic call is needed.

The machine-readable implementation lives in `skills/margos/scripts/margos_decide.py`; Policy rule IDs are stable `MARGOS-POL-*` identifiers so tests and future route receipts can explain deterministic decisions without free-form model prose.
