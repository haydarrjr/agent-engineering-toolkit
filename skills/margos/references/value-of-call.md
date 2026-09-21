# ValueOfCall and pre-retrieval contracts

Issue #21 separates semantic judgment from economic and authority decisions.
Hosts first compile an `ExecutionOpportunity` or metadata-only
`RetrievalCandidate` set. Deterministic code then checks whether a concrete
operation can be avoided, whether the host can exploit the result, whether the
latency/cost ceiling can pay for Jev, and whether calibration is current. Only
then may a provider receive the minimized state.

For context, `margos_retrieval.py` sends bounded metadata before any payload is
loaded. Mandatory/protected candidates remain in the Policy floor. A validated
plan selects optional IDs; `PayloadLoader` materializes only those IDs and
checks content hashes before producing payload artifacts. Provider failure,
stale calibration, privacy suppression, low confidence, or budget exhaustion
returns the safe Policy set.
