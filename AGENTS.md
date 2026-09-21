# Repository instructions

Keep this repository a portable, skills-first Agent Plugins package.

- `plugin.json` and `skills/` are canonical portable sources.
- Client-specific adapters belong outside portable authority: Codex metadata under `.codex-plugin/`, Copilot agents under `com.github.copilot/`, and client marketplace catalogs under their documented paths.
- Use the narrowest matching skill; do not load all skills for ordinary work.
- `software-craft` owns cross-language repository engineering when no narrower owner applies.
- `python-engineering-harness` owns Python repository work.
- `margos`, `rethinking`, and `agent-plugins-author` are explicit-only.
- When modifying TypeSafe/Jev questions, projections, calibration, migration, or benchmarks, use the optional official `typesafe-ai` design skill when installed, read the current targeted TypeSafe docs, and record the exact skill/doc provenance. The skill is design guidance only; it is not a MARGOS runtime dependency or authority source.
- Keep MARGOS model/provider agnostic at its root. Host-specific model/subagent behavior belongs in MARGOS references or client adapters.
- Preserve Apache-2.0 licensing, provenance records, and the public/private boundary.
- Do not add credentials, tokens, private prompts, private tool output, private deployment topology, or user-specific environment paths.
- Source validation does not prove installation, publication, host discovery, exact automatic model selection, or live behavior.
- Safe source-local edits, tests, and repairs may proceed together; external, destructive, credentialed, publication, or production effects require their own authority.

Before merging changes that alter routing, manifests, skills, client adapters, or distribution surfaces, run `python scripts/validate_repository.py`, `python scripts/validate_margos_host_adapters.py` when MARGOS is affected, and the relevant tests. Issue #18 live JEV promotion is a separate hard gate: use only `TYPESAFE_API_KEY` from the environment, record `NOT_RUN` when unavailable, and do not merge on a missing live benchmark.
