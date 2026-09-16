# Repository instructions

Keep this repository a portable, skills-first Agent Plugins package.

- `plugin.json` and `skills/` are canonical portable sources.
- Use the narrowest matching skill; do not load all skills for ordinary work.
- `software-craft` owns cross-language repository engineering when no narrower owner applies.
- `python-engineering-harness` owns Python repository work.
- `margos`, `rethinking`, and `agent-plugins-author` are explicit-only.
- Preserve Apache-2.0 licensing, provenance records, and the public/private boundary.
- Do not add credentials, tokens, private prompts, private tool output, private deployment topology, or user-specific environment paths.
- Source validation does not prove installation, publication, host discovery, or live behavior.
- Safe source-local edits, tests, and repairs may proceed together; external, destructive, credentialed, publication, or production effects require their own authority.

Before merging changes that alter routing, manifests, skills, or distribution surfaces, run `python scripts/validate_repository.py` and the affected tests.
