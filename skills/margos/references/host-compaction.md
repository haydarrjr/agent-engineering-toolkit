# MARGOS optional host compaction

Phase 4 defines a host-neutral proposal contract for optional root-context compaction. It does not make any host hook part of the portable MARGOS runtime.

## Hard boundary

`margos_host_compaction.py` may propose one of:
- `NO_AET_INTERCEPTION`: leave the root context alone;
- `DEFER_HOST_NATIVE`: use the host's own proven compaction path if the host chooses;
- `OFFER_DERIVED_VIEW`: an explicitly enabled, proven host adapter may receive the already-built `DERIVED_VIEW`.

The result remains `PROPOSED`. It is never evidence that the host actually compacted anything.

`OFFER_DERIVED_VIEW` requires all of:
- explicit experimental adapter opt-in;
- a proven root-compaction hook/capability for the current host;
- `DERIVED_VIEW` authority;
- `canonical_source_mutated = false`;
- reduction above the versioned minimum threshold.

Otherwise AET does not intercept root context.

## Host strategy

### Codex

Do not invent a root transcript hook. Continue to use Phase 3 bounded child bundles unless Codex later exposes a stable, observable compaction contract.

### GitHub Copilot / VS Code

Do not assume control over the internal context window. Continue to pass bounded MARGOS child bundles to the shipped leaf agents.

### Claude Code or another hook-capable host

A separate optional adapter may map a proven host compaction lifecycle hook to `OFFER_DERIVED_VIEW`. That adapter is outside the portable core and must fall back to host-native compaction or no AET interception on provider/error/insufficient-reduction conditions. No Claude package, hook implementation, or configuration is required by AET.

Canonical AET evidence is never deleted by this proposal contract.
