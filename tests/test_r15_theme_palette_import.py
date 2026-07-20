from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R15ThemePaletteImportTests(unittest.TestCase):
    def test_home_screen_imports_theme_palette_used_by_sunday_card(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        self.assertIn("import com.orthodoxprayers.privateapp.ui.ThemePalette;", source)
        self.assertIn("ThemePalette.NAVY", source)
        self.assertIn("ThemePalette.GOLD", source)
        self.assertLess(
            source.index("import com.orthodoxprayers.privateapp.ui.ThemePalette;"),
            source.index("public final class HomeScreen"),
        )

    def test_r15_verifier_tracks_compile_fix(self):
        verifier = (ROOT / "scripts/verify_r15_patch.py").read_text(encoding="utf-8")
        self.assertIn("PATCH_R15_OK", verifier)
        self.assertIn("R15_THEME_PALETTE_IMPORT", verifier)


if __name__ == "__main__":
    unittest.main()
