import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/margos/scripts"
sys.path.insert(0, str(SCRIPTS))

import margos_context as ctx
import margos_handoff as handoff


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item(
    item_id,
    text,
    *,
    tool="read_file",
    locator=None,
    authority=None,
    replay_method="READ_FILE",
):
    locator = locator or f"src/{item_id}.txt"
    return {
        "schema_version": "margos-context-item/v1",
        "item_id": item_id,
        "kind": "TOOL_RESULT",
        "source": {
            "tool": tool,
            "locator": locator,
            "result_status": "OK",
            "content_version": "phase3-fixture",
        },
        "content_sha256": digest(text),
        "size": {
            "chars": len(text),
            "tokens_estimated": max(1, len(text) // 4),
        },
        "authority": authority or {},
        "evidence": {},
        "replay": {
            "status": "REPLAYABLE",
            "method": replay_method,
            "locator": locator,
        },
        "supersession": {"status": "CURRENT", "superseded_by": None},
        "recency": {"turn_distance": 2},
    }


def context_fixture():
    payloads = {
        "constraint": "Never mutate canonical evidence.",
        "search": "S" * 2400,
        "owned": "W" * 3600,
        "chatter": "C" * 4200,
        "implementation": "I" * 1800,
        "testlog": "T" * 2800,
        "fresh": "F" * 3200,
        "rerun": "R" * 1200,
    }
    items = [
        item(
            "constraint",
            payloads["constraint"],
            locator="policy/user-constraint.txt",
            authority={"contains_user_constraint": True},
        ),
        item(
            "search",
            payloads["search"],
            tool="repo_search",
            locator="src/router.py",
        ),
        item("owned", payloads["owned"], locator="src/worker.py"),
        item(
            "chatter",
            payloads["chatter"],
            tool="read_file",
            locator="notes/implementation-chat.txt",
        ),
        item(
            "implementation",
            payloads["implementation"],
            tool="read_child_result",
            locator=".aet/results/worker.json",
        ),
        item(
            "testlog",
            payloads["testlog"],
            tool="run_test",
            locator=".aet/tests/run.log",
        ),
        item("fresh", payloads["fresh"], locator="src/critical.py"),
        item(
            "rerun",
            payloads["rerun"],
            tool="run_test",
            locator=".aet/tests/rerun.log",
            replay_method="REPEAT_TEST",
        ),
    ]
    state = {
        "schema_version": "margos-context-state/v1",
        "task": {
            "task_id": "phase3",
            "objective": "Perform the delegated obligation with bounded evidence.",
            "verification_obligation": "Preserve required evidence.",
        },
        "items": items,
        "view": {"head_chars": 64},
    }
    return state, payloads


def route(role, *, coordination="TRANSFER"):
    compute = "ECONOMY_READ" if role == "SCOUT" else "BALANCED_EXEC"
    if role == "INDEPENDENT_CRITIC":
        compute = "FRONTIER_REASONING"
    return {
        "schema_version": "margos-route-receipt/v1",
        "decision_authority": "PROPOSED",
        "state_sha256": "a" * 64,
        "policy_version": "margos-policy/v1",
        "question_set_version": "margos-questions/v1",
        "question_set_sha256": "b" * 64,
        "threshold_policy_version": "margos-thresholds/v1",
        "provider": {"kind": "fixture", "status": "AVAILABLE"},
        "admissible": {},
        "blocked": [],
        "policy_rules_applied": [],
        "reflex": {},
        "selected": {
            "disposition": "PROCEED",
            "coordination": coordination,
            "compute": compute,
            "role": role,
            "source": "REFLEX_ASSISTED",
            "abstained": False,
            "model_provider_constraint": None,
        },
        "host_execution": {"status": "PENDING"},
    }


def contract(role):
    value = {
        "schema_version": "margos-child-contract/v1",
        "child_id": f"child-{role.lower()}",
        "role": role,
        "objective": "Close only the delegated obligation.",
        "owned_paths": [],
        "required_context_ids": [],
        "required_full_ids": [],
        "implementation_result_ids": [],
        "verification_evidence_ids": [],
        "fresh_evidence_ids": [],
        "verification_obligation": "",
        "output_contract": "Return evidence and unresolved obligations.",
        "budget": {
            "max_optional_items": 1,
            "max_optional_payload_chars": 64,
        },
    }
    if role == "SCOUT":
        value["required_context_ids"] = ["search"]
    elif role == "WORKER":
        value["owned_paths"] = ["src"]
        value["required_context_ids"] = ["owned"]
        value["required_full_ids"] = ["owned"]
    elif role == "VERIFIER":
        value["implementation_result_ids"] = ["implementation"]
        value["verification_evidence_ids"] = ["testlog"]
        value["verification_obligation"] = "Reproduce the acceptance evidence."
    elif role == "INDEPENDENT_CRITIC":
        value["implementation_result_ids"] = ["implementation"]
        value["fresh_evidence_ids"] = ["fresh"]
        value["verification_obligation"] = "Try to falsify the implementation."
    return value


class ChildContextTests(unittest.TestCase):
    def test_frozen_role_contracts_are_evidence_sufficient_and_bounded(self):
        expected = json.loads(
            (
                ROOT
                / "tests/fixtures/margos/child-role-contract-v1.json"
            ).read_text(encoding="utf-8")
        )
        state, payloads = context_fixture()
        for case in expected["cases"]:
            role = case["role"]
            with self.subTest(role=role):
                bundle, receipt, bound, parent = handoff.build_child_handoff(
                    route(role), state, payloads, contract(role)
                )
                selected = {entry["item_id"] for entry in bundle["items"]}
                self.assertTrue(set(case["must_include"]) <= selected)
                self.assertTrue(set(case["must_exclude"]).isdisjoint(selected))
                self.assertEqual(receipt["required_coverage"], 1.0)
                self.assertFalse(receipt["canonical_source_mutated"])
                self.assertEqual(bundle["authority"], "DERIVED_VIEW")
                self.assertEqual(bound["context_binding"]["status"], "BOUND")
                self.assertEqual(
                    bound["context_binding"]["context_bundle_sha256"],
                    receipt["bundle_sha256"],
                )
                self.assertEqual(
                    parent["authority"],
                    "DERIVED_VIEW",
                )
                self.assertLess(
                    receipt["output"]["characters_serialized"],
                    receipt["input"]["characters"],
                )

    def test_scout_gets_reference_not_full_search_payload(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("SCOUT"), state, payloads, contract("SCOUT")
        )
        by_id = {entry["item_id"]: entry for entry in bundle["items"]}
        self.assertEqual(by_id["constraint"]["action"], "PIN")
        self.assertEqual(by_id["constraint"]["content"], payloads["constraint"])
        self.assertEqual(by_id["search"]["action"], "KEEP_REF")
        self.assertNotIn("content", by_id["search"])

    def test_worker_gets_owned_full_requirement_without_unrelated_chatter(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("WORKER"), state, payloads, contract("WORKER")
        )
        by_id = {entry["item_id"]: entry for entry in bundle["items"]}
        self.assertEqual(by_id["owned"]["action"], "KEEP_FULL")
        self.assertEqual(by_id["owned"]["content"], payloads["owned"])
        self.assertNotIn("chatter", by_id)

    def test_verifier_gets_exact_implementation_and_verification_evidence(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("VERIFIER"), state, payloads, contract("VERIFIER")
        )
        by_id = {entry["item_id"]: entry for entry in bundle["items"]}
        self.assertEqual(by_id["implementation"]["content"], payloads["implementation"])
        self.assertEqual(by_id["testlog"]["content"], payloads["testlog"])
        self.assertNotIn("owned", by_id)
        self.assertNotIn("chatter", by_id)

    def test_critic_has_fresh_bounded_evidence_not_worker_chatter(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("INDEPENDENT_CRITIC"),
            state,
            payloads,
            contract("INDEPENDENT_CRITIC"),
        )
        by_id = {entry["item_id"]: entry for entry in bundle["items"]}
        self.assertEqual(
            by_id["implementation"]["content"],
            payloads["implementation"],
        )
        self.assertEqual(by_id["fresh"]["action"], "KEEP_HEAD")
        self.assertEqual(by_id["fresh"]["head"], payloads["fresh"][:64])
        self.assertNotIn("chatter", by_id)
        self.assertNotIn("owned", by_id)

    def test_route_binding_is_hash_bound_without_mutating_input(self):
        state, payloads = context_fixture()
        raw_route = route("SCOUT")
        before = copy.deepcopy(raw_route)
        _, receipt, bound, _ = handoff.build_child_handoff(
            raw_route, state, payloads, contract("SCOUT")
        )
        self.assertEqual(raw_route, before)
        self.assertNotIn("context_binding", raw_route)
        self.assertEqual(
            receipt["route_receipt_sha256"],
            handoff._hash_json(before),
        )
        self.assertEqual(
            bound["context_binding"]["context_receipt_sha256"],
            handoff._hash_json(receipt),
        )

    def test_direct_route_cannot_create_child_handoff(self):
        state, payloads = context_fixture()
        raw_route = route("SCOUT", coordination="TRANSFER")
        raw_route["selected"]["coordination"] = "DIRECT"
        raw_route["selected"]["role"] = "PRIMARY"
        with self.assertRaisesRegex(ValueError, "child handoff requires"):
            handoff.build_child_handoff(
                raw_route, state, payloads, contract("SCOUT")
            )

    def test_role_mismatch_is_rejected(self):
        state, payloads = context_fixture()
        with self.assertRaisesRegex(ValueError, "must match"):
            handoff.build_child_handoff(
                route("SCOUT"), state, payloads, contract("WORKER")
            )

    def test_child_result_can_trigger_hash_bound_rehydration(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("SCOUT"), state, payloads, contract("SCOUT")
        )
        result = {
            "schema_version": "margos-child-result/v1",
            "child_id": bundle["child_id"],
            "role": bundle["role"],
            "status": "ESCALATE",
            "rehydration_requests": [
                {"item_id": "search", "reason": "Need the exact matched lines."}
            ],
        }
        plan = handoff.plan_child_rehydration(result, bundle)
        self.assertEqual(plan["requests"][0]["status"], "READY")

        class Resolver:
            def recover(self, rehydration_contract):
                self.contract = rehydration_contract
                return payloads["search"]

        resolver = Resolver()
        hydrated = handoff.resolve_child_rehydration(plan, state, resolver)
        self.assertEqual(hydrated["items"][0]["status"], "REHYDRATED")
        self.assertEqual(hydrated["items"][0]["content"], payloads["search"])
        self.assertFalse(resolver.contract["may_repeat_external_effect"])
        self.assertFalse(hydrated["canonical_source_mutated"])

    def test_rehydration_recompute_requires_authority_recheck(self):
        state, payloads = context_fixture()
        c = contract("SCOUT")
        c["required_context_ids"] = ["rerun"]
        bundle, _, _, _ = handoff.build_child_handoff(
            route("SCOUT"), state, payloads, c
        )
        result = {
            "schema_version": "margos-child-result/v1",
            "child_id": bundle["child_id"],
            "role": bundle["role"],
            "status": "ESCALATE",
            "rehydration_requests": [
                {"item_id": "rerun", "reason": "Need exact rerun evidence."}
            ],
        }
        plan = handoff.plan_child_rehydration(result, bundle)
        self.assertEqual(
            plan["requests"][0]["status"],
            "PENDING_AUTHORITY_RECHECK",
        )

        class Resolver:
            called = False

            def recover(self, rehydration_contract):
                self.called = True
                return payloads["rerun"]

        resolver = Resolver()
        pending = handoff.resolve_child_rehydration(plan, state, resolver)
        self.assertFalse(resolver.called)
        self.assertEqual(
            pending["items"][0]["status"],
            "PENDING_AUTHORITY_RECHECK",
        )
        hydrated = handoff.resolve_child_rehydration(
            plan, state, resolver, authority_recheck=True
        )
        self.assertTrue(resolver.called)
        self.assertEqual(hydrated["items"][0]["status"], "REHYDRATED")

    def test_unexposed_rehydration_request_is_rejected(self):
        state, payloads = context_fixture()
        bundle, _, _, _ = handoff.build_child_handoff(
            route("SCOUT"), state, payloads, contract("SCOUT")
        )
        result = {
            "schema_version": "margos-child-result/v1",
            "child_id": bundle["child_id"],
            "role": bundle["role"],
            "status": "ESCALATE",
            "rehydration_requests": [
                {"item_id": "chatter", "reason": "Try to fetch unrelated chatter."}
            ],
        }
        plan = handoff.plan_child_rehydration(result, bundle)
        self.assertEqual(
            plan["requests"][0]["status"],
            "REJECTED_NOT_EXPOSED",
        )

    def test_context_provider_runs_once_per_handoff_batch(self):
        state, payloads = context_fixture()
        calls = 0

        class Provider:
            def evaluate(self, request, questions):
                nonlocal calls
                calls += 1
                return {
                    "schema_version": ctx.CONTEXT_REFLEX_RESULT_VERSION,
                    "provider": {
                        "kind": "fixture-counting",
                        "status": "AVAILABLE",
                        "calibration_status": "UNCALIBRATED",
                        "network_request_count": 0,
                    },
                    "question_set_sha256": ctx.question_set_sha256(),
                    "answers": {
                        candidate["item_id"]: {
                            question["id"]: {"probability": 0.9}
                            for question in questions
                        }
                        for candidate in request["candidates"]
                    },
                }

        handoff.build_child_handoff(
            route("SCOUT"),
            state,
            payloads,
            contract("SCOUT"),
            Provider(),
        )
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
