# Issue #24 Verification Governor — live A/B/C/D report

Run date: 2026-09-21  
Run mode: authorized live TypeSafe request, one synthetic holdout case  
Promotion status: **`JEV_RESEARCH_ONLY`**

This report is evidence for the Verification Governor boundary, not a claim
that JEV output is ground truth. The fixture's downstream verifier outcomes are
the gold labels. The system under test did not select the arm.

## Runtime binding

| Field | Value |
| --- | --- |
| Implementation source SHA used for run | `1f3343314c7598934d0bcd6537ccc9dfeed86efb` |
| Requested model | `jev-latest` |
| Concrete response model | `jev-1.13.0` |
| Models resolved at run time | `jev-latest`, `jev-preview` |
| Protocol | `margos-jev-verification/v1` |
| Corpus hash | `f73e89695673aef80d003b5b46f91f1107c13a16e5f78649a2be582d708a7a36` |
| Verification question hash | `52269af6368427db8570fe5ff8130fad06eabc21b48c16f838b6e72a329be6f9` |
| Verification threshold hash | `54c3d9dee2262d20402ebc0e6535f388689ecf6ea27f2423e4e2d6d25d3261f3` |
| Calibration binding hash | `90efaec7a33df777a89955638f770cc157e1b6cf83751c85c0e9cc2ac9357278` |

The provider request used a bounded metadata projection with one comparable
Noul per optional candidate. No API key or raw private payload is present in
the repository or this report.

## Forced-arm results

| Arm | Provider requests | Verified finding recall@3 | Optional verified recall | False de-escalation | JEV overhead | Gross verifier work saved | Net wall saved | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A Policy-only baseline | 0 | 1.00 | 1.00 | 0 | 0 ms | 0 ms | 0 ms | all 3 optional dispatched |
| B JEV shadow | 1 | 1.00 | 1.00 | 0 | 948.546 ms | 0 ms | 0 ms | execution unchanged |
| C JEV active cold | 1 | 0.50 | 0.00 | 1 | 924.649 ms | 300 ms | **-624.649 ms** | mandatory only; all optional skipped |
| D JEV active warm | 0 network / cached | 0.50 | 0.00 | 1 | 0 ms | 300 ms | 300 ms | mandatory only; warm replay |

The live C response probabilities were below the active threshold for all three
optional candidates (`upstream-contract=0.43`, `deployment-drift=0.52`,
`adapter-capability=0.26`). The gold upstream contract finding was therefore
missed. This is a real quality failure, not an artifact of route-label scoring.
The observed cold TypeSafe request took 924.649 ms; this is a variable remote
measurement, while the source SHA above identifies the unchanged implementation
under test (the later commit only refreshed this report).

Protected finding retention, mandatory retention, exact plan/dispatch equality,
one-request enforcement, and report protection all passed. Active cold quality
was not non-inferior to the Policy baseline, and active cold end-to-end latency
regressed after JEV overhead. Therefore the result cannot promote JEV or make
it the default. Policy-only remains the default until a larger cold disjoint
holdout demonstrates both quality non-inferiority and material positive net
value.

The provider request hash was recorded in the machine-readable receipt under
`.aet/issue-24-live-verification-final.json`; that file is local evidence and
is intentionally not packaged as portable plugin content.
