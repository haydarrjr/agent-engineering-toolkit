# GitHub Copilot and VS Code Agent Plugins

GitHub Copilot consumes the portable Agent Plugins 1.0 package from the root `plugin.json` and immediate `skills/` children. Keep portable authority separate from Copilot-only components.

Copilot-specific components belong under the fixed client namespace:

```text
com.github.copilot/agents/
com.github.copilot/commands/
com.github.copilot/rules/
com.github.copilot/hooks/hooks.json
com.github.copilot/lsp.json
```

Do not add legacy component-path fields such as `agents`, `skills`, `hooks`, `mcpServers`, or `lspServers` to the portable Agent Plugins 1.0 manifest.

For repository distribution, use `.github/plugin/marketplace.json`. When the marketplace and plugin share the repository root, `source: "."` is the deterministic local source. Keep `strict: true`; marketplace version should match `plugin.json`.

Custom agents may define host-specific model/tool behavior. Treat `model: auto` as host-owned model selection, not proof of the exact provider/model used. Source validation proves package shape only; installation, discovery, child execution, and runtime model readback remain separate evidence.
