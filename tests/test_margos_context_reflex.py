import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/margos/scripts"
sys.path.insert(0, str(SCRIPTS))

import margos_context as ctx
import margos_reflex_jev as jev


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def item(item_id, text, *, authority=None, superseded_by=None, locator=None):
    return {
        "schema_version": "margos-context-item/v1",
        "item_id": item_id,
        "kind": "TOOL_RESULT",
        "source": {
            "tool": "read_file",
            "locator": locator or f"src/{item_id}.py",
            "result_status": "OK",
            "content_version": "abc123",
        },
        "content_sha256": digest(text),
        "size": {"chars": len(text), "tokens_estimated": max(1, len(text) // 4)},
        "authority": authority or {},
        "evidence": {},
        "replay": {
            "status": "REPLAYABLE",
            "method": "READ_FILE",
            "locator": locator or f"src/{item_id}.py",
        },
        "supersession": {
            "status": "SUPERSEDED" if superseded_by else "CURRENT",
            "superseded_by": superseded_by,
        },
        "recency": {"turn_distance": 2},
    }


def state(items):
    return {
        "schema_version": "margos-context-state/v1",
        "task": {
            "task_id": "phase2",
            "objective": "Choose the smallest evidence-sufficient active context.",
            "verification_obligation": "Preserve protected evidence and safe rehydration.",
        },
        "items": items,
        "view": {"head_chars": 32},
    }


def answers(keep_awareness, keep_full, replay_needed):
    return {
        "keep_awareness": {"probability": keep_awareness},
        "keep_full": {"probability": keep_full},
        "replay_needed": {"probability": replay_needed},
    }


def available_result(request, value=None, provider_kind="recording"):
    value = value or answers(0.85, 0.10, 0.10)
    return {
        "schema_version": ctx.CONTEXT_REFLEX_RESULT_VERSION,
        "provider": {
            "kind": provider_kind,
            "status": "AVAILABLE",
            "calibration_status": "UNCALIBRATED",
            "network_request_count": 0,
        },
        "question_set_sha256": ctx.question_set_sha256(),
        "answers": {
            candidate["item_id"]: value
            for candidate in request["candidates"]
        },
    }


def fake_jev_response(payload):
    result = {}
    for qid in payload["questions"]:
        if qid.endswith("_keep_full"):
            probability = 0.12
        elif qid.endswith("_keep_awareness"):
            probability = 0.88
        elif qid.endswith("_replay_needed"):
            probability = 0.18
        else:
            raise AssertionError(qid)
        result[qid] = {"type": "noul", "noul": probability}
    return {
        "model": "jev-early-access",
        "answers": result,
        "usage": {"input_tokens": 211, "output_tokens": 31},
    }


class ContextReflexTests(unittest.TestCase):
    def test_fixture_reflex_composes_full_ref_and_omit(self):
        payloads = {"full": "full payload", "ref": "reference payload", "omit": "omit payload"}
        raw_state = state([item(key, value) for key, value in payloads.items()])
        provider = ctx.FixtureContextReflexProvider(
            {
                "full": answers(0.90, 0.90, 0.20),
                "ref": answers(0.90, 0.10, 0.20),
                "omit": answers(0.10, 0.10, 0.10),
            }
        )
        view, receipt = ctx.materialize_context_view(raw_state, payloads, provider)
        actions = {entry["item_id"]: entry["action"] for entry in receipt["actions"]}
        self.assertEqual(
            actions,
            {"full": "KEEP_FULL", "ref": "KEEP_REF", "omit": "OMIT_REHYDRATABLE"},
        )
        self.assertEqual(receipt["provider"]["status"], "AVAILABLE")
        self.assertEqual(receipt["provider"]["network_request_count"], 0)
        self.assertEqual(receipt["provider"]["items_evaluated"], 3)
        self.assertNotIn("omit", {entry["item_id"] for entry in view["items"]})

    def test_low_margin_abstains_to_keep_ref(self):
        text = "ambiguous candidate"
        provider = ctx.FixtureContextReflexProvider(
            {"candidate": answers(0.61, 0.10, 0.10)}
        )
        _, receipt = ctx.materialize_context_view(
            state([item("candidate", text)]), {"candidate": text}, provider
        )
        decision = receipt["actions"][0]
        self.assertEqual(decision["action"], "KEEP_REF")
        self.assertEqual(decision["decision_source"], "REFLEX_CONSERVATIVE_FALLBACK")
        self.assertTrue(decision["reflex"]["abstained"])

    def test_provider_error_prefers_reference_over_omission(self):
        old = "old result"
        new = "new result"

        class ErrorProvider:
            def evaluate(self, request, questions):
                del questions
                return {
                    "schema_version": ctx.CONTEXT_REFLEX_RESULT_VERSION,
                    "provider": {
                        "kind": "synthetic",
                        "status": "ERROR",
                        "calibration_status": "UNKNOWN",
                        "network_request_count": 0,
                        "error": "synthetic failure",
                    },
                    "question_set_sha256": ctx.question_set_sha256(),
                    "answers": {},
                }

        raw_state = state(
            [item("old", old, superseded_by="new"), item("new", new)]
        )
        _, receipt = ctx.materialize_context_view(
            raw_state, {"old": old, "new": new}, ErrorProvider()
        )
        actions = {entry["item_id"]: entry for entry in receipt["actions"]}
        self.assertEqual(receipt["provider"]["status"], "ERROR")
        self.assertEqual(actions["old"]["action"], "KEEP_REF")
        self.assertEqual(
            actions["old"]["decision_source"], "REFLEX_CONSERVATIVE_FALLBACK"
        )

    def test_protected_items_never_enter_provider_candidate_set(self):
        protected = "binding user constraint"
        candidate = "replayable candidate"
        seen = []

        class RecordingProvider:
            def evaluate(self, request, questions):
                del questions
                seen.extend(x["item_id"] for x in request["candidates"])
                return available_result(request)

        raw_state = state(
            [
                item(
                    "protected",
                    protected,
                    authority={"contains_user_constraint": True},
                ),
                item("candidate", candidate),
            ]
        )
        _, receipt = ctx.materialize_context_view(
            raw_state,
            {"protected": protected, "candidate": candidate},
            RecordingProvider(),
        )
        self.assertEqual(seen, ["candidate"])
        actions = {entry["item_id"]: entry["action"] for entry in receipt["actions"]}
        self.assertEqual(actions["protected"], "PIN")

    def test_batching_respects_max_items_per_request(self):
        count = int(ctx.THRESHOLDS["max_items_per_batch"]) * 2 + 1
        payloads = {f"item-{i}": f"payload-{i}" for i in range(count)}
        calls = []

        class RecordingProvider:
            def evaluate(self, request, questions):
                del questions
                calls.append(len(request["candidates"]))
                return available_result(request)

        _, receipt = ctx.materialize_context_view(
            state([item(key, value) for key, value in payloads.items()]),
            payloads,
            RecordingProvider(),
        )
        self.assertEqual(receipt["provider"]["request_count"], 3)
        self.assertEqual(receipt["provider"]["items_evaluated"], count)
        self.assertTrue(all(x <= int(ctx.THRESHOLDS["max_items_per_batch"]) for x in calls))

    def test_missing_key_makes_no_network_call_and_preserves_status(self):
        called = False

        def transport(*args):
            nonlocal called
            called = True
            raise AssertionError("network must not run without a key")

        text = "candidate"
        provider = jev.JevReflexProvider(api_key="", transport=transport)
        _, receipt = ctx.materialize_context_view(
            state([item("candidate", text)]), {"candidate": text}, provider
        )
        self.assertFalse(called)
        self.assertEqual(receipt["provider"]["status"], "NOT_CONFIGURED")
        self.assertEqual(receipt["provider"]["network_request_count"], 0)
        self.assertEqual(receipt["actions"][0]["action"], "KEEP_REF")
        self.assertEqual(
            receipt["actions"][0]["decision_source"],
            "REFLEX_CONSERVATIVE_FALLBACK",
        )

    def test_api_key_presence_alone_does_not_enable_context_reflex(self):
        text = "candidate"
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "early-access-secret"}):
            _, receipt = ctx.materialize_context_view(
                state([item("candidate", text)]), {"candidate": text}
            )
        self.assertEqual(receipt["provider"]["status"], "DISABLED")
        self.assertEqual(receipt["provider"]["request_count"], 0)
        self.assertEqual(receipt["provider"]["network_request_count"], 0)

    def test_semantic_capsule_is_bounded_and_uses_explicit_state_path(self):
        seen = {"payloads": []}
        text = "parser failure: expected token near closing bracket"

        def transport(base, key, payload, timeout):
            del base, key, timeout
            seen["payloads"].append(payload)
            if any("semantic_capsule" in candidate for candidate in payload["state"]["candidates"]):
                return fake_jev_response(payload)
            result = {}
            for qid in payload["questions"]:
                result[qid] = {"type": "noul", "noul": 0.72 if qid.endswith("_keep_full") else 0.10}
            return {"model": "jev-early-access", "answers": result}

        raw_state = state([item("candidate", text, locator="src/parser.py")])
        raw_state["view"].update(
            {
                "remote_semantic_capsule_allowed": True,
                "semantic_capsule_chars": 24,
            }
        )
        provider = jev.JevReflexProvider(api_key="test-key", transport=transport)
        ctx.materialize_context_view(raw_state, {"candidate": text}, provider)
        self.assertEqual(len(seen["payloads"]), 2)
        candidate = seen["payloads"][1]["state"]["candidates"][0]
        capsule = candidate["semantic_capsule"]
        self.assertLessEqual(capsule["characters"], 24)
        self.assertEqual(capsule["status"], "AVAILABLE")
        self.assertEqual(len(capsule["payload_sha256"]), 64)
        self.assertEqual(len(capsule["excerpt_sha256s"]), len(capsule["exact_excerpts"]))
        for question in seen["payloads"][1]["questions"].values():
            self.assertIn("state.candidates[0]", question["instructions"])

    def test_semantic_capsule_suppresses_secret_like_prefix(self):
        seen = {}
        text = "sk-" + ("A" * 24) + " parser context"

        def transport(base, key, payload, timeout):
            seen["payload"] = payload
            return fake_jev_response(payload)

        raw_state = state([item("candidate", text, locator="src/parser.py")])
        raw_state["view"].update(
            {
                "remote_semantic_capsule_allowed": True,
                "semantic_capsule_chars": 40,
            }
        )
        provider = jev.JevReflexProvider(api_key="test-key", transport=transport)
        ctx.materialize_context_view(raw_state, {"candidate": text}, provider)
        candidate = seen["payload"]["state"]["candidates"][0]
        self.assertNotIn("semantic_capsule", candidate)
        self.assertNotIn(text, json.dumps(seen["payload"]))

    def test_existing_jev_transport_handles_context_reflex(self):
        seen = {}

        def transport(base, key, payload, timeout):
            seen.update(
                {"base": base, "key": key, "payload": payload, "timeout": timeout}
            )
            return fake_jev_response(payload)

        secret_payload = "TOP_SECRET_PAYLOAD_NOT_FOR_REMOTE_PROVIDER"
        raw_item = item(
            "private-local-id",
            secret_payload,
            locator="src/neutral.py",
        )
        provider = jev.JevReflexProvider(
            api_key="test-key",
            transport=transport,
        )
        _, receipt = ctx.materialize_context_view(
            state([raw_item]),
            {"private-local-id": secret_payload},
            provider,
        )
        encoded = json.dumps(seen["payload"])
        self.assertEqual(seen["base"], "https://api.typesafe.ai")
        self.assertEqual(seen["key"], "test-key")
        self.assertNotIn(secret_payload, encoded)
        self.assertNotIn("private-local-id", encoded)
        self.assertIn("candidate_key", encoded)
        self.assertEqual(receipt["provider"]["status"], "AVAILABLE")
        self.assertEqual(receipt["provider"]["network_request_count"], 1)
        self.assertEqual(receipt["provider"]["usage"]["input_tokens"], 211)
        self.assertEqual(receipt["actions"][0]["action"], "KEEP_REF")


if __name__ == "__main__":
    unittest.main()
