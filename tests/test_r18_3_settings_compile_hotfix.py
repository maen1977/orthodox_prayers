from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"


def test_settings_screen_hides_technical_coverage_badges_without_duplicate_variables():
    source = SETTINGS.read_text(encoding="utf-8")
    assert "TextView coverage =" not in source
    assert "TextView liturgyCoverageBadge =" not in source
    assert "TranslationCoverage" not in source
    assert "ui_current_native_official_text_coverage" not in source
