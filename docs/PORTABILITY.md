# Portability

AET targets portable Agent Plugins 1.0 for the canonical plugin surface. GitHub Copilot currently documents Agent Plugins 1.0 with a root `plugin.json`, fixed `skills/`, and optional root `mcp.json`; AET uses only the portable skills subset.

Client-specific adapters and marketplaces are intentionally separate. Compatibility claims are bounded:

- source structure can be validated locally;
- marketplace syntax can be validated locally;
- a real host installation requires host evidence;
- a live execution requires runtime evidence.

The project avoids absolute developer paths, credentials, machine-local state, and hidden dependency installation.
