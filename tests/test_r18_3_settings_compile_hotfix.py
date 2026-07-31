from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"


def test_settings_screen_hides_technical_coverage_badges():
    source = SETTINGS.read_text(encoding="utf-8")
    assert "TranslationCoverage" not in source
    assert "TextView coverage =" not in source
    assert "liturgyCoverageBadge" not in source
    assert "addLanguageButton" in source
    assert "addReminder" in source
