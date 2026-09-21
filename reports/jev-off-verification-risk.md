# MARGOS JEV OFF — corrected verification-risk baseline

This is the A / Policy-only arm from the same corrected frozen protocol and corpus used by the JEV ON report. The arm is forced by the benchmark driver; MARGOS cannot choose the comparison arm.

## Run identity

- Toolkit: `1.3.0`
- Protocol: `margos-jev-v3-benchmark/v1`
- Corpus SHA-256: `37d4a5ea91234ca52fb1093e90922c8adbe1b3aa04eb708df172fac2aa8c16e7`
- Partitions: calibration 180 / holdout 120, disjoint
- Requested/response model calls: none
- JEV requests: 0

## Performance

| Measure | JEV OFF / A |
|---|---:|
| Route verified success | 300/300 (100%) |
| Context verified success | 300/300 (100%) |
| Mean route latency | 0.327 ms |
| Mean context latency | 1.133 ms |
| JEV requests | 0 |
| Expensive compute selections | 43 |
| False escalation / de-escalation | 0 / 0 |
| Harmful omission | 0 |
| Safety violations | 0 |

## Interpretation

Policy-only closes the deterministic obligations with no provider overhead. Hard verification evidence is handled deterministically as `TRANSFER + FRONTIER_REASONING + INDEPENDENT_CRITIC`, while unresolved external effects halt. This is the control baseline against which a future JEV path must demonstrate a real downstream or end-to-end benefit.
