# Routing

| Intent | Primary skill | Activation |
| --- | --- | --- |
| Cross-language implementation, architecture, refactor, debugging, review | `software-craft` | implicit |
| Python code, tests, packaging, Python architecture | `python-engineering-harness` | implicit |
| Delegation, host capability, runtime/profile decision, external-effect coordination | `margos` | explicit only |
| AGENTS.md / skill / prompt / agent-configuration audit against current OpenAI ReThinking guidance | `rethinking` | explicit only |
| Create, audit, port, package, validate, or reconcile Agent Plugins | `agent-plugins-author` | explicit only |

## Precedence

Choose the narrowest owner. A Python task does not load Software Craft as a second primary. Mentioning `plugin.json` in an ordinary bug report does not activate Agent Plugins Author unless authoring/compatibility is the requested task. ReThinking does not run automatically simply because instructions exist.
