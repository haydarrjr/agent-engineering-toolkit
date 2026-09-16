---
name: python-engineering-harness
description: "Use when Python repository code, tests, packaging, or Python-specific architecture is material to the requested engineering work."
---

# Python Engineering Harness

Own Python repository work with project-native tools and evidence. Choose the smallest workflow that fits the request; the references below are routing hints, not a mandatory sequence.

## Choose context when needed

- Use [tooling](references/tooling.md) when the environment, formatter, linter, or test command is not obvious.
- Use [debugging](references/debugging.md) for a reproducible failure or wrong result.
- Use [architecture](references/architecture.md) for ownership, public API, or module-boundary decisions.
- Use [testing](references/testing.md) for regression design or test strategy.
- Use [review](references/review.md) for an existing change.
- Use [quality gates](references/quality-gates.md) only when verification depth is unclear.

Optional indexing or localization helpers are diagnostics. Use them for a named uncertainty, not as mandatory ceremony. Do not install dependencies merely to activate this skill.

## Ownership and completion

Preserve supported Python versions, dependency policy, public contracts, and local conventions. Safe local tests and fixes may continue without a confirmation pause. Production, destructive, credentialed, irreversible, or external actions remain separately authorized.

Finish with the requested Python behavior, relevant evidence, and unresolved risks. A failed affected check means the work is not complete.
