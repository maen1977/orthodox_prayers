from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class R21Phase8FinalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = load("phase8_packet", "scripts/build_native_liturgy_review_packet.py")
        cls.apply = load("phase8_apply", "scripts/apply_native_liturgy_review_packet.py")
        cls.bilingual = load("phase8_bilingual", "scripts/import_dcs_bilingual_source.py")
        cls.build = load("phase8_build", "scripts/build_android_with_local_gradle.py")
        cls.gate = load("phase8_gate", "scripts/validate_liturgy_phase8_completion.py")
        cls.contract = json.loads((ROOT / "canonical/liturgy_phase8_completion_contract.json").read_text(encoding="utf-8"))

    def sample_candidate(self):
        return {
            "status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
            "service_type": "basil",
            "service_id": "divine_liturgy_basil",
            "language": "en",
            "source": {"source_id": "goarch_digital_chant_stand_english"},
            "ecclesiastical_review": {"status": "PENDING", "candidate_sha256": ""},
            "service": {
                "segments": [
                    {"type": "text", "speaker": {"en": "Priest"}, "text": {"en": "First exact paragraph."}, "source_paragraph": 1},
                    {"type": "text", "speaker": {"en": "People"}, "text": {"en": "Amen."}, "source_paragraph": 2},
                ]
            }
        }

    def test_contract_requires_all_final_release_gates(self):
        gates = self.contract["required_release_gates"]
        self.assertEqual({"native_service_editions", "rolling_liturgical_window", "signed_daily_data", "android_build"}, set(gates))
        self.assertFalse(self.contract["completion_claim"]["current_value"])

    def test_review_packet_hashes_every_segment(self):
        packet = self.packet.build_packet(self.sample_candidate())
        self.assertEqual(2, len(packet["segment_reviews"]))
        self.assertTrue(all(len(item["segment_sha256"]) == 64 for item in packet["segment_reviews"]))
        self.assertTrue(all(item["decision"] == "PENDING" for item in packet["segment_reviews"]))

    def test_review_application_rejects_pending_segments(self):
        candidate = self.sample_candidate()
        packet = self.packet.build_packet(candidate)
        packet.update({"status": "REVIEW_PACKET_COMPLETED", "reviewer": "Reviewer", "reviewed_at": "2026-07-27", "attestation": self.apply.REQUIRED_ATTESTATION})
        with self.assertRaisesRegex(RuntimeError, "not APPROVED"):
            self.apply.validate_and_apply(candidate, packet)

    def test_completed_review_sets_static_candidate_hash(self):
        candidate = self.sample_candidate()
        packet = self.packet.build_packet(candidate)
        packet.update({"status": "REVIEW_PACKET_COMPLETED", "reviewer": "Fr. Reviewer", "reviewed_at": "2026-07-27", "attestation": self.apply.REQUIRED_ATTESTATION})
        for item in packet["segment_reviews"]:
            item["decision"] = "APPROVED"
        reviewed = self.apply.validate_and_apply(candidate, packet)
        self.assertEqual("APPROVED", reviewed["ecclesiastical_review"]["status"])
        self.assertEqual(self.packet.candidate_hash(reviewed), reviewed["ecclesiastical_review"]["candidate_sha256"])

    def test_bilingual_parser_splits_native_lanes_without_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.html"
            path.write_text("<table><tr><td>ΙΕΡΕΥΣ</td><td>PRIEST</td></tr><tr><td>Εὐλογημένη ἡ βασιλεία.</td><td>Blessed is the Kingdom.</td></tr></table>", encoding="utf-8")
            pairs = self.bilingual.parse_pairs(path)
            self.assertEqual(2, len(pairs))
            self.assertIn("ΙΕΡΕΥΣ", pairs[0][0])
            self.assertIn("PRIEST", pairs[0][1])

    def test_bilingual_parser_ignores_wrong_script_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("English only | English again\nΕἰρήνη πᾶσι | Peace be with all\n", encoding="utf-8")
            pairs = self.bilingual.parse_pairs(path)
            self.assertEqual(1, len(pairs))

    def test_local_gradle_distribution_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "gradle.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("gradle-8.13/bin/gradle", "#!/bin/sh\n")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                self.build.verify_distribution(archive, "0" * 64)

    def test_local_gradle_distribution_accepts_verified_zip_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "gradle.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("gradle-8.13/bin/gradle", "#!/bin/sh\n")
            expected = self.build.file_sha256(archive)
            self.build.verify_distribution(archive, expected)

    def test_phase8_gate_reports_real_blockers(self):
        report = self.gate.build_report()
        self.assertFalse(report["complete_release_allowed"])
        self.assertNotIn("native_service_not_displayable:basil", report["blockers"])
        self.assertNotIn("native_service_not_displayable:presanctified", report["blockers"])
        self.assertIn("android_apk_build_evidence_missing", report["blockers"])
        self.assertTrue(report["fail_closed"])

    def test_no_review_candidates_or_packets_ship(self):
        root = ROOT / "data/services/candidates"
        leaked = [p for p in root.rglob("*.json")]
        self.assertEqual([], leaked)


if __name__ == "__main__":
    unittest.main()
