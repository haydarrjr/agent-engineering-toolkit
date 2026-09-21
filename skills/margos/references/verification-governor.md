# Verification Governor

Use this contract when a task has several independent audit findings and each
finding has a bounded, potentially expensive verifier. This is not the route
selection contract: `ExecutionOpportunity` still owns interchangeable
coordination/compute routes.

The portable graph is:

```text
cheap discovery -> FindingLedger -> Policy/evidence floor
  -> VerificationOpportunity (unresolved candidates only)
  -> VerificationValueOfCall
  -> one batched same-state Noul request, if admitted
  -> deterministic VerificationPlan
  -> host dispatch + verifier readback
  -> deterministic final report
```

Each optional candidate carries a bounded remote-safe claim summary, claim and
source hashes, evidence kind/state, Policy priority, host capability proof,
parallel group, and cost vector. `VERIFIED` candidates are rejected from this
contract. Mandatory candidate IDs are selected before Reflex and always survive.

The dedicated Noul proposition is: should this unresolved candidate consume one
slot in the next bounded verification batch because verifying it now is likely
to produce new evidence that materially changes the actionable result rather
than being safely deferrable? Its probability is not truth, severity,
confidence, or final finding rank. Questions use exact backticked paths such as
`candidates[0]`; all candidates share one state and one batch.

The code owns Policy bands, thresholds, capacity, critical-path arithmetic,
fallback, dispatch, readback validation, and final report order. A stale
calibration binding, provider error, missing evidence, unavailable selective
dispatch proof, empty budget, or invalid result returns a deterministic
Policy-priority plan. Production planning permits at most one provider request.

The schemas and question/threshold contracts are in `skills/margos/schemas/`
and `skills/margos/contracts/`. The provider-free regression gate is:

```bash
python scripts/validate_margos_verification.py
python scripts/benchmark_margos_jev_verification.py --mode fixture --strict
```
