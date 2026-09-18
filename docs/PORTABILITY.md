# Portability

AET targets portable Agent Plugins 1.0 for the canonical plugin surface. The root `plugin.json` and immediate `skills/` children remain portable authority.

## Codex

`.codex-plugin/plugin.json` is a native adapter, and `.agents/plugins/marketplace.json` is the repository-scoped Codex catalog. MARGOS uses native subagent/model controls only when the effective host exposes them. AET does not install project or global profiles merely to force orchestration.

## GitHub Copilot / VS Code

GitHub Copilot consumes the portable Agent Plugins package plus optional client-specific components under `com.github.copilot/`. AET ships only four bounded MARGOS leaf agents under `com.github.copilot/agents/`, each with host-owned `model: auto` binding and no recursive agent tool.

The Copilot marketplace lives at `.github/plugin/marketplace.json` and keeps strict Agent Plugins 1.0 validation enabled.

## Evidence boundary

Compatibility claims are bounded:

- source structure and marketplace syntax can be validated locally;
- client-specific adapter structure can be validated locally;
- a real host installation requires host evidence;
- a delegated child run requires runtime evidence;
- the exact model selected by a host `auto` policy requires runtime readback.

The project avoids absolute developer paths, credentials, machine-local state, hidden dependency installation, MCP configuration, and background orchestration daemons.
