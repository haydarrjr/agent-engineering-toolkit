import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_margos_jev_v3 as benchmark
import margos_context as context
import margos_decide as routing
import margos_evidence_capsule as capsule
import margos_fingerprint as fingerprint


def route_state(**overrides):
    state = {
        "task": {"objective": "inspect parser", "task_kind": "RESEARCH", "mutation_kind": "READ_ONLY", "requested_outcome": "report", "verification_obligation": "cite evidence"},
        "host": {"host_id": "test", "subagents_proven": True, "per_child_model_control_proven": True, "reasoning_control_proven": True, "concurrency_proven": True, "isolation_proven": True, "available_compute_classes": ["ECONOMY_READ", "BALANCED_EXEC", "FRONTIER_REASONING"]},
        "authority": {"explicit_model_provider_constraint": None, "remote_write_authorized": False, "destructive_or_production_authorized": False, "unresolved_external_effect": False},
        "work_shape": {"obligation_count": 2, "overlapping_write_scopes": False, "shared_state": False, "parallel_safe": True},
        "evidence": {"verification_failed": False, "conflicting_sources": False, "unresolved_ambiguity": False, "cross_system_impact": False, "high_impact_correctness_or_security": False},
        "budget": {"max_children": 2, "max_escalations": 1, "cost_class": "NORMAL", "latency_class": "NORMAL"},
    }
    for section, values in overrides.items():
        state[section].update(values)
    return state


def signal_reflex(ambiguity=0.0, verification=0.0, direct=0.0):
    def score(options, high, value):
        return {"probabilities": {option: ((value / len(high)) if option in high else (1 - value) / (len(options) - len(high))) for option in options}}
    return {"answers": {
        "task_ambiguity": score(["LOW", "MODERATE", "HIGH", "SEVERE"], {"HIGH", "SEVERE"}, ambiguity),
        "verification_risk": score(["LOW", "MEDIUM", "HIGH", "CRITICAL"], {"HIGH", "CRITICAL"}, verification),
        "needs_escalation": {"probability": direct},
        "needs_independent_critic": {"probability": 0.0},
        "transfer_sufficient": {"probability": 1.0},
        "coordination_preference": {"probabilities": {"DIRECT": 1.0}},
        "compute_preference": {"probabilities": {"ECONOMY_READ": 1.0}},
    }}


class CountingProvider:
    def __init__(self):
        self.calls = 0

    def evaluate(self, request, questions):
        self.calls += 1
        raise AssertionError("provider must not be called")


class JevV3ContractTests(unittest.TestCase):
    def test_threshold_boundaries_are_independent_and_dead_thresholds_are_empty(self):
        self.assertEqual(routing.dead_thresholds(), set())
        for field, signal_key in (("ambiguity_escalation", "ambiguity"), ("verification_escalation", "verification"), ("direct_escalation", "direct")):
            threshold = routing.THRESHOLDS[field]
            below = {"ambiguity": 0.0, "verification": 0.0, "direct": 0.0}
            below[signal_key] = threshold - 1e-6
            signals = routing.reflex_signals(signal_reflex(**below))
            self.assertFalse(signals["frontier_required"])
            at = {"ambiguity": 0.0, "verification": 0.0, "direct": 0.0}
            at[signal_key] = threshold
            signals = routing.reflex_signals(signal_reflex(**at))
            self.assertTrue(signals["frontier_required"])

    def test_admission_skips_policy_budget_host_and_disabled_without_calls(self):
        cases = [
            (route_state(host={"subagents_proven": False}), routing.AdmissionReason.SKIP_POLICY_SUFFICIENT),
            (route_state(budget={"max_escalations": 0}), routing.AdmissionReason.SKIP_BUDGET),
            (route_state(work_shape={"route_equivalent": True}), routing.AdmissionReason.SKIP_NO_MATERIAL_ROUTE_DELTA),
            (route_state(task={"trivial": True}), routing.AdmissionReason.SKIP_POLICY_SUFFICIENT),
            (route_state(), routing.AdmissionReason.SKIP_DISABLED),
        ]
        for state, expected in cases:
            provider = CountingProvider()
            if expected == routing.AdmissionReason.SKIP_DISABLED:
                receipt = routing.decide(state)
            else:
                receipt = routing.decide(state, provider)
            self.assertEqual(receipt["admission"]["reason"], expected.value)
            self.assertEqual(provider.calls, 0)

    def test_admission_skips_hard_verification_cases_before_jev(self):
        provider = CountingProvider()
        receipt = routing.decide(
            route_state(evidence={"verification_failed": True, "conflicting_sources": True}),
            provider,
        )
        self.assertEqual(
            receipt["admission"]["reason"],
            routing.AdmissionReason.SKIP_POLICY_SUFFICIENT.value,
        )
        self.assertEqual(receipt["provider"]["status"], "DISABLED")
        self.assertEqual(receipt["selected"]["compute"], "FRONTIER_REASONING")
        self.assertEqual(provider.calls, 0)

    def test_api_key_presence_alone_does_not_call_routing_provider(self):
        provider = CountingProvider()
        receipt = routing.decide(route_state(), None)
        self.assertEqual(receipt["provider"]["status"], "DISABLED")
        self.assertEqual(provider.calls, 0)

    def test_policy_admissibility_and_final_veto_remain_authoritative(self):
        pre = routing.policy_pre_evaluate(route_state(work_shape={"overlapping_write_scopes": True}))
        self.assertNotIn("DELEGATED", pre["admissible"]["coordination"])
        bad = routing.FixtureReflexProvider({
            "coordination_preference": {"value": "DELEGATED", "probabilities": {x: 0.0 for x in routing.Coordination}},
            "compute_preference": {"value": "BALANCED_EXEC", "probabilities": {x: (1.0 if x == "BALANCED_EXEC" else 0.0) for x in routing.ComputeTier}},
            "task_ambiguity": {"value": "LOW", "probabilities": {x: (1.0 if x == "LOW" else 0.0) for x in ("LOW", "MODERATE", "HIGH", "SEVERE")}},
            "verification_risk": {"value": "LOW", "probabilities": {x: (1.0 if x == "LOW" else 0.0) for x in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}},
            "needs_escalation": {"probability": 0.0}, "needs_independent_critic": {"probability": 0.0}, "transfer_sufficient": {"probability": 1.0},
        })
        receipt = routing.decide(route_state(work_shape={"overlapping_write_scopes": True}), bad)
        self.assertEqual(receipt["provider"]["status"], "ERROR")
        self.assertNotEqual(receipt["selected"]["coordination"], "DELEGATED")

    def test_evidence_extractor_covers_kinds_hashes_budget_and_fallback(self):
        examples = [
            ({"kind": "SOURCE", "source": {"tool": "read_file"}}, "def parser():\n    return 'parser'"),
            ({"kind": "DIFF", "source": {"tool": "git_diff"}}, "@@ -1 +1 @@\n-parser\n+parser"),
            ({"kind": "TEST", "source": {"tool": "pytest"}}, "Traceback (most recent call last):\nAssertionError: parser"),
            ({"kind": "SEARCH", "source": {"tool": "repo_search"}}, "src/parser.py: parser"),
            ({"kind": "DOCUMENT", "source": {"tool": "docs"}}, "Parser documentation"),
            ({"kind": "STRUCTURED", "source": {"tool": "tool_result"}}, '{"parser": true}'),
            ({"kind": "OTHER", "source": {"tool": "unknown"}}, "unmatched payload"),
        ]
        for item, text in examples:
            result = capsule.extract_evidence_capsule(item, text, {"objective": "parser"}, budget=24)
            self.assertEqual(result["status"], "AVAILABLE")
            self.assertLessEqual(result["total_characters"], 24)
            self.assertEqual(result["payload_sha256"], hashlib.sha256(text.encode()).hexdigest())
            self.assertEqual(len(result["exact_excerpts"]), len(result["excerpt_sha256s"]))
        secret = capsule.extract_evidence_capsule(examples[-1][0], "safe prefix\nsk-" + "A" * 24, budget=24)
        self.assertEqual(secret["status"], "SUPPRESSED_SECRET")
        self.assertEqual(secret["exact_excerpts"], [])

    def test_fingerprint_mismatch_is_detectable_and_benchmark_is_forced_and_partitioned(self):
        args = type("Args", (), {
            "mode": "fixture", "model": None,
            "routing_dataset": ROOT / "tests/fixtures/margos/routing-cases-v1.json",
            "context_dataset": ROOT / "tests/fixtures/margos/context-benchmark-v1.json",
            "min_routing_cases": 10, "min_context_cases": 10,
            "workers": 1,
        })()
        report = benchmark.run(args)
        self.assertEqual(set(report["arms"]), set(benchmark.ARMS))
        self.assertEqual(report["promotion_status"], "JEV_NOT_PROMOTED")
        self.assertTrue(report["partition_isolation"])
        self.assertEqual(report["threshold_selection"]["policy"], "CALIBRATION_SET_ONLY")
        self.assertEqual(report["threshold_selection"]["holdout_evaluations"], 1)
        self.assertTrue(report["gold_labels_are_external_to_jev"])
        self.assertEqual(report["arms"]["A_POLICY_ONLY"]["routing"]["jev_request_count"], 0)
        self.assertEqual(report["arms"]["B_POLICY_JEV_ROUTING"]["routing"]["cases"], 10)
        self.assertIn("fingerprint_sha256", report["runtime_fingerprint"])
        changed = copy.deepcopy(report["runtime_fingerprint"])
        changed["source_sha"] = "different"
        self.assertIn("source_sha", fingerprint.fingerprint_mismatches(report["runtime_fingerprint"], changed))

    def test_promotion_requires_pinned_observed_model_and_live_gates(self):
        self.assertEqual(
            benchmark.promotion_status(
                live=True, model="jev-1.13.0", response_models=["jev-1.13.0"], safe=True, non_inferior=True, provider_errors=0,
                efficiency_non_regression=True, material_benefit=True,
            ),
            "JEV_PROMOTED_FOR_FROZEN_SUITE",
        )
        self.assertEqual(
            benchmark.promotion_status(
                live=True, model="jev-latest", response_models=["jev-1.13.0"], safe=True, non_inferior=True, provider_errors=0,
                efficiency_non_regression=True, material_benefit=True,
            ),
            "JEV_PROMOTED_FOR_FROZEN_SUITE",
        )
        self.assertEqual(
            benchmark.promotion_status(
                live=True, model="jev-latest", response_models=["jev-1.14.0"], safe=True, non_inferior=True, provider_errors=0
            ),
            "JEV_RESEARCH_ONLY",
        )
        self.assertEqual(
            benchmark.promotion_status(
                live=True, model="jev-1.13.0", response_models=["jev-1.13.0"], safe=False, non_inferior=True, provider_errors=0
            ),
            "JEV_NOT_PROMOTED",
        )


if __name__ == "__main__":
    unittest.main()
