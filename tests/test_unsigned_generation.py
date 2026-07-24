from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class UnsignedGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_module("unsigned_update_test", "scripts/update.py")
        cls.lane = load_module("unsigned_lane_test", "scripts/update_language_lane.py")
        cls.verify_lane = load_module("unsigned_lane_verify_test", "scripts/verify_language_lanes.py")

    def test_daily_unsigned_generation_removes_stale_signatures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = (
                root / "data/calendar/today.json.sig",
                root / "app/src/main/assets/data/today.json.sig",
                root / "data/calendar/2026-07-16.json.sig",
            )
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stale", encoding="utf-8")
            with mock.patch.object(self.update, "ROOT", root):
                self.update.remove_stale_daily_signatures("2026-07-16")
            self.assertTrue(all(not path.exists() for path in paths))

    def test_language_lane_unsigned_mode_removes_stale_signatures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data/calendar/today.json"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                json.dumps(
                    {
                        "schema_version": 9,
                        "date_iso": "2026-07-16",
                        "language_sources": {"en": {}},
                        "services": [{"id": "divine_liturgy"}],
                        "readings": [],
                    }
                ),
                encoding="utf-8",
            )
            dated_sig = root / "data/daily/2026-07-16/en.json.sig"
            current_sig = root / "data/daily/current/en.json.sig"
            for path in (dated_sig, current_sig):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stale", encoding="utf-8")

            argv = [
                "update_language_lane.py",
                "--language",
                "en",
                "--date",
                "2026-07-16",
                "--unsigned",
            ]
            with mock.patch.object(self.lane, "ROOT", root), mock.patch.object(sys, "argv", argv):
                self.lane.main()

            dated = root / "data/daily/2026-07-16/en.json"
            current = root / "data/daily/current/en.json"
            self.assertEqual(dated.read_bytes(), current.read_bytes())
            self.assertFalse(dated_sig.exists())
            self.assertFalse(current_sig.exists())

    def test_language_lane_removes_other_text_and_source_evidence(self):
        source = {
            "title": {"ar": "عنوان", "en": "Title", "el": "Τίτλος"},
            "native_source_verification": {
                "ar": {"source_id": "ar-source"},
                "en": {"source_id": "en-source"},
                "el": {"source_id": "el-source"},
            },
        }
        lane = self.lane.keep_only_language(source, "en")
        self.assertEqual("", lane["title"]["ar"])
        self.assertEqual("Title", lane["title"]["en"])
        self.assertEqual("", lane["title"]["el"])
        self.assertEqual({"en"}, set(lane["native_source_verification"]))
        self.assertEqual(
            "",
            self.verify_lane.isolation_error(lane, "en"),
        )

    def test_unsigned_lane_validation_rejects_stale_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "en.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 9,
                        "lane_schema_version": 2,
                        "date_iso": "2026-07-16",
                        "language": "en",
                        "machine_translation_used": False,
                        "automatic_diacritization_used": False,
                        "services": [{"id": "divine_liturgy"}],
                        "readings": [],
                    }
                ),
                encoding="utf-8",
            )
            Path(str(path) + ".sig").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "stale signature"):
                self.verify_lane.verify_lane(path, "2026-07-16", "en", unsigned=True)

    def test_legacy_multilingual_lane_requires_explicit_migration_flag(self):
        payload = {
            "title": {"ar": "عنوان", "en": "Title", "el": "Τίτλος"},
            "schema_version": 9,
            "lane_schema_version": 2,
            "date_iso": "2026-07-16",
            "language": "en",
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
            "services": [{"id": "divine_liturgy"}],
            "readings": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "en.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "not isolated"):
                self.verify_lane.verify_lane(path, "2026-07-16", "en", unsigned=True)
            self.verify_lane.verify_lane(
                path,
                "2026-07-16",
                "en",
                unsigned=True,
                allow_legacy_multilingual=True,
            )


if __name__ == "__main__":
    unittest.main()
