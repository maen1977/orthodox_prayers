from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_510_version_and_reader_progress_contract():
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    prefs = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
    reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    assert 'versionName = "5.5.2"' in build
    assert "versionCode = 50502" in build
    assert "readerProgressPercent" in prefs
    assert "setReaderProgressPercent" in reader
    assert "ReadingProgressPolicy.isResumable" in home
    assert 'host.navigate("reader", serviceId)' in home


def test_search_and_favorites_have_direct_collection_actions():
    search = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SearchScreen.java").read_text(encoding="utf-8")
    favorites = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/FavoritesScreen.java").read_text(encoding="utf-8")
    assert "preferences.toggleFavorite(serviceId)" in search
    assert "preferences.toggleFavorite(id)" in favorites
    assert "ui_delete_ea349e00" in favorites


def test_continue_reading_is_localized_in_all_languages():
    expected = {
        "values": "استكمال القراءة",
        "values-en": "Continue reading",
        "values-el": "Συνέχεια ἀναγνώσεως",
    }
    for folder, text in expected.items():
        resource = (ROOT / f"app/src/main/res/{folder}/ui_strings.xml").read_text(encoding="utf-8")
        assert 'name="ui_continue_reading"' in resource
        assert text in resource
