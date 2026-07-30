from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UiLocalizationTests(unittest.TestCase):
    def test_android_ui_catalogs_are_complete_and_language_isolated(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_ui_localizations.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("direct_java_triples=0", result.stdout)

    def test_manual_language_selection_resolves_android_resources(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/LocalizedResources.java").read_text(encoding="utf-8")
        self.assertIn("createConfigurationContext", source)
        self.assertIn("configuration.setLocale(locale)", source)
        self.assertIn("configuration.setLayoutDirection(locale)", source)


if __name__ == "__main__":
    unittest.main()
