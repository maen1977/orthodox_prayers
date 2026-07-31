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

    def test_current_pipeline_verifies_r32_home_contract_not_retired_palette_marker(self):
        update = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        self.assertIn('str(home_path.relative_to(ROOT)): "R32_OWNER_UI_REFINEMENT"', update)
        self.assertNotIn('str(home_path.relative_to(ROOT)): "R15_THEME_PALETTE_IMPORT"', update)


if __name__ == "__main__":
    unittest.main()
