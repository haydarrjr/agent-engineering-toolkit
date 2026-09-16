# GitHub Copilot compatibility

GitHub documents Agent Plugins 1.0 with a root `plugin.json`, fixed `skills/`, and optional root `mcp.json`. Repository marketplaces use `.github/plugin/marketplace.json`. Keep Copilot-only components separate from the portable contract. Validate marketplace source paths and versions deterministically.
