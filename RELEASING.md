# Releasing

Releases are immutable source snapshots.

1. Update `CHANGELOG.md` and version fields in `plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `CITATION.cff`, `.github/plugin/marketplace.json`, and `provenance/imports.json`.
2. Render/check the Codex and GitHub Copilot marketplace surfaces independently.
3. Run `python scripts/validate_repository.py`, `python scripts/validate_margos_host_adapters.py`, and the full unit test suite.
4. Run `python scripts/build_release.py --check-reproducible`.
5. Review provenance and secret-hygiene output.
6. Merge through the normal review path.
7. Tag the exact merged commit as `vX.Y.Z` and create release notes from the changelog.

A tag or package build is not proof that any external marketplace or host has installed the release.
