from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R15ThemePaletteImportTests(unittest.TestCase):
    def test_r32_removes_the_duplicate_sunday_card_and_palette_dependency(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        self.assertNotIn("import com.orthodoxprayers.privateapp.ui.ThemePalette;", source)
        self.assertNotIn("ThemePalette.NAVY", source)
        self.assertNotIn("ThemePalette.GOLD", source)
        self.assertNotIn("addNextSunday", source)

    def test_r15_verifier_tracks_compile_fix(self):
        verifier = (ROOT / "scripts/verify_r15_patch.py").read_text(encoding="utf-8")
        self.assertIn("PATCH_R15_OK", verifier)
        self.assertIn("R15_THEME_PALETTE_IMPORT", verifier)


if __name__ == "__main__":
    unittest.main()
