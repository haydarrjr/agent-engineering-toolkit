# MARGOS JEV ON — corrected verification-risk benchmark

This report is the corrected live A/B/C/D run after the JEV integration audit. It is not a promotion claim; the result is `JEV_NOT_PROMOTED`.

## Run identity

- Source: corrected `codex/jev-root-cause-fix` working tree
- Toolkit: `1.3.0`
- Requested model: `jev-latest`
- Observed response model: `jev-1.13.0`
- Protocol: `margos-jev-v3-benchmark/v1`
- Corpus SHA-256: `37d4a5ea91234ca52fb1093e90922c8adbe1b3aa04eb708df172fac2aa8c16e7`
- Runtime fingerprint: `e726a98f26be70bf50101db9b17a8f71aa2360d0dfcd1c4d609836424d123596`
- Partitions: calibration 180 / holdout 120, disjoint
- Provider errors: 1 attempted request error; skipped Policy calls are not counted as errors
- Promotion: **JEV_NOT_PROMOTED**

## Performance

| Arm | Route verified | Context verified | Route latency | Context latency | Route JEV requests | Context requests | Expensive compute | Harmful omission |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A JEV OFF / Policy-only | 300/300 | 300/300 | 0.327 ms | 1.133 ms | 0 | 0 | 43 | 0 |
| B JEV ON / routing | 300/300 | 300/300 | 492.628 ms | 1.377 ms | 179 | 0 | 43 | 0 |
| C JEV ON / metadata Context | 300/300 | 300/300 | 504.531 ms | 845.239 ms | 182 | 300 | 43 | 0 |
| D JEV ON / staged evidence | 300/300 | 300/300 | 497.418 ms | 1,654.203 ms | 180 | 564 | 43 | 0 |

False escalation and false de-escalation were both zero. All safety violation counters were zero. Context reduction and rehydration were identical to the Policy baseline, so JEV produced no material context benefit. B/C/D added latency and did not reduce expensive compute.

## Interpretation

The corrected integration works safely and confirms that `jev-latest` returned `jev-1.13.0`. It does not justify default activation: end-to-end efficiency failed, material benefit was false, and one attempted provider request failed after bounded retries. Policy-only remains the default; JEV remains an optional research Reflex for targeted cases until a benchmark with measurable downstream benefit passes.
