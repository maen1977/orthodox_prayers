from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R17UpdateReliabilityTests(unittest.TestCase):
    def test_android_uses_local_workmanager_without_network_or_exact_alarm(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        coordinator = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java").read_text(encoding="utf-8")
        worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/DailyUpdateWorker.java").read_text(encoding="utf-8")
        engine = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java").read_text(encoding="utf-8")
        self.assertNotIn("SCHEDULE_EXACT_ALARM", manifest)
        self.assertIn(".update.MidnightUpdateReceiver", manifest)
        self.assertNotIn("AlarmManager", coordinator)
        self.assertIn("LOCAL_REFRESH_HOUR = 0", coordinator)
        self.assertIn("LOCAL_REFRESH_MINUTE = 3", coordinator)
        self.assertIn("LOCAL_SCHEDULE_WORK", coordinator)
        self.assertIn("LEGACY_MORNING_SCHEDULE_WORK", coordinator)
        self.assertIn("LEGACY_EVENING_SCHEDULE_WORK", coordinator)
        self.assertNotIn("NetworkType.CONNECTED", coordinator)
        self.assertNotIn("setRequiredNetworkType", coordinator)
        self.assertNotIn("Result.retry", worker)
        self.assertIn("LocalDailyContentEngine", engine)
        self.assertNotIn("HttpURLConnection", engine)


    def test_signed_manifest_scripts_round_trip_with_a_test_key(self):
        date_iso = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))["date_iso"]
        with tempfile.TemporaryDirectory(prefix="orthodox-r17-") as directory:
            target = Path(directory)
            shutil.copytree(ROOT / "data", target / "data")
            (target / "canonical/signing").mkdir(parents=True)
            shutil.copy2(ROOT / "canonical/update_contract.json", target / "canonical/update_contract.json")
            (target / "scripts").mkdir()
            for name in (
                "build_update_manifest.py",
                "sign_update_manifest.py",
                "verify_update_manifest.py",
            ):
                shutil.copy2(ROOT / "scripts" / name, target / "scripts" / name)

            private_key = target / "test-private.pem"
            public_key = target / "canonical/signing/data_signing_public_key.pub"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [sys.executable, "scripts/build_update_manifest.py", "--date", date_iso, "--revision", "17", "--published-at-utc", f"{date_iso}T00:05:00Z"],
                cwd=target,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [sys.executable, "scripts/sign_update_manifest.py", "--private-key", str(private_key)],
                cwd=target,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [sys.executable, "scripts/verify_update_manifest.py", "--expected-date", date_iso],
                cwd=target,
                check=True,
                stdout=subprocess.DEVNULL,
            )

            manifest = json.loads((target / "data/update-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(17, manifest["revision"])
            self.assertEqual({"ar", "en", "el"}, set(manifest["languages"]))
            self.assertGreater(manifest["languages"]["ar"]["size_bytes"], 1000)

    def test_daily_content_no_longer_depends_on_github_actions(self):
        workflows = ROOT / ".github/workflows"
        self.assertFalse((workflows / "update.yml").exists())
        self.assertEqual({"church-prayers.yml"}, {path.name for path in workflows.glob("*.yml")})
        build = (workflows / "church-prayers.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", build)
        self.assertNotIn("production-data-signing", build)



if __name__ == "__main__":
    unittest.main()
