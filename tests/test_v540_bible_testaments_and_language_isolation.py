from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def catalog(path: str) -> dict[str, str]:
    root = ET.parse(ROOT / path).getroot()
    return {node.attrib["name"]: "".join(node.itertext()) for node in root.findall("string")}


def test_bible_root_is_split_into_old_and_new_testaments():
    screen = text("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleScreen.java")
    testament = text("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleTestamentScreen.java")
    main = text("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    assert 'host.navigate("bible_testament", "old")' in screen
    assert 'host.navigate("bible_testament", "new")' in screen
    assert 'case "bible_testament": return new BibleTestamentScreen' in main
    assert "BibleBookNames.isNewTestament(book.code) != newTestament" in testament


def test_four_gospels_have_full_book_titles_in_every_supported_language():
    names = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleBookNames.java")
    expected = [
        ('MAT', 'إنجيل متى', 'Gospel of Matthew', 'Κατὰ Ματθαῖον Εὐαγγέλιον'),
        ('MRK', 'إنجيل مرقس', 'Gospel of Mark', 'Κατὰ Μᾶρκον Εὐαγγέλιον'),
        ('LUK', 'إنجيل لوقا', 'Gospel of Luke', 'Κατὰ Λουκᾶν Εὐαγγέλιον'),
        ('JHN', 'إنجيل يوحنا', 'Gospel of John', 'Κατὰ Ἰωάννην Εὐαγγέλιον'),
    ]
    for code, ar, en, el in expected:
        assert f'add("{code}","{ar}","{en}","{el}")' in names


def test_bible_ui_strings_are_isolated_by_language():
    ar = catalog("app/src/main/res/values/ui_strings.xml")
    en = catalog("app/src/main/res/values-en/ui_strings.xml")
    el = catalog("app/src/main/res/values-el/ui_strings.xml")
    keys = {key for key in ar if key.startswith("ui_bible_")}
    assert len(keys) >= 20
    assert keys == {key for key in en if key.startswith("ui_bible_")}
    assert keys == {key for key in el if key.startswith("ui_bible_")}
    arabic = re.compile(r"[\u0600-\u06ff]")
    greek = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
    for key in keys:
        assert arabic.search(ar[key]), key
        assert not greek.search(ar[key]), key
        assert not arabic.search(en[key]) and not greek.search(en[key]), key
        assert greek.search(el[key]), key
        assert not arabic.search(el[key]), key
    assert "public domain" not in el["ui_bible_source_label"].lower()


def test_bible_runtime_never_falls_back_to_another_language():
    repo = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleCorpusRepository.java")
    names = text("app/src/main/java/com/orthodoxprayers/privateapp/bible/BibleBookNames.java")
    assert 'if ("en".equals(language)) return new CorpusSource[] {ENGLISH_SOURCE};' in repo
    assert "return new CorpusSource[0];" in repo
    assert 'if ("en".equals(language)) return names[1];' in names
    assert "return code;" in names


def test_bible_screens_use_localized_resource_catalog_not_inline_language_triples():
    for path in [
        "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleScreen.java",
        "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleTestamentScreen.java",
        "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleBookScreen.java",
        "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BibleChapterScreen.java",
    ]:
        source = text(path)
        assert "private static String t(" not in source
        assert '"الكتاب المقدس"' not in source
        assert '"Holy Bible"' not in source
        assert '"Ἁγία Γραφή"' not in source
