import concurrent.futures
import copy
import json
import sys
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/margos/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_margos_jev_v4 as benchmark
import margos_decide as routing
import margos_reflex_jev as jev
import margos_retrieval as retrieval
import margos_value as value


def state():
    return {
        "task": {"objective": "inspect parser", "task_kind": "RESEARCH", "mutation_kind": "READ_ONLY", "requested_outcome": "report", "verification_obligation": "cite evidence"},
        "host": {"host_id": "test", "subagents_proven": True, "per_child_model_control_proven": True, "reasoning_control_proven": True, "concurrency_proven": True, "isolation_proven": True, "available_compute_classes": ["ECONOMY_READ", "BALANCED_EXEC", "FRONTIER_REASONING"]},
        "authority": {"explicit_model_provider_constraint": None, "remote_write_authorized": False, "destructive_or_production_authorized": False, "unresolved_external_effect": False},
        "work_shape": {"obligation_count": 2, "overlapping_write_scopes": False, "shared_state": False, "parallel_safe": True, "route_equivalent": False},
        "evidence": {"verification_failed": False, "conflicting_sources": False, "unresolved_ambiguity": False, "cross_system_impact": False, "high_impact_correctness_or_security": False},
        "budget": {"max_children": 2, "max_escalations": 1, "cost_class": "NORMAL", "latency_class": "NORMAL"},
    }


class CountingProvider:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.lock = threading.Lock()

    def evaluate(self, request, questions):
        del request, questions
        with self.lock:
            self.calls += 1
        time.sleep(0.02)
        return copy.deepcopy(self.response)


class JevV4Tests(unittest.TestCase):
    def test_explicit_missing_execution_opportunity_is_zero_call(self):
        provider = CountingProvider({})
        raw = state()
        raw["execution_opportunity"] = None
        receipt = routing.decide(raw, provider)
        self.assertEqual(receipt["admission"]["reason"], "SKIP_NO_AVOIDABLE_OPERATION")
        self.assertEqual(provider.calls, 0)

    def test_shadow_records_reflex_without_changing_policy_fallback(self):
        raw = state()
        raw["execution_opportunity"] = benchmark._opportunity(raw)
        pre = routing.policy_pre_evaluate(raw)
        provider = benchmark.UnbiasedRouteProvider()
        active = routing.decide(raw, provider)
        shadow = routing.decide(raw, provider, shadow=True)
        self.assertEqual(shadow["rollout"]["mode"], "SHADOW")
        self.assertFalse(shadow["rollout"]["execution_affected_by_reflex"])
        self.assertEqual(shadow["selected"]["source"], "POLICY_FALLBACK")
        self.assertEqual(active["rollout"]["mode"], "ACTIVE")
        self.assertEqual(active["admission"]["policy_state_sha256"], pre["state_sha256"])

    def test_stale_calibration_cannot_affect_explicit_operation(self):
        raw = state()
        raw["execution_opportunity"] = benchmark._opportunity(raw)
        provider = jev.JevReflexProvider(
            api_key="test",
            calibration_binding={"evaluation_status": "FAILED", "model": jev.PINNED_MODEL},
            transport=lambda *args: {"model": jev.PINNED_MODEL, "answers": {}},
        )
        receipt = routing.decide(raw, provider)
        self.assertEqual(receipt["admission"]["reason"], "SKIP_UNCALIBRATED_VALUE_MODEL")
        self.assertEqual(receipt["selected"]["source"], "POLICY_FALLBACK")
        provider.close()

    def test_value_of_call_is_cost_vector_not_magic_scalar(self):
        opportunity = {
            "opportunity_id": "op-1",
            "fallback_operation_id": "expensive",
            "candidates": [
                {"operation_id": "cheap", "coordination": "DIRECT", "compute": "ECONOMY_READ", "host_capability_proof": "test", "cost": {"latency_ms_p50": 2, "latency_ms_p95": 4, "model_tokens": 10, "money_microunits": 1, "retrieval_bytes": 20, "verification_cost_units": 1}},
                {"operation_id": "expensive", "coordination": "DIRECT", "compute": "FRONTIER_REASONING", "host_capability_proof": "test", "cost": {"latency_ms_p50": 100, "latency_ms_p95": 200, "model_tokens": 900, "money_microunits": 30, "retrieval_bytes": 1000, "verification_cost_units": 8}},
            ],
            "critical_path": True,
            "host_can_exploit_result": True,
            "jev_latency_budget_ms": 50,
            "cost_model_version": "test/v1",
        }
        result = value.evaluate_value_of_call(opportunity, calibration_status="CALIBRATED_FOR_FROZEN_SUITE")
        self.assertTrue(result.admitted)
        self.assertEqual(result.reason, "CALL_REFLEX")
        self.assertGreater(result.max_possible_saving["model_tokens"], 0)
        self.assertGreater(result.max_possible_saving["retrieval_bytes"], 0)

    def test_session_cache_and_singleflight(self):
        raw = state()
        pre = routing.policy_pre_evaluate(raw)
        answers = {
            "coordination_preference": {"choice": "TRANSFER", "probabilities": {"DIRECT": 0.0, "TRANSFER": 1.0, "DELEGATED": 0.0, "SERIALIZED": 0.0}},
            "compute_preference": {"choice": "ECONOMY_READ", "probabilities": {"ECONOMY_READ": 1.0, "BALANCED_EXEC": 0.0, "FRONTIER_REASONING": 0.0}},
            "task_ambiguity": {"score": 0, "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 0.0}},
            "verification_risk": {"score": 0, "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 0.0}},
            "needs_escalation": {"noul": 0.0}, "needs_independent_critic": {"noul": 0.0}, "transfer_sufficient": {"noul": 1.0},
        }
        response = {"model": "jev-1.13.0", "answers": answers}
        calls = 0
        lock = threading.Lock()
        def transport(base, key, payload, timeout):
            nonlocal calls
            del base, key, payload, timeout
            with lock:
                calls += 1
            time.sleep(0.02)
            return copy.deepcopy(response)
        provider = jev.JevReflexProvider(api_key="test", transport=transport)
        request = routing.build_reflex_request(pre)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: provider.evaluate(request, routing.QUESTION_SET), range(4)))
        self.assertEqual(calls, 1)
        self.assertTrue(any(result["provider"].get("coalesced") for result in results))
        cached = provider.evaluate(request, routing.QUESTION_SET)
        self.assertTrue(cached["provider"]["cache_hit"])
        self.assertEqual(cached["provider"]["network_request_count"], 0)
        provider.close()

    def test_retrieval_planner_does_not_load_unselected_optional_payloads(self):
        metadata = retrieval.build_metadata_state(
            {"objective": "inspect", "verification_obligation": "cite"},
            [
                {"candidate_id": "protected", "kind": "SOURCE", "source": {"tool": "read", "locator": "policy"}, "estimated_size": {"bytes": 10, "tokens": 2}, "mandatory_by_policy": True},
                {"candidate_id": "needed", "kind": "SOURCE", "source": {"tool": "read", "locator": "needed"}, "estimated_size": {"bytes": 100, "tokens": 25}, "mandatory_by_policy": False},
                {"candidate_id": "optional", "kind": "SOURCE", "source": {"tool": "read", "locator": "optional"}, "estimated_size": {"bytes": 100, "tokens": 25}, "mandatory_by_policy": False},
            ],
        )
        class Provider:
            def evaluate(self, request, questions):
                self.request = request
                return {"provider": {"status": "AVAILABLE", "network_request_count": 1}, "answers": {"needed": {"needed_for_next_obligation": {"probability": 0.9}}, "optional": {"needed_for_next_obligation": {"probability": 0.1}}}}
        provider = Provider()
        plan = retrieval.plan_context_retrieval(
            metadata,
            provider,
            calibration_status="CALIBRATED_FOR_FROZEN_SUITE",
        )
        self.assertEqual(plan["selected_ids"], ["protected", "needed"])
        self.assertNotIn('"content":', json.dumps(provider.request))
        loader = retrieval.InMemoryPayloadLoader({"protected": "P", "needed": "N", "optional": "O"})
        materialized = retrieval.materialize_context_from_plan(plan, loader)
        self.assertEqual(loader.loaded_ids, ["protected", "needed"])
        self.assertEqual(materialized["telemetry"]["actual_fetch_count"], 2)

    def test_v4_has_disjoint_holdout_and_realized_operation_metrics(self):
        args = type("Args", (), {"mode": "fixture", "model": None, "routing_dataset": ROOT / "tests/fixtures/margos/routing-cases-v1.json", "context_dataset": ROOT / "tests/fixtures/margos/context-benchmark-v1.json"})()
        report = benchmark.run(args)
        self.assertEqual(set(report["arms"]), set(benchmark.ARMS))
        self.assertTrue(report["partition_isolation"])
        self.assertTrue(report["promotion_gates"]["realized_expensive_work_observed"])
        self.assertEqual(report["promotion_status"], "JEV_NOT_PROMOTED")
        self.assertTrue(all("expensive_operations" in report["arms"][arm]["routing"] for arm in benchmark.ARMS))


if __name__ == "__main__":
    unittest.main()
