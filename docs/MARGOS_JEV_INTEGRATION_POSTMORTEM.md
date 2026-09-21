# MARGOS JEV integration root cause

The earlier JEV result was not a valid test of JEV's value. The failure was in our integration and benchmark boundaries, not evidence that typed Reflex judgments are useless.

## What went wrong

1. The projected payload already had a top-level `state` object, but every question referenced paths such as `` `state.task...` `` and `` `state.candidates[0]` ``. TypeSafe structured paths are resolved inside the request state, so the correct paths are `` `task...` ``, `` `admissible...` ``, and `` `candidates[0]...` ``. The old adapter therefore asked a fast model to reason through invalid or indirect references.

2. Admission measured whether multiple theoretical choices existed, not whether the actual deterministic Policy route could be materially changed and executed by the host. Hard verification evidence already forced the expensive compute floor, yet JEV still received a remote call. A roughly sub-millisecond local decision consequently paid hundreds of milliseconds of network latency without reducing expensive execution.

3. The offline fixture provider read `case.fixture` and returned those values as if they were JEV answers. The metric then called exact route-label equality `verified_success`. That was target leakage and not downstream verification. The corrected forced benchmark uses an oracle-free uncertainty provider for fixture plumbing, reports route-contract matching separately, and verifies the executable route against deterministic host-obligation rules.

4. The promotion gate checked safety and non-inferiority but did not require end-to-end non-regression or a material compute/context benefit. A run could therefore be labelled promoted while adding JEV latency and leaving expensive compute unchanged.

## Why the corrected integration was still slower

The corrected contract removed the unsafe calls, but the first corrected live run exposed a second, performance-specific integration failure:

5. The benchmark compared a sub-millisecond local Policy decision with a synchronous remote Reflex request. JEV is a typed judgment service; its useful comparison is against the expensive model or host operation that the judgment prevents, not against local deterministic Python. In the corpus, every arm still executed the same 43 Frontier cases, so the remote judgment had no expensive downstream work to eliminate.

6. The default HTTP adapter created a fresh HTTPS connection for each request. A direct probe of the same routing payload measured 776--1080 ms with the current transport, versus 282--408 ms after reusing one HTTPS connection. The missing keep-alive/pooling was integration overhead, not JEV reasoning time.

7. Staged Context Reflex serialized a metadata request and an evidence request. In the live run, 264/300 D-arm cases crossed the unresolved band and paid for the second remote request; the resulting context latency was 1,654.203 ms while the Policy baseline was 1.133 ms. A ten-case live probe found 19/25 eligible items conservatively abstaining, so the current `abstain_band` and unbound live calibration produce more second-stage work without changing the final `KEEP_REF` outcome in most cases.

8. The context benchmark materializes all payloads before Reflex runs. JEV therefore selects retention after retrieval; it is not being used to avoid the retrieval/search operation whose speedup the public JEV examples describe. The benchmark also expands the small frozen corpus into derived duplicates: 300 routing rows contained only four unique admitted request shapes, but the driver constructed a new provider and paid the network call for each row.

These measurements explain the reversal: the integration paid remote latency, connection setup, serial staging, and repeated requests while preserving the same local route/context result. They do not show that JEV is intrinsically ineffective. They show that this MARGOS insertion point did not give JEV a costly operation to replace.

## Corrected authority chain

`Policy → admission → one batched typed Reflex request when material → deterministic composition/veto → host-native execution → downstream verification`.

Hard verification evidence removes cheaper compute tiers from the admissible set and produces `SKIP_POLICY_SUFFICIENT` when only the Frontier floor remains. JEV can still help on genuinely ambiguous, executable route choices where the host can apply the result. Policy remains final.

## Evidence and status

The historical live run is retained as evidence of what the old protocol measured, not as a promotion claim. The corrected live run used the environment-only `TYPESAFE_API_KEY`, requested `jev-latest`, and recorded `jev-1.13.0`; it remains `JEV_NOT_PROMOTED` because no material downstream benefit was observed. The next implementation must make the comparison valid: reuse connections, avoid duplicate requests, admit JEV only when it can replace an expensive executable operation, and benchmark pre-retrieval selection against the actual expensive alternative.

References: [TypeSafe primitives](https://docs.typesafe.ai/primitives), [TypeSafe models](https://docs.typesafe.ai/models), [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13), [Issue #18](https://github.com/haydarrjr/agent-engineering-toolkit/issues/18).

## Issue #21 implementation boundary

The corrective implementation is intentionally an execution-graph change, not
only a faster adapter:

- `margos_value.py` admits Jev only when a concrete avoidable operation and
  material cost-vector delta are present.
- `margos_reflex_jev.py` uses a session-scoped pooled HTTPS runtime, bounded
  deadlines, validated cache entries, singleflight, concrete model telemetry,
  and retrieval metadata projection.
- `margos_retrieval.py` plans before payload loading and verifies hashes at the
  lazy materialization boundary.
- `margos_handoff.py` can build a child handoff from a retrieval plan without
  forcing full payload materialization.
- `benchmark_margos_jev_v4.py` executes the selected operation and records
  realized host/loader outcomes; it does not infer savings from route labels.

The official TypeSafe skill alignment is a separate design-time plane. The
checked-in conformance checklist, freshness binding, and shadow-first rollout
are documented in `docs/MARGOS_TYPESAFE_CONFORMANCE.md` and
`provenance/typesafe-jev-design.json`. The skill cannot grant Policy or
execution authority, and an unavailable skill/provider always falls back to
Policy-only behavior.
