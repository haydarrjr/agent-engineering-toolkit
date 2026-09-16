# Architecture

## Authority

The root `plugin.json` and `skills/` tree are the portable source of truth. Distribution surfaces translate that authority for hosts; they do not own behavior.

## Skill ownership

- Software Craft: cross-language engineering owner.
- Python Engineering Harness: Python-specific owner; narrower than Software Craft.
- MARGOS: explicit coordination and effect-boundary advisor.
- ReThinking: explicit repository instruction audit/repair workflow.
- Agent Plugins Author: explicit plugin authoring/portability workflow.

Only one engineering skill should normally own an implementation task. Explicit skills may advise a distinct requested concern but should not silently become background ceremony.

## Failure model

Source-local validators fail closed on malformed manifests, missing skill metadata, activation-policy drift, proprietary markers, unsafe repository artifacts, or version mismatch. They do not claim external installation or runtime success.

## Dependencies

Core validation uses the Python standard library. The toolkit should not need network access merely to validate its own source tree. Tasks that claim conformance to current external guidance must fetch and cite the current source at execution time.
