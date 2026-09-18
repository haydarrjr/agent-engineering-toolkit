# Agent Engineering Toolkit

[![CI](https://github.com/haydarrjr/agent-engineering-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/haydarrjr/agent-engineering-toolkit/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

**Agent Engineering Toolkit (AET)** is an open-source, skills-first engineering plugin for agent-assisted software development. It combines focused repository engineering, a Python-specific engineering harness, explicit host-native MARGOS orchestration, repository instruction audits based on OpenAI's current ReThinking guidance, and Agent Plugins authoring/validation in one portable package.

AET is intentionally small at activation time: the host sees five narrow skills and loads detailed references, client adapters, or scripts only when the task needs them.

> AET is an independent open-source project. It is not an OpenAI or GitHub product and is not endorsed by either company.

## Why this project exists

Modern coding agents can read repository instructions, skills, manifests, and tool configuration, but more context is not automatically better. AET gives maintainers reusable, reviewable engineering workflows while keeping task ownership, model-routing evidence, and external-effect boundaries explicit.

The project is designed for real maintainer work: implementation, debugging, test repair, PR review, instruction audits, plugin packaging, compatibility checks, release validation, and OSS maintenance automation.

## Skills

| Skill | Activation | Purpose |
| --- | --- | --- |
| `software-craft` | implicit | Cross-language repository engineering when no narrower owner applies |
| `python-engineering-harness` | implicit | Python implementation, debugging, tests, packaging, and architecture |
| `margos` | explicit only | Host-native subagent orchestration, compute-tier routing, ownership, and runtime/effect boundaries |
| `rethinking` | explicit only | Audit and repair repository instruction surfaces against current official OpenAI guidance |
| `agent-plugins-author` | explicit only | Author, audit, port, validate, package, and reconcile portable Agent Plugins |

Explicit-only skills do not activate merely because a repository contains agent configuration.

## MARGOS adaptive orchestration

MARGOS keeps the root session as integration owner without forcing every subtask onto the root model.

```text
root / parent session
        |
        v
      MARGOS
        |
        +-- ECONOMY_READ
        |     bounded mapping, research, mechanical review
        |
        +-- BALANCED_EXEC
        |     ordinary implementation and debugging
        |
        +-- FRONTIER_REASONING
        |     contradictions, failed verification, high-impact synthesis
        |
        +-- INDEPENDENT_CRITIC
              fresh-context falsification
```

Routing is evidence-driven. Prompt length, file count, or the words "research" and "review" are not escalation signals by themselves. An explicit user model/provider constraint remains authoritative. If a host cannot prove child/model-routing capability, MARGOS falls back to direct execution rather than claiming a model switch occurred.

## Quick examples

```text
Fix the failing parser tests and preserve the public API.
```

Routes to the Python harness when the repository is Python.

```text
Use $margos to map this repository with a low-cost read-only child, then escalate only if verification exposes a hard contradiction.
```

```text
Use $rethinking to audit this repository's AGENTS.md and skills against the current OpenAI ReThinking guidance.
```

```text
Use $agent-plugins-author to turn this repository into a portable Agent Plugins 1.0 package and validate the Codex and Copilot marketplace surfaces.
```

## Portable plugin layout

```text
agent-engineering-toolkit/
├── plugin.json
├── skills/
│   ├── software-craft/
│   ├── python-engineering-harness/
│   ├── margos/
│   ├── rethinking/
│   └── agent-plugins-author/
├── com.github.copilot/
│   └── agents/
│       ├── margos-scout.agent.md
│       ├── margos-worker.agent.md
│       ├── margos-verifier.agent.md
│       └── margos-critic.agent.md
├── .codex-plugin/plugin.json
├── .agents/plugins/marketplace.json
└── .github/plugin/marketplace.json
```

The root `plugin.json` and `skills/` directory are portable authority. Copilot custom agents and Codex/native metadata are client adapters, not a second source of portable policy. AET does not require an MCP server or background orchestration daemon.

## Install / use

### GitHub Copilot CLI

GitHub documents Agent Plugins 1.0 and repository-hosted marketplaces. Register the marketplace and install the plugin:

```bash
copilot plugin marketplace add haydarrjr/agent-engineering-toolkit
copilot plugin install agent-engineering-toolkit@agent-engineering-toolkit
```

The Copilot adapter exposes hidden `margos-*` leaf agents with `model: auto`; the host/account decides the exact available provider/model.

### ChatGPT / Codex-compatible hosts

Use the repository as an Agent Plugins source or marketplace in a compatible host. Codex-specific MARGOS guidance uses native subagents and host-reported child model/reasoning controls when available. Installation, discovery, authentication, child execution, and exact model selection remain separate runtime evidence from source validation.

## Local validation

AET has no required third-party Python dependency for source validation.

```bash
python scripts/validate_repository.py
python scripts/validate_margos_host_adapters.py
python -m unittest discover -s tests -p 'test_*.py' -v
python skills/python-engineering-harness/scripts/self_test.py
python skills/rethinking/scripts/audit_repository.py --root . --format text
python skills/agent-plugins-author/scripts/validate_agent_plugin.py .
python skills/agent-plugins-author/scripts/validate_skill_design.py .
python skills/agent-plugins-author/scripts/render_marketplace.py . --check
python skills/agent-plugins-author/scripts/render_copilot_marketplace.py . --check
python scripts/build_release.py --check-reproducible
```

## Open-source lineage

This repository starts a clean OSS lineage. It does **not** publish the private Git history of its source projects. Selected maintainer-owned concepts were transformed from `engineering-agent-toolkit`, while Agent Plugins authoring material was adapted from the MIT-licensed `agent-plugins-author` repository. Exact immutable source commits and treatment are recorded in [`provenance/imports.json`](provenance/imports.json).

Official OpenAI and GitHub documentation is referenced, not vendored as project-authored content.

## Maintainer model

Önder Türkan (`@haydarrjr`) is the founding primary maintainer. See [GOVERNANCE.md](GOVERNANCE.md), [MAINTAINERS.md](MAINTAINERS.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

For the public maintenance roadmap and evidence model, see [docs/MAINTAINER_WORKFLOWS.md](docs/MAINTAINER_WORKFLOWS.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
