from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def resource_value(relative: str, name: str) -> str:
    root = ET.parse(ROOT / relative).getroot()
    for item in root.findall("string"):
        if item.attrib.get("name") == name:
            return "".join(item.itertext()).strip()
    raise AssertionError(f"missing resource {name} in {relative}")


def test_subscreens_use_a_compact_mirrored_arrow_only_back_control() -> None:
    ui = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/UiKit.java")
    reader = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java")
    service_list = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ServiceListScreen.java")

    assert "public TextView backArrow(Runnable backAction)" in ui
    assert 'preferences.isRtl() ? "→" : "←"' in ui
    assert "new LinearLayout.LayoutParams(dp(48), dp(48))" in ui
    assert "ui_return_to_the_previous_screen_adc27814" in ui
    assert "backArrow(backAction)" in ui
    assert "ui.backArrow(host::goBack)" in reader
    assert "page(title, true)" in service_list
    assert "ui_back_18fb18e2" not in reader


def test_home_uses_six_shortcut_cards_and_one_context_aware_fasting_card() -> None:
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    ui = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/UiKit.java")

    assert "R35_HOME_SHORTCUT_CARDS" in home
    assert "public LinearLayout shortcutCard(int iconResource, String title)" in ui
    assert "ui.shortcutCard(iconResource, title)" in home
    assert "ui_prayer_of_the_day" in home
    assert '"readings", null' in home
    assert 'ui_calendar_and_fasting_51a9bf84), "upcoming", null' in home
    assert 'ui_churches_and_live_services_53a37eff), "churches", null' in home
    assert home.count("addShortcutCard(") >= 7  # six calls plus the helper declaration
    assert 'bibleTitle(), "bible", null' in home
    assert 'searchTitle(), "search", null' in home
    assert "addSmartFastingNotice(page.root);" in home
    assert "FastingNoticeEngine.evaluate" in home
    assert 'host.navigate("calendar_day", notice.targetDate.toString())' in home
    assert "specificCommemoration(today)" not in home
    assert "addRollingWeekStatus(page.root);" not in home


def test_prayer_of_the_day_title_is_native_in_all_languages() -> None:
    expected = {
        "app/src/main/res/values/ui_strings.xml": "صلاة اليوم",
        "app/src/main/res/values-en/ui_strings.xml": "Prayer of the day",
        "app/src/main/res/values-el/ui_strings.xml": "Προσευχὴ τῆς ἡμέρας",
    }
    for file_name, value in expected.items():
        assert resource_value(file_name, "ui_prayer_of_the_day") == value
