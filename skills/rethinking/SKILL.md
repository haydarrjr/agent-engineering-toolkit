---
name: rethinking
description: "Use only when the user explicitly requests an OpenAI ReThinking/GPT-6 Astra audit or repair of repository instructions, skills, prompts, or agent configuration."
---

# ReThinking

This is an explicit audit-and-repair workflow for instruction surfaces. It does not replace the engineering skill that owns the requested product change.

## Start with the current source

Read the current official OpenAI guidance before claiming conformance:
<https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra>

Use the fetched source, not a search snippet or memory. If the source cannot be read, report `UNVERIFIED` and do not claim current conformance.

## Audit the repository

Discover tracked files instead of assuming a fixed layout. Inspect `AGENTS.md`, `SKILL.md`, linked references, `agents/openai.yaml`, plugin manifests, routing/contribution/distribution docs, validators, and tests that enforce instruction behavior. Classify material guidance as `KEEP`, `NARROW`, `RELOCATE`, `REMOVE`, or `UNVERIFIED`.

Ask whether each instruction needs to be present for every task in its scope. Preserve project-specific architecture, unusual commands, security, secrets, destructive/production boundaries, and facts the model cannot reliably infer. Narrow generic competence advice, blanket reading lists, duplicated rules, legacy compensations, and unnecessary approval pauses. Move specialized detail behind the skill or reference that needs it.

## Repair and report

Update the smallest coherent source set and its tests/provenance. Keep safe local work autonomous. Do not publish, install, merge, or perform an external/destructive mutation without separate authority.

The read-only discovery helper may be used:

```bash
python skills/rethinking/scripts/audit_repository.py --root <repository>
```

Read [the audit checklist](references/audit-checklist.md) when a detailed classification record is useful.
