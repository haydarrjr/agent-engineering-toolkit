# Codex host adapter

Use Codex native subagents; do not add an MCP server or background runtime for MARGOS.

- `ECONOMY_READ`: prefer a read-focused/explorer child with the lowest sufficient proven capability.
- `BALANCED_EXEC`: use an execution-focused worker with task-appropriate reasoning.
- `FRONTIER_REASONING`: use a fresh strongest available reasoning configuration only after escalation.
- `INDEPENDENT_CRITIC`: prefer fresh read-only context.

A route receipt remains `PROPOSED`; runtime evidence is required before claiming a child/model tier ran.

## Phase 3 bounded child context

For `TRANSFER`, `DELEGATED`, or `SERIALIZED`, build a `margos-child-context-bundle/v1` before invoking the native subagent. Pass the bounded task + bundle, not an assumed copy of the whole root transcript.

Preserve Policy-protected state, role-specific requirements, Worker owned paths, Verifier implementation/verification evidence, Critic fresh bounded evidence, and rehydration references.

The bound route receipt carries child-context receipt/bundle hashes. These identify the proposed handoff, not execution.

If exact content behind `KEEP_REF`/`KEEP_HEAD` is needed, the child returns a structured rehydration request. The parent resolves it through deterministic safety checks; the child must not silently rerun mutable/external effects.

Do not invent a Codex transcript-compaction hook. Exact model names remain host state. If only the parent model is available, run directly rather than pretending a tier change occurred.
