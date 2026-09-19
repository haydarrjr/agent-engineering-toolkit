import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))

import benchmark_margos_context as bench
import margos_host_compaction as host_compaction


class MargosContextEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "tests/fixtures/margos/context-benchmark-v1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_frozen_fixture_has_no_high_risk_secret_patterns(self):
        hits = bench.scan_fixture_for_secrets(
            ROOT / "tests/fixtures/margos/context-benchmark-v1.json"
        )
        self.assertEqual(hits, [])

    def test_policy_counterfactual_passes_strict_safety_and_success_gate(self):
        result = bench.evaluate_mode(self.fixture, "policy")
        ok, failures = bench.strict_gate(result["aggregate"], self.fixture)
        self.assertTrue(ok, failures)
        self.assertEqual(result["aggregate"]["verified_success_rate"], 1.0)
        self.assertEqual(result["aggregate"]["harmful_omission_cases"], 0)
        self.assertEqual(result["aggregate"]["protected_loss_violations"], 0)
        self.assertEqual(
            result["aggregate"]["non_replayable_omission_violations"], 0
        )
        self.assertEqual(result["aggregate"]["external_effect_loss_violations"], 0)
        self.assertEqual(result["aggregate"]["contradiction_loss_violations"], 0)
        self.assertGreater(
            result["aggregate"]["serialized_reduction_ratio"], 0.40
        )

    def test_fixture_reflex_counterfactual_is_non_inferior_and_measurable(self):
        result = bench.evaluate_mode(self.fixture, "fixture")
        aggregate = result["aggregate"]
        ok, failures = bench.strict_gate(aggregate, self.fixture)
        self.assertTrue(ok, failures)
        self.assertEqual(aggregate["verified_success_delta"], 0.0)
        self.assertEqual(aggregate["harmful_omission_rate"], 0.0)
        self.assertGreater(aggregate["rehydration_count"], 0)
        self.assertGreater(aggregate["calibration_observations"], 0)
        self.assertIsNotNone(aggregate["brier_score"])
        self.assertIsNotNone(aggregate["ece_5_bin"])

    def test_costly_omission_requires_rehydration_but_is_not_harmful(self):
        result = bench.evaluate_mode(self.fixture, "fixture")
        costly = [
            case
            for case in result["cases"]
            if case["oracle"]["omission_class"] == "COSTLY"
        ]
        self.assertTrue(costly)
        self.assertTrue(all(case["candidate"]["verified_success"] for case in costly))
        self.assertTrue(
            all(case["oracle"]["rehydration_count"] > 0 for case in costly)
        )

    def test_live_jev_research_without_key_performs_zero_network(self):
        case = self.fixture["cases"][0]
        with patch.dict(os.environ, {}, clear=True):
            result = bench.evaluate_case(case, "jev")
        self.assertEqual(result["candidate"]["provider_status"], "NOT_CONFIGURED")
        self.assertEqual(result["candidate"]["provider_network_request_count"], 0)

    def test_host_compaction_is_disabled_without_explicit_opt_in(self):
        request = {
            "schema_version": "margos-host-compaction-request/v1",
            "host": {
                "host_id": "fixture-host",
                "root_compaction_hook_proven": True,
                "native_compaction_proven": True,
            },
            "experimental_adapter_enabled": False,
            "context": {
                "authority": "DERIVED_VIEW",
                "canonical_source_mutated": False,
                "context_view_sha256": "a" * 64,
                "input_characters": 10000,
                "output_characters": 2000,
            },
        }
        result = host_compaction.decide_host_compaction(request)
        self.assertEqual(result["action"], "NO_AET_INTERCEPTION")
        self.assertEqual(result["host_execution"]["status"], "NOT_APPLICABLE")

    def test_host_compaction_requires_proven_root_hook(self):
        request = {
            "schema_version": "margos-host-compaction-request/v1",
            "host": {
                "host_id": "fixture-host",
                "root_compaction_hook_proven": False,
                "native_compaction_proven": True,
            },
            "experimental_adapter_enabled": True,
            "context": {
                "authority": "DERIVED_VIEW",
                "canonical_source_mutated": False,
                "context_view_sha256": "b" * 64,
                "input_characters": 10000,
                "output_characters": 2000,
            },
        }
        result = host_compaction.decide_host_compaction(request)
        self.assertEqual(result["action"], "DEFER_HOST_NATIVE")
        self.assertIsNone(result["context_view_sha256"])

    def test_host_compaction_offer_remains_proposed(self):
        request = {
            "schema_version": "margos-host-compaction-request/v1",
            "host": {
                "host_id": "fixture-hook-host",
                "root_compaction_hook_proven": True,
                "native_compaction_proven": True,
            },
            "experimental_adapter_enabled": True,
            "context": {
                "authority": "DERIVED_VIEW",
                "canonical_source_mutated": False,
                "context_view_sha256": "c" * 64,
                "input_characters": 10000,
                "output_characters": 2000,
            },
        }
        result = host_compaction.decide_host_compaction(request)
        self.assertEqual(result["action"], "OFFER_DERIVED_VIEW")
        self.assertEqual(result["decision_authority"], "PROPOSED")
        self.assertEqual(result["host_execution"]["status"], "PENDING")
        self.assertFalse(result["canonical_source_mutated"])

    def test_host_compaction_rejects_non_derived_authority(self):
        request = {
            "schema_version": "margos-host-compaction-request/v1",
            "host": {
                "host_id": "fixture-hook-host",
                "root_compaction_hook_proven": True,
                "native_compaction_proven": True,
            },
            "experimental_adapter_enabled": True,
            "context": {
                "authority": "CANONICAL",
                "canonical_source_mutated": False,
                "context_view_sha256": "d" * 64,
                "input_characters": 10000,
                "output_characters": 2000,
            },
        }
        with self.assertRaisesRegex(ValueError, "DERIVED_VIEW"):
            host_compaction.decide_host_compaction(request)


if __name__ == "__main__":
    unittest.main()
