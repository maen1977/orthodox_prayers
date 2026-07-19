from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class JordanLiturgicalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.integrity = load_module("orthodox_integrity_jordan_contract_test", "scripts/orthodox_integrity.py")
        cls.validator = load_module("jordan_contract_validator_test", "scripts/validate_jordan_liturgical_contract.py")
        cls.policy = json.loads((ROOT / "canonical/source_policy.json").read_text(encoding="utf-8"))
        cls.today = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))

    def test_jordan_pinned_calendar_wins_for_2026_07_19_offline(self):
        resolution, evidence = self.integrity.resolve_official_date(date(2026, 7, 19), self.policy, allow_network=False)
        self.assertEqual("PUBLISH", resolution.decision)
        self.assertEqual("orthodox_jordan", resolution.selected_source)
        self.assertEqual("Romans 15:1-7", resolution.fields["epistle_reference"])
        self.assertEqual("Matthew 9:27-35", resolution.fields["gospel_reference"])
        jordan = next(item for item in evidence if item.id == "orthodox_jordan")
        self.assertEqual("current", jordan.status)

    def test_validator_rejects_wrong_jordan_readings(self):
        payload = copy.deepcopy(self.today)
        payload["date_iso"] = "2026-07-19"
        payload.setdefault("publication", {})["selected_source"] = "orthodox_jordan"
        payload["publication"]["jurisdiction_lock"] = "ORTHODOX_JORDAN_FAIL_CLOSED"
        errors = self.validator.validate_payload(payload, expected_date="2026-07-19", require_record=True, require_authority=False, require_complete_liturgy=False)
        rendered = "\n".join(errors)
        self.assertIn("expected ROM.15.1-7", rendered)
        self.assertIn("expected MAT.9.27-35", rendered)

    def test_validator_accepts_exact_jordan_pair_and_liturgy_overlay(self):
        ep_body = "verified Romans body"
        go_body = "verified Matthew body"
        payload = {
            "date_iso": "2026-07-19",
            "publication": {
                "selected_source": "orthodox_jordan",
                "jurisdiction_lock": "ORTHODOX_JORDAN_FAIL_CLOSED",
            },
            "source_evidence": [{
                "id": "orthodox_jordan", "status": "current", "date_iso": "2026-07-19"
            }],
            "readings": [
                {"kind": "epistle", "integrity": {"canonical_reference": "ROM.15.1-7"}, "body": {"en": ep_body}},
                {"kind": "gospel", "integrity": {"canonical_reference": "MAT.9.27-35"}, "body": {"en": go_body}},
            ],
            "services": [{
                "id": "divine_liturgy",
                "dynamic_date": "2026-07-19",
                "daily_reading_contract": {
                    "authority": "orthodox_jordan", "date_iso": "2026-07-19",
                    "epistle_canonical": "ROM.15.1-7", "gospel_canonical": "MAT.9.27-35",
                },
                "segment_replacements": {
                    "[البروكيمنن]": {"ar": "نص موثق"},
                    "[فصل من رسالة اليوم]": {"en": "Romans 15:1-7\n" + ep_body},
                    "[فصل الإنجيل المعيّن لهذا اليوم]": {"en": "Matthew 9:27-35\n" + go_body},
                    "[طروبارية اليوم]": {"ar": "قطعة اليوم"},
                    "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]": {"ar": "قطعة الكنيسة"},
                    "[القنداق]": {"ar": "القنداق"},
                    "[آية المناولة]": {"ar": "آية المناولة"},
                },
                "inline_replacements": {"[اسم الإنجيلي]": {"ar": "متى البشير"}},
            }],
        }
        errors = self.validator.validate_payload(
            payload, expected_date="2026-07-19", require_record=True,
            require_authority=True, require_complete_liturgy=True
        )
        self.assertEqual([], errors)

    def test_android_blocks_stale_readings_and_daily_liturgy_overlay(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        readings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReadingsScreen.java").read_text(encoding="utf-8")
        self.assertIn("public JSONArray currentReadings()", repository)
        self.assertIn("if (!isTodayCurrent()) return new JSONArray();", repository)
        self.assertIn("JSONObject dynamic = isTodayCurrent()", repository)
        search = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/SearchEngine.java").read_text(encoding="utf-8")
        self.assertIn("if (!data.isTodayCurrent())", readings)
        self.assertIn("حُجبت قراءات النسخة القديمة", readings)
        self.assertIn("if (repository.isTodayCurrent())", search)
        self.assertNotIn('scan(repository.today().optJSONArray("services"), repository, needle, bestById);\n        scan(repository.library()', search)

    def test_update_workflow_requires_jordan_contract_and_complete_liturgy(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("validate_jordan_liturgical_contract.py", workflow)
        self.assertIn("--require-jordan-authority --require-complete-liturgy", workflow)

    def test_manual_update_path_cannot_bypass_jordan_gate(self):
        update = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        generator = (ROOT / "scripts/update_liturgical_data.py").read_text(encoding="utf-8")
        validator_pos = update.index('"scripts/validate_jordan_liturgical_contract.py"')
        asset_copy_pos = update.index('shutil.copy2(ROOT / "data/calendar/today.json", asset)')
        signing_pos = update.index('run("scripts/sign_daily_data.py"')
        self.assertLess(validator_pos, asset_copy_pos)
        self.assertLess(validator_pos, signing_pos)
        self.assertIn('"--require-jordan-authority"', update)
        self.assertIn('"--require-complete-liturgy"', update)
        self.assertNotIn("ASSET_TODAY.write_text", generator)
        self.assertIn("untrusted candidate", generator)


if __name__ == "__main__":
    unittest.main()
