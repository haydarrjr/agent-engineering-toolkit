# MARGOS Reflex confidence and calibration

Keep these concepts separate:
- provider probability;
- provider confidence metadata;
- local calibration status;
- local threshold policy;
- observed routing accuracy;
- downstream verification outcome.

A numeric provider confidence never becomes an AET permission, execution fact, or correctness claim.

Calibration states are `UNKNOWN`, `UNCALIBRATED`, `CALIBRATED_FOR_FROZEN_SUITE`, and `STALE`. A future provider may be called calibrated only after measurement on a frozen AET routing suite bound to provider/model/version, question-set hash, routing-state schema, threshold policy, and dataset hash.

Current thresholds are versioned separately from the question set. Low winner margin triggers abstention; high escalation/critic probability may change compute/role only inside the deterministic Policy envelope.

## Probability-first composition

Routing consumes the full Choice/Score distributions, not only their winning labels. MARGOS derives high-mass ambiguity and verification-risk probabilities and composes them with `needs_escalation` under deterministic thresholds. Jev still does not choose permissions or execution authority.

Calibration is artifact-bound. A pinned model may report `CALIBRATED_FOR_FROZEN_SUITE` only when the supplied binding matches model, question-set hash, threshold-policy hash, projection version, and corpus hash with a recorded passing evaluation. Any drift is `STALE`; absence of a binding remains `UNCALIBRATED`.
