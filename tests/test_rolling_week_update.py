from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data/rolling-week/candidates/2026-07-28"
LANGUAGES = ("ar", "en", "el")
REQUIRED_SERVICES = {
    "divine_liturgy",
    "vespers",
    "orthros",
    "morning_prayer",
    "evening_prayer",
    "small_compline",
}


class RollingWeekUpdateTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_unsigned_candidate_contains_today_plus_seven_days(self):
        payload = self.load(CANDIDATE / "package.json")
        metadata = payload["rolling_week"]
        self.assertEqual("TODAY_PLUS_SEVEN_COMPLETE_DAYS", metadata["policy"])
        self.assertEqual("2026-07-28", metadata["start_date"])
        self.assertEqual("2026-08-04", metadata["end_date"])
        self.assertEqual(8, metadata["day_count"])
        self.assertEqual("COMPLETE", metadata["status"])
        self.assertTrue(metadata["fail_closed"])

        days = [payload, *payload["weekly_days"]]
        self.assertEqual(8, len(days))
        start = date(2026, 7, 28)
        for offset, day_payload in enumerate(days):
            self.assertEqual((start + timedelta(days=offset)).isoformat(), day_payload["date_iso"])
            self.assertEqual("FULL", day_payload["publication"]["daily_availability"])
            services = {item["id"] for item in day_payload["services"]}
            self.assertTrue(REQUIRED_SERVICES.issubset(services))
            readings = {item["kind"]: item for item in day_payload["readings"]}
            for kind in ("epistle", "gospel"):
                for language in LANGUAGES:
                    self.assertTrue(readings[kind]["body"][language].strip())

    def test_candidate_and_each_native_lane_pass_the_fail_closed_validator(self):
        subprocess.run(
            [
                sys.executable,
                "scripts/validate_rolling_week.py",
                "data/rolling-week/candidates/2026-07-28/package.json",
                "--expected-start",
                "2026-07-28",
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for language in LANGUAGES:
            subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_rolling_week.py",
                    f"data/rolling-week/candidates/2026-07-28/lanes/{language}.json",
                    "--expected-start",
                    "2026-07-28",
                    "--language",
                    language,
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )

    def test_unsigned_candidate_does_not_replace_the_last_trusted_release(self):
        trusted = ROOT / "data/calendar/today.json"
        trusted_signature = ROOT / "data/calendar/today.json.sig"
        embedded = ROOT / "app/src/main/assets/data/today.json"
        embedded_signature = ROOT / "app/src/main/assets/data/today.json.sig"
        self.assertEqual("2026-07-26", self.load(trusted)["date_iso"])
        self.assertEqual(trusted.read_bytes(), embedded.read_bytes())
        self.assertEqual(trusted_signature.read_bytes(), embedded_signature.read_bytes())
        self.assertNotEqual(trusted.read_bytes(), (CANDIDATE / "package.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
