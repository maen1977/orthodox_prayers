import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
RANGE = re.compile(r"^([1-3]?[A-Z]+)\.(\d+)\.(\d+)-(?:([1-3]?[A-Z]+)\.)?(?:(\d+)\.)?(\d+)$")


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DailyLiturgyAndCalendarReadingsTest(unittest.TestCase):
    def test_liturgy_library_is_available_independently_of_stale_today(self):
        repository = text(
            "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"
        )
        hub = text(
            "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/LiturgyHubScreen.java"
        )
        self.assertIn('requestedId.startsWith("library::")', repository)
        self.assertIn('data.findService("library::divine_liturgy")', hub)
        self.assertIn('host.navigate("reader", "library::divine_liturgy")', hub)
        for service_id in (
            "proskomide",
            "orthros",
            "first_hour",
            "third_hour",
            "sixth_hour",
            "ninth_hour",
            "pre_communion_prayers",
            "thanksgiving_after_communion",
        ):
            self.assertIn(f'"{service_id}"', hub)

    def test_stale_daily_package_rebuild_starts_at_launch(self):
        activity = text(
            "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java"
        )
        marker = "if (!repository.hasUsableCurrentData())"
        self.assertIn(marker, activity)
        launch_block = activity[activity.index(marker): activity.index(marker) + 300]
        self.assertIn("requestDataRefresh(false, true, true);", launch_block)

    def test_daily_readings_are_injected_into_liturgy_slots(self):
        engine = text(
            "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java"
        )
        self.assertIn('slots.put(kind, copyObject(body));', engine)
        self.assertIn('service.put("slot_replacements", readingSlots)', engine)
        self.assertIn('"epistle".equals(kind)', engine)
        self.assertIn('"gospel".equals(kind)', engine)

    def test_prayer_of_the_day_rotates_by_jordan_date(self):
        home = text(
            "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
        )
        self.assertIn("DAILY_PRAYER_ROTATION", home)
        self.assertIn("toLocalDate().toEpochDay()", home)
        self.assertIn("Math.floorMod(day, DAILY_PRAYER_ROTATION.length)", home)

    def test_every_calendar_reference_has_native_offline_coverage(self):
        references = set()
        for year in range(2026, 2051):
            payload = json.loads(text(
                f"app/src/main/assets/data/calendar/calendar_{year}.json"
            ))
            for day in payload["days"]:
                for item in (day.get("reading_references") or {}).values():
                    canonical = str(item.get("canonical_reference") or "").strip().upper()
                    if canonical:
                        references.add(canonical)
        self.assertEqual(313, len(references))

        for language in LANGUAGES:
            manifest = json.loads(text(
                f"app/src/main/assets/data/scripture/manifest_{language}.json"
            ))
            verses = json.loads(text(
                f"app/src/main/assets/data/scripture/verses_{language}.json"
            ))
            supported = set(manifest["supported_canonical_references"])
            omissions = set(manifest["allowed_source_verse_omissions"])
            verse_ids = {item["id"] for item in verses}
            self.assertEqual(references, supported)
            self.assertEqual(
                "ALL_EMBEDDED_CALENDAR_REFERENCES_2026_2050",
                manifest["coverage_status"],
            )
            available = verse_ids | omissions
            for reference in references:
                for part in reference.split(";"):
                    match = RANGE.fullmatch(part.strip())
                    self.assertIsNotNone(match, reference)
                    start_book, start_chapter, start_verse, end_book, end_chapter, end_verse = match.groups()
                    end_book = end_book or start_book
                    end_chapter = end_chapter or start_chapter
                    self.assertIn(f"{start_book}.{start_chapter}.{start_verse}", available)
                    self.assertIn(f"{end_book}.{end_chapter}.{end_verse}", available)


if __name__ == "__main__":
    unittest.main()
