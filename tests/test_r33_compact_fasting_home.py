from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_large_fasting_table_is_removed_from_home_and_opened_from_icon() -> None:
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    upcoming = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java")
    assert "R33_COMPACT_FASTING_HOME" in home
    assert "private void addUpcoming" not in home
    assert "int dayCount = Math.min(8, upcoming.length());" not in home
    assert "ic_action_calendar" in home
    assert 'ui_calendar_and_fasting_51a9bf84), "upcoming", null' in home
    assert "ui_calendar_and_fasting_51a9bf84" in upcoming
    assert "ui_church_calendar_54dcd19b" in upcoming
    assert 'host.navigate("calendar", null)' in upcoming
