# GitHub Copilot and VS Code host adapter

The Agent Plugins 1.0 package ships MARGOS helper agents under `com.github.copilot/agents/`. They are client-specific adapters; the portable MARGOS skill remains model/provider agnostic and no MCP server is required.

## Shipped agents

- `margos-scout` — read-only mapping and bounded research.
- `margos-worker` — ordinary scoped implementation.
- `margos-verifier` — independent checks without production-code edits.
- `margos-critic` — fresh-context falsification for ambiguous or high-impact work.

Each helper uses `model: auto` so Copilot/VS Code can choose among models allowed by the current account. MARGOS chooses the role and compute need; the host resolves the exact available model.

When a vNext route receipt is available, map roles as follows:
- `SCOUT` -> `margos-scout`
- `WORKER` -> `margos-worker`
- `VERIFIER` -> `margos-verifier`
- `INDEPENDENT_CRITIC` -> `margos-critic`
- `PRIMARY` -> root session

The route receipt remains `PROPOSED`. Client runtime evidence is required before changing `host_execution.status` or claiming an exact model ran.

When subagent execution is available, invoke the narrowest helper with a bounded return contract. The shipped helpers do not receive an agent tool, so they cannot recursively expand the graph. If the client does not expose subagent execution or automatic model selection, fall back to direct work and report the host limitation.

Do not infer the exact provider/model from `auto`; use runtime readback when available. An explicit instruction to use one model/provider for all work overrides automatic binding.
