from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R18CalendarAliasCleanupTests(unittest.TestCase):
    def test_update_pipeline_cleans_stale_calendar_aliases_before_signing(self):
        update = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        cleanup_call = 'run("scripts/clean_legacy_calendar_snapshots.py")'
        self.assertIn(cleanup_call, update)
        self.assertLess(update.index(cleanup_call), update.index("if args.unsigned:"))
        self.assertLess(update.index(cleanup_call), update.index('run("scripts/sign_daily_data.py"'))

    def test_cleanup_removes_old_dated_alias_and_preserves_current_signed_pair(self):
        with tempfile.TemporaryDirectory(prefix="orthodox-calendar-cleanup-") as directory:
            target = Path(directory)
            shutil.copytree(ROOT / "data", target / "data")
            (target / "scripts").mkdir(parents=True)
            for name in ("clean_legacy_calendar_snapshots.py", "validate_publication_consistency.py"):
                shutil.copy2(ROOT / "scripts" / name, target / "scripts" / name)
            (target / "app/src/main/assets/data").mkdir(parents=True)
            shutil.copy2(ROOT / "app/src/main/assets/data/today.json", target / "app/src/main/assets/data/today.json")
            shutil.copy2(ROOT / "app/src/main/assets/data/today.json.sig", target / "app/src/main/assets/data/today.json.sig")

            payload = json.loads((target / "data/calendar/today.json").read_text(encoding="utf-8"))
            current = payload["date_iso"]
            old = "1999-01-01"
            shutil.copy2(target / "data/calendar/today.json", target / f"data/calendar/{old}.json")
            shutil.copy2(target / "data/calendar/today.json.sig", target / f"data/calendar/{old}.json.sig")

            before = subprocess.run(
                [sys.executable, "scripts/validate_publication_consistency.py", "--expected-date", current],
                cwd=target,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(0, before.returncode)
            self.assertIn("unexpected calendar aliases", before.stderr + before.stdout)

            subprocess.run(
                [sys.executable, "scripts/clean_legacy_calendar_snapshots.py"],
                cwd=target,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [sys.executable, "scripts/validate_publication_consistency.py", "--expected-date", current],
                cwd=target,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            self.assertFalse((target / f"data/calendar/{old}.json").exists())
            self.assertFalse((target / f"data/calendar/{old}.json.sig").exists())
            self.assertTrue((target / f"data/calendar/{current}.json").is_file())
            self.assertTrue((target / f"data/calendar/{current}.json.sig").is_file())


if __name__ == "__main__":
    unittest.main()
