# MARGOS decision model

Use the smallest useful coordination shape.

- **Direct:** keep work on the root when the task is tiny, sequential, or coordination overhead would exceed likely compute/context savings.
- **Transfer:** hand a self-contained obligation to one cheaper or better-suited child, then return the artifact to the root. A single bounded read-only research or review task may use this shape; parallelism is not required.
- **Delegated:** split independent obligations with disjoint write scopes and explicit return artifacts. The root owns interpretation and integration.
- **Serialized:** use children in sequence when they share files, state, or evidence and cannot safely execute concurrently.
- **Stop/fallback:** use the root path when the host cannot prove required child capability, authority is unclear, write scopes overlap unsafely, or an external mutation outcome is unresolved.

Delegation is an execution choice, not a permission upgrade. A child cannot expand connector scope, sandbox, credentials, production authority, or the user's model/provider constraint. Keep each child contract small: outcome, inputs, owned paths, allowed effects, return artifact, and completion signal.
