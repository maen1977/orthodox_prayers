from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FollowAlongLiturgyTests(unittest.TestCase):
    def test_focused_contract_and_assets_validate(self):
        subprocess.run(
            [sys.executable, "scripts/validate_follow_along_liturgy.py"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    def test_contract_forbids_book_downloads_and_cross_language_fallback(self):
        contract = json.loads(
            (ROOT / "canonical/follow_along_liturgy_contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(
            contract["product_scope"]["download_full_religious_book_libraries"]
        )
        self.assertEqual(
            ["00:03"],
            contract["update_policy"]["windows"],
        )
        self.assertFalse(
            contract["religious_text_rules"]["translation_between_lanes"]
        )
        self.assertFalse(
            contract["religious_text_rules"]["cross_language_fallback"]
        )

    def test_android_regression_guard_test_handles_checked_json_exceptions(self):
        source = (
            ROOT
            / "app/src/test/java/com/orthodoxprayers/privateapp/data/"
            "DailySnapshotRegressionGuardTest.java"
        ).read_text(encoding="utf-8")
        self.assertIn("import org.json.JSONException;", source)
        for method in (
            "acceptsASecondWindowThatAddsMatinsGospel() throws JSONException",
            "rejectsASecondWindowThatDropsAcceptedReadingText() throws JSONException",
            "doesNotCompareDifferentDates() throws JSONException",
            "day(JSONObject... readings) throws JSONException",
            "localized(String value) throws JSONException",
        ):
            self.assertIn(method, source)


if __name__ == "__main__":
    unittest.main()
