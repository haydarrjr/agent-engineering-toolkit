# MARGOS Execution layer

Execution consumes a finalized abstract route after Policy has revalidated it.

It maps:
- coordination shape;
- disposition;
- compute tier;
- role;
- explicit user model/provider constraint;

to the host-native mechanisms the current client actually exposes.

Execution cannot infer a child/model switch from configuration text. If a requested abstract capability cannot be proven at runtime, use the Policy-defined fallback and report the limitation. Root approval policy, sandbox, credentials, connectors, and mutation authority remain unchanged.

Phase 2 does not change Codex or Copilot runtime behavior; host-specific mapping remains in the existing host references and leaf agents. Phase 3 will connect this typed route contract to those surfaces.
