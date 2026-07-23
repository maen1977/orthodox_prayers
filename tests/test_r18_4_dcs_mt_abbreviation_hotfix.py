from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class DcsMtAbbreviationHotfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.integrity = load_module("r184_integrity", "scripts/orthodox_integrity.py")
        cls.connectors = load_module("r184_connectors", "scripts/source_connectors.py")
        cls.policy = cls.integrity.load_json(ROOT / "canonical/source_policy.json")

    @staticmethod
    def actual_dcs_sample() -> bytes:
        return b"""
        <html><body>
        <div>2026</div><div>On Tuesday | July 21</div>
        <div>The Readings from the Regular Cycle</div>
        <div>The Epistle</div><div>Tuesday of the 8th Week</div>
        <div>1 Cor. 10:5 - 12</div>
        <div>The Gospel</div><div>Tuesday of the 8th Week of Matthew</div>
        <div>Mt. 16:6 - 12</div>
        </body></html>
        """

    def test_integrity_parser_accepts_actual_dcs_mt_abbreviation(self):
        text = self.integrity.html_to_text(self.actual_dcs_sample())
        self.assertEqual(
            "1 Corinthians 10:5-12",
            self.integrity._dcs_reference_after_heading(text, "The Epistle"),
        )
        self.assertEqual(
            "Matthew 16:6-12",
            self.integrity._dcs_reference_after_heading(text, "The Gospel"),
        )

    def test_regular_cycle_fetch_becomes_publishable_for_actual_page(self):
        cfg = self.policy["sources"]["official_greek_orthodox"]
        with patch.object(self.integrity, "http_get", return_value=(self.actual_dcs_sample(), {})):
            result = self.integrity.fetch_goarch_regular_cycle(date(2026, 7, 21), cfg)
        self.assertEqual("current", result.status)
        self.assertEqual("1 Corinthians 10:5-12", result.epistle)
        self.assertEqual("Matthew 16:6-12", result.gospel)

    def test_resolver_selects_dcs_when_higher_jordan_sources_are_unavailable(self):
        unavailable_jordan = self.integrity.SourceResult(
            "orthodox_jordan", "official_local_primary", "https://orthodoxjordan.org/",
            "unavailable", "2026-07-21", note="network unavailable",
        )
        unavailable_antioch = self.integrity.OfficialEvidence(
            "antioch_patriarchate", 3, True, "https://www.antiochpatriarchate.org/",
            "unavailable", "2026-07-21", reason="network unavailable",
        )
        dcs = self.integrity.SourceResult(
            "official_greek_orthodox", "official_byzantine_regular_cycle_machine_gate",
            "https://digitalchantstand.goarch.org/goa/dcs/h/s/2026/07/21/h91/en/index.html",
            "current", "2026-07-21", "1 Corinthians 10:5-12", "Matthew 16:6-12",
        )
        with patch.object(self.integrity, "fetch_orthodox_jordan", return_value=unavailable_jordan), \
             patch.object(self.integrity, "fetch_antioch_guide", return_value=unavailable_antioch), \
             patch.object(self.integrity, "fetch_goarch_regular_cycle", return_value=dcs):
            resolution, evidence = self.integrity.resolve_official_date(
                date(2026, 7, 21), self.policy, allow_network=True
            )
        self.assertEqual("PUBLISH", resolution.decision)
        self.assertEqual("official_greek_orthodox", resolution.selected_source)
        self.assertEqual("1 Corinthians 10:5-12", resolution.fields["epistle_reference"])
        self.assertEqual("Matthew 16:6-12", resolution.fields["gospel_reference"])
        selected = next(item for item in evidence if item.id == "official_greek_orthodox")
        self.assertEqual("current", selected.status)

    def test_cross_chapter_dcs_reference_remains_parseable(self):
        sample = """
        The Readings from the Regular Cycle
        The Epistle
        Thursday of the 8th Week
        1 Cor. 10:28 - 33; 11:1 - 8
        The Gospel
        Mt. 16:24 - 28
        """
        epistle = self.integrity._dcs_reference_after_heading(sample, "The Epistle")
        self.assertEqual("1 Corinthians 10:28-33; 11:1-8", epistle)
        self.assertEqual(
            "1CO.10.28-33;1CO.11.1-8",
            self.integrity.parse_reference(epistle)[0],
        )
        self.assertEqual(
            "1 Corinthians 10:28-33; 11:1-8",
            self.connectors.dcs_reference_after_heading(sample, "The Epistle"),
        )

    def test_compound_canonical_validation_is_ordered_and_single_book(self):
        self.assertTrue(
            self.integrity.canonical_reference_is_valid(
                "1CO.10.28-33;1CO.11.1-8"
            )
        )
        self.assertFalse(
            self.integrity.canonical_reference_is_valid(
                "1CO.10.28-33;MAT.11.1-8"
            )
        )
        self.assertFalse(
            self.integrity.canonical_reference_is_valid(
                "1CO.11.1-8;1CO.10.28-33"
            )
        )

    def test_source_health_extracts_same_dcs_references(self):
        text = self.connectors.parse_html(
            self.actual_dcs_sample(),
            "https://digitalchantstand.goarch.org/goa/dcs/h/s/2026/07/21/h91/en/index.html",
        ).text
        self.assertEqual(
            "1 Corinthians 10:5-12",
            self.connectors.dcs_reference_after_heading(text, "The Epistle"),
        )
        self.assertEqual(
            "Matthew 16:6-12",
            self.connectors.dcs_reference_after_heading(text, "The Gospel"),
        )

    def test_integrity_reuses_fresh_hashed_dcs_health_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data/sources/health/current.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "date_iso": "2026-07-21",
                "observations": [{
                    "connector_id": "goarch_digital_chant_stand",
                    "official": True,
                    "status": "current",
                    "target_date": "2026-07-21",
                    "detected_date": "2026-07-21",
                    "epistle_reference": "1 Corinthians 10:5-12",
                    "gospel_reference": "Matthew 16:6-12",
                    "service_links": [{
                        "url": "https://digitalchantstand.goarch.org/goa/dcs/h/s/2026/07/21/h91/en/index.html",
                        "status": "available",
                        "content_sha256": "a" * 64,
                    }],
                }],
            }), encoding="utf-8")
            with patch.object(self.integrity, "ROOT", root):
                evidence = self.integrity._monitored_dcs_regular_cycle_evidence(
                    date(2026, 7, 21), self.policy
                )
        self.assertIsNotNone(evidence)
        self.assertEqual("current", evidence.status)
        self.assertEqual("official_greek_orthodox", evidence.id)
        self.assertEqual("1 Corinthians 10:5-12", evidence.epistle_reference)
        self.assertEqual("Matthew 16:6-12", evidence.gospel_reference)
        self.assertEqual("a" * 64, evidence.sha256)

    def test_integrity_rejects_unhashed_dcs_health_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data/sources/health/current.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "date_iso": "2026-07-21",
                "observations": [{
                    "connector_id": "goarch_digital_chant_stand",
                    "official": True,
                    "status": "current",
                    "target_date": "2026-07-21",
                    "detected_date": "2026-07-21",
                    "epistle_reference": "1 Corinthians 10:5-12",
                    "gospel_reference": "Matthew 16:6-12",
                    "service_links": [{
                        "url": "https://digitalchantstand.goarch.org/goa/dcs/h/s/2026/07/21/h91/en/index.html",
                        "status": "available",
                    }],
                }],
            }), encoding="utf-8")
            with patch.object(self.integrity, "ROOT", root):
                evidence = self.integrity._monitored_dcs_regular_cycle_evidence(
                    date(2026, 7, 21), self.policy
                )
        self.assertIsNone(evidence)

    def test_source_health_probe_attaches_regular_cycle_pair(self):
        _, definitions = self.connectors.load_registry()
        definition = next(item for item in definitions if item.id == "goarch_digital_chant_stand")
        observation = self.connectors.parse_dcs_probe(
            definition,
            date(2026, 7, 21),
            definition.url_for(date(2026, 7, 21)),
            200,
            b"<html><body>Digital Chant Stand daily services</body></html>",
        )

        def fake_fetch(url: str, timeout_seconds: int, max_bytes: int):
            if "/h91/" in url:
                return 200, self.actual_dcs_sample(), url
            return 200, b"<html><body>Official dated service page is available.</body></html>", url

        with patch.object(self.connectors, "safe_fetch", side_effect=fake_fetch):
            updated = self.connectors.probe_service_links(observation, definition)
        self.assertEqual("current", updated.status)
        self.assertEqual("1 Corinthians 10:5-12", updated.epistle_reference)
        self.assertEqual("Matthew 16:6-12", updated.gospel_reference)

    def test_pipeline_patch_level_is_r18_4(self):
        update = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        self.assertIn('PIPELINE_PATCH_LEVEL = "R18.4"', update)


if __name__ == "__main__":
    unittest.main()
