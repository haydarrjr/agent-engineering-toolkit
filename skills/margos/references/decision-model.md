# MARGOS decision model

Keep four decision dimensions separate.

## Coordination shape

- **DIRECT** — keep work on the root when coordination overhead would exceed likely compute/context savings or the host cannot prove child capability.
- **TRANSFER** — hand one self-contained obligation to one better-suited child, then return the artifact/result to the root.
- **DELEGATED** — split independent obligations across children only when write/effect scopes are disjoint and the host proves concurrency support.
- **SERIALIZED** — use children in sequence when they share files, state, evidence, or another ordering dependency.

## Disposition

- **PROCEED** — a safe route remains.
- **FALLBACK_DIRECT** — requested/possible delegation cannot be proven safely, so the root owns the obligation.
- **HALT** — authority or external-effect state must be reconciled before execution continues.

Fallback and halt are intentionally different. Missing child capability normally falls back to the root. An unresolved destructive/credentialed/production effect halts until authoritative readback resolves the state.

## Compute tier

- **ECONOMY_READ** — bounded low-ambiguity read-only work.
- **BALANCED_EXEC** — ordinary implementation/debugging/verification.
- **FRONTIER_REASONING** — unresolved contradictions, failed verification, high-impact obligations, or difficult synthesis that cannot be decomposed safely.

## Role

Role is not compute. A `SCOUT`, `WORKER`, `VERIFIER`, or `INDEPENDENT_CRITIC` may run at whichever compute tier is sufficient and proven available. This preserves the existing `INDEPENDENT_CRITIC` concept while preventing it from being mistaken for a model tier.

Delegation is an execution choice, not a permission upgrade. A child cannot expand connector scope, sandbox, credentials, production authority, or the user's model/provider constraint. Keep each child contract small: outcome, inputs, owned paths, allowed effects, return artifact, and completion signal.
