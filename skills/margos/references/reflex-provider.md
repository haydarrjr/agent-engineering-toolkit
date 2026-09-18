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

The optional adapter is `scripts/margos_reflex_jev.py`.

- Direct endpoint: `POST https://api.typesafe.ai/v1/systemone`.
- Default model alias: `jev-latest`.
- Credential: `TYPESAFE_API_KEY` read at runtime only.
- Optional overrides: `TYPESAFE_BASE_URL` and `TYPESAFE_DEFAULT_MODEL`.
- No key: return a typed unavailable state and let deterministic Policy fall back.
- Provider/transport/schema error: return a typed error state and let deterministic Policy fall back.
- No automatic retry loop is added in the experimental adapter.

## Data minimization

The adapter sends a bounded Reflex projection, not a transcript or repository dump. It excludes:
- host identity;
- the literal model/provider constraint value;
- credentials/environment variables;
- connector state;
- arbitrary raw logs.

It includes only the task digest fields, boolean capability/authority facts, work-shape/evidence flags, budget class, and Policy-admissible choices needed for routing.

Do not enable a remote Reflex provider for proprietary/private state unless the deployment policy explicitly permits that processing.
