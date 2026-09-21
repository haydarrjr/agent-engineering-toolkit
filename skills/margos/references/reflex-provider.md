# Optional Reflex provider: TypeSafe Jev

MARGOS vNext is provider-neutral. TypeSafe AI's Jev is the first experimental external Reflex adapter because its public System One interface closely matches the architecture in issue #6: bounded state, typed Choice/Score/Noul judgments, probabilities, and deterministic code composition.

## Attribution and limits

AET is inspired by Jev's typed-decision shape. It does not implement TypeSafe's proprietary architecture or RLCD training and does not inherit TypeSafe calibration claims. The adapter remains `UNCALIBRATED` until a frozen AET routing suite is measured with the exact provider/model/question-set binding.

References:
- https://docs.typesafe.ai/introduction
- https://docs.typesafe.ai/primitives
- https://docs.typesafe.ai/confidence
- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/agent-skill

## Runtime contract

The optional adapter is `skills/margos/scripts/margos_reflex_jev.py`.

- Direct endpoint: `POST https://api.typesafe.ai/v1/systemone`.
- Default model alias: `jev-latest`.
- Credential: `TYPESAFE_API_KEY` read at runtime only.
- Optional overrides: `TYPESAFE_BASE_URL` and `TYPESAFE_DEFAULT_MODEL`.
- Provider selection is explicit; merely setting `TYPESAFE_API_KEY` does not enable a Reflex path.
- Provider selected but no key: return `NOT_CONFIGURED`, perform zero network requests, and let deterministic Policy/conservative composition fall back.
- Provider/transport/schema error: return a typed error state and let deterministic Policy fall back.
- No automatic retry loop is added in the experimental adapter.

## Data minimization

The adapter sends a bounded Reflex projection, not a transcript or repository dump. It excludes:
- host identity;
- the literal model/provider constraint value;
- credentials/environment variables;
- connector state;
- arbitrary raw logs.

It includes only the fields needed by the active decision family. Routing Reflex receives its existing bounded task/capability/evidence projection. Context Reflex receives bounded task fields plus candidate metadata (tool/locator, size, evidence flags, replayability, supersession, recency, and Policy-admissible actions). Context raw payloads, canonical item IDs, full transcripts, credentials, and unrelated source content are not sent.

Do not enable a remote Reflex provider for proprietary/private state unless the deployment policy explicitly permits that processing.


## Shared transport for Context Reflex

Issue #10 Phase 2 reuses the same `JevReflexProvider`, HTTPS endpoint, Bearer credential, timeout/error boundary, and runtime environment variables for Context Reflex. The adapter dispatches by the typed request schema; it does not create another TypeSafe client.

Context requests batch multiple independent Noul judgments against one minimized state. Batch size and projected-character budgets are deterministic local contracts. CI exercises fixture and injected-transport paths only; it never enables the live Jev provider.

## JEV v2 runtime and model lifecycle

The normal routing CLI can explicitly select the adapter with `--reflex-provider jev`; setting `TYPESAFE_API_KEY` alone still does nothing. Routing and Context Reflex questions point to explicit state paths so the provider evaluates the intended bounded fields rather than relying on alias prose.

`jev-latest` remains the research default. A calibrated run must explicitly select a pinned model and supply a `margos-jev-calibration/v2` binding that matches the provider, model, question-set hash, threshold-policy hash, projection version, frozen-corpus hash, and a recorded `PASSED` evaluation. Alias use, model drift, or contract drift yields `STALE`, not a calibration claim. The Issue #18 live benchmark resolves `/v1/models` at run time and prefers pinned `jev-1.13.0` when available.

Context Reflex may optionally receive a derived `semantic_capsule` only when the Context View explicitly enables remote semantic capsules. The capsule contains exact excerpts from the locally hash-verified payload, bounded to the deterministic policy budget, with extractor, payload, excerpt, and provenance hashes; secret-like material suppresses the whole capsule. Canonical item IDs and the full payload remain excluded from the remote projection.
