from __future__ import annotations

import hashlib
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

    def test_current_state_matches_contract_and_source_template(self):
        self.assertEqual(45, len(self.contract["current_exact_lanes"]) + len(self.contract["required_new_source_lanes"]))
        self.assertEqual(set(self.contract["required_new_source_lanes"]), set(self.template["entries"]))
        self.assertEqual(len(self.contract["required_new_source_lanes"]), self.template["required_entry_count"])
        self.assertTrue(all(entry["permission_confirmed"] is False for entry in self.template["entries"].values()))


    def test_inventory_without_private_sources_never_modifies_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.prepare.run(root / "sources", root / "output")
            self.assertEqual("SOURCE_BUNDLE_INCOMPLETE_FAIL_CLOSED", report["status"])
            self.assertEqual(len(self.contract["current_exact_lanes"]), report["resolved_lanes"])
            self.assertEqual(len(self.contract["required_new_source_lanes"]), len(report["missing_lanes"]))
            self.assertFalse(report["runtime_modified"])
            self.assertEqual([], list((root / "output/candidates").rglob("*.json")))

    def test_clean_structured_source_builds_candidate_and_review_packet(self):
        lane_key = "midnight_office:en"
        lane = self.contract["lanes"][lane_key]
        paragraph = (
            "Midnight Office. Behold, the Bridegroom comes at midnight, and blessed is the servant "
            "whom He shall find watching. Have mercy on me, O God, according to Your great mercy; "
            "cleanse me, awaken my soul, and guide me in the path of repentance and unceasing prayer."
        )
        paragraphs = [f"{paragraph} Paragraph {index}. {paragraph}" for index in range(1, 61)]
        raw = "\n\n".join(paragraphs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            service_dir = sources / "midnight_office"
            service_dir.mkdir(parents=True)
            source_file = service_dir / "en.txt"
            source_file.write_text(raw, encoding="utf-8")
            structured = {
                "id": lane["service_id"],
                "category": "daily_office",
                "icon": "⛪",
                "title": {"ar": "", "en": "Midnight Office", "el": ""},
                "summary": {"ar": "", "en": "Complete native source office", "el": ""},
                "segments": [
                    {
                        "type": "text",
                        "speaker": {"ar": "", "en": "Reader", "el": ""},
                        "text": {"ar": "", "en": text, "el": ""},
                        "source_paragraph": index,
                    }
                    for index, text in enumerate(paragraphs, start=1)
                ],
            }
            structured_file = service_dir / "en.service.json"
            structured_file.write_text(json.dumps(structured, ensure_ascii=False), encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "entries": {
                    lane_key: {
                        "file": "midnight_office/en.txt",
                        "normalized_service_file": "midnight_office/en.service.json",
                        "source_id": lane["source_id"],
                        "source_url": "https://digitalchantstand.goarch.org/",
                        "document_title": "Midnight Office",
                        "official_source": True,
                        "permission_confirmed": True,
                        "machine_translation_used": False,
                        "ai_rewriting_or_correction_used": False,
                        "file_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
                    }
                },
            }
            (sources / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = self.prepare.run(sources, root / "output")
            self.assertEqual(1, report["candidates_prepared"])
            candidate = json.loads((root / "output/candidates/midnight_office/en.json").read_text(encoding="utf-8"))
            packet = json.loads((root / "output/review_packets/midnight_office/en.json").read_text(encoding="utf-8"))
            self.assertEqual("STRUCTURED_EXACT_SOURCE_MAPPING", candidate["structure_status"])
            self.assertEqual(60, len(candidate["service"]["segments"]))
            self.assertEqual(60, len(packet["segment_reviews"]))
            self.assertFalse(candidate["publication"]["displayable"])

    def test_atomic_promotion_rejects_any_missing_reviewed_lane(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "reviewed candidate missing"):
                self.promote.load_reviewed(Path(directory), self.contract)

    def test_command_require_complete_exits_nonzero_without_source_bundle(self):
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
            self.assertEqual(2, completed.returncode)
            self.assertIn(f"resolved={len(self.contract['current_exact_lanes'])}/45", completed.stdout)


if __name__ == "__main__":
    unittest.main()
