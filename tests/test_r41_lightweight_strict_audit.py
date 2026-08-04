from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_calendar_assets_are_lazy_and_memory_pressure_releases_only_caches() -> None:
    repository = read("app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java")
    app = read("app/src/main/java/com/orthodoxprayers/privateapp/OrthodoxPrayersApp.java")
    constructor = repository.split("private DataRepository", 1)[1].split("private synchronized void loadCalendarYear", 1)[0]
    assert 'loadCalendarYear(LocalDate.now' not in constructor
    assert "public synchronized void releaseOptionalCaches(int level)" in repository
    assert "activeLanguageSearchIndex = null;" in repository
    assert "calendarByDate.clear();" in repository
    assert "repository.releaseOptionalCaches(level);" in app


def test_primary_back_targets_are_at_least_48dp() -> None:
    ui = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/UiKit.java")
    reader = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java")
    assert "new LinearLayout.LayoutParams(dp(48), dp(48))" in ui
    assert "setMinWidth(dp(48))" in ui
    assert "setMinHeight(dp(48))" in ui
    assert "new LinearLayout.LayoutParams(ui.dp(48), ui.dp(48))" in reader


def test_android_8_security_floor_remains_unchanged() -> None:
    build = read("app/build.gradle.kts")
    assert "minSdk = 26" in build
    assert "targetSdk = 36" in build
    assert "compileSdk = 36" in build
