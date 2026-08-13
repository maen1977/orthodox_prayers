from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AllServicesCompletionRoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "canonical/all_services_completion_round.json").read_text(encoding="utf-8"))
        cls.template = json.loads((ROOT / "canonical/all_services_source_bundle.template.json").read_text(encoding="utf-8"))
        cls.prepare = load("all_services_prepare_test", "scripts/prepare_all_services_completion_round.py")
        cls.promote = load("all_services_promote_test", "scripts/promote_all_services_completion_round.py")

    def test_contract_has_exactly_fifteen_services_and_forty_five_lanes(self):
        self.assertEqual(15, len(self.contract["required_services"]))
        self.assertEqual(45, self.contract["total_lanes"])
        expected = {
            f"{service}:{language}"
            for service in self.contract["required_services"]
            for language in ("ar", "en", "el")
        }
        self.assertEqual(expected, set(self.contract["lanes"]))
        self.assertFalse(self.contract["machine_translation_allowed"])
        self.assertFalse(self.contract["automatic_ocr_publication_allowed"])

    def test_all_forty_five_lanes_are_complete_after_authorized_import(self):
        self.assertEqual(45, len(self.contract["current_complete_lanes"]))
        self.assertEqual(38, len(self.contract["current_exact_lanes"]))
        self.assertEqual([], self.contract["required_new_source_lanes"])
        # The acquisition template follows the current incomplete-lane set.
        # R66 has no missing lanes, so it must not advertise obsolete requests.
        self.assertEqual({}, self.template["entries"])
        self.assertEqual(0, self.template["required_entry_count"])
        self.assertEqual("NO_ADDITIONAL_SOURCE_LANES_REQUIRED_R66", self.template["status"])

    def test_inventory_without_private_sources_reports_existing_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.prepare.run(root / "sources", root / "output")
            self.assertEqual("SOURCE_BUNDLE_READY_FOR_REVIEW", report["status"])
            self.assertEqual(45, report["resolved_lanes"])
            self.assertEqual([], report["missing_lanes"])
            self.assertEqual(0, report["candidates_prepared"])
            self.assertFalse(report["runtime_modified"])
            self.assertEqual([], list((root / "output/candidates").rglob("*.json")))

    def test_already_complete_lane_is_not_reimported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir(parents=True)
            (sources / "manifest.json").write_text(
                json.dumps({"schema_version": 1, "entries": {"midnight_office:en": {}}}),
                encoding="utf-8",
            )
            report = self.prepare.run(sources, root / "output")
            self.assertEqual(0, report["candidates_prepared"])
            self.assertEqual(45, report["resolved_lanes"])

    def test_atomic_promotion_has_nothing_to_promote_after_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual({}, self.promote.load_reviewed(Path(directory), self.contract))

    def test_command_require_complete_succeeds_from_recorded_completed_lanes(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/prepare_all_services_completion_round.py",
                    "--source-root",
                    str(Path(directory) / "sources"),
                    "--output-root",
                    str(Path(directory) / "output"),
                    "--require-complete",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertIn("resolved=45/45", completed.stdout)


if __name__ == "__main__":
    unittest.main()
