# Changelog

All notable project changes are documented here.

## [Unreleased]

### Planned
- Gather external installation and compatibility reports.
- Add maintainer-oriented PR/issue automation examples without adding mandatory runtime dependencies.

## [1.1.0] - 2026-09-18

### Added
- Host-native MARGOS compute routing with `ECONOMY_READ`, `BALANCED_EXEC`, `FRONTIER_REASONING`, and `INDEPENDENT_CRITIC` classes.
- GitHub Copilot / VS Code leaf agents under `com.github.copilot/agents/` with host-owned `model: auto` binding.
- Deterministic MARGOS adapter validation and routing regression coverage.
- Separate deterministic Codex and GitHub Copilot marketplace rendering.

### Changed
- MARGOS now treats the selected root model as the parent/integration session rather than a blanket child-model constraint.
- Escalation is evidence-driven: failed verification, conflicting evidence, material ambiguity, cross-system impact, or explicit deeper-review need.
- Release metadata and provenance were advanced to the 1.1.0 public feature release.

### Security / boundaries
- No MCP server, background runtime daemon, AERO kernel, telemetry sink, or global model installer was added.
- Source validation still does not claim live host installation, child execution, or exact automatic model selection.

## [1.0.0] - 2026-09-17

### Added
- Clean Apache-2.0 OSS lineage.
- Five-skill routing model: Software Craft, Python Engineering Harness, MARGOS, ReThinking, and Agent Plugins Author.
- Portable Agent Plugins 1.0 manifest plus Codex and GitHub Copilot marketplace surfaces.
- Deterministic source validation and reproducible release packaging.
- Public governance, contribution, security, provenance, and maintainer workflow documentation.
