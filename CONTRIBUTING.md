# Contributing

Thanks for helping improve Agent Engineering Toolkit.

## Good contributions

Useful contributions include bug fixes, routing improvements, tests, documentation, portability fixes, deterministic validators, new reference material that is genuinely non-obvious, and narrowly scoped new skills that solve a reusable maintainer problem.

Avoid adding generic advice that a capable coding agent can infer, large always-loaded instruction files, hidden network calls, telemetry, secrets, or host-specific policy to portable surfaces.

## Development

1. Fork or branch from `main`.
2. Make the smallest coherent change.
3. Add or update tests when behavior changes.
4. Run `python scripts/validate_repository.py` and `python -m unittest discover -s tests -p 'test_*.py' -v`.
5. If a skill changes, run its relevant helper or self-test.
6. Explain behavior, evidence, and remaining risk in the pull request.

## Skill design

Keep each `SKILL.md` compact and route detailed knowledge to `references/` or deterministic logic to `scripts/`. Trigger behavior belongs in the YAML `description`. Explicit-only skills must also set `policy.allow_implicit_invocation: false` in `agents/openai.yaml`.

## Provenance

Do not copy private or third-party material without clear rights and provenance. When importing or adapting material, update `provenance/imports.json` with the source, immutable commit, treatment, and licensing basis.

## Security

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).
