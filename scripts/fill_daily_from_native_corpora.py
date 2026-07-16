#!/usr/bin/env python3
"""Fill daily Scripture readings from exact, independently imported native corpora.

The liturgical calendar chooses the canonical reference. This script only resolves
that reference inside the corpus for the same language. It never translates,
rewrites, normalizes, automatically adds marks, or publishes a partial passage.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, source_url_allowed
from enforce_native_daily_lanes import date_evidence
from orthodox_integrity import parse_reference as parse_human_reference
from public_domain_scripture import load_public_domain_corpus

SCRIPTURE_KINDS = {"epistle", "gospel"}
REFERENCE_RE = re.compile(r"^(?P<book>[1-3]?[A-Z]+)\.(?P<start_chapter>\d+)\.(?P<start_verse>\d+)(?:-(?:(?P<end_chapter>\d+)\.)?(?P<end_verse>\d+))?$")


def reading_lists(data: dict[str, Any]) -> Iterable[list[Any]]:
    if isinstance(data.get("readings"), list):
        yield data["readings"]
    sunday = data.get("next_sunday")
    if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
        yield sunday["readings"]
    integrity_inputs = data.get("integrity_inputs")
    if isinstance(integrity_inputs, dict):
        sunday = integrity_inputs.get("next_sunday")
        if isinstance(sunday, dict) and isinstance(sunday.get("readings"), list):
            yield sunday["readings"]
    for service in data.get("services") or []:
        if isinstance(service, dict) and isinstance(service.get("readings"), list):
            yield service["readings"]


def canonical_reference(reading: dict[str, Any]) -> str:
    integrity = reading.get("integrity")
    if isinstance(integrity, dict) and integrity.get("canonical_reference"):
        return str(integrity["canonical_reference"])
    native = reading.get("native_source_verification")
    if isinstance(native, dict):
        for item in native.values():
            if isinstance(item, dict) and item.get("canonical_reference"):
                return str(item["canonical_reference"])
    old = reading.get("translation_verification")
    if isinstance(old, dict):
        for item in old.values():
            if isinstance(item, dict) and item.get("canonical_reference"):
                return str(item["canonical_reference"])
    # Partial official-source resolution can leave the canonical integrity field
    # unset while the calendar-discovery step still has the appointed human
    # reference. Resolve that reference before the native-lane enforcer clears
    # display-only discovery fields.
    references = reading.get("reference")
    if isinstance(references, dict):
        for language in ("en", "ar", "el"):
            raw = str(references.get(language) or "").strip()
            if not raw:
                continue
            try:
                return parse_human_reference(raw)[0]
            except Exception:
                continue
    return ""


def parse_reference(value: str) -> tuple[str, int, int, int, int] | None:
    match = REFERENCE_RE.fullmatch((value or "").strip().upper())
    if not match:
        return None
    book = match.group("book")
    start_chapter = int(match.group("start_chapter"))
    start_verse = int(match.group("start_verse"))
    end_chapter = int(match.group("end_chapter") or start_chapter)
    end_verse = int(match.group("end_verse") or start_verse)
    if (end_chapter, end_verse) < (start_chapter, start_verse):
        return None
    return book, start_chapter, start_verse, end_chapter, end_verse


def load_corpus(language: str, contract: dict[str, Any]) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]] | None:
    base = ROOT / "data" / "scripture" / "native" / language
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    verses = json.loads((base / "verses.json").read_text(encoding="utf-8"))
    persisted_statuses = {
        "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
        "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
    }
    if manifest.get("status") not in persisted_statuses or not verses:
        public_manifest, public_index = load_public_domain_corpus(language)
        source_id = str(public_manifest.get("source_id") or "")
        source_url = str(public_manifest.get("source_url") or "")
        if not source_allowed(language, source_id, contract) or not source_url_allowed(source_id, source_url, contract):
            raise ValueError(f"{language}: public-domain corpus source is outside the registered language lane")
        if public_manifest.get("machine_translation_used") is not False or public_manifest.get("automatic_diacritization_used") is not False:
            raise ValueError(f"{language}: public-domain corpus has forbidden transformation flags")
        return public_manifest, public_index
    source_id = str(manifest.get("source_id") or "")
    source_url = str(manifest.get("source_url") or "")
    if not source_allowed(language, source_id, contract) or not source_url_allowed(source_id, source_url, contract):
        raise ValueError(f"{language}: imported corpus source is outside the registered language lane")
    if manifest.get("machine_translation_used") is not False or manifest.get("automatic_diacritization_used") is not False:
        raise ValueError(f"{language}: imported corpus has forbidden transformation flags")
    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    for verse in verses:
        key = (str(verse.get("book_id") or "").upper(), int(verse.get("chapter") or 0), int(verse.get("verse") or 0))
        text = str(verse.get("text") or "")
        if verse.get("text_sha256") != sha256_text(text):
            raise ValueError(f"{language}: corpus hash mismatch at {key}")
        if key in index:
            raise ValueError(f"{language}: duplicate corpus verse {key}")
        index[key] = verse
    return manifest, index


def passage_verses(index: dict[tuple[str, int, int], dict[str, Any]], parsed: tuple[str, int, int, int, int]) -> list[dict[str, Any]] | None:
    book, start_chapter, start_verse, end_chapter, end_verse = parsed
    selected = [
        verse for (item_book, chapter, number), verse in index.items()
        if item_book == book and (start_chapter, start_verse) <= (chapter, number) <= (end_chapter, end_verse)
    ]
    selected.sort(key=lambda item: (int(item["chapter"]), int(item["verse"])))
    if not selected:
        return None
    if (int(selected[0]["chapter"]), int(selected[0]["verse"])) != (start_chapter, start_verse):
        return None
    if (int(selected[-1]["chapter"]), int(selected[-1]["verse"])) != (end_chapter, end_verse):
        return None
    # Refuse apparent gaps. A chapter boundary may reset to verse 1; within a
    # chapter every verse number must be consecutive.
    previous: tuple[int, int] | None = None
    for item in selected:
        current = (int(item["chapter"]), int(item["verse"]))
        if previous is not None:
            if current[0] == previous[0] and current[1] != previous[1] + 1:
                return None
            if current[0] > previous[0]:
                if current[0] > previous[0] + 1 or current[1] != 1:
                    return None
                previous_chapter_max = max(
                    (number for (item_book, chapter, number) in index if item_book == book and chapter == previous[0]),
                    default=0,
                )
                if previous[1] != previous_chapter_max:
                    return None
        previous = current
    return selected


def format_reference(verses: list[dict[str, Any]], parsed: tuple[str, int, int, int, int]) -> str:
    _, start_chapter, start_verse, end_chapter, end_verse = parsed
    book_name = str(verses[0].get("book_name") or verses[0].get("book_id") or "")
    if (start_chapter, start_verse) == (end_chapter, end_verse):
        span = f"{start_chapter}:{start_verse}"
    elif start_chapter == end_chapter:
        span = f"{start_chapter}:{start_verse}-{end_verse}"
    else:
        span = f"{start_chapter}:{start_verse}-{end_chapter}:{end_verse}"
    return f"{book_name} {span}".strip()


def fill_reading(reading: dict[str, Any], corpora: dict[str, tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]] | None], reference_evidence: dict[str, dict[str, Any]] | None = None) -> int:
    if str(reading.get("kind") or "") not in SCRIPTURE_KINDS:
        return 0
    canonical = canonical_reference(reading)
    parsed = parse_reference(canonical)
    if parsed is None:
        return 0
    integrity = reading.setdefault("integrity", {})
    if not isinstance(integrity, dict):
        integrity = {}
        reading["integrity"] = integrity
    integrity["canonical_reference"] = canonical
    body = reading.setdefault("body", {})
    reference = reading.setdefault("reference", {})
    source = reading.setdefault("source", {})
    verification = reading.setdefault("native_source_verification", {})
    filled = 0
    for language in LANGUAGES:
        corpus = corpora.get(language)
        if corpus is None:
            continue
        manifest, index = corpus
        selected = passage_verses(index, parsed)
        if selected is None:
            # All-or-nothing: never publish a partial passage.
            continue
        exact_texts = [str(item["text"]) for item in selected]
        display_text = "\n".join(exact_texts)
        body[language] = display_text
        reference[language] = format_reference(selected, parsed)
        source[language] = str(manifest["source_url"])
        verification[language] = {
            "status": str(manifest.get("status") or "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS"),
            "source_id": manifest["source_id"],
            "source_url": manifest["source_url"],
            "canonical_reference": canonical,
            "reference_available": True,
            "text_available": True,
            "text_sha256": sha256_text(display_text),
            "verse_count": len(selected),
            "verse_hashes": [item["text_sha256"] for item in selected],
            "join_policy": "SOURCE_VERSES_JOINED_WITH_LF_NO_TEXT_MUTATION",
            "machine_translation_used": False,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
            "daily_reference_source_id": (reference_evidence or {}).get(language, {}).get("source_id"),
            "daily_reference_source_url": (reference_evidence or {}).get(language, {}).get("source_url"),
            "corpus_archive_sha256": manifest.get("archive_sha256"),
            "corpus_license": manifest.get("license"),
        }
        filled += 1
    reading["native_source_verification"] = verification
    return filled


def process(path: Path) -> int:
    contract = load_contract()
    corpora = {language: load_corpus(language, contract) for language in LANGUAGES}
    data = json.loads(path.read_text(encoding="utf-8"))
    target_date = str(data.get("date_iso") or data.get("date") or "")
    filled = 0
    for readings in reading_lists(data):
        for reading in readings:
            if not isinstance(reading, dict):
                continue
            canonical = canonical_reference(reading)
            evidence_by_language: dict[str, dict[str, Any]] = {}
            field = "epistle_reference" if reading.get("kind") == "epistle" else "gospel_reference"
            for language in LANGUAGES:
                daily = date_evidence(data, target_date, language, contract)
                if daily is None:
                    continue
                evidence = daily["evidence"]
                raw_reference = str(evidence.get(field) or "")
                try:
                    resolved = parse_human_reference(raw_reference)[0]
                except Exception:
                    resolved = ""
                if resolved != canonical:
                    continue
                evidence_by_language[language] = {
                    "source_id": daily["source_id"],
                    "source_url": evidence.get("url"),
                }
            filled += fill_reading(reading, corpora, evidence_by_language)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return filled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=["data/calendar/today.json"])
    args = parser.parse_args()
    total = 0
    for raw_path in args.paths:
        path = ROOT / raw_path
        count = process(path)
        total += count
        print(f"Filled {count} exact same-language daily passage(s) in {path.relative_to(ROOT)}")
    print(f"Native-corpus daily fill complete; total language-passages={total}")


if __name__ == "__main__":
    main()
