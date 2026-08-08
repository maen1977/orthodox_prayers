from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_510_version_and_reader_progress_contract():
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    prefs = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
    reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    assert 'versionName = "5.6.4"' in build
    assert "versionCode = 50604" in build
    assert "readerProgressPercent" in prefs
    assert "setReaderProgressPercent" in reader
    # Reader progress remains stored for the reader/history features, but the
    # user explicitly removed the Continue Reading card from Home.
    assert "ReadingProgressPolicy.isResumable" not in home
    assert "addContinueReading" not in home


def test_search_and_favorites_have_direct_collection_actions():
    search = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SearchScreen.java").read_text(encoding="utf-8")
    favorites = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/FavoritesScreen.java").read_text(encoding="utf-8")
    assert "preferences.toggleFavorite(serviceId)" in search
    assert "preferences.toggleFavorite(id)" in favorites
    assert "ui_delete_ea349e00" in favorites


def test_continue_reading_home_card_and_label_are_removed_in_all_languages():
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    assert "addContinueReading" not in home
    assert "ui_continue_reading" not in home
    for folder in ("values", "values-en", "values-el"):
        resource = (ROOT / f"app/src/main/res/{folder}/ui_strings.xml").read_text(encoding="utf-8")
        assert 'name="ui_continue_reading"' not in resource

