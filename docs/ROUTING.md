# Routing

| Intent | Primary skill | Activation |
| --- | --- | --- |
| Cross-language implementation, architecture, refactor, debugging, review | `software-craft` | implicit |
| Python code, tests, packaging, Python architecture | `python-engineering-harness` | implicit |
| Host-native delegation, compute-tier routing, host capability, runtime/profile decision, external-effect coordination | `margos` | explicit only |
| AGENTS.md / skill / prompt / agent-configuration audit against current OpenAI ReThinking guidance | `rethinking` | explicit only |
| Create, audit, port, package, validate, or reconcile Agent Plugins | `agent-plugins-author` | explicit only |

## Precedence

Choose the narrowest owner. A Python task does not load Software Craft as a second primary. Mentioning `plugin.json` in an ordinary bug report does not activate Agent Plugins Author unless authoring/compatibility is the requested task. ReThinking does not run automatically simply because instructions exist.

Inside explicit MARGOS work, the root/UI model is the parent session choice, not a blanket child constraint. Start an independent obligation at the lowest sufficient compute class and escalate only from evidence.

## MARGOS structural examples

- Bounded read-only repository research -> `ECONOMY_READ` child when the host proves a cheaper native child.
- Ordinary scoped implementation -> `BALANCED_EXEC`.
- Lower-tier result fails relevant verification or leaves a material contradiction -> `FRONTIER_REASONING`.
- Important review that benefits from fresh context -> `INDEPENDENT_CRITIC`.
- Long prompt or many files without ambiguity -> no automatic escalation.
- Explicit all-work model/provider requirement -> preserve it.
- No proven subagent/model-routing capability -> direct fallback; never fabricate a child run.
