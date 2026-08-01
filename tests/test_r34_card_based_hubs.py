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


def test_prayer_hub_uses_three_navigable_category_cards() -> None:
    hub = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/PrayerHubScreen.java")
    main = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    ui = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/UiKit.java")

    assert hub.count("addCategory(page,") == 3
    assert 'addCategory(page, "daily"' in hub
    assert 'addCategory(page, "basic"' in hub
    assert 'addCategory(page, "communion"' in hub
    assert "ui.actionCard" in hub
    assert 'host.navigate("prayer_category", category)' in hub
    assert 'case "prayer_category"' in main
    assert '"prayer_category".equals(entry.screenId)' in main
    assert "new ServiceListScreen" in main
    assert "actionCard(int iconResource" in ui


def test_settings_are_grouped_into_requested_cards_and_about_is_plain() -> None:
    settings = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java")

    assert "settingsCard(local(com.orthodoxprayers.privateapp.R.string.ui_language_settings_title))" in settings
    assert "settingsCard(local(com.orthodoxprayers.privateapp.R.string.ui_font_size_settings_title))" in settings
    assert "settingsCard(local(com.orthodoxprayers.privateapp.R.string.ui_calendar_and_reminders_acba78af))" in settings
    assert "settingsCard(local(com.orthodoxprayers.privateapp.R.string.ui_update_and_data_bf22bb6d))" in settings
    assert "ui.actionCard(" in settings
    assert "ui_church_directory_and_live_services_b4f52ad3" in settings
    assert "aboutCard" not in settings
    assert "freeNotice.setTextIsSelectable(true)" in settings


def test_new_card_titles_are_native_in_all_three_languages() -> None:
    expected = {
        "app/src/main/res/values/ui_strings.xml": ("اللغة", "حجم الخط"),
        "app/src/main/res/values-en/ui_strings.xml": ("Language", "Font size"),
        "app/src/main/res/values-el/ui_strings.xml": ("Γλῶσσα", "Μέγεθος γραμματοσειρᾶς"),
    }
    for file_name, (language, font_size) in expected.items():
        assert resource_value(file_name, "ui_language_settings_title") == language
        assert resource_value(file_name, "ui_font_size_settings_title") == font_size
