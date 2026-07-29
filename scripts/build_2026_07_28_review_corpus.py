#!/usr/bin/env python3
"""Build a non-publishing native Scripture review corpus for 2026-07-28.

Arabic and Greek are copied byte-for-byte from the registered cached USFM
corpora. English is copied verse-for-verse from the registered public-domain
World English Bible pages for the appointed passages. The output is stored
under canonical/generated_daily and never replaces the signed Android overlay.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fill_daily_from_native_corpora import parse_reference_parts, passage_verses
from public_domain_scripture import parse_usfm_archive

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = (
    "1CO.12.12-26",
    "MAT.18.18-22;MAT.19.1-2;MAT.19.13-15",
)

ENGLISH_WEB = {
    ("1CO", 12, 12): "For as the body is one and has many members, and all the members of the body, being many, are one body; so also is Christ.",
    ("1CO", 12, 13): "For in one Spirit we were all baptized into one body, whether Jews or Greeks, whether bond or free; and were all given to drink into one Spirit.",
    ("1CO", 12, 14): "For the body is not one member, but many.",
    ("1CO", 12, 15): "If the foot would say, “Because I’m not the hand, I’m not part of the body,” it is not therefore not part of the body.",
    ("1CO", 12, 16): "If the ear would say, “Because I’m not the eye, I’m not part of the body,” it’s not therefore not part of the body.",
    ("1CO", 12, 17): "If the whole body were an eye, where would the hearing be? If the whole were hearing, where would the smelling be?",
    ("1CO", 12, 18): "But now God has set the members, each one of them, in the body, just as he desired.",
    ("1CO", 12, 19): "If they were all one member, where would the body be?",
    ("1CO", 12, 20): "But now they are many members, but one body.",
    ("1CO", 12, 21): "The eye can’t tell the hand, “I have no need for you,” or again the head to the feet, “I have no need for you.”",
    ("1CO", 12, 22): "No, much rather, those members of the body which seem to be weaker are necessary.",
    ("1CO", 12, 23): "Those parts of the body which we think to be less honorable, on those we bestow more abundant honor; and our unpresentable parts have more abundant modesty,",
    ("1CO", 12, 24): "while our presentable parts have no such need. But God composed the body together, giving more abundant honor to the inferior part,",
    ("1CO", 12, 25): "that there should be no division in the body, but that the members should have the same care for one another.",
    ("1CO", 12, 26): "When one member suffers, all the members suffer with it. When one member is honored, all the members rejoice with it.",
    ("MAT", 18, 18): "Most certainly I tell you, whatever things you bind on earth will have been bound in heaven, and whatever things you release on earth will have been released in heaven.",
    ("MAT", 18, 19): "Again, assuredly I tell you, that if two of you will agree on earth concerning anything that they will ask, it will be done for them by my Father who is in heaven.",
    ("MAT", 18, 20): "For where two or three are gathered together in my name, there I am in the middle of them.”",
    ("MAT", 18, 21): "Then Peter came and said to him, “Lord, how often shall my brother sin against me, and I forgive him? Until seven times?”",
    ("MAT", 18, 22): "Jesus said to him, “I don’t tell you until seven times, but, until seventy times seven.",
    ("MAT", 19, 1): "When Jesus had finished these words, he departed from Galilee and came into the borders of Judea beyond the Jordan.",
    ("MAT", 19, 2): "Great multitudes followed him, and he healed them there.",
    ("MAT", 19, 13): "Then little children were brought to him that he should lay his hands on them and pray; and the disciples rebuked them.",
    ("MAT", 19, 14): "But Jesus said, “Allow the little children, and don’t forbid them to come to me; for the Kingdom of Heaven belongs to ones like these.”",
    ("MAT", 19, 15): "He laid his hands on them, and departed from there.",
}

BOOK_NAMES = {
    "en": {"1CO": "1 Corinthians", "MAT": "Matthew"},
}
SOURCE_IDS = {
    "ar": "ebible_arabic_van_dyck",
    "en": "ebible_world_english_bible",
    "el": "ebible_greek_byzantine_1904",
}
SOURCE_URLS = {
    "ar": "https://ebible.org/find/details.php?id=arb-vd",
    "en": "https://ebible.org/find/details.php?id=engwebp",
    "el": "https://ebible.org/find/details.php?id=grcbyz",
}


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def required_keys() -> list[tuple[str, int, int]]:
    keys: list[tuple[str, int, int]] = []
    for reference in REFERENCES:
        parsed = parse_reference_parts(reference)
        if parsed is None:
            raise RuntimeError(reference)
        for book, start_chapter, start_verse, end_chapter, end_verse in parsed:
            for chapter in range(start_chapter, end_chapter + 1):
                first = start_verse if chapter == start_chapter else 1
                last = end_verse if chapter == end_chapter else 999
                keys.extend((book, chapter, verse) for verse in range(first, last + 1))
    return keys


def write_review_corpus(language: str, additions: list[dict]) -> None:
    base = ROOT / "canonical" / "generated_daily" / "scripture_2026-07-28" / language
    base.mkdir(parents=True, exist_ok=True)
    merged = sorted(additions, key=lambda v: (v["book_id"], int(v["chapter"]), int(v["verse"])))
    compact = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    (base / "verses.json").write_text(compact + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "date_iso": "2026-07-28",
        "language": language,
        "status": "NON_PUBLISHING_EXACT_NATIVE_REVIEW_CORPUS",
        "source_id": SOURCE_IDS[language],
        "source_url": SOURCE_URLS[language],
        "verse_count": len(merged),
        "books": sorted({v["book_id"] for v in merged}),
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "content_sha256": hashlib.sha256(compact.encode("utf-8")).hexdigest(),
    }
    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def corpus_additions(language: str, archive_name: str) -> list[dict]:
    payload = (ROOT / ".cache" / "scripture" / archive_name).read_bytes()
    index, _ = parse_usfm_archive(payload)
    additions: list[dict] = []
    for reference in REFERENCES:
        parsed = parse_reference_parts(reference)
        assert parsed is not None
        selected = passage_verses(index, parsed)
        if selected is None:
            raise RuntimeError(f"{language}: missing {reference}")
        for verse in selected:
            text = str(verse["text"])
            additions.append({
                "automatic_diacritization_used": False,
                "book_id": verse["book_id"],
                "book_name": verse["book_name"],
                "chapter": int(verse["chapter"]),
                "id": f"{verse['book_id']}.{verse['chapter']}.{verse['verse']}",
                "machine_translation_used": False,
                "source_id": SOURCE_IDS[language],
                "source_url": SOURCE_URLS[language],
                "text": text,
                "text_sha256": sha(text),
                "verse": int(verse["verse"]),
            })
    return additions


def english_additions() -> list[dict]:
    expected: set[tuple[str, int, int]] = set()
    # Passage boundaries are all within one chapter in this release slice.
    for reference in REFERENCES:
        parsed = parse_reference_parts(reference)
        assert parsed is not None
        for book, sc, sv, ec, ev in parsed:
            if sc != ec:
                raise RuntimeError("unexpected cross-chapter span")
            expected.update((book, sc, verse) for verse in range(sv, ev + 1))
    if set(ENGLISH_WEB) != expected:
        raise RuntimeError(f"English slice mismatch: missing={expected-set(ENGLISH_WEB)} extra={set(ENGLISH_WEB)-expected}")
    return [{
        "automatic_diacritization_used": False,
        "book_id": book,
        "book_name": BOOK_NAMES["en"][book],
        "chapter": chapter,
        "id": f"{book}.{chapter}.{verse}",
        "machine_translation_used": False,
        "source_id": SOURCE_IDS["en"],
        "source_url": SOURCE_URLS["en"],
        "text": text,
        "text_sha256": sha(text),
        "verse": verse,
    } for (book, chapter, verse), text in sorted(ENGLISH_WEB.items())]


def main() -> None:
    write_review_corpus("ar", corpus_additions("ar", "arb-vd_usfm.zip"))
    write_review_corpus("el", corpus_additions("el", "grcbyz_usfm.zip"))
    write_review_corpus("en", english_additions())
    print("2026-07-28 non-publishing review corpus built in ar/en/el")


if __name__ == "__main__":
    main()
