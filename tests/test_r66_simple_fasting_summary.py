from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_home_fasting_notice_opens_the_simple_summary_route() -> None:
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    activity = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")

    assert 'host.navigate("fasting_summary", notice.targetDate.toString())' in home
    assert 'case "fasting_summary": return new FastingSummaryScreen(this, entry.argument);' in activity


def test_simple_summary_shows_only_fast_type_period_days_and_food_rules() -> None:
    screen = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/FastingSummaryScreen.java")

    assert 'ui_fast_summary_type' in screen
    assert 'ui_fast_summary_period' in screen
    assert 'ui_fast_summary_days' in screen
    assert 'ui_fast_summary_allowed' in screen
    assert 'ui_fast_summary_forbidden' in screen
    assert 'FastingNoticeEngine.evaluate' in screen
    assert 'new CalendarDayScreen' not in screen


def test_calendar_day_route_remains_available_for_full_calendar_details() -> None:
    activity = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    calendar = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java")

    assert 'case "calendar_day": return new CalendarDayScreen(this, entry.argument);' in activity
    assert 'addServiceButtons(card, item);' in calendar
