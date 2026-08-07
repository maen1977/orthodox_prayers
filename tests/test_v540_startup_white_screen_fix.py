from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_startup_never_rebuilds_daily_package_synchronously():
    repo = text("app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java")
    ctor = repo[repo.index("private DataRepository(Context context"):repo.index("private synchronized void loadCalendarYear")]
    assert "buildCurrentWindow" not in ctor
    assert "activateLocalCurrentPackageIfNeeded" not in repo
    assert "activateCachedLocalPackageIfAvailable()" in ctor
    assert "localDailyCacheStore.save(encoded)" in repo


def test_app_open_refresh_is_skipped_when_current():
    main = text("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    check = main[main.index("private final Runnable automaticOpenRefreshCheck"):main.index("private final Runnable resumeMaintenance")]
    assert "updateCoordinator.shouldRefresh(dayChanged, true)" in check
    assert "dayChanged || !repository.hasUsableCurrentData()" in check


def test_noncritical_application_startup_work_is_backgrounded():
    app = text("app/src/main/java/com/orthodoxprayers/privateapp/OrthodoxPrayersApp.java")
    assert "OrthodoxStartupMaintenance" in app
    assert "startupMaintenance.execute" in app
    block = app[app.index("startupMaintenance.execute"):app.index("    }\n\n    @Override\n    public void onTrimMemory")]
    for call in ["scheduleDailyRefresh", "schedulePeriodicChecks", "scheduleAll", "DailyAgendaWidget.updateAll", "AppShortcuts.install"]:
        assert call in block


def test_bible_daily_lookup_uses_small_per_book_assets():
    repo = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleCorpusRepository.java")
    prepare = text("scripts/prepare_bible_corpus.py")
    assert '"books/" + source.id + "/" + book + ".tsv"' in repo
    resolve = repo[repo.index("public ResolvedPassage resolve"):repo.index("public Chapter chapter")]
    assert "openBook(source, range.book)" in resolve
    assert "open(source.monolithicFile)" not in resolve
    assert "write_book_tsvs" in prepare
    assert 'output_dir / "books" / source_id' in prepare


def test_launch_window_is_not_plain_white():
    styles = text("app/src/main/res/values/styles.xml")
    assert '<item name="android:windowBackground">#062B4F</item>' in styles
