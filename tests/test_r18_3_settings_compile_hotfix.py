from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"


def test_settings_screen_uses_distinct_coverage_badge_variables():
    source = SETTINGS.read_text(encoding="utf-8")
    assert source.count("TextView coverage =") == 1
    assert "TextView liturgyCoverageBadge =" in source
    assert "add(page.root, liturgyCoverageBadge, 0, 7);" in source
