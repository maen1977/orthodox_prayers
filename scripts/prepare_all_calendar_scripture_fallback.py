#!/usr/bin/env python3
"""Build the offline Scripture fallback for every calendar reading through 2050.

Only verses appointed by the embedded calendar are retained. Wording comes
unchanged from the registered public-domain Arabic, English and Greek corpora;
no translation, rewriting or automatic diacritization is performed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from fill_daily_from_native_corpora import parse_reference_parts
from public_domain_scripture import load_public_domain_corpus

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")

# Documented source-edition verse-number omissions. The surrounding wording is
# present and the canonical lectionary reference remains unchanged for display.
# Historical source-edition omissions retained as a fail-safe.  Newer USFM
# archives are also inspected directly: an explicit verse marker that contains
# only source footnote material is recorded by public_domain_scripture.py as a
# numbered_source_omission.  Canonical lectionary references are never rewritten.
ALLOWED_SOURCE_OMISSIONS = {
    "ar": set(),
    "en": {"ACT.15.34", "LUK.17.36"},
    "el": {"2CO.13.14", "MRK.7.16"},
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(raw)


def calendar_references() -> list[str]:
    references: set[str] = set()
    for year in range(2026, 2051):
        path = ROOT / f"app/src/main/assets/data/calendar/calendar_{year}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for day in payload.get("days") or []:
            for item in (day.get("reading_references") or {}).values():
                if not isinstance(item, dict):
                    continue
                value = str(item.get("canonical_reference") or "").strip().upper()
                if value:
                    references.add(value)
    if not references:
        raise ValueError("embedded calendar contains no Scripture references")
    return sorted(references)


def expected_span_ids(index: dict, span: tuple[str, int, int, int, int]) -> list[str]:
    book, start_chapter, start_verse, end_chapter, end_verse = span
    chapter_max = {
        chapter: max(
            (verse for item_book, item_chapter, verse in index if item_book == book and item_chapter == chapter),
            default=0,
        )
        for chapter in range(start_chapter, end_chapter + 1)
    }
    result: list[str] = []
    for chapter in range(start_chapter, end_chapter + 1):
        first = start_verse if chapter == start_chapter else 1
        last = end_verse if chapter == end_chapter else chapter_max[chapter]
        if last < first:
            raise ValueError(f"invalid or unavailable chapter range: {book}.{chapter}.{first}-{last}")
        result.extend(f"{book}.{chapter}.{verse}" for verse in range(first, last + 1))
    return result


def selected_for_reference(
    language: str,
    reference: str,
    index: dict,
    allowed_omissions: set[str] | None = None,
) -> list[dict[str, Any]]:
    parsed = parse_reference_parts(reference)
    if parsed is None:
        raise ValueError(f"invalid canonical reference: {reference}")
    selected: list[dict[str, Any]] = []
    allowed = set(ALLOWED_SOURCE_OMISSIONS[language])
    allowed.update(allowed_omissions or set())
    for span in parsed:
        for verse_id in expected_span_ids(index, span):
            book, chapter, verse = verse_id.split(".")
            item = index.get((book, int(chapter), int(verse)))
            if item is None:
                if verse_id in allowed:
                    continue
                raise ValueError(f"{language}: source verse missing for {reference}: {verse_id}")
            selected.append(item)
    if not selected:
        raise ValueError(f"{language}: empty source passage: {reference}")
    return selected


def write_language(language: str, references: list[str]) -> dict[str, Any]:
    source, index = load_public_domain_corpus(language)
    detected_omissions = {
        str(item).strip().upper()
        for item in source.get("numbered_source_omissions", [])
        if str(item).strip()
    }
    allowed_omissions = set(ALLOWED_SOURCE_OMISSIONS[language]) | detected_omissions
    selected: dict[tuple[str, int, int], dict[str, Any]] = {}
    for reference in references:
        for item in selected_for_reference(language, reference, index, allowed_omissions):
            key = (str(item["book_id"]), int(item["chapter"]), int(item["verse"]))
            selected[key] = item

    source_id = str(source["source_id"])
    source_url = str(source["source_url"])
    verses = []
    for key in sorted(selected):
        item = selected[key]
        text = str(item["text"])
        verse_payload = {
            "automatic_diacritization_used": False,
            "book_id": key[0],
            "book_name": str(item.get("book_name") or key[0]),
            "chapter": key[1],
            "id": f"{key[0]}.{key[1]}.{key[2]}",
            "machine_translation_used": False,
            "source_id": source_id,
            "source_url": source_url,
            "text": text,
            "text_sha256": sha256_text(text),
            "verse": key[2],
        }
        if item.get("source_verse_relocation") is True:
            verse_payload.update({
                "source_book_id": str(item.get("source_book_id") or key[0]),
                "source_chapter": int(item.get("source_chapter") or key[1]),
                "source_verse": int(item.get("source_verse") or key[2]),
                "source_verse_relocation": True,
            })
        verses.append(verse_payload)

    omissions = sorted(allowed_omissions)
    manifest = {
        "schema_version": 2,
        "language": language,
        "contract": "canonical/source_native_contract.json",
        "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
        "corpus_kind": "public-domain-liturgical-reading-subset",
        "coverage_status": "ALL_EMBEDDED_CALENDAR_REFERENCES_2026_2050",
        "calendar_start": "2026-01-01",
        "calendar_end": "2050-12-31",
        "supported_canonical_reference_count": len(references),
        "supported_canonical_references": references,
        "allowed_source_verse_omissions": omissions,
        "detected_numbered_source_omissions": sorted(detected_omissions),
        "source_id": source_id,
        "source_url": source_url,
        "source_title": str(source.get("title") or ""),
        "license": str(source.get("license") or "Public Domain"),
        "source_verse_relocations": list(source.get("source_verse_relocations") or []),
        "verse_count": len(verses),
        "books": sorted({item["book_id"] for item in verses}),
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "display_text_policy": "PRESERVE_SOURCE_UNICODE_CODEPOINTS_EXACTLY",
        "content_sha256": canonical_hash(verses),
    }

    for base in (
        ROOT / "data/scripture/native" / language,
        ROOT / "app/src/main/assets/data/scripture",
    ):
        base.mkdir(parents=True, exist_ok=True)
        verses_name = "verses.json" if base.name == language else f"verses_{language}.json"
        manifest_name = "manifest.json" if base.name == language else f"manifest_{language}.json"
        (base / verses_name).write_text(
            json.dumps(verses, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (base / manifest_name).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {"verses": len(verses), "references": len(references), "omissions": omissions}


def main() -> int:
    references = calendar_references()
    report = {language: write_language(language, references) for language in LANGUAGES}
    print(json.dumps({"status": "ALL_CALENDAR_SCRIPTURE_READY", "languages": report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ALL_CALENDAR_SCRIPTURE_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
