import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

import margos_verification as verification


def candidate(candidate_id="c1", rank=0, group="g1", p95=100, *, state="UNVERIFIED", remote=True):
    return {
        "schema_version": verification.CANDIDATE_VERSION,
        "candidate_id": candidate_id,
        "claim_fingerprint": (candidate_id.encode().hex() + "0" * 64)[:64],
        "claim_summary": f"Synthetic bounded claim {candidate_id}",
        "evidence_state": state,
        "evidence_kind": "HYPOTHESIS",
        "policy_priority_rank": rank,
        "mandatory_by_policy": False,
        "remote_semantic_allowed": remote,
        "verifier": {
            "operation_id": f"op-{candidate_id}",
            "kind": "fixture-verifier",
            "host_capability_proof": "host-selective-v1",
            "parallel_group": group,
            "cost": {"latency_ms_p50": p95 / 2, "latency_ms_p95": p95, "verification_cost_units": 1},
        },
        "discovery_provenance": {
            "provenance_kind": "SYNTHETIC",
            "source_sha256": "a" * 64,
            "extractor_version": "test/v1",
        },
    }


def opportunity(**overrides):
    raw = {
        "schema_version": verification.OPPORTUNITY_VERSION,
        "opportunity_id": "opp-1",
        "task_objective": "close unresolved audit claims",
        "budget": {"max_optional_candidates": 1, "max_verification_cost_units": 5, "max_wall_clock_ms": 500},
        "mandatory_candidate_ids": ["mandatory-policy"],
        "optional_candidates": [candidate("c1", 0, "g1", 100), candidate("c2", 1, "g2", 200)],
        "host_selective_dispatch_proof": "host-selective-v1",
        "critical_path_model_version": "critical-path/v1",
        "jev_latency_budget_ms": 20,
        "cost_model_version": "cost/v1",
        "cache_lookup_status": "MISS",
        "calibration_binding_hash": "b" * 64,
    }
    raw.update(overrides)
    return raw


class VerificationGovernorTests(unittest.TestCase):
    def test_verified_findings_cannot_enter_optional_jev_projection(self):
        with self.assertRaises(verification.VerificationContractError):
            verification.normalize_verification_candidate(candidate(state="VERIFIED"))

    def test_remote_suppressed_candidate_is_not_projected(self):
        with self.assertRaises(verification.VerificationContractError):
            verification.normalize_verification_opportunity(opportunity(optional_candidates=[candidate(remote=False)]))

    def test_admission_boundaries_and_dead_work(self):
        cases = [
            ({"provider_enabled": False}, "SKIP_DISABLED"),
            ({"policy_forced": True}, "SKIP_POLICY_SUFFICIENT"),
            ({"calibration_status": "STALE"}, "SKIP_STALE_CALIBRATION"),
            ({"provider_enabled": True, "calibration_status": "CALIBRATED_FOR_FROZEN_SUITE"}, "CALL_REFLEX"),
        ]
        for kwargs, expected in cases:
            self.assertEqual(verification.evaluate_verification_value_of_call(opportunity(), **kwargs).reason, expected)
        self.assertEqual(verification.evaluate_verification_value_of_call(opportunity(host_selective_dispatch_proof=""), calibration_status="CALIBRATED_FOR_FROZEN_SUITE").reason, "SKIP_HOST_CANNOT_EXPLOIT_RESULT")
        self.assertEqual(verification.evaluate_verification_value_of_call(opportunity(budget={"max_optional_candidates": 0, "max_verification_cost_units": 5, "max_wall_clock_ms": 500}), calibration_status="CALIBRATED_FOR_FROZEN_SUITE").reason, "SKIP_BUDGET")
        self.assertEqual(verification.evaluate_verification_value_of_call(opportunity(budget={"max_optional_candidates": 2, "max_verification_cost_units": 5, "max_wall_clock_ms": 500}), calibration_status="CALIBRATED_FOR_FROZEN_SUITE").reason, "SKIP_NO_MATERIAL_ROUTE_DELTA")

    def test_exact_question_paths_and_no_generic_routing_questions(self):
        request = verification.build_verification_request(opportunity())
        questions = verification.verification_questions(len(request["candidates"]))
        self.assertEqual(len(questions), 2)
        for index, question in enumerate(questions):
            self.assertIn(f"`candidates[{index}]`", question["instructions"])
            self.assertNotIn("coordination_preference", question["instructions"])
            self.assertNotIn("route_", question["instructions"])
            self.assertEqual(question["kind"], "noul")

    def test_policy_band_composition_never_lets_jev_change_priority(self):
        raw = opportunity(optional_candidates=[candidate("high", 0, "g1", 100), candidate("low", 1, "g2", 100)])
        plan = verification.compose_verification_plan(raw, {"high": 0.61, "low": 0.99})
        self.assertEqual(plan["selected_optional_candidate_ids"], ["high"])

    def test_invalid_or_stale_results_use_deterministic_fallback(self):
        raw = opportunity()
        fallback = verification.compose_verification_plan(raw, {"wrong": 0.99})
        self.assertTrue(fallback["fallback_used"])
        self.assertEqual(fallback["fallback_reason"], "INVALID_REFLEX_RESULT")
        self.assertEqual(fallback["selected_optional_candidate_ids"], ["c1"])

    def test_dispatch_is_exactly_the_plan_and_mandatory_survives(self):
        raw = opportunity()
        normalized = verification.normalize_verification_opportunity(raw)
        plan = verification.compose_verification_plan(raw, {"c1": 0.9, "c2": 0.1})
        class Dispatcher:
            def dispatch_selected(self, *, candidate_ids, operation_ids, plan):
                self.args = (list(candidate_ids), list(operation_ids), copy.deepcopy(plan))
                return {"dispatched_operation_ids": list(operation_ids)}
        dispatcher = Dispatcher()
        receipt = verification.dispatch_verification_plan(plan, normalized, dispatcher)
        self.assertEqual(receipt["dispatched_operation_ids"], ["mandatory-policy", "op-c1"])
        self.assertEqual(dispatcher.args[0], ["mandatory-policy", "c1"])
        with self.assertRaises(verification.VerificationContractError):
            verification.validate_dispatch_receipt(plan, normalized, {"dispatched_operation_ids": ["op-c2"]})

    def test_final_report_is_protected_from_jev_scores(self):
        ordered = verification.final_finding_order([
            {"finding_id": "hypothesis", "evidence_state": "UNVERIFIED", "policy_priority_rank": 0},
            {"finding_id": "hard", "evidence_state": "VERIFIED", "policy_priority_rank": 99},
        ])
        self.assertEqual([item["finding_id"] for item in ordered], ["hard", "hypothesis"])

    def test_provider_failure_is_conservative_and_bounded(self):
        class FailingProvider:
            def evaluate(self, request, questions):
                raise RuntimeError("provider unavailable")
        governed = verification.govern_verification(opportunity(), FailingProvider())
        self.assertEqual(governed["receipt"]["provider_request_count"], 0)
        self.assertTrue(governed["plan"]["fallback_used"])
        self.assertEqual(governed["plan"]["selected_optional_candidate_ids"], ["c1"])

    def test_readback_requires_proof_and_cannot_demote_verified(self):
        raw = candidate("c1")
        ledger = verification.FindingLedger([{"finding_id": "c1", "evidence_state": "UNVERIFIED", "policy_priority_rank": 0}])
        record = ledger.apply_readback(raw, {"verifier_operation_id": "op-c1", "evidence_state": "VERIFIED", "proof_hash": "d" * 64, "evidence_refs": ["fixture://proof"]})
        self.assertEqual(record["evidence_state"], "VERIFIED")
        with self.assertRaises(verification.VerificationContractError):
            ledger.apply_readback(raw, {"verifier_operation_id": "op-c1", "evidence_state": "FALSIFIED", "proof_hash": "e" * 64, "evidence_refs": ["fixture://proof-2"]})

    def test_api_key_only_or_disabled_provider_makes_zero_request(self):
        class CountingProvider:
            def __init__(self): self.calls = 0
            def evaluate(self, request, questions): self.calls += 1; return {}
        provider = CountingProvider()
        result = verification.govern_verification(opportunity(), provider, provider_enabled=False)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result["receipt"]["admission"]["reason"], "SKIP_DISABLED")


if __name__ == "__main__":
    unittest.main()
