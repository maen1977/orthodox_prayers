from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_liturgy_is_stable_top_level_destination():
    main = text('app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java')
    assert 'addNav(R.drawable.ic_nav_liturgy' in main
    assert 'case "liturgy": return new LiturgyHubScreen(this);' in main
    assert 'case "liturgy": return new ReaderScreen(this, "divine_liturgy");' not in main


def test_hub_never_hides_tab_when_appointed_text_is_blocked():
    hub = text('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/LiturgyHubScreen.java')
    assert 'selection.optBoolean("displayable", false)' in hub
    assert 'host.navigate("reader", "divine_liturgy")' in hub
    assert 'no_divine_liturgy' in hub
    assert 'typikon_override_required' in hub
    # Reader action belongs only to the displayable branch.
    assert hub.index('if (displayable)') < hub.index('host.navigate("reader", "divine_liturgy")')


def test_home_liturgy_card_routes_via_day_aware_hub():
    home = text('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java')
    assert 'host.navigate("liturgy", null)' in home


def test_calendar_keeps_blocked_liturgy_visible_but_not_openable():
    screen = text('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java')
    assert 'if ("divine_liturgy".equals(id) && !complete)' in screen
    assert 'button.setEnabled(false);' in screen


def test_release_version_is_561():
    build = text('app/build.gradle.kts')
    assert 'versionCode = 50603' in build
    assert 'versionName = "5.6.3"' in build
