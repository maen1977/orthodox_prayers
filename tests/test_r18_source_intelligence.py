from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from source_connectors import load_registry, normalize_reference, observe_connector


class R18SourceIntelligenceTests(unittest.TestCase):
    def test_registry_prioritizes_jordan_and_monitors_three_languages(self):
        policy, connectors = load_registry()
        self.assertEqual("orthodox_jordan", policy["local_authority_source_id"])
        self.assertEqual("jerusalem_patriarchate", policy["calendar_authority_source_id"])
        self.assertGreaterEqual(len(connectors), 9)
        self.assertEqual(1, min(c.authority_tier for c in connectors if c.source_id == "orthodox_jordan"))
        self.assertEqual({"ar", "en", "el"}, {lang for c in connectors for lang in c.languages})
        self.assertTrue(all(c.official and c.url_template.startswith("https://") for c in connectors))

    def test_daily_connectors_extract_matching_references_from_fixtures(self):
        _, connectors = load_registry()
        by_id = {item.id: item for item in connectors}
        target = date(2026, 7, 17)
        for connector_id in ("orthodox_jordan_daily", "goarch_online_chapel_daily", "oca_daily_readings"):
            raw = (ROOT / "tests/fixtures/source_connectors" / f"{connector_id}.html").read_bytes()
            observation = observe_connector(by_id[connector_id], target, raw=raw)
            self.assertEqual("current", observation.status, connector_id)
            self.assertEqual("1 corinthians 7:35-8:7", normalize_reference(observation.epistle_reference))
            self.assertEqual("matthew 15:29-31", normalize_reference(observation.gospel_reference))

    def test_directory_parser_discovers_official_churches(self):
        with tempfile.TemporaryDirectory(prefix="orthodox-r18-") as directory:
            output = Path(directory) / "churches.json"
            # Exercise the parser directly without mutating source data.
            from build_church_directory import parse_live
            raw = (ROOT / "tests/fixtures/source_connectors/orthodox_jordan_churches.html").read_bytes()
            churches = parse_live(raw)
            output.write_text(json.dumps(churches, ensure_ascii=False), encoding="utf-8")
            self.assertGreaterEqual(len(churches), 6)
            self.assertTrue(all(item["official"] and item["url"].startswith("https://orthodoxjordan.org/") for item in churches))

    def test_daily_payload_embeds_health_directory_and_truthful_coverage(self):
        daily = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))
        health = json.loads((ROOT / "data/sources/health/current.json").read_text(encoding="utf-8"))
        directory = json.loads((ROOT / "data/directory/churches.json").read_text(encoding="utf-8"))
        coverage = json.loads((ROOT / "app/src/main/assets/data/service_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(daily["date_iso"], health["date_iso"])
        self.assertGreaterEqual(health["summary"]["connector_count"], 9)
        self.assertGreaterEqual(directory["count"], 5)
        liturgy = next(x for x in coverage["services"] if x["service_id"] == "divine_liturgy")
        self.assertFalse(liturgy["complete"])
        self.assertGreater(len(liturgy["missing_variables"]), 0)

    def test_android_exposes_smart_search_sources_and_church_directory(self):
        search = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/SearchEngine.java").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertIn("scanChurches", search)
        self.assertIn("officialServiceLinks", search)
        self.assertIn("editDistanceAtMostOne", search)
        self.assertIn("metadataLocalized", repository)
        self.assertIn('case "churches"', main)
        self.assertIn('host.navigate("churches", null)', settings)

    def test_workflow_enables_live_monitoring_and_validates_publication(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn('ORTHODOX_ENABLE_LIVE_SOURCE_FETCH: "1"', workflow)
        self.assertGreaterEqual(workflow.count("validate_source_intelligence.py"), 2)
        self.assertIn("canonical/source_connectors.json", workflow)
        self.assertIn('rsync -a --delete "$SOURCE/data/"', workflow)


if __name__ == "__main__":
    unittest.main()
