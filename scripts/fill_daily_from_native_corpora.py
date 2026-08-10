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
from typing import Any, Iterable, TypeAlias

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, source_url_allowed
from enforce_native_daily_lanes import date_evidence
from orthodox_integrity import parse_reference as parse_human_reference
from public_domain_scripture import load_public_domain_corpus

SCRIPTURE_KINDS = {"matins_gospel", "epistle", "gospel"}
REFERENCE_RE = re.compile(r"^(?P<book>[1-3]?[A-Z]+)\.(?P<start_chapter>\d+)\.(?P<start_verse>\d+)(?:-(?:(?P<end_chapter>\d+)\.)?(?P<end_verse>\d+))?$")
ReferenceSpan: TypeAlias = tuple[str, int, int, int, int]
CanonicalSpans: TypeAlias = tuple[ReferenceSpan, ...]


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


def parse_reference_parts(value: str) -> CanonicalSpans | None:
    """Parse one or more appointed spans without filling verses between them."""
    raw_parts = [part.strip().upper() for part in (value or "").split(";")]
    if not raw_parts or any(not part for part in raw_parts):
        return None

    spans: list[ReferenceSpan] = []
    appointed_book = ""
    previous_end: tuple[int, int] | None = None
    for part in raw_parts:
        match = REFERENCE_RE.fullmatch(part)
        if not match:
            return None
        book = match.group("book")
        start_chapter = int(match.group("start_chapter"))
        start_verse = int(match.group("start_verse"))
        end_chapter = int(match.group("end_chapter") or start_chapter)
        end_verse = int(match.group("end_verse") or start_verse)
        start = (start_chapter, start_verse)
        end = (end_chapter, end_verse)
        if end < start:
            return None
        if appointed_book and book != appointed_book:
            return None
        if previous_end is not None and start <= previous_end:
            return None
        appointed_book = book
        previous_end = end
        spans.append((book, start_chapter, start_verse, end_chapter, end_verse))
    return tuple(spans)


def parse_reference(value: str) -> ReferenceSpan | None:
    """Backward-compatible parser for one continuous canonical span."""
    spans = parse_reference_parts(value)
    return spans[0] if spans is not None and len(spans) == 1 else None


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




def declared_source_omissions(manifest: dict[str, Any]) -> set[str]:
    """Return source-edition verse numbers that intentionally have no wording."""
    result: set[str] = set()
    for field in ("numbered_source_omissions", "allowed_source_verse_omissions"):
        for item in manifest.get(field, []) or []:
            value = str(item or "").strip().upper()
            if value:
                result.add(value)
    return result

def current_reading_lists(data: dict[str, Any]) -> Iterable[list[Any]]:
    """Yield today's readings and today's services, excluding preview Sundays."""
    if isinstance(data.get("readings"), list):
        yield data["readings"]
    for service in data.get("services") or []:
        if isinstance(service, dict) and isinstance(service.get("readings"), list):
            yield service["readings"]


def required_references(data: dict[str, Any], *, include_preview: bool = True) -> list[tuple[str, CanonicalSpans]]:
    """Return unique canonical Epistle/Gospel references required by this payload."""
    required: list[tuple[str, CanonicalSpans]] = []
    seen: set[str] = set()
    lists = reading_lists(data) if include_preview else current_reading_lists(data)
    for readings in lists:
        for reading in readings:
            if not isinstance(reading, dict) or str(reading.get("kind") or "") not in SCRIPTURE_KINDS:
                continue
            canonical = canonical_reference(reading)
            parsed = parse_reference_parts(canonical)
            if parsed is None or canonical in seen:
                continue
            seen.add(canonical)
            required.append((canonical, parsed))
    return required


def ensure_corpus_coverage(
    language: str,
    corpus: tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]] | None,
    required: list[tuple[str, CanonicalSpans]],
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]] | None:
    """Lazily load the complete public-domain corpus when the checked-in slice is insufficient.

    The repository keeps a small verified slice so the known release candidate can be
    reproduced offline. Daily generation may require different passages (especially
    next Sunday's readings), so a missing passage must trigger the registered complete
    native corpus rather than publishing blanks or failing with a misleading language
    error. The download is cached by public_domain_scripture.py.
    """
    if corpus is None or not required:
        return corpus
    manifest, index = corpus
    omissions = declared_source_omissions(manifest)
    missing = [
        canonical for canonical, parsed in required
        if passage_verses(index, parsed, omissions) is None
    ]
    if not missing:
        return corpus

    print(
        f"{language}: checked-in Scripture slice is missing {', '.join(missing)}; "
        "loading the complete registered public-domain corpus",
        flush=True,
    )
    try:
        full_manifest, full_index = load_public_domain_corpus(language)
    except Exception as error:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"{language}: checked-in Scripture slice does not cover {joined}; "
            f"the complete registered public-domain corpus could not be loaded: {error}"
        ) from error

    source_id = str(full_manifest.get("source_id") or "")
    source_url = str(full_manifest.get("source_url") or "")
    if not source_allowed(language, source_id, contract) or not source_url_allowed(source_id, source_url, contract):
        raise ValueError(f"{language}: complete public-domain corpus source is outside the registered language lane")
    if full_manifest.get("machine_translation_used") is not False or full_manifest.get("automatic_diacritization_used") is not False:
        raise ValueError(f"{language}: complete public-domain corpus has forbidden transformation flags")

    full_omissions = declared_source_omissions(full_manifest)
    unresolved = [
        canonical for canonical, parsed in required
        if passage_verses(full_index, parsed, full_omissions) is None
    ]
    if unresolved:
        raise ValueError(f"{language}: complete public-domain corpus is missing required passage(s): {', '.join(unresolved)}")
    return full_manifest, full_index


def _span_verses(
    index: dict[tuple[str, int, int], dict[str, Any]],
    parsed: ReferenceSpan,
    allowed_omissions: set[str] | None = None,
) -> list[dict[str, Any]] | None:
    book, start_chapter, start_verse, end_chapter, end_verse = parsed
    allowed = allowed_omissions or set()

    # Resolve the appointed numeric span exactly, allowing only verse numbers
    # that the source edition explicitly declares as numbered-but-textless.
    # This distinguishes a genuine source omission (for example Acts 15:34 in
    # WEB) from an accidental missing verse in a damaged or partial corpus.
    chapter_max: dict[int, int] = {}
    for item_book, chapter, number in index:
        if item_book == book and start_chapter <= chapter <= end_chapter:
            chapter_max[chapter] = max(chapter_max.get(chapter, 0), number)
    for verse_id in allowed:
        parts = verse_id.split('.')
        if len(parts) != 3 or parts[0] != book:
            continue
        try:
            chapter = int(parts[1]); number = int(parts[2])
        except ValueError:
            continue
        if start_chapter <= chapter <= end_chapter:
            chapter_max[chapter] = max(chapter_max.get(chapter, 0), number)

    selected: list[dict[str, Any]] = []
    for chapter in range(start_chapter, end_chapter + 1):
        first = start_verse if chapter == start_chapter else 1
        last = end_verse if chapter == end_chapter else chapter_max.get(chapter, 0)
        if last < first:
            return None
        for number in range(first, last + 1):
            key = (book, chapter, number)
            item = index.get(key)
            if item is not None:
                selected.append(item)
                continue
            if f"{book}.{chapter}.{number}" in allowed:
                continue
            return None
    return selected or None


def passage_verses(
    index: dict[tuple[str, int, int], dict[str, Any]],
    parsed: ReferenceSpan | CanonicalSpans,
    allowed_omissions: set[str] | None = None,
) -> list[dict[str, Any]] | None:
    """Resolve every appointed span independently and preserve its exact order."""
    if len(parsed) == 5 and isinstance(parsed[0], str):
        spans: CanonicalSpans = (parsed,)  # type: ignore[assignment]
    else:
        spans = parsed  # type: ignore[assignment]

    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for span in spans:
        selected = _span_verses(index, span, allowed_omissions)
        if selected is None:
            return None
        for verse in selected:
            key = (
                str(verse.get("book_id") or "").upper(),
                int(verse.get("chapter") or 0),
                int(verse.get("verse") or 0),
            )
            if key in seen:
                return None
            seen.add(key)
            combined.append(verse)
    return combined or None


def _format_span(parsed: ReferenceSpan) -> str:
    _, start_chapter, start_verse, end_chapter, end_verse = parsed
    if (start_chapter, start_verse) == (end_chapter, end_verse):
        return f"{start_chapter}:{start_verse}"
    elif start_chapter == end_chapter:
        return f"{start_chapter}:{start_verse}-{end_verse}"
    return f"{start_chapter}:{start_verse}-{end_chapter}:{end_verse}"


def format_reference(verses: list[dict[str, Any]], parsed: CanonicalSpans) -> str:
    book_name = str(verses[0].get("book_name") or verses[0].get("book_id") or "")
    return f"{book_name} {'; '.join(_format_span(span) for span in parsed)}".strip()


def fill_reading(reading: dict[str, Any], corpora: dict[str, tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]] | None], reference_evidence: dict[str, dict[str, Any]] | None = None) -> int:
    if str(reading.get("kind") or "") not in SCRIPTURE_KINDS:
        return 0
    canonical = canonical_reference(reading)
    parsed = parse_reference_parts(canonical)
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
        omissions = declared_source_omissions(manifest)
        selected = passage_verses(index, parsed, omissions)
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
            "source_verse_omissions_in_reference": sorted(
                verse_id for verse_id in omissions
                if any(
                    span[0] == verse_id.split('.')[0]
                    and (span[1], span[2]) <= (int(verse_id.split('.')[1]), int(verse_id.split('.')[2])) <= (span[3], span[4])
                    for span in parsed
                )
            ),
        }
        filled += 1
    reading["native_source_verification"] = verification
    return filled


def process(path: Path, *, include_preview: bool = True) -> int:
    contract = load_contract()
    data = json.loads(path.read_text(encoding="utf-8"))
    required = required_references(data, include_preview=include_preview)
    corpora = {
        language: ensure_corpus_coverage(language, load_corpus(language, contract), required, contract)
        for language in LANGUAGES
    }
    target_date = str(data.get("date_iso") or data.get("date") or "")
    filled = 0
    lists = reading_lists(data) if include_preview else current_reading_lists(data)
    for readings in lists:
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
    parser.add_argument("--current-only", action="store_true", help="fill today and today services, excluding next-Sunday previews")
    args = parser.parse_args()
    total = 0
    for raw_path in args.paths:
        path = ROOT / raw_path
        count = process(path, include_preview=not args.current_only)
        total += count
        print(f"Filled {count} exact same-language daily passage(s) in {path.relative_to(ROOT)}")
    print(f"Native-corpus daily fill complete; total language-passages={total}")


if __name__ == "__main__":
    main()
