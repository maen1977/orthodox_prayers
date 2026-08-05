from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "liturgy_delivery", ROOT / "scripts/validate_divine_liturgy_delivery_integrity.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def service(lang: str) -> dict:
    pack = read(f"data/services/native/library_{lang}.json")
    return next(item for item in pack["services"] if item["id"] == "divine_liturgy")


def document(lang: str) -> dict:
    index = read(f"data/search/search_index_{lang}.json")
    return next(item for item in index["documents"] if item["id"] == "service:divine_liturgy")


def test_android_and_data_assets_are_byte_identical() -> None:
    for lang in MODULE.LANGUAGES:
        assert (ROOT / f"data/services/native/library_{lang}.json").read_bytes() == (
            ROOT / f"app/src/main/assets/data/native/library_{lang}.json"
        ).read_bytes()
        assert (ROOT / f"data/search/search_index_{lang}.json").read_bytes() == (
            ROOT / f"app/src/main/assets/data/search/search_index_{lang}.json"
        ).read_bytes()


def test_search_document_is_built_from_current_native_pack() -> None:
    for lang in MODULE.LANGUAGES:
        expected = MODULE.search_display_text(service(lang), lang)
        doc = document(lang)
        assert doc["display_text"] == expected
        assert doc["display_sha256"] == hashlib.sha256(expected.encode("utf-8")).hexdigest()


def test_arabic_third_antiphon_is_not_duplicated() -> None:
    text = MODULE.search_display_text(service("ar"), "ar")
    assert text.count("هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه.") == 1


def test_no_known_corruption_is_delivered() -> None:
    for lang in MODULE.LANGUAGES:
        text = MODULE.full_visible_text(service(lang), lang) + "\n" + document(lang)["display_text"]
        for token in MODULE.KNOWN_BAD[lang]:
            assert token.casefold() not in text.casefold()
