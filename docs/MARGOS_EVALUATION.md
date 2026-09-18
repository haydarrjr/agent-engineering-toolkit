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
