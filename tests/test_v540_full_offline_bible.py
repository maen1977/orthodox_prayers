from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_v540_version_and_full_bible_build_assets():
    gradle = text("app/build.gradle.kts")
    prepare = text("scripts/prepare_bible_corpus.py")
    assert 'versionCode = 50502' in gradle
    assert 'versionName = "5.5.2"' in gradle
    for name in ["arb-arb-vd.tsv", "eng-eng-webbe.tsv", "grc-grcbrent.tsv", "grc-grcbyz.tsv"]:
        assert name in prepare
    assert 'tasks.named("preBuild").configure { dependsOn(prepareBibleCorpus, prepareChurchServiceCorpus) }' in gradle
    assert 'rootProject.file("scripts/prepare_bible_corpus.py")' in gradle
    assert "raw.githubusercontent.com/BibleNLP/ebible/main" not in gradle
    assert "https://ebible.org/Scriptures/" in prepare
    assert "_usfm.zip" in prepare


def test_runtime_bible_is_offline_and_daily_readings_prefer_it():
    repo = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleCorpusRepository.java")
    engine = text("app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java")
    assert "getAssets().open" in repo
    assert "HttpURLConnection" not in repo
    assert "URL(" not in repo
    assert "fullBible.resolve(language, canonicalReference)" in engine
    full_pos = engine.index("fullBible.resolve(language, canonicalReference)")
    slice_pos = engine.index("ScriptureCorpus corpus = scriptureCorpus(language)", full_pos)
    assert full_pos < slice_pos


def test_bible_browse_search_and_chapter_routes_exist():
    main = text("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    home = text("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    screen = text("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleScreen.java")
    testament = text("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleTestamentScreen.java")
    assert 'case "bible":' in main
    assert 'case "bible_testament":' in main
    assert 'case "bible_book":' in main
    assert 'case "bible_chapter":' in main
    assert '"bible", null' in home
    assert "bible.search(lang, value, 80)" in screen
    assert 'host.navigate("bible_testament", "old")' in screen
    assert 'host.navigate("bible_testament", "new")' in screen
    assert "bible.books(lang)" in testament


def test_reference_parser_supports_daily_ranges_and_single_verses():
    parser = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleReference.java")
    assert "parseMany" in parser
    assert "parseVrefLine" in parser
    assert 'canonical.split(";")' in parser


def test_public_domain_sources_are_named_explicitly():
    repo = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleCorpusRepository.java")
    for source in ["arb-vd", "eng-webbe", "grcbrent", "grcbyz"]:
        assert source in repo


def test_bible_builder_has_retries_cache_and_completeness_gates():
    prepare = text("scripts/prepare_bible_corpus.py")
    assert "for attempt in range(1, 4)" in prepare
    assert "zipfile.is_zipfile" in prepare
    assert "min_verses" in prepare
    assert "BIBLE_CORPUS_FAILED" in prepare
    assert "archiveSha256" in prepare
