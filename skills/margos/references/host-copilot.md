# GitHub Copilot and VS Code host adapter

The Agent Plugins package ships hidden MARGOS leaf agents under `com.github.copilot/agents/`; no MCP server is required.

- `SCOUT` -> `margos-scout`
- `WORKER` -> `margos-worker`
- `VERIFIER` -> `margos-verifier`
- `INDEPENDENT_CRITIC` -> `margos-critic`
- `PRIMARY` -> root session

Each helper keeps `model: auto`; MARGOS selects the abstract role/compute need while the host resolves the exact available model. Runtime evidence is required before changing execution status.

## Phase 3 bounded handoff

Before a child invocation:
1. build the role-aware bundle with `margos_handoff.py`;
2. bind child-context receipt hashes into the derived route receipt;
3. pass the child task contract + bounded bundle to the mapped leaf agent;
4. do not automatically attach the root's whole conversation;
5. parse any `rehydration_requests` at the parent boundary;
6. rehydrate only exposed references through deterministic checks.

Leaf agents treat omitted context as unavailable instead of guessing it. Independent Critic receives no optional inherited implementation context. Children never gain authority to repeat a remote mutation.

If subagent execution/model selection is unavailable, fall back to direct work and report the host limitation. Do not infer the exact provider/model from `auto`.
