# Issue #18 ReThinking and Agent Plugins audit

Audit date: 2026-09-21
Scope: Issue #18, MARGOS JEV v3 hardening, and the portable/Codex/Copilot plugin surfaces.

Authoritative guidance read for this audit:

- [OpenAI ReThinking guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
- [Agent Plugins portable contract](../skills/agent-plugins-author/references/portable-contract.md)
- [Agent Plugins Codex adapter contract](../skills/agent-plugins-author/references/codex-adapter-contract.md)
- [Agent Plugins Copilot contract](../skills/agent-plugins-author/references/copilot-agent-plugins.md)
- [Agent Plugins quality gates](../skills/agent-plugins-author/references/quality-gates.md)

## Classification

| Surface | Classification | Decision and evidence |
| --- | --- | --- |
| `AGENTS.md` | KEEP | Retains repository-specific authority, privacy, destructive-action, host-readback, and required-gate boundaries. Generic competence guidance is not duplicated there. |
| `skills/margos/SKILL.md` | KEEP | Remains a short router for Policy, Reflex, Execution, Context, and the progressively disclosed references. It does not carry provider-specific instructions. |
| `skills/margos/references/*` | KEEP | Specialized routing, host, context, evidence, and external-effect contracts remain behind the MARGOS skill boundary. |
| `skills/margos/contracts/*` | KEEP | Versioned question and threshold contracts are executable authority for the deterministic kernels. |
| `skills/margos/schemas/*` | KEEP | Versioned receipts, requests, results, calibration, context, and benchmark schemas are package contracts. Historical v1 schemas remain for compatibility evidence. |
| `skills/rethinking/*` | KEEP | The audit workflow is explicit-only and points to current OpenAI guidance rather than copying generic advice into every task. |
| `skills/agent-plugins-author/*` | KEEP | Portable-first authoring and client-specific reconciliation remain explicit-only and progressively disclosed. |
| `plugin.json` | KEEP | Portable manifest is authoritative for identity, version, skills, and keywords. |
| `.codex-plugin/plugin.json` | KEEP | Client adapter mirrors identity/version without becoming portable authority or owning keywords. |
| `.agents/plugins/marketplace.json` | KEEP | Codex marketplace remains client-specific and references the repository source/ref. |
| `.github/plugin/marketplace.json` | KEEP | Copilot marketplace remains client-specific, strict, and version-aligned with `plugin.json`. |
| `com.github.copilot/agents/*` | KEEP | Hidden `model: auto` leaf agents preserve host-owned execution and do not recursively invoke agents. |
| `scripts/validate_*.py` | KEEP | Validators encode repository, host adapter, Context, handoff, evaluation/privacy, and reproducible-release boundaries; they do not claim installation or live behavior. |
| `scripts/benchmark_*.py` | NARROW | Offline fixture benchmarks remain CI gates. Live JEV is isolated to the explicit Issue #18 driver and reports `NOT_RUN` without a key. |
| `scripts/benchmark_margos_jev_v3.py` | KEEP | Owns forced A/B/C/D arm selection, provenance, partition isolation, raw outcome metrics, runtime fingerprinting, and promotion status. |
| `tests/*` and `tests/fixtures/*` | KEEP | Regression fixtures are synthetic/redacted and are not treated as live-model ground truth. |
| release/provenance/privacy docs | KEEP | Required repository-specific release, lineage, privacy, and evidence boundaries cannot be inferred safely and remain explicit. |
| untracked `.aet/*` baseline | RELOCATE | Local baseline evidence is retained outside the package and excluded from commits; it is not portable plugin content. |
| duplicated legacy v1 contracts/schemas | NARROW | Kept as compatibility/history surfaces; new runtime authority is v2 and validators bind v2. |
| live provider output, credentials, host installation/readback | UNVERIFIED | No `TYPESAFE_API_KEY`, external host execution, marketplace installation, or live promotion evidence is available in this environment. |

## Counts and gates

The repository heuristic audit completed with `PASS` and no findings. Manual classification above covers the requested instruction, MARGOS, manifest, adapter, validator, benchmark, test, provenance, and release surfaces. The portable plugin contract remains authoritative; Codex and Copilot catalogs are reconciled adapters.

Local gates completed before implementation included the repository/host/context/handoff/evaluation validators, 84 repository tests, frozen routing/context/trace benchmarks, Agent Plugin and skill validators, both marketplace render checks, surface reconciliation, and reproducible packaging. The Issue #18 forced-arm fixture driver is also deterministic and emits a runtime fingerprint; its live mode is a hard pre-merge gate and currently reports `NOT_RUN` because the environment has no `TYPESAFE_API_KEY`.

## ReThinking outcome

The repair keeps project-specific authority and safety guidance, narrows generic or provider-specific routing at the portable root, and relocates evidence selection, calibration, model lifecycle, and benchmark detail to versioned contracts or specialized references. The implementation follows the current guidance’s preference for short routers, progressive disclosure, self-contained questions, and explicit completion criteria.
