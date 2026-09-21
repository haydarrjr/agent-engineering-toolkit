# MARGOS vNext evaluation

## Frozen suite

`tests/fixtures/margos/routing-cases-v1.json` covers:
- bounded read-only transfer;
- keyword/model-name noise invariance;
- ordinary local-write worker routing;
- failed-verification escalation and independent criticism;
- overlapping/shared-write serialization;
- missing-child direct fallback;
- unresolved external-effect halt.

Run the deterministic fixture benchmark:

```bash
python scripts/benchmark_margos_routing.py --mode fixture --strict
```

The CI gate requires zero hard Policy violations, zero equivalence-group invariance failures, and all frozen fixture cases matching their gold route.

## Modes

- `policy`: deterministic Policy with no Reflex provider.
- `fixture`: deterministic fixture Reflex for regression testing.
- `jev`: optional live TypeSafe Jev adapter. Requires `TYPESAFE_API_KEY` and is never used by default CI.

Example live research run:

```bash
TYPESAFE_API_KEY=... python scripts/benchmark_margos_routing.py --mode jev --output .aet/margos-jev-eval.json
```

Do not commit the key or raw private routing state.

## Calibration

The harness can calculate multiclass Brier score and a simple five-bin ECE for Choice judgments when Reflex probabilities are present. Fixture metrics prove the evaluator works; they are **not model calibration evidence**.

A live Jev run remains `UNCALIBRATED` until the exact model/version, question-set hash, threshold policy, routing-state schema, and frozen dataset are bound and evaluated. Changing any of those makes prior calibration stale.

## Promotion boundary

The optional Reflex path remains experimental until live evidence demonstrates either:
- lower cost/latency at comparable verified success; or
- higher verified success at comparable budget;

with zero deterministic authority-expansion violations.

Route receipts remain `PROPOSED`; host execution and task correctness require separate runtime/verification evidence.

## CI boundary

Repository CI validates the deterministic fixture suite only. It never consumes `TYPESAFE_API_KEY`, never makes a live Jev request, and therefore cannot be cited as live-provider calibration evidence.


## Context Reflex Phase 2

Context Reflex is evaluated separately from routing. Phase 2 CI covers:
- deterministic protected-item admission;
- fixture `keep_awareness` / `keep_full` / `replay_needed` composition;
- low-margin abstention to conservative retention;
- provider-error and missing-key fallback;
- explicit batching budgets;
- minimized Jev context projection with no raw payload;
- the invariant that an environment API key alone does not activate Context Reflex.

Live Context Reflex is research-only and explicit opt-in:

```bash
TYPESAFE_API_KEY=... python skills/margos/scripts/margos_context.py \
  --state state.json \
  --payloads payloads.json \
  --reflex-provider jev
```

Without `--reflex-provider jev`, no live provider is selected even when the environment contains a key. If Jev is selected without a key, the typed provider state is `NOT_CONFIGURED` and the adapter performs zero network requests.

Phase 2 fixture tests establish contract behavior, not live calibration. Full-vs-compacted counterfactual evaluation, false-omit metrics, and live calibration remain Phase 4 work.


## Phase 3 child-handoff gate

`tests/fixtures/margos/child-role-contract-v1.json` freezes role-specific inclusion/exclusion expectations for Scout, Worker, Verifier, and Independent Critic.

Phase 3 CI verifies:
- required evidence coverage remains 1.0;
- Policy-protected state is retained;
- Scout and Critic do not inherit broad implementation payloads;
- Worker receives owned-path context;
- Verifier receives exact implementation + verification evidence;
- child bundle serialized characters are lower than the full fixture payload characters;
- route/context/bundle hashes bind consistently;
- child rehydration requests can recover exposed content and cannot fetch unexposed context;
- replay requiring authority recheck remains pending until explicitly approved;
- a Context Reflex provider is invoked only once per handoff batch.

These deterministic fixture checks demonstrate bounded-context reduction without a fixture-level evidence-coverage regression. They are not a live verified-success or model-calibration claim. Full counterfactual success, false-omit, rehydration-cost, and live Jev measurements remain Phase 4.


## Phase 4 frozen context benchmark

The frozen corpus is `tests/fixtures/margos/context-benchmark-v1.json`. It contains synthetic cases for old binding constraints, owned-path work, failed-then-successful verification, contradictions, unresolved external effects, non-replayable evidence, critic handoff, serialized work, long trivial context, and short high-impact context.

Run the portable gates:

```bash
python scripts/benchmark_margos_context.py --mode policy --strict
python scripts/benchmark_margos_context.py --mode fixture --strict
```

Each case compares:
- Baseline A: all context retained verbatim;
- Baseline B: deterministic Context Policy;
- Candidate D: Policy + fixture Context Reflex;
- Baseline C host-native root compaction is reported as not observable in portable CI;
- Candidate E live Jev is available only through explicit research mode.

The deterministic downstream oracle names required awareness, required exact evidence, and forbidden inherited context. If exact evidence is only a reference/head, the benchmark performs the same parent-side hash-checked rehydration protocol used by Phase 3. A compacted case is successful only when the required evidence remains available after any permitted rehydration.

Strict frozen gates require:
- 100% candidate verified-success on the corpus;
- zero harmful omission;
- zero protected/non-replayable/external-effect/contradiction loss;
- zero forbidden-context violation;
- at least 40% aggregate serialized-context reduction;
- committed fixture secret scan PASS.

Reported metrics include estimated before/after tokens, serialized reduction, provider request/network/token counts, compaction latency, rehydration count/characters/latency, harmful/costly omission, false-full retention, Brier score, and five-bin ECE when probabilities are available.

The fallback token estimator is explicitly marked estimated and uses `ceil(characters/4)`; host/tokenizer measurements should replace it when a host exposes trustworthy token counts.

### Live Jev research mode

```bash
TYPESAFE_API_KEY=... \
python scripts/benchmark_margos_context.py \
  --mode jev \
  --output .aet/margos-context-jev-eval.json
```

Live mode reuses the existing optional TypeSafe/Jev adapter and credential path. The key is never committed. A missing key yields `NOT_CONFIGURED` and zero network calls.

A live run may report Brier/ECE and false-omit/false-keep observations against this corpus, but no `CALIBRATED` claim is made automatically. Fixture probabilities remain evaluator self-tests, not provider calibration.

## Privacy and optional host compaction

The Phase 4 privacy review is `docs/MARGOS_PRIVACY_REVIEW.md`. It confirms the portable default remains metadata/bounded-context only and CI is synthetic/offline.

`margos_host_compaction.py` defines only a host-neutral proposal contract. Root transcript interception requires explicit experimental opt-in, a proven host hook, a `DERIVED_VIEW`, unchanged canonical source, and sufficient reduction. Codex/Copilot continue using the Phase 3 child-bundle baseline unless a future stable host contract is observed.

## JEV v2 redacted trace evaluation

`scripts/benchmark_margos_trace.py` accepts the public `margos-trace-benchmark/v1` format. The committed fixture is synthetic; maintainers may point `--input` at a local redacted Codex/MARGOS export. Inputs must declare `redacted=true` and pass secret-pattern screening.

The trace harness evaluates both routing and context cases and reports route/context success, abstention, hard Policy-boundary violations, harmful omission, rehydration count, context reduction, Brier score, and five-bin ECE where probability labels exist. It uses recorded fixture probabilities, not a live provider, in CI.

A live provider remains a separate explicitly authorized research step. Calibration can only be promoted with a pinned model and a matching `margos-jev-calibration/v2` binding. `jev-latest` is intentionally unsuitable for a persistent calibrated claim because the alias can move. Issue #18 additionally requires disjoint calibration/holdout partitions, downstream-verification gold labels, and a runtime fingerprint bound to the exact policy, questions, thresholds, projection, extractor, model, protocol, and corpus.

## Issue #18 forced-arm benchmark

The four arms are assigned by `scripts/benchmark_margos_jev_v3.py`, not by the system under test: A is Policy-only; B adds JEV routing; C adds metadata-only Context Reflex; D adds staged evidence Context Reflex. The driver keeps case state, contracts, provenance, gold labels, and calibration/holdout partitions identical across arms. It reports raw verified success, false escalation/de-escalation, expensive-compute use, latency, JEV overhead, context reduction, rehydration, calibration metrics, safety counts, and the runtime fingerprint.

The live command requires at least 300 routing and 300 context cases, resolves `/v1/models`, requests `jev-latest` by default, records the concrete response model, and returns exactly one promotion status. Without `TYPESAFE_API_KEY`, it returns `live_status=NOT_RUN` and `JEV_NOT_PROMOTED` and must not be merged. Smaller fixture invocations are local smoke tests only. `JEV_PROMOTED_FOR_FROZEN_SUITE` additionally requires end-to-end latency non-regression and a material compute or context benefit; safety/non-inferiority alone is insufficient. A model, question, threshold, projection, extractor, corpus, or benchmark-protocol change requires a new calibration/promotion run.

The historical Issue #18 run on source `b78c26a` requested `jev-latest` and observed response model `jev-1.13.0`, but its promotion result is superseded by the root-cause audit in `docs/MARGOS_JEV_INTEGRATION_POSTMORTEM.md`. The old fixture provider copied fixture answers into JEV responses, the old metric equated route-label equality with verified success, and admission still called JEV for Policy-forced Frontier cases. The corrected benchmark forbids those shortcuts, requires end-to-end efficiency evidence, and keeps JEV research-only until a fresh authorized live run passes those gates. Policy-only remains the safe default whenever admission skips, the host cannot exploit the result, the provider is disabled/unavailable, a budget applies, or final Policy veto rejects the proposal.

## Issue #21 executable benchmark v4

`scripts/benchmark_margos_jev_v4.py` compares forced arms over identical case
state and contracts. The system under test never selects the arm.

| Arm | Execution path | JEV mode | Replay |
|---|---|---|---|
| A | Policy-only executable fallback | none | cold |
| B | Policy + ValueOfCall + routing | one batched routing request when admitted | cold |
| C | B + metadata-first retrieval planning | one metadata request when admitted | cold |
| D | C with session memoization/singleflight | same contracts | warm replay |

Calibration and holdout cases are unique by canonical state hash and disjoint;
thresholds are frozen before the holdout is evaluated once. Provenance remains
separate for `SYNTHETIC`, `REDACTED_REAL_CODEX`, and
`DERIVED_COUNTERFACTUAL`. Gold labels come from downstream host/loader
verification receipts, never from Jev output or the selected route label.

The v4 report includes p50/p95 end-to-end latency, Jev requests and retries,
cache/coalescing telemetry, actual expensive operations, selected/fetched
items and bytes, stage counts, raw-payload projection counts, Policy violations,
and a runtime fingerprint containing contract hashes and model identity. The
offline fixture gate is:

```text
python scripts/benchmark_margos_jev_v4.py --mode fixture --strict
```

Live mode must resolve the available model list, use only the environment
`TYPESAFE_API_KEY`, bind thresholds to the concrete response model, and produce
one frozen holdout report. Until that report is safe and net-positive after
Jev overhead, `JEV_NOT_PROMOTED` and Policy-only remain the default.

The TypeSafe design-time checklist and current docs/skill provenance are
maintained in `docs/MARGOS_TYPESAFE_CONFORMANCE.md`.
