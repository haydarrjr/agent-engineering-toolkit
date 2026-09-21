# MARGOS JEV integration root cause

The earlier JEV result was not a valid test of JEV's value. The failure was in our integration and benchmark boundaries, not evidence that typed Reflex judgments are useless.

## What went wrong

1. The projected payload already had a top-level `state` object, but every question referenced paths such as `` `state.task...` `` and `` `state.candidates[0]` ``. TypeSafe structured paths are resolved inside the request state, so the correct paths are `` `task...` ``, `` `admissible...` ``, and `` `candidates[0]...` ``. The old adapter therefore asked a fast model to reason through invalid or indirect references.

2. Admission measured whether multiple theoretical choices existed, not whether the actual deterministic Policy route could be materially changed and executed by the host. Hard verification evidence already forced the expensive compute floor, yet JEV still received a remote call. A roughly sub-millisecond local decision consequently paid hundreds of milliseconds of network latency without reducing expensive execution.

3. The offline fixture provider read `case.fixture` and returned those values as if they were JEV answers. The metric then called exact route-label equality `verified_success`. That was target leakage and not downstream verification. The corrected forced benchmark uses an oracle-free uncertainty provider for fixture plumbing, reports route-contract matching separately, and verifies the executable route against deterministic host-obligation rules.

4. The promotion gate checked safety and non-inferiority but did not require end-to-end non-regression or a material compute/context benefit. A run could therefore be labelled promoted while adding JEV latency and leaving expensive compute unchanged.

## Corrected authority chain

`Policy → admission → one batched typed Reflex request when material → deterministic composition/veto → host-native execution → downstream verification`.

Hard verification evidence removes cheaper compute tiers from the admissible set and produces `SKIP_POLICY_SUFFICIENT` when only the Frontier floor remains. JEV can still help on genuinely ambiguous, executable route choices where the host can apply the result. Policy remains final.

## Evidence and status

The historical live run is retained as evidence of what the old protocol measured, not as a promotion claim. The corrected offline smoke run is oracle-free and currently reports no material JEV benefit. A fresh live run must use the environment-only `TYPESAFE_API_KEY`, resolve `jev-latest` at runtime, record the concrete response model (currently expected to be `jev-1.13.0`), and pass the corrected A/B/C/D gates before promotion can be reconsidered.

References: [TypeSafe primitives](https://docs.typesafe.ai/primitives), [TypeSafe models](https://docs.typesafe.ai/models), [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [Issue #18](https://github.com/haydarrjr/agent-engineering-toolkit/issues/18).
