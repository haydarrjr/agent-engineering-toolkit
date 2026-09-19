import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/margos/scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "margos_context.py"
spec = importlib.util.spec_from_file_location("margos_context", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item(item_id, text, *, authority=None, evidence=None, replayable=True, superseded_by=None, turn_distance=1):
    return {
        "schema_version": "margos-context-item/v1",
        "item_id": item_id,
        "kind": "TOOL_RESULT",
        "source": {"tool": "read_file", "locator": f"src/{item_id}.py", "result_status": "OK", "content_version": "abc123"},
        "content_sha256": digest(text),
        "size": {"chars": len(text), "tokens_estimated": max(1, len(text) // 4)},
        "authority": authority or {},
        "evidence": evidence or {},
        "replay": {
            "status": "REPLAYABLE" if replayable else "NON_REPLAYABLE",
            "method": "READ_FILE" if replayable else "UNAVAILABLE",
            "locator": f"src/{item_id}.py" if replayable else None,
        },
        "supersession": {
            "status": "SUPERSEDED" if superseded_by else "CURRENT",
            "superseded_by": superseded_by,
        },
        "recency": {"turn_distance": turn_distance},
    }


def state(items):
    return {
        "schema_version": "margos-context-state/v1",
        "task": {"task_id": "t1", "objective": "implement safely", "verification_obligation": "tests green"},
        "items": items,
        "view": {"head_chars": 32},
    }


class ContextPolicyTests(unittest.TestCase):
    def test_old_binding_user_constraint_is_pinned(self):
        text = "Never edit generated files."
        obj = item("constraint", text, authority={"contains_user_constraint": True}, turn_distance=80)
        decision = mod.decide_item(obj)
        self.assertEqual(decision["action"], "PIN")
        self.assertEqual(decision["protection_class"], "PINNED")
        self.assertEqual(decision["admissible_actions"], ["PIN"])

    def test_unresolved_external_effect_is_pinned(self):
        text = "Remote write returned an ambiguous timeout."
        obj = item("effect", text, authority={"contains_unresolved_external_effect": True})
        self.assertEqual(mod.decide_item(obj)["action"], "PIN")

    def test_active_contradiction_is_pinned(self):
        text = "Source A conflicts with source B."
        obj = item("conflict", text, evidence={"contradiction_open": True})
        self.assertEqual(mod.decide_item(obj)["action"], "PIN")

    def test_non_replayable_evidence_keeps_full_payload(self):
        text = "Ephemeral response that cannot be reconstructed."
        obj = item("ephemeral", text, replayable=False)
        decision = mod.decide_item(obj)
        self.assertEqual(decision["action"], "KEEP_FULL")
        self.assertEqual(decision["rehydration"]["status"], "UNAVAILABLE")
        self.assertEqual(decision["admissible_actions"], ["KEEP_FULL"])

    def test_superseded_replayable_result_is_omitted_with_rehydration(self):
        old = "old test log"
        new = "new test log"
        items = [item("old", old, superseded_by="new"), item("new", new)]
        view, receipt = mod.materialize_context_view(state(items), {"old": old, "new": new})
        actions = {entry["item_id"]: entry["action"] for entry in receipt["actions"]}
        self.assertEqual(actions["old"], "OMIT_REHYDRATABLE")
        old_decision = next(entry for entry in receipt["actions"] if entry["item_id"] == "old")
        self.assertEqual(set(old_decision["admissible_actions"]), {"KEEP_FULL", "KEEP_REF", "KEEP_HEAD", "OMIT_REHYDRATABLE"})
        self.assertEqual(actions["new"], "KEEP_REF")
        self.assertNotIn("old", {entry["item_id"] for entry in view["items"]})
        self.assertIn("old", {entry["item_id"] for entry in view["rehydration_index"]})
        self.assertTrue(receipt["rehydration_available"])

    def test_frozen_fixture_materializes_bounded_child_ready_view(self):
        fixture = json.loads((ROOT / "tests/fixtures/margos/context-materialization-v1.json").read_text(encoding="utf-8"))
        view, receipt = mod.materialize_context_view(fixture["state"], fixture["payloads"])
        actions = {entry["item_id"]: entry["action"] for entry in receipt["actions"]}
        self.assertEqual(actions, fixture["expect"]["actions"])
        self.assertEqual({entry["item_id"] for entry in view["items"]}, set(fixture["expect"]["active_ids"]))
        self.assertTrue(set(fixture["expect"]["omitted_ids"]).isdisjoint({entry["item_id"] for entry in view["items"]}))
        self.assertLess(receipt["output"]["characters_serialized"], receipt["input"]["characters"])

    def test_materializer_preserves_exact_pinned_payload_and_does_not_mutate_inputs(self):
        protected = "binding exact text"
        replayable = "large replayable payload"
        raw = state([
            item("protected", protected, authority={"contains_active_verification_obligation": True}),
            item("replayable", replayable),
        ])
        payloads = {"protected": protected, "replayable": replayable}
        raw_before = copy.deepcopy(raw)
        payloads_before = copy.deepcopy(payloads)
        view, receipt = mod.materialize_context_view(raw, payloads)
        by_id = {entry["item_id"]: entry for entry in view["items"]}
        self.assertEqual(by_id["protected"]["content"], protected)
        self.assertEqual(by_id["replayable"]["action"], "KEEP_REF")
        self.assertNotIn("content", by_id["replayable"])
        self.assertEqual(raw, raw_before)
        self.assertEqual(payloads, payloads_before)
        self.assertFalse(receipt["canonical_source_mutated"])
        self.assertEqual(receipt["authority"], "DERIVED_VIEW")

    def test_payload_hash_mismatch_is_rejected_for_protected_content(self):
        obj = item("protected", "trusted", authority={"contains_user_constraint": True})
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            mod.materialize_context_view(state([obj]), {"protected": "altered"})

    def test_supersession_requires_known_successor(self):
        obj = item("old", "old", superseded_by="missing")
        with self.assertRaisesRegex(ValueError, "superseded_by"):
            mod.normalize_state(state([obj]))

    def test_rehydrator_cannot_recover_non_replayable_item(self):
        class Resolver:
            def recover(self, contract):
                return "should not run"
        with self.assertRaisesRegex(ValueError, "no safe deterministic rehydration"):
            mod.rehydrate_item(item("ephemeral", "x", replayable=False), Resolver())

    def test_rehydrated_content_is_hash_bound(self):
        class Resolver:
            def recover(self, contract):
                self.contract = contract
                return "content"
        resolver = Resolver()
        self.assertEqual(mod.rehydrate_item(item("file", "content"), resolver), "content")
        self.assertFalse(resolver.contract["may_repeat_external_effect"])

    def test_action_model_is_closed_and_contains_no_delete(self):
        values = {entry.value for entry in mod.ContextAction}
        self.assertEqual(values, {"PIN", "KEEP_FULL", "KEEP_REF", "KEEP_HEAD", "OMIT_REHYDRATABLE"})
        self.assertNotIn("DELETE", values)


if __name__ == "__main__":
    unittest.main()
