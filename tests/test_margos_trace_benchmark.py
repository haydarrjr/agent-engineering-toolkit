import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/benchmark_margos_trace.py"
spec = importlib.util.spec_from_file_location("benchmark_margos_trace", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MargosTraceBenchmarkTests(unittest.TestCase):
    def test_frozen_redacted_fixture_passes(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/margos/trace-benchmark-v1.json").read_text(
                encoding="utf-8"
            )
        )
        report = mod.evaluate_corpus(fixture)
        self.assertTrue(report["aggregate"]["pass"])
        self.assertEqual(report["aggregate"]["hard_boundary_violations"], 0)
        self.assertEqual(report["aggregate"]["harmful_omission_cases"], 0)
        self.assertGreater(report["aggregate"]["calibration_observations"], 0)

    def test_secret_scan_rejects_unredacted_input(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/margos/trace-benchmark-v1.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["description"] = "TYPESAFE_API_KEY=do-not-commit"
        report = mod.evaluate_corpus(fixture)
        self.assertFalse(report["aggregate"]["pass"])
        self.assertTrue(report["aggregate"]["secret_pattern_hits"])

    def test_redacted_flag_is_mandatory(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/margos/trace-benchmark-v1.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["redacted"] = False
        with self.assertRaises(ValueError):
            mod.evaluate_corpus(fixture)


if __name__ == "__main__":
    unittest.main()
