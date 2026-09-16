# Agent Engineering Toolkit

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

**Agent Engineering Toolkit (AET)** is an open-source, skills-first engineering plugin for agent-assisted software development. It combines focused repository engineering, a Python-specific engineering harness, explicit coordination/governance tools, repository instruction audits based on OpenAI's current ReThinking guidance, and Agent Plugins authoring/validation in one portable package.

AET is intentionally small at activation time: the host sees five narrow skills and loads detailed references or scripts only when the task needs them.

> AET is an independent open-source project. It is not an OpenAI or GitHub product and is not endorsed by either company.

## Why this project exists

Modern coding agents can read repository instructions, skills, manifests, and tool configuration, but more context is not automatically better. AET gives maintainers reusable, reviewable engineering workflows while keeping task ownership and external-effect boundaries explicit.

The project is designed for real maintainer work: implementation, debugging, test repair, PR review, instruction audits, plugin packaging, compatibility checks, release validation, and OSS maintenance automation.

## Skills

| Skill | Activation | Purpose |
| --- | --- | --- |
| `software-craft` | implicit | Cross-language repository engineering when no narrower owner applies |
| `python-engineering-harness` | implicit | Python implementation, debugging, tests, packaging, and architecture |
| `margos` | explicit only | Coordination, delegation, host-capability, and external-effect boundaries |
| `rethinking` | explicit only | Audit and repair repository instruction surfaces against current official OpenAI guidance |
| `agent-plugins-author` | explicit only | Author, audit, port, validate, package, and reconcile portable Agent Plugins |

Explicit-only skills do not activate merely because a repository contains agent configuration.

## Quick examples

```text
Fix the failing parser tests and preserve the public API.
```

Routes to the Python harness when the repository is Python.

```text
Use $rethinking to audit this repository's AGENTS.md and skills against the current OpenAI ReThinking guidance.
```

```text
Use $agent-plugins-author to turn this repository into a portable Agent Plugins 1.0 package and validate the marketplace surfaces.
```

```text
Use $margos to decide whether these three independent repository audits should be delegated and define the write boundaries.
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
├── .codex-plugin/plugin.json
├── .agents/plugins/marketplace.json
└── .github/plugin/marketplace.json
```

The root `plugin.json` and `skills/` directory are the portable authority. Client-specific marketplace or adapter files are derived distribution surfaces, not a second source of policy.

## Install / use

### GitHub Copilot CLI

GitHub documents Agent Plugins 1.0 and repository-hosted marketplaces. After the repository is public, register the marketplace and install the plugin:

```bash
copilot plugin marketplace add haydarrjr/agent-engineering-toolkit
copilot plugin install agent-engineering-toolkit@agent-engineering-toolkit
```

### ChatGPT / Codex-compatible hosts

Use the repository as an Agent Plugins source or marketplace in a host that supports portable Agent Plugins. Host installation, discovery, authentication, and live behavior are separate evidence from source validation; AET never claims a host is installed or live merely because CI is green.

## Local validation

AET has no required third-party Python dependency for source validation.

```bash
python scripts/validate_repository.py
python -m unittest discover -s tests -p 'test_*.py' -v
python skills/python-engineering-harness/scripts/self_test.py
python skills/rethinking/scripts/audit_repository.py --root . --format text
python skills/agent-plugins-author/scripts/validate_agent_plugin.py .
python skills/agent-plugins-author/scripts/validate_skill_design.py .
python scripts/build_release.py --check-reproducible
```

## Open-source lineage

This repository starts a clean OSS lineage. It does **not** publish the private Git history of its source projects. Selected concepts and maintainer-owned material were transformed from `engineering-agent-toolkit`, while Agent Plugins authoring material was adapted from the MIT-licensed `agent-plugins-author` repository. Exact source commits and treatment are recorded in [`provenance/imports.json`](provenance/imports.json).

Official OpenAI and GitHub documentation is referenced, not vendored as project-authored content.

## Maintainer model

Önder Türkan (`@haydarrjr`) is the founding primary maintainer. See [GOVERNANCE.md](GOVERNANCE.md), [MAINTAINERS.md](MAINTAINERS.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

For the public maintenance roadmap and evidence model, see [docs/MAINTAINER_WORKFLOWS.md](docs/MAINTAINER_WORKFLOWS.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
