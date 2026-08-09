from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_settings_hub_uses_action_cards_and_keeps_about_plain() -> None:
    settings = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java")

    assert "private View createSettingsHubView()" in settings
    assert settings.count("addSettingsAction(page,") == 3
    assert "ic_action_language" in settings
    assert "ui_language_and_text_settings_title" in settings
    assert "ic_action_calendar" in settings
    assert "ic_action_settings" in settings
    assert "ui_church_directory_and_live_services_b4f52ad3" not in settings
    assert 'ui.actionCard(iconResource, title, "")' in settings
    assert 'host.navigate("settings_section", targetSection)' in settings
    assert "appendAboutSection(page);" in settings
    assert "aboutCard" not in settings
    assert "freeNotice.setTextIsSelectable(true)" in settings


def test_each_settings_card_opens_its_own_back_navigable_detail_page() -> None:
    settings = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java")
    main = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")

    for section in ("language_text", "language", "font_size", "calendar_reminders", "update_data"):
        assert f'"{section}"' in settings
    assert "SECTION_LANGUAGE_AND_TEXT.equals(section)" in settings
    assert "LEGACY_SECTION_LANGUAGE.equals(section)" in settings
    assert "LEGACY_SECTION_FONT_SIZE.equals(section)" in settings
    assert "return createLanguageAndTextSettingsView();" in settings
    assert "if (SECTION_CALENDAR.equals(section)) return createCalendarSettingsView();" in settings
    assert "if (SECTION_UPDATE.equals(section)) return createUpdateSettingsView();" in settings
    assert "return page(local(com.orthodoxprayers.privateapp.R.string.ui_settings_25169a1d), true);" in settings
    assert 'case "settings_section": return new SettingsScreen(this, entry.argument);' in main
    assert '"settings_section".equals(entry.screenId)' in main


def test_setting_changes_refresh_the_open_detail_instead_of_returning_to_the_hub() -> None:
    settings = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java")
    main = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")

    assert "private void reloadCurrentSettingsScreen()" in settings
    assert 'else host.navigate("settings_section", section);' in settings
    assert settings.count("reloadCurrentSettingsScreen();") >= 12
    assert '("settings".equals(current.screenId) || "settings_section".equals(current.screenId))' in main
