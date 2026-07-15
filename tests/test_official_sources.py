from __future__ import annotations

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


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class OfficialSourcePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_module("official_sources_test", "scripts/official_sources.py")
        cls.integrity = load_module("orthodox_integrity_sources_test", "scripts/orthodox_integrity.py")
        cls.policy = json.loads((ROOT / "canonical/source_policy.json").read_text(encoding="utf-8"))
        cls.today = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))

    def test_priority_is_jordan_jerusalem_antioch_greece_then_oca(self):
        self.assertEqual([], self.sources.validate_source_order(self.policy))
        self.assertEqual(
            ["orthodox_jordan", "jerusalem_patriarchate", "antioch_patriarchate", "official_greek_orthodox", "orthodox_church_in_america"],
            self.policy["source_priority"],
        )

    def test_strict_resolver_never_lets_lower_priority_override_valid_jordan(self):
        E = self.sources.SourceEvidence
        result = self.sources.strict_resolve([
            E("official_greek_orthodox", 4, True, "g", "current", epistle_reference="Romans 9:1-5", gospel_reference="Matthew 9:18-26"),
            E("orthodox_jordan", 1, True, "j", "current", epistle_reference="Romans 15:1-7", gospel_reference="Matthew 9:27-35"),
            E("jerusalem_patriarchate", 2, True, "p", "current", epistle_reference="2 Corinthians 11:21-12:9", gospel_reference="Matthew 16:13-19"),
        ])
        self.assertEqual("PUBLISH", result.decision)
        self.assertEqual("orthodox_jordan", result.selected_source)
        self.assertEqual(1, result.selected_priority)

    def test_stale_or_poisoned_jordan_is_rejected(self):
        target = date(2026, 7, 12)
        status, _ = self.sources.validate_source_document(
            source_id="orthodox_jordan", target=target, detected_date=date(2024, 7, 28), text="صفحة قديمة"
        )
        self.assertEqual("stale", status)
        status, _ = self.sources.validate_source_document(
            source_id="orthodox_jordan", target=target, detected_date=target, text="Lorem ipsum"
        )
        self.assertEqual("poisoned", status)

    def test_current_day_uses_old_calendar_fixed_feast_before_sunday_cycle(self):
        resolution, evidence = self.integrity.resolve_official_date(date(2026, 7, 12), self.policy, allow_network=False)
        self.assertEqual("PUBLISH", resolution.decision)
        self.assertEqual("jerusalem_patriarchate", resolution.selected_source)
        self.assertEqual("2 Corinthians 11:21-12:9", resolution.fields["epistle_reference"])
        self.assertEqual("Matthew 16:13-19", resolution.fields["gospel_reference"])
        self.assertTrue(any(item.id == "jerusalem_patriarchate" and item.status == "current" for item in evidence))

    def test_current_weekday_uses_pinned_official_orthodox_fallback(self):
        resolution, evidence = self.integrity.resolve_official_date(date(2026, 7, 14), self.policy, allow_network=False)
        self.assertEqual("PUBLISH", resolution.decision)
        self.assertEqual("orthodox_church_in_america", resolution.selected_source)
        self.assertEqual("1 Corinthians 6:20-7:12", resolution.fields["epistle_reference"])
        self.assertEqual("Matthew 14:1-13", resolution.fields["gospel_reference"])
        self.assertTrue(any(item.id == "orthodox_church_in_america" and item.status == "current" for item in evidence))

    def test_next_sunday_uses_verified_orthodox_cycle_only_after_fixed_feast_check(self):
        resolution, _ = self.integrity.resolve_official_date(date(2026, 7, 19), self.policy, allow_network=False)
        self.assertEqual("PUBLISH", resolution.decision)
        self.assertEqual("official_greek_orthodox", resolution.selected_source)
        self.assertEqual("Romans 15:1-7", resolution.fields["epistle_reference"])
        self.assertEqual("Matthew 9:27-35", resolution.fields["gospel_reference"])

    def test_scripture_is_either_exact_native_source_or_safe_unavailable(self):
        for reading in self.today["readings"]:
            if reading["kind"] not in {"epistle", "gospel"}:
                continue
            self.assertEqual("NATIVE_LANGUAGE_LANES_ENFORCED", reading["integrity"]["status"])
            self.assertTrue(reading["translation_locked"])
            verification = reading["native_source_verification"]
            self.assertEqual({"ar", "en", "el"}, set(verification))
            for language in ("ar", "en", "el"):
                evidence = verification[language]
                self.assertFalse(evidence["ai_translation_used"])
                self.assertFalse(evidence["automatic_diacritization_used"])
                text = reading["body"].get(language, "")
                if text:
                    self.assertIn(evidence["status"], {"VERIFIED_EXACT_NATIVE_SOURCE", "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS", "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS"})
                    self.assertTrue(evidence["text_available"])
                else:
                    self.assertFalse(evidence["text_available"])

    def test_publication_is_automatic_fail_closed_without_ai_or_human_daily_reviewer(self):
        publication = self.today["publication"]
        self.assertEqual("AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED", publication["status"])
        self.assertTrue(publication["fail_closed"])
        self.assertFalse(publication["human_review_required"])
        self.assertFalse(self.today["integrity"]["ai_scripture_translation_used"])
        self.assertFalse(self.today["integrity"]["ai_liturgical_translation_used"])
        self.assertFalse(self.today["automatic_diacritization_used"])
        self.assertEqual("DISABLED_NO_CROSS_LANGUAGE_FALLBACK", self.today["translation_fallback_policy"])


if __name__ == "__main__":
    unittest.main()
