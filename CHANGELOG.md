# Changelog

All notable project changes are documented here.

## [Unreleased]

### MARGOS JEV v3
- Hardened routing with independent ambiguity, verification-risk, and direct-escalation thresholds plus deterministic Reflex Admission receipts.
- Added versioned Context Reflex contracts, staged metadata/evidence evaluation, exact evidence capsules, runtime fingerprints, and forced A/B/C/D benchmark tooling.
- Added the Issue #18 ReThinking and Agent Plugins surface audit; live JEV promotion remains gated on an authorized benchmark with `TYPESAFE_API_KEY`.

## [1.2.0] - 2026-09-19

### Added
- MARGOS JEV v2 runtime routing: explicit live Reflex provider selection on the normal routing CLI, probability-derived semantic escalation, direct Jev state-path questions, pinned-model calibration bindings, and stale-calibration detection.
- Privacy-safe semantic Context Reflex capsules: explicit remote opt-in, exact-prefix derivation, SHA-256 binding, deterministic 512-character cap, and secret-like prefix suppression.
- Redacted Codex/MARGOS trace benchmark format, schema, fixture, CI gate, and routing/context metrics for local preflight without committing private transcripts.

- MARGOS vNext three-layer Policy -> Reflex -> Execution contracts with versioned routing-state, Reflex, decision, and route-receipt schemas.
- Optional stdlib TypeSafe Jev Reflex adapter with minimized state projection, typed fail-closed fallback, and no mandatory API key/dependency.
- Frozen MARGOS routing benchmark with authority-boundary, keyword-noise, fallback, escalation, serialization, and abstention coverage.
- Research and evaluation documentation covering Jev inspiration, routing/cascade literature, calibration, and selective deferral.
- MARGOS Context Governor Phase 1 deterministic retention/rehydration contracts and Phase 2 optional Context Reflex with atomic Noul judgments, batching, minimized remote projection, and conservative fallback.
- MARGOS Context Governor Phase 3 role-aware child handoffs with versioned child contracts/policy, route-to-context hash binding, bounded Scout/Worker/Verifier/Critic bundles, and parent-side rehydration requests.
- MARGOS Context Governor Phase 4 frozen counterfactual benchmark, false-omit/rehydration/calibration metrics, privacy review, live Jev research mode, and optional host-neutral root-compaction proposal contract.

### Changed
- Routing composition now uses high-mass task-ambiguity and verification-risk distributions together with the explicit escalation probability instead of leaving those two Jev signals telemetry-only.
- Context Jev questions now reference explicit `state.candidates[N]` paths; calibrated deployments can bind model, question set, threshold policy, projection version, and corpus hash.

- MARGOS now separates coordination shape, disposition, compute tier, and child role instead of conflating critic role with compute.
- Codex and Copilot adapters consume proposed abstract routes while still requiring host runtime evidence before claiming delegated execution.

### Security / boundaries
- Semantic capsules remain disabled by default and never mutate canonical evidence; private/full payload upload is still not a portable default.
- Calibration claims require an explicit pinned model plus a matching PASSED binding; aliases such as `jev-latest` are treated as stale for calibrated operation.
- Redacted trace inputs must declare `redacted=true` and pass committed secret-pattern checks.

- Reflex output cannot prove host capability or widen permissions.
- Remote Reflex projection omits host identity and literal model/provider constraint values.
- CI never requires a TypeSafe credential or live external model call.
- Context Reflex is explicit opt-in: API-key presence alone does not enable it, missing-key selection performs zero network requests, and raw context payloads are excluded from the remote projection.
- Phase 4 CI remains synthetic/offline, committed context fixtures are secret-scanned, and optional root compaction cannot run without explicit opt-in plus proven host capability.

### Planned
- Gather external installation and compatibility reports.
- Collect live, explicitly authorized Jev routing measurements before making any calibration or promotion claim.

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
