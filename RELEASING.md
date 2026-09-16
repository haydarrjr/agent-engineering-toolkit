# Releasing

Releases are immutable source snapshots.

1. Update `CHANGELOG.md` and version fields in `plugin.json`, `.codex-plugin/plugin.json`, `.github/plugin/marketplace.json`, and `.agents/plugins/marketplace.json`.
2. Run `python scripts/validate_repository.py` and the full unit test suite.
3. Run `python scripts/build_release.py --check-reproducible`.
4. Review provenance and secret-hygiene output.
5. Merge through the normal review path.
6. Tag the exact merged commit as `vX.Y.Z` and create release notes from the changelog.

A tag or package build is not proof that any external marketplace or host has installed the release.
