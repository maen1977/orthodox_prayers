from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status = 200

    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class DailyPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_module(
            "update_liturgical_data_test", "scripts/update_liturgical_data.py"
        )
        cls.integrity = load_module(
            "orthodox_integrity_test", "scripts/orthodox_integrity.py"
        )
        cls.schedule = load_module(
            "validate_liturgical_schedule_test", "scripts/validate_liturgical_schedule.py"
        )

    def test_orthocal_julian_endpoint_receives_civil_date(self):
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            seen_urls.append(request.full_url)
            return FakeResponse({"readings": []})

        with patch.object(self.update.urllib.request, "urlopen", fake_urlopen):
            result = self.update.fetch_orthocal_old(date(2026, 7, 10), attempts=1)

        self.assertEqual(result, {"readings": []})
        self.assertEqual(
            seen_urls,
            ["https://orthocal.info/api/julian/2026/7/10/"],
        )

    def test_scripture_reference_parser_supports_cross_chapter_ranges(self):
        canonical, spans = self.integrity.parse_reference(
            "2 Corinthians 11:21-12:9"
        )
        self.assertEqual(canonical, "2CO.11.21-12.9")
        self.assertEqual(spans[0].chapter, 11)
        self.assertEqual(spans[0].final_chapter, 12)
        self.assertEqual(spans[0].start, 21)
        self.assertEqual(spans[0].end, 9)

        canonical, spans = self.integrity.parse_reference(
            "St. Paul's First Letter to the Corinthians 4:5-8"
        )
        self.assertEqual(canonical, "1CO.4.5-8")
        self.assertEqual(self.integrity.reference_display_ar(spans), "كورنثوس الأولى 4:5-8")

    def test_exact_verse_extraction_uses_only_canonical_bible(self):
        bible = {
            "books": {
                "MAT": {
                    "chapters": {
                        "5": {"3": "طوبى للمساكين بالروح", "4": "طوبى للحزانى"}
                    }
                }
            }
        }
        _, spans = self.integrity.parse_reference("Matthew 5:3-4")
        body, evidence = self.integrity.extract_verses(bible, spans)
        self.assertEqual(body, "5:3 طوبى للمساكين بالروح\n5:4 طوبى للحزانى")
        self.assertEqual([(v["chapter"], v["verse"]) for v in evidence], [(5, 3), (5, 4)])

    def test_orthodox_jordan_current_page_is_parsed(self):
        sample = """
        <html><body>
        <div>التاريخ غربي 10 تموز 2026</div>
        <h2>رسالة اليوم</h2><p>1 كورنثوس 4:5-8</p>
        <h2>إنجيل اليوم</h2><p>متى 13:44-54</p>
        </body></html>
        """.encode("utf-8")
        cfg = {"url": "https://example.test/jordan", "role": "official"}
        with patch.object(
            self.integrity, "http_get", lambda url: (sample, {})
        ):
            result = self.integrity.fetch_orthodox_jordan(date(2026, 7, 10), cfg)
        self.assertEqual(result.status, "current")
        self.assertEqual(result.epistle, "1 كورنثوس 4:5-8")
        self.assertEqual(result.gospel, "متى 13:44-54")

    def test_pinned_jerusalem_fixed_feast_rule_is_enforced(self):
        data = {
            "julian_date": {"month": 6, "day": 29},
            "feast": {
                "ar": "عيد هامتي الرسل القديسين بطرس وبولس"
            },
        }
        errors, status = self.integrity.verify_jerusalem_fixed_feast(data)
        self.assertEqual(errors, [])
        self.assertEqual(status, "verified")

        data["feast"]["ar"] = "اسم مختلف"
        errors, status = self.integrity.verify_jerusalem_fixed_feast(data)
        self.assertEqual(status, "conflict")
        self.assertEqual(len(errors), 1)

    def test_goarch_page_is_advisory_and_parsed_by_date(self):
        sample = """
        <html><body>
        <div>10 Friday, July 10, 2026</div>
        <div>Fast Day (Wine and Oil Allowed) | Wine and oil are allowed.</div>
        <div>Epistle Reading - St. Paul's First Letter to the Corinthians 4:5-8</div>
        <div>Gospel Reading - Matthew 13:44-54</div>
        <div>11 Saturday, July 11, 2026</div>
        </body></html>
        """.encode("utf-8")
        cfg = {
            "url_template": "https://example.test?month={month}&year={year}",
            "role": "advisory",
        }
        with patch.object(
            self.integrity, "http_get", lambda url: (sample, {})
        ):
            result = self.integrity.fetch_goarch(date(2026, 7, 10), cfg)
        self.assertEqual(result.status, "current")
        self.assertEqual(
            self.integrity.parse_reference(result.epistle)[0], "1CO.4.5-8"
        )
        self.assertEqual(
            self.integrity.parse_reference(result.gospel)[0], "MAT.13.44-54"
        )
        self.assertEqual(result.fasting_code, "wine_oil")

    def test_all_date_sensitive_services_are_generated(self):
        target = date(2026, 7, 10)
        def fake_daily_source(day, attempts=4):
            return {
                "readings": [
                    {"display": "Romans 1.1-3", "text": "Epistle source text"},
                    {"display": "Matthew 1.1-5", "text": "Gospel source text"},
                ]
            }

        with patch.object(
            self.update,
            "fetch_orthocal_old",
            fake_daily_source,
        ):
            data = self.update.build_day(target)

        service_map = {service["id"]: service for service in data["services"]}
        expected = {
            "divine_liturgy",
            "vespers",
            "orthros",
            "morning_prayer",
            "evening_prayer",
            "small_compline",
            "next_sunday_full_liturgy",
        }
        self.assertEqual(set(service_map), expected)
        for service_id in expected - {"next_sunday_full_liturgy"}:
            self.assertEqual(service_map[service_id]["dynamic_date"], "2026-07-10")

        for service_id in {
            "vespers",
            "orthros",
            "morning_prayer",
            "evening_prayer",
            "small_compline",
        }:
            self.assertEqual(service_map[service_id]["extends_service_id"], service_id)
            self.assertLess(len(service_map[service_id]["segments"]), 20)
            rendered = json.dumps(service_map[service_id], ensure_ascii=False)
            self.assertIn("ملحق اليوم الكنسي", rendered)
            self.assertIn("حالة قطع اليوم", rendered)
            self.assertIn(data["feast"]["ar"], rendered)
            self.assertIn(data["fast"]["ar"], rendered)

        self.assertEqual(data["recommended_services"][0], "divine_liturgy")
        self.assertEqual(
            data["integrity_inputs"]["next_sunday"]["date_iso"], "2026-07-12"
        )
        self.assertIsInstance(
            data["integrity_inputs"]["next_sunday"]["readings"], list
        )
        self.assertEqual(len(data["upcoming"]), 7)
        self.assertEqual(data["next_sunday"]["date_iso"], "2026-07-12")
        self.assertEqual(
            data["next_sunday"]["fasting"],
            next(item for item in data["upcoming"] if item["date"] == "2026-07-12")["fasting"],
        )
        for item in data["upcoming"]:
            self.assertIn(item["fasting"]["code"], {"fast_free", "dairy_allowed", "fish_allowed", "wine_oil", "strict"})
            self.assertIn("epistle", item["reading_references"])
            self.assertIn("gospel", item["reading_references"])
        self.assertEqual(self.schedule.validate(data), [])

    def test_canonical_injection_clears_unverified_target_language_bodies(self):
        reading = {
            "kind": "gospel",
            "reference": {"ar": "", "en": "Matthew 5:3-4", "el": ""},
            "body": {"ar": "", "en": "Wrong English body", "el": "English in Greek slot"},
        }
        snapshot = {
            "canonical_reference": "MAT.5.3-4",
            "body": "5:3 طُوبَى لِلْمَسَاكِينِ بِالرُّوحِ\n5:4 طُوبَى لِلْحَزَانَى",
            "verses": [],
            "chapter_sources": [],
        }
        with patch.object(self.integrity, "load_verified_scripture_snapshots", lambda: {"MAT.5.3-4": snapshot}), \
             patch.object(self.integrity, "scripture_snapshot_body", lambda item: (item["body"], [], [])), \
             patch.object(self.integrity, "diacritic_metrics", lambda text: {"diacritic_ratio": 0.5, "arabic_letters": 10, "diacritics": 5}):
            result = self.integrity.inject_canonical_readings(
                [reading],
                {},
                {
                    "id": "test",
                    "name_ar": "test",
                    "pinned_revision": "test",
                    "file_sha256": "x",
                    "vocalized_source": {"requirements": {"minimum_arabic_diacritic_ratio": 0.18}},
                },
                allow_network=False,
            )[0]
        self.assertEqual(result["body"]["en"], "")
        self.assertEqual(result["body"]["el"], "")
        self.assertEqual(
            result["translation_verification"]["en"]["status"],
            "UNAVAILABLE_UNTIL_INDEPENDENT_VERIFICATION",
        )

    def test_next_sunday_is_strictly_future(self):
        self.assertEqual(
            self.update.next_sunday(date(2026, 7, 12)),
            date(2026, 7, 19),
        )

    def test_fasting_profiles_cover_typikon_levels(self):
        pascha = self.update.orthodox_pascha_gregorian(2026)

        bright = self.update.day_info(pascha + self.update.timedelta(days=2))["fasting"]
        self.assertEqual(bright["code"], "fast_free")
        self.assertEqual(bright["display_icons"], ["✅"])

        cheesefare = self.update.day_info(pascha - self.update.timedelta(days=52))["fasting"]
        self.assertEqual(cheesefare["code"], "dairy_allowed")
        self.assertTrue(cheesefare["allowed"]["dairy"])
        self.assertFalse(cheesefare["allowed"]["meat"])

        palm = self.update.day_info(pascha - self.update.timedelta(days=7))["fasting"]
        self.assertEqual(palm["code"], "fish_allowed")
        self.assertTrue(palm["allowed"]["fish"])

        lent_weekday = self.update.day_info(pascha - self.update.timedelta(days=40))["fasting"]
        self.assertEqual(lent_weekday["code"], "strict")

        apostles_start = pascha + self.update.timedelta(days=57)
        apostles_tuesday = self.update.day_info(apostles_start + self.update.timedelta(days=1))["fasting"]
        self.assertEqual(apostles_tuesday["code"], "wine_oil")
        apostles_saturday = self.update.day_info(apostles_start + self.update.timedelta(days=5))["fasting"]
        self.assertEqual(apostles_saturday["code"], "fish_allowed")

        transfiguration = self.update.julian_to_gregorian_date(2026, 8, 6)
        dormition_feast = self.update.day_info(transfiguration)["fasting"]
        self.assertEqual(dormition_feast["code"], "fish_allowed")

        entry = self.update.julian_to_gregorian_date(2026, 11, 21)
        nativity_feast = self.update.day_info(entry)["fasting"]
        self.assertEqual(nativity_feast["code"], "fish_allowed")

    def test_home_services_remain_generated_but_can_be_hidden(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        prayers = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/PrayerHubScreen.java").read_text(encoding="utf-8")
        generator = (ROOT / "scripts/update_liturgical_data.py").read_text(encoding="utf-8")
        self.assertNotIn("addRecommendedServices", home)
        self.assertIn('addCategory(page, "daily"', prayers)
        self.assertIn('addCategory(page, "basic"', prayers)
        for service_id in ("vespers", "orthros", "morning_prayer", "evening_prayer", "small_compline"):
            self.assertIn(f'"{service_id}"', generator)


if __name__ == "__main__":
    unittest.main()
