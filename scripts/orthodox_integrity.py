#!/usr/bin/env python3
"""Automated Orthodox text-integrity gate.

The gate never asks an AI service to create Scripture or liturgical text. It resolves
references through the strict official order (Jordan, Jerusalem, Antioch, then an
official Greek Orthodox source), fetches exact vocalized Arabic Bible verses,
checks their words against a pinned base text, rebuilds services, and publishes
only after every required source and integrity gate passes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import importlib.util
import json
import os
import re
import sys
import subprocess
import shutil
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from official_sources import (
    SourceEvidence as OfficialEvidence,
    diacritic_metrics,
    parse_antioch_guide_text,
    sha256_text,
    strict_resolve,
    strip_arabic_diacritics,
    validate_source_document,
    verify_vocalized_against_base,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "canonical" / "source_policy.json"
TODAY_PATH = ROOT / "data" / "calendar" / "today.json"
ASSET_PATH = ROOT / "app" / "src" / "main" / "assets" / "data" / "today.json"
TZ = ZoneInfo("Asia/Amman")

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
AR_MONTHS = {
    "كانون الثاني": 1, "يناير": 1,
    "شباط": 2, "فبراير": 2,
    "آذار": 3, "اذار": 3, "مارس": 3,
    "نيسان": 4, "أبريل": 4, "ابريل": 4,
    "أيار": 5, "ايار": 5, "مايو": 5,
    "حزيران": 6, "يونيو": 6,
    "تموز": 7, "يوليو": 7,
    "آب": 8, "اب": 8, "أغسطس": 8, "اغسطس": 8,
    "أيلول": 9, "ايلول": 9, "سبتمبر": 9,
    "تشرين الأول": 10, "تشرين الاول": 10, "أكتوبر": 10, "اكتوبر": 10,
    "تشرين الثاني": 11, "نوفمبر": 11,
    "كانون الأول": 12, "كانون الاول": 12, "ديسمبر": 12,
}

BOOK_ALIASES: dict[str, str] = {
    "genesis": "GEN", "exodus": "EXO", "leviticus": "LEV", "numbers": "NUM", "deuteronomy": "DEU",
    "joshua": "JOS", "judges": "JDG", "ruth": "RUT", "1 samuel": "1SA", "i samuel": "1SA",
    "2 samuel": "2SA", "ii samuel": "2SA", "1 kings": "1KI", "i kings": "1KI", "2 kings": "2KI", "ii kings": "2KI",
    "1 chronicles": "1CH", "i chronicles": "1CH", "2 chronicles": "2CH", "ii chronicles": "2CH",
    "ezra": "EZR", "nehemiah": "NEH", "esther": "EST", "job": "JOB", "psalm": "PSA", "psalms": "PSA",
    "proverbs": "PRO", "ecclesiastes": "ECC", "song of songs": "SNG", "song of solomon": "SNG",
    "isaiah": "ISA", "jeremiah": "JER", "lamentations": "LAM", "ezekiel": "EZK", "daniel": "DAN",
    "hosea": "HOS", "joel": "JOL", "amos": "AMO", "obadiah": "OBA", "jonah": "JON", "micah": "MIC",
    "nahum": "NAM", "habakkuk": "HAB", "zephaniah": "ZEP", "haggai": "HAG", "zechariah": "ZEC", "malachi": "MAL",
    "matthew": "MAT", "mark": "MRK", "luke": "LUK", "john": "JHN", "acts": "ACT", "romans": "ROM",
    "1 corinthians": "1CO", "i corinthians": "1CO", "first corinthians": "1CO",
    "2 corinthians": "2CO", "ii corinthians": "2CO", "second corinthians": "2CO",
    "galatians": "GAL", "ephesians": "EPH", "philippians": "PHP", "colossians": "COL",
    "1 thessalonians": "1TH", "i thessalonians": "1TH", "2 thessalonians": "2TH", "ii thessalonians": "2TH",
    "1 timothy": "1TI", "i timothy": "1TI", "2 timothy": "2TI", "ii timothy": "2TI",
    "titus": "TIT", "philemon": "PHM", "hebrews": "HEB", "james": "JAS",
    "1 peter": "1PE", "i peter": "1PE", "2 peter": "2PE", "ii peter": "2PE",
    "1 john": "1JN", "i john": "1JN", "2 john": "2JN", "ii john": "2JN", "3 john": "3JN", "iii john": "3JN",
    "jude": "JUD", "revelation": "REV",
    "متى": "MAT", "مرقس": "MRK", "لوقا": "LUK", "يوحنا": "JHN", "أعمال الرسل": "ACT", "اعمال الرسل": "ACT",
    "رومية": "ROM", "روميه": "ROM", "الروم": "ROM", "غلاطية": "GAL", "أفسس": "EPH", "افسس": "EPH",
    "فيلبي": "PHP", "كولوسي": "COL", "عبرانيين": "HEB", "يعقوب": "JAS", "تيطس": "TIT",
    "١ كورنثوس": "1CO", "1 كورنثوس": "1CO", "كورنثوس الأولى": "1CO", "كورنثوس الاولى": "1CO",
    "٢ كورنثوس": "2CO", "2 كورنثوس": "2CO", "كورنثوس الثانية": "2CO",
    "١ تيموثاوس": "1TI", "1 تيموثاوس": "1TI", "٢ تيموثاوس": "2TI", "2 تيموثاوس": "2TI",
    "١ بطرس": "1PE", "1 بطرس": "1PE", "٢ بطرس": "2PE", "2 بطرس": "2PE",
    "١ يوحنا": "1JN", "1 يوحنا": "1JN", "٢ يوحنا": "2JN", "2 يوحنا": "2JN", "٣ يوحنا": "3JN", "3 يوحنا": "3JN",
}

BOOK_AR = {
    "MAT": "متى", "MRK": "مرقس", "LUK": "لوقا", "JHN": "يوحنا", "ACT": "أعمال الرسل", "ROM": "رومية",
    "1CO": "كورنثوس الأولى", "2CO": "كورنثوس الثانية", "GAL": "غلاطية", "EPH": "أفسس", "PHP": "فيلبي",
    "COL": "كولوسي", "1TH": "تسالونيكي الأولى", "2TH": "تسالونيكي الثانية", "1TI": "تيموثاوس الأولى",
    "2TI": "تيموثاوس الثانية", "TIT": "تيطس", "PHM": "فليمون", "HEB": "العبرانيين", "JAS": "يعقوب",
    "1PE": "بطرس الأولى", "2PE": "بطرس الثانية", "1JN": "يوحنا الأولى", "2JN": "يوحنا الثانية",
    "3JN": "يوحنا الثالثة", "JUD": "يهوذا", "REV": "الرؤيا", "PSA": "المزامير",
}


class TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "br", "tr", "td"}
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK:
            self.parts.append("\n")
    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK:
            self.parts.append("\n")
    def handle_data(self, data: str) -> None:
        self.parts.append(data)
    def text(self) -> str:
        raw = html.unescape("".join(self.parts)).replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


@dataclass
class SourceResult:
    id: str
    role: str
    url: str
    status: str
    date_iso: str | None = None
    epistle: str | None = None
    gospel: str | None = None
    note: str | None = None
    fasting_code: str | None = None


@dataclass(frozen=True)
class VerseSpan:
    book: str
    chapter: int
    start: int
    end: int
    end_chapter: int | None = None

    @property
    def final_chapter(self) -> int:
        return self.end_chapter or self.chapter


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "").translate(ARABIC_DIGITS)
    value = value.replace("–", "-").replace("—", "-").replace("−", "-")
    value = value.replace("：", ":").replace("٫", ".")
    return re.sub(r"\s+", " ", value).strip()


def normalize_book_name(value: str) -> str:
    value = normalize_text(value).lower().strip(" .:-")
    value = value.replace("st. paul's", "").replace("saint paul's", "").strip()
    value = re.sub(r"^the\s+", "", value).strip()
    value = re.sub(r"^(?:holy\s+)?gospel\s+according\s+to\s+", "", value).strip()
    value = re.sub(r"^gospel\s+according\s+to\s+", "", value).strip()
    value = re.sub(r"^(?:the\s+)?(?:first|1st)\s+letter\s+to\s+(?:the\s+)?", "first ", value).strip()
    value = re.sub(r"^(?:the\s+)?(?:second|2nd)\s+letter\s+to\s+(?:the\s+)?", "second ", value).strip()
    value = re.sub(r"^(?:the\s+)?letter\s+to\s+(?:the\s+)?", "", value).strip()
    value = re.sub(r"^epistle\s+to\s+(?:the\s+)?", "", value).strip()
    value = re.sub(r"^رسالة\s+(?:القديس\s+)?بولس(?:\s+الرسول)?\s+(?:الأولى|الاولى)\s+إلى\s+(?:أهل\s+)?", "1 ", value)
    value = re.sub(r"^رسالة\s+(?:القديس\s+)?بولس(?:\s+الرسول)?\s+(?:الثانية)\s+إلى\s+(?:أهل\s+)?", "2 ", value)
    value = re.sub(r"^رسالة\s+(?:القديس\s+)?بولس(?:\s+الرسول)?\s+إلى\s+(?:أهل\s+)?", "", value)
    value = re.sub(r"^(?:إنجيل|انجيل)\s+(?:القديس\s+)?", "", value)
    value = value.replace("first corinthians", "1 corinthians")
    value = value.replace("second corinthians", "2 corinthians")
    value = value.replace("first thessalonians", "1 thessalonians")
    value = value.replace("second thessalonians", "2 thessalonians")
    value = value.replace("first timothy", "1 timothy")
    value = value.replace("second timothy", "2 timothy")
    value = value.replace("first peter", "1 peter")
    value = value.replace("second peter", "2 peter")
    value = value.replace("first john", "1 john")
    value = value.replace("second john", "2 john")
    value = value.replace("third john", "3 john")
    value = re.sub(r"\bof\b.*$", "", value).strip(" .:-")
    value = value.replace("saint ", "").replace("st. ", "").replace("st ", "")
    return re.sub(r"\s+", " ", value).strip()


def parse_reference(reference: str) -> tuple[str, list[VerseSpan]]:
    original = reference
    ref = normalize_text(reference)
    ref = re.sub(r"^(Epistle Reading|Gospel Reading|Matins Gospel Reading)\s*[-:]\s*", "", ref, flags=re.I)
    ref = re.sub(r"^رسالة\s+", "", ref)
    ref = re.sub(r"^(?:إنجيل|انجيل)\s+(?:القديس\s+)?", "", ref)
    match = re.match(r"^(.+?)\s+(\d+)\s*[:.]\s*(.+)$", ref)
    if not match:
        raise ValueError(f"Unsupported scripture reference: {original!r}")
    book_raw, first_chapter, rest = match.groups()
    normalized_book = normalize_book_name(book_raw)
    book_key = BOOK_ALIASES.get(normalized_book) or BOOK_ALIASES.get(normalize_text(book_raw))
    if not book_key:
        raise ValueError(f"Unknown Bible book in reference {original!r}: {book_raw!r}")

    current_chapter = int(first_chapter)
    spans: list[VerseSpan] = []
    # Semicolons and commas separate ranges. A token may repeat the chapter
    # (11:1-8) or cross into another chapter (11:21-12:9).
    for raw_token in re.split(r"\s*[;,]\s*", rest):
        token = raw_token.strip()
        if not token:
            continue
        m = re.match(
            r"^(?:(\d+)\s*[:.]\s*)?(\d+)(?:\s*-\s*(?:(\d+)\s*[:.]\s*)?(\d+))?$",
            token,
        )
        if not m:
            raise ValueError(f"Unsupported verse component {token!r} in {original!r}")
        explicit_chapter, start_verse, end_chapter, end_verse = m.groups()
        if explicit_chapter:
            current_chapter = int(explicit_chapter)
        start = int(start_verse)
        final_chapter = int(end_chapter) if end_chapter else current_chapter
        end = int(end_verse) if end_verse else start
        if final_chapter < current_chapter:
            raise ValueError(f"Reversed chapter range in {original!r}")
        if final_chapter == current_chapter and end < start:
            raise ValueError(f"Reversed verse range in {original!r}")
        spans.append(
            VerseSpan(
                book=book_key,
                chapter=current_chapter,
                start=start,
                end=end,
                end_chapter=final_chapter if final_chapter != current_chapter else None,
            )
        )
        current_chapter = final_chapter
    if not spans:
        raise ValueError(f"Reference contains no verses: {original!r}")
    canonical_parts = []
    for span in spans:
        if span.final_chapter == span.chapter:
            canonical_parts.append(f"{span.book}.{span.chapter}.{span.start}-{span.end}")
        else:
            canonical_parts.append(f"{span.book}.{span.chapter}.{span.start}-{span.final_chapter}.{span.end}")
    return ";".join(canonical_parts), spans


def reference_display_ar(spans: list[VerseSpan]) -> str:
    groups: list[str] = []
    for span in spans:
        name = BOOK_AR.get(span.book, span.book)
        if span.final_chapter == span.chapter:
            verses = str(span.start) if span.start == span.end else f"{span.start}-{span.end}"
            groups.append(f"{name} {span.chapter}:{verses}")
        else:
            groups.append(f"{name} {span.chapter}:{span.start}-{span.final_chapter}:{span.end}")
    return "؛ ".join(groups)


def resolve_book(bible: dict[str, Any], key: str) -> dict[str, Any]:
    books = bible.get("books")
    if not isinstance(books, dict):
        raise RuntimeError("Canonical Bible JSON has no books object")
    candidates = [key, key.upper(), key.lower()]
    aliases = {"MRK": ["MAR"], "JHN": ["JOH"], "PSA": ["PSM"], "SNG": ["SOS"], "JAS": ["JAM"]}
    candidates.extend(aliases.get(key, []))
    for candidate in candidates:
        if candidate in books:
            return books[candidate]
    for book in books.values():
        if isinstance(book, dict) and normalize_book_name(str(book.get("name", ""))) in {normalize_book_name(k) for k, v in BOOK_ALIASES.items() if v == key}:
            return book
    raise KeyError(f"Canonical Bible is missing book {key}")


def extract_verses(bible: dict[str, Any], spans: list[VerseSpan]) -> tuple[str, list[dict[str, Any]]]:
    lines: list[str] = []
    evidence: list[dict[str, Any]] = []
    for span in spans:
        book = resolve_book(bible, span.book)
        chapters = book.get("chapters", {})
        for chapter_number in range(span.chapter, span.final_chapter + 1):
            chapter = chapters.get(str(chapter_number))
            if not isinstance(chapter, dict):
                raise KeyError(f"Missing chapter {span.book} {chapter_number}")
            numeric_verses = sorted(int(v) for v in chapter if str(v).isdigit())
            if not numeric_verses:
                raise KeyError(f"Chapter {span.book} {chapter_number} has no numbered verses")
            first_verse = span.start if chapter_number == span.chapter else min(numeric_verses)
            last_verse = span.end if chapter_number == span.final_chapter else max(numeric_verses)
            for verse in range(first_verse, last_verse + 1):
                text = chapter.get(str(verse))
                if not isinstance(text, str) or not text.strip():
                    raise KeyError(f"Missing verse {span.book} {chapter_number}:{verse}")
                clean = normalize_text(text)
                lines.append(f"{chapter_number}:{verse} {clean}")
                evidence.append({
                    "book": span.book,
                    "chapter": chapter_number,
                    "verse": verse,
                    "sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
                })
    return "\n".join(lines), evidence


def http_get(url: str, attempts: int = 3, timeout: int = 35) -> tuple[bytes, dict[str, str]]:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"Accept": "text/html,application/json;q=0.9,*/*;q=0.8", "User-Agent": "orthodox-prayers-integrity/3.2 (+https://github.com/maen1977/orthodox_prayers)"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                return body, headers
        except urllib.error.HTTPError as exc:
            last = RuntimeError(f"HTTP {exc.code} for {url}")
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt < attempts:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"Cannot fetch {url}: {last}")


SCRIPTURE_SNAPSHOT_DIR = ROOT / "canonical" / "scripture"


def load_verified_scripture_snapshots() -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for path in sorted(SCRIPTURE_SNAPSHOT_DIR.glob("*.json")):
        payload = load_json(path)
        for display_ref, item in payload.get("readings", {}).items():
            canonical_ref, _ = parse_reference(display_ref)
            if canonical_ref in snapshots:
                raise RuntimeError(f"Duplicate verified Scripture snapshot for {canonical_ref}")
            snapshots[canonical_ref] = {
                "display_reference": display_ref,
                "translation_id": payload.get("translation_id"),
                "title_ar": payload.get("title_ar"),
                "license": payload.get("license"),
                "source_page": payload.get("source_page"),
                "snapshot_file": str(path.relative_to(ROOT)),
                **item,
            }
    return snapshots


def scripture_snapshot_body(item: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    verses = item.get("verses")
    if not isinstance(verses, list) or not verses:
        raise RuntimeError("Verified Scripture snapshot has no verses")
    lines: list[str] = []
    evidence: list[dict[str, Any]] = []
    expected_previous: tuple[int, int] | None = None
    for row in verses:
        chapter = int(row["chapter"])
        verse = int(row["verse"])
        text = unicodedata.normalize("NFC", re.sub(r"\s+", " ", str(row["text"])).strip())
        if expected_previous:
            previous_chapter, previous_verse = expected_previous
            if chapter == previous_chapter and verse != previous_verse + 1:
                raise RuntimeError(f"Non-contiguous Scripture snapshot at {chapter}:{verse}")
            if chapter < previous_chapter or (chapter == previous_chapter and verse <= previous_verse):
                raise RuntimeError(f"Out-of-order Scripture snapshot at {chapter}:{verse}")
        expected_previous = (chapter, verse)
        lines.append(f"{chapter}:{verse} {text}")
        evidence.append({
            "chapter": chapter,
            "verse": verse,
            "sha256": sha256_text(text),
        })
    source_rows = [
        {"url": url, "sha256": None, "snapshot_file": item.get("snapshot_file")}
        for url in item.get("chapters", [])
    ]
    return "\n".join(lines), evidence, source_rows


def verified_scripture_for_reference(reference: str) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | None:
    canonical_ref, _ = parse_reference(reference)
    item = load_verified_scripture_snapshots().get(canonical_ref)
    if not item:
        return None
    body, evidence, sources = scripture_snapshot_body(item)
    return body, evidence, sources, item


def ensure_canonical_bible(policy: dict[str, Any], allow_network: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return Scripture-policy metadata without crossing language lanes.

    The current publication contract uses one independently imported official
    native corpus per language. Missing corpora are allowed and mean that the
    corresponding text remains unavailable. The older single Arabic eBible
    cache is retained only for historical tests and is never a publication
    authority in this mode.
    """
    cfg = policy["scripture_canonical"]
    mode = str(cfg.get("mode") or "")
    if mode == "PER_LANGUAGE_OFFICIAL_NATIVE_CORPUS_ONLY":
        contract_path = ROOT / str(policy.get("native_language_contract") or "canonical/source_native_contract.json")
        contract = load_json(contract_path) if contract_path.is_file() else {}
        manifests: dict[str, Any] = {}
        for language, relative in (cfg.get("corpus_manifests") or {}).items():
            manifest_path = ROOT / str(relative)
            entry: dict[str, Any] = {
                "path": str(relative),
                "available": False,
                "status": "NOT_IMPORTED",
                "sha256": None,
                "source_id": None,
            }
            if manifest_path.is_file():
                raw = manifest_path.read_bytes()
                try:
                    manifest = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Invalid native Scripture manifest for {language}: {relative}: {exc}") from exc
                entry.update({
                    "available": manifest.get("status") == "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
                    "status": manifest.get("status") or "UNKNOWN",
                    "sha256": sha256_bytes(raw),
                    "source_id": manifest.get("source_id"),
                })
            manifests[str(language)] = entry
        return {}, {
            "mode": mode,
            "id": "per_language_official_native_corpora",
            "name_ar": "مكتبات كتاب مقدس رسمية أصلية مستقلة لكل لغة",
            "status": "NATIVE_CORPUS_POLICY",
            "pinned_revision": contract.get("effective_from"),
            "url": None,
            "file_sha256": None,
            "independent_base_available": False,
            "verified_snapshot_hashes": {},
            "corpus_manifests": manifests,
            "missing_text_behavior": cfg.get("missing_text_behavior"),
            "native_text_contract": str(contract_path.relative_to(ROOT)) if contract_path.is_file() else None,
        }

    # Legacy compatibility for old policy files. A cache path is usable only
    # when it names a regular file; Path("") resolves to the repository root
    # and must never be read as bytes.
    cache_value = str(cfg.get("base_cache_path") or "").strip()
    cache = ROOT / cache_value if cache_value else None
    pinned_url = cfg.get("base_pinned_url")
    bible: dict[str, Any] = {}
    base_sha: str | None = None
    if cache is not None and cache.is_file():
        raw = cache.read_bytes()
        candidate = json.loads(raw.decode("utf-8"))
        if candidate.get("id") == cfg.get("base_id") and isinstance(candidate.get("books"), dict):
            bible = candidate
            base_sha = sha256_bytes(raw)
    elif allow_network and pinned_url and cache is not None:
        try:
            body, _ = http_get(pinned_url, attempts=3, timeout=90)
            candidate = json.loads(body.decode("utf-8"))
            if candidate.get("id") == cfg.get("base_id") and isinstance(candidate.get("books"), dict):
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(body)
                bible = candidate
                base_sha = sha256_bytes(body)
        except Exception:
            bible = {}

    snapshot_hashes = {
        str(path.relative_to(ROOT)): sha256_bytes(path.read_bytes())
        for path in sorted(SCRIPTURE_SNAPSHOT_DIR.glob("*.json"))
    }
    vocalized = cfg["vocalized_source"]
    meta = {
        "mode": mode or "LEGACY_SINGLE_CORPUS",
        "id": cfg["id"],
        "name_ar": cfg["name_ar"],
        "status": cfg["status"],
        "note_ar": cfg.get("note_ar"),
        "pinned_revision": vocalized.get("source_files_date"),
        "url": vocalized.get("source_page"),
        "file_sha256": base_sha,
        "independent_base_available": bool(bible),
        "verified_snapshot_hashes": snapshot_hashes,
        "vocalized_source": vocalized,
    }
    return bible, meta

def html_to_text(raw: bytes, charset: str = "utf-8") -> str:
    parser = TextExtractor(); parser.feed(raw.decode(charset, errors="replace")); return parser.text()



class EBibleVerseParser(HTMLParser):
    """Collect Haiola verse spans identified by id=Vn or class=verse."""
    def __init__(self) -> None:
        super().__init__()
        self.current: int | None = None
        self.verses: dict[int, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        identifier = attr.get("id", "")
        match = re.fullmatch(r"V(\d+)", identifier, flags=re.I)
        if match:
            self.current = int(match.group(1))
            self.verses.setdefault(self.current, [])
            return
        classes = set(attr.get("class", "").split())
        if "verse" in classes and self.current is None:
            # Some Haiola builds place the number in data; handle_data will ignore it.
            self.current = -1

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        if self.current == -1:
            match = re.search(r"([0-9٠-٩]+)", data)
            if match:
                self.current = int(match.group(1).translate(ARABIC_DIGITS))
                self.verses.setdefault(self.current, [])
            return
        cleaned = data.replace("\xa0", " ")
        # Ignore the printed verse number itself.
        if normalize_text(cleaned).isdigit():
            return
        self.verses[self.current].append(cleaned)


def parse_ebible_chapter_html(raw: bytes) -> dict[int, str]:
    parser = EBibleVerseParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    output = {
        number: re.sub(r"\s+", " ", html.unescape("".join(parts))).strip()
        for number, parts in parser.verses.items()
        if number > 0 and re.sub(r"\s+", " ", "".join(parts)).strip()
    }
    if output:
        return output

    # Conservative fallback for changed HTML: extract rendered text and require a
    # contiguous numbered sequence beginning at verse 1.
    rendered = html_to_text(raw)
    digit = r"[0-9٠-٩]+"
    matches = list(re.finditer(rf"(?m)(?:^|\n)\s*({digit})\s+", rendered))
    candidates: dict[int, str] = {}
    for i, match in enumerate(matches):
        number = int(match.group(1).translate(ARABIC_DIGITS))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(rendered)
        text = re.sub(r"\s+", " ", rendered[match.end():end]).strip()
        if text and any("\u0600" <= ch <= "\u06ff" for ch in text):
            candidates[number] = text
    if 1 not in candidates:
        raise RuntimeError("Could not parse numbered verses from eBible chapter HTML")
    return candidates


def fetch_vocalized_verses(
    spans: list[VerseSpan],
    canonical_meta: dict[str, Any],
    allow_network: bool = True,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = canonical_meta["vocalized_source"]
    chapter_cache = ROOT / ".cache" / "canonical" / "ebible-arb-vd"
    chapter_cache.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    evidence: list[dict[str, Any]] = []
    chapter_sources: list[dict[str, Any]] = []
    seen_chapters: dict[tuple[str, int], dict[int, str]] = {}
    for span in spans:
        for chapter in range(span.chapter, span.final_chapter + 1):
            key = (span.book, chapter)
            if key not in seen_chapters:
                url = cfg["chapter_url_template"].format(book=span.book, chapter=chapter)
                cache = chapter_cache / f"{span.book}{chapter:02d}.htm"
                if not cache.exists():
                    if not allow_network:
                        raise RuntimeError(f"Vocalized chapter cache missing: {cache}")
                    raw, _ = http_get(url, attempts=4, timeout=60)
                    with tempfile.NamedTemporaryFile(dir=cache.parent, delete=False) as tmp:
                        tmp.write(raw); temp_path = Path(tmp.name)
                    temp_path.replace(cache)
                raw = cache.read_bytes()
                seen_chapters[key] = parse_ebible_chapter_html(raw)
                chapter_sources.append({
                    "book": span.book,
                    "chapter": chapter,
                    "url": url,
                    "sha256": sha256_bytes(raw),
                })
            verses = seen_chapters[key]
            first = span.start if chapter == span.chapter else min(verses)
            last = span.end if chapter == span.final_chapter else max(verses)
            for verse in range(first, last + 1):
                text = verses.get(verse)
                if not text:
                    raise RuntimeError(f"Missing vocalized verse {span.book} {chapter}:{verse}")
                clean = unicodedata.normalize("NFC", re.sub(r"\s+", " ", text).strip())
                lines.append(f"{chapter}:{verse} {clean}")
                evidence.append({
                    "book": span.book,
                    "chapter": chapter,
                    "verse": verse,
                    "sha256": sha256_text(clean),
                })
    return "\n".join(lines), evidence, chapter_sources


_ANTIOCH_TEXT_CACHE: dict[int, tuple[str, str, str]] = {}


def fetch_antioch_guide(target: date, cfg: dict[str, Any], allow_network: bool = True) -> OfficialEvidence:
    registry = load_json(ROOT / cfg["registry"])
    entry = registry.get("guides", {}).get(str(target.year))
    if not entry:
        return OfficialEvidence("antioch_patriarchate", 3, True, "", "unavailable", target.isoformat(), reason="لا يوجد دليل سنوي مثبت لهذه السنة.")
    if target.year not in _ANTIOCH_TEXT_CACHE:
        cache = ROOT / ".cache" / "sources" / f"antioch-guide-{target.year}.pdf"
        cache.parent.mkdir(parents=True, exist_ok=True)
        if not cache.exists():
            if not allow_network:
                return OfficialEvidence("antioch_patriarchate", 3, True, entry["url"], "unavailable", target.isoformat(), reason="ملف الدليل الرسمي غير موجود في الذاكرة المحلية.")
            body, _ = http_get(entry["url"], attempts=4, timeout=120)
            cache.write_bytes(body)
        raw = cache.read_bytes()
        digest = sha256_bytes(raw)
        if digest != entry["sha256"]:
            return OfficialEvidence("antioch_patriarchate", 3, True, entry["url"], "conflict", target.isoformat(), sha256=digest, reason="بصمة الدليل الرسمي تغيرت عن النسخة المثبتة.")
        out = cache.with_suffix(".txt")
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-layout", str(cache), str(out)], check=True)
            text = out.read_text(encoding="utf-8", errors="replace")
        else:
            from pypdf import PdfReader
            reader = PdfReader(str(cache))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        _ANTIOCH_TEXT_CACHE[target.year] = (text, entry["url"], digest)
    text, url, digest = _ANTIOCH_TEXT_CACHE[target.year]
    return parse_antioch_guide_text(text, target, url, digest)


def set_official_references(readings: list[dict[str, Any]], epistle: str, gospel: str) -> None:
    mapping = {"epistle": epistle, "gospel": gospel}
    for reading in readings:
        kind = reading.get("kind")
        if kind in mapping:
            reading.setdefault("reference", {})["en"] = mapping[kind]
            reading.setdefault("reference", {})["el"] = mapping[kind]

def parse_arabic_date(text: str) -> date | None:
    t = normalize_text(text)
    month_pattern = "|".join(sorted((re.escape(m) for m in AR_MONTHS), key=len, reverse=True))
    patterns = [
        rf"غربي[^\d]{{0,25}}(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})",
        rf"التاريخ[^\d]{{0,25}}(\d{{1,2}})\s+({month_pattern})\s+(\d{{4}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, t, flags=re.I)
        if m:
            return date(int(m.group(3)), AR_MONTHS[m.group(2)], int(m.group(1)))
    return None


def find_reference_after_heading(text: str, headings: list[str]) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if any(h in line for h in headings):
            candidates = [line] + lines[idx + 1: idx + 5]
            for candidate in candidates:
                candidate = re.sub(r"^(?:رسالة اليوم|إنجيل اليوم|انجيل اليوم)\s*[:：-]?\s*", "", candidate).strip()
                if re.search(r"\d+\s*[:.]\s*\d+", normalize_text(candidate)) and len(candidate) < 180:
                    return candidate
    return None


def fetch_orthodox_jordan(target: date, cfg: dict[str, Any]) -> SourceResult:
    url = cfg["url"]
    try:
        raw, headers = http_get(url)
        text = html_to_text(raw)
        page_date = parse_arabic_date(text)
        status, reason = validate_source_document(
            source_id="orthodox_jordan", target=target, detected_date=page_date, text=text,
            extra_poison_markers=cfg.get("poison_markers", []),
        )
        epistle = find_reference_after_heading(text, ["رسالة اليوم"])
        gospel = find_reference_after_heading(text, ["إنجيل اليوم", "انجيل اليوم"])
        if status != "current":
            return SourceResult("orthodox_jordan", cfg["role"], url, status, page_date.isoformat() if page_date else None, epistle, gospel, reason)
        if not epistle or not gospel:
            return SourceResult("orthodox_jordan", cfg["role"], url, "partial", page_date.isoformat(), epistle, gospel, "تاريخ اليوم صحيح لكن أحد المرجعين غير قابل للاستخراج.")
        return SourceResult("orthodox_jordan", cfg["role"], url, "current", page_date.isoformat(), epistle, gospel, note=f"sha256={sha256_bytes(raw)}")
    except Exception as exc:
        return SourceResult("orthodox_jordan", cfg["role"], url, "unavailable", note=str(exc))


def parse_goarch_fasting_code(block: str) -> str | None:
    normalized = normalize_text(block).lower()
    if "strict fast" in normalized:
        return "strict"
    if "wine & oil" in normalized or "wine and oil" in normalized or "fast day (wine" in normalized:
        return "wine_oil"
    if "fish, oil and wine are allowed" in normalized or "fast day (fish" in normalized:
        return "fish_allowed"
    if "dairy allowed" in normalized or "dairy, eggs, fish" in normalized:
        return "dairy_allowed"
    if "fast free" in normalized or "all foods allowed" in normalized or "no fast" in normalized:
        return "fast_free"
    return None


DCS_BOOK_EXPANSIONS = {
    "1 Cor.": "1 Corinthians", "2 Cor.": "2 Corinthians",
    "Rom.": "Romans", "Gal.": "Galatians", "Eph.": "Ephesians",
    "Phil.": "Philippians", "Col.": "Colossians",
    "1 Thess.": "1 Thessalonians", "2 Thess.": "2 Thessalonians",
    "1 Tim.": "1 Timothy", "2 Tim.": "2 Timothy", "Tit.": "Titus",
    "Heb.": "Hebrews", "Jas.": "James", "1 Pet.": "1 Peter",
    "2 Pet.": "2 Peter", "1 Jn.": "1 John", "2 Jn.": "2 John",
    "3 Jn.": "3 John", "Matt.": "Matthew", "Mk.": "Mark",
    "Lk.": "Luke", "Jn.": "John",
}


def _normalize_dcs_reference(value: str) -> str:
    value = normalize_text(value).replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*[-]\s*", "-", value)
    value = re.sub(r"\s*:\s*", ":", value)
    for short, full in sorted(DCS_BOOK_EXPANSIONS.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(short):
            value = full + value[len(short):]
            break
    return re.sub(r"\s+", " ", value).strip(" .")


def _dcs_reference_after_heading(text: str, heading: str) -> str | None:
    lines = [normalize_text(line).strip() for line in text.splitlines() if normalize_text(line).strip()]
    for index, line in enumerate(lines):
        if line.casefold() != heading.casefold():
            continue
        for candidate in lines[index + 1:index + 9]:
            if re.search(r"\d+\s*:\s*\d+", candidate) and len(candidate) < 140:
                normalized = _normalize_dcs_reference(candidate)
                try:
                    parse_reference(normalized)
                except Exception:
                    continue
                return normalized
    return None


def fetch_goarch_regular_cycle(target: date, cfg: dict[str, Any]) -> SourceResult:
    """Fetch only the Byzantine regular-cycle readings from official DCS.

    This endpoint labels the regular cycle explicitly, avoiding new-calendar
    fixed-feast readings that must not override Jordan/Jerusalem old-calendar use.
    """
    template = cfg.get("regular_cycle_url_template")
    if not template:
        return SourceResult("official_greek_orthodox", cfg.get("role", "official"), cfg.get("url_template", ""), "unavailable", target.isoformat(), note="regular-cycle URL is not configured")
    url = template.format(year=target.year, month=target.month, day=target.day)
    try:
        raw, _ = http_get(url)
        text = html_to_text(raw)
        if "The Readings from the Regular Cycle" not in text:
            return SourceResult("official_greek_orthodox", cfg.get("regular_cycle_role", cfg.get("role", "official")), url, "unusable", target.isoformat(), note="صفحة DCS لا تحتوي عنوان قراءات الدورة العادية.")
        date_tokens = (str(target.year), target.strftime("%B"), str(target.day))
        if not all(token.casefold() in text.casefold() for token in date_tokens):
            return SourceResult("official_greek_orthodox", cfg.get("regular_cycle_role", cfg.get("role", "official")), url, "stale", note="تعذر إثبات تاريخ صفحة DCS للدورة العادية.")
        epistle = _dcs_reference_after_heading(text, "The Epistle")
        gospel = _dcs_reference_after_heading(text, "The Gospel")
        if not epistle or not gospel:
            return SourceResult("official_greek_orthodox", cfg.get("regular_cycle_role", cfg.get("role", "official")), url, "partial", target.isoformat(), epistle, gospel, "تعذر استخراج زوج الدورة العادية كاملًا من DCS.")
        return SourceResult("official_greek_orthodox", cfg.get("regular_cycle_role", cfg.get("role", "official")), url, "current", target.isoformat(), epistle, gospel, note=f"sha256={sha256_bytes(raw)}")
    except Exception as exc:
        return SourceResult("official_greek_orthodox", cfg.get("regular_cycle_role", cfg.get("role", "official")), url, "unavailable", target.isoformat(), note=str(exc))


def fetch_goarch(target: date, cfg: dict[str, Any]) -> SourceResult:
    url = cfg["url_template"].format(month=target.month, year=target.year)
    try:
        raw, _ = http_get(url)
        text = html_to_text(raw)
        month_name = target.strftime("%B")
        # GOARCH formatting varies between zero-padded and non-padded day.
        matches = list(re.finditer(rf"(?:^|\n){target.day}\s+{target.strftime('%A')},\s+{month_name}\s+0?{target.day},\s+{target.year}", text, flags=re.I))
        if not matches:
            matches = list(re.finditer(rf"{target.strftime('%A')},\s+{month_name}\s+0?{target.day},\s+{target.year}", text, flags=re.I))
        if not matches:
            return SourceResult("goarch", cfg["role"], url, "unusable", note="لم يُعثر على كتلة تاريخ اليوم في صفحة الرزنامة.")
        start = matches[0].start(); tail = text[start:]
        next_date = re.search(r"\n\d{1,2}\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),", tail[20:], flags=re.I)
        block = tail[:20 + next_date.start()] if next_date else tail[:5000]
        ep = re.search(r"Epistle Reading\s*[-–:]\s*([^\n]+)", block, flags=re.I)
        go = re.search(r"(?<!Matins )Gospel Reading\s*[-–:]\s*([^\n]+)", block, flags=re.I)
        fasting_code = parse_goarch_fasting_code(block)
        if not ep or not go:
            return SourceResult("goarch", cfg["role"], url, "partial", target.isoformat(), ep.group(1).strip() if ep else None, go.group(1).strip() if go else None, fasting_code=fasting_code)
        return SourceResult("goarch", cfg["role"], url, "current", target.isoformat(), ep.group(1).strip(), go.group(1).strip(), fasting_code=fasting_code)
    except Exception as exc:
        return SourceResult("goarch", cfg["role"], url, "unavailable", note=str(exc))


def verify_jerusalem_fixed_feast(data: dict[str, Any]) -> tuple[list[str], str]:
    rules_path = ROOT / "canonical" / "jerusalem_fixed_feasts.json"
    rules = load_json(rules_path)
    julian = data.get("julian_date", {})
    try:
        key = f"{int(julian.get('month')):02d}-{int(julian.get('day')):02d}"
    except Exception:
        return ["Daily data has no valid Julian month/day for Jerusalem feast verification"], "invalid_date"
    expected = rules.get("feasts", {}).get(key)
    if not expected:
        return [], "not_a_pinned_fixed_feast"
    actual = str(data.get("feast", {}).get("ar") or "").strip()
    if actual != expected:
        return [f"Jerusalem fixed-feast mismatch for {key}: expected {expected!r}, got {actual!r}"], "conflict"
    return [], "verified"


def source_refs_from_data(data: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for reading in data.get("readings", []):
        kind = reading.get("kind")
        if kind in {"epistle", "gospel"}:
            ref = reading.get("reference", {}).get("en") or reading.get("reference", {}).get("el")
            if isinstance(ref, str) and ref.strip(): result[kind] = ref.strip()
    if set(result) != {"epistle", "gospel"}:
        raise RuntimeError("Generated data is missing epistle or gospel reference")
    return result


def compare_source(primary: dict[str, str], source: SourceResult) -> dict[str, Any]:
    comparison: dict[str, Any] = {"source": source.id, "status": source.status, "matches": {}, "conflicts": []}
    if source.status != "current": return comparison
    for kind in ("epistle", "gospel"):
        candidate = getattr(source, kind)
        if not candidate: continue
        try:
            pnorm, _ = parse_reference(primary[kind]); cnorm, _ = parse_reference(candidate)
            matched = pnorm == cnorm
            comparison["matches"][kind] = matched
            if not matched: comparison["conflicts"].append({"kind": kind, "primary": primary[kind], "candidate": candidate, "primary_normalized": pnorm, "candidate_normalized": cnorm})
        except Exception as exc:
            comparison["matches"][kind] = False; comparison["conflicts"].append({"kind": kind, "error": str(exc), "candidate": candidate})
    return comparison


def load_update_module():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("update_liturgical_integrity", path)
    if spec is None or spec.loader is None: raise RuntimeError("Cannot load update_liturgical_data.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def _verified_translation_body(reading: dict[str, Any], lang: str, canonical_ref: str) -> str:
    """Return a translation only when independent exact verification metadata matches it."""
    body = str(reading.get("body", {}).get(lang) or "").strip()
    if not body:
        return ""
    verification = reading.get("translation_verification", {}).get(lang, {})
    if not isinstance(verification, dict):
        return ""
    if verification.get("status") != "VERIFIED_EXACT_TRANSLATION":
        return ""
    if verification.get("canonical_reference") not in (None, "", canonical_ref):
        return ""
    if verification.get("body_sha256") != sha256_text(body):
        return ""
    if verification.get("ai_translation_used") is not False:
        return ""
    if not str(verification.get("source") or "").strip():
        return ""
    return body


def _lock_unverified_translations(reading: dict[str, Any], canonical_ref: str) -> None:
    """Fail closed: never publish a Scripture translation without exact provenance."""
    body = reading.setdefault("body", {})
    verification = reading.setdefault("translation_verification", {})
    for lang in ("en", "el"):
        verified = _verified_translation_body(reading, lang, canonical_ref)
        body[lang] = verified
        if not verified:
            verification[lang] = {
                "status": "UNAVAILABLE_UNTIL_INDEPENDENT_VERIFICATION",
                "canonical_reference": canonical_ref,
                "ai_translation_used": False,
            }


def _native_source_display_language(selected_source: str | None, raw_reference: str) -> str | None:
    """Return the one display lane proven by the selected reference source."""
    source = str(selected_source or "")
    if source in {"orthodox_jordan", "antioch_patriarchate"} and re.search(r"[\u0600-\u06ff]", raw_reference):
        return "ar"
    if source in {"official_greek_orthodox", "orthodox_church_in_america"} and re.search(r"[A-Za-z]", raw_reference):
        return "en"
    # Jerusalem fixed-feast records and internal canonical registries establish
    # the canonical passage, but they do not automatically license a displayed
    # native-language reference in another lane.
    return None


def prepare_native_corpus_readings(
    readings: list[dict[str, Any]],
    epistle_reference: str,
    gospel_reference: str,
    selected_source: str | None,
) -> list[dict[str, Any]]:
    """Keep canonical references while publishing no translated discovery text."""
    output = copy.deepcopy(readings)
    mapping = {"epistle": epistle_reference, "gospel": gospel_reference}
    for reading in output:
        kind = str(reading.get("kind") or "")
        if kind not in {"prokeimenon", "epistle", "gospel"}:
            continue
        references = {"ar": "", "en": "", "el": ""}
        canonical_reference = ""
        raw_reference = str(mapping.get(kind) or "")
        if kind in mapping:
            canonical_reference, _ = parse_reference(raw_reference)
            display_language = _native_source_display_language(selected_source, raw_reference)
            if display_language:
                references[display_language] = raw_reference
        reading["reference"] = references
        reading["body"] = {"ar": "", "en": "", "el": ""}
        reading["source"] = {"ar": "", "en": "", "el": ""}
        reading["translation_locked"] = True
        reading.pop("translation_verification", None)
        reading.pop("native_source_verification", None)
        reading.pop("publication_status", None)
        reading.pop("discovery_text", None)
        reading["integrity"] = {
            "status": "OFFICIAL_REFERENCE_RESOLVED_NATIVE_TEXT_PENDING",
            "canonical_reference": canonical_reference,
            "selected_source": selected_source,
            "display_text_changed": False,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        }
    return output


def inject_canonical_readings(
    readings: list[dict[str, Any]],
    bible: dict[str, Any],
    canonical_meta: dict[str, Any],
    *,
    allow_network: bool = True,
) -> list[dict[str, Any]]:
    if canonical_meta.get("mode") == "PER_LANGUAGE_OFFICIAL_NATIVE_CORPUS_ONLY":
        # Native corpora are filled by fill_daily_from_native_corpora.py after
        # official canonical references have been resolved. Never use the
        # quarantined legacy Arabic snapshots in this mode.
        return copy.deepcopy(readings)
    output = copy.deepcopy(readings)
    minimum_ratio = float(canonical_meta["vocalized_source"]["requirements"]["minimum_arabic_diacritic_ratio"])
    snapshots = load_verified_scripture_snapshots()
    for reading in output:
        kind = reading.get("kind")
        if kind not in {"epistle", "gospel"}:
            continue
        ref = reading.get("reference", {}).get("en") or reading.get("reference", {}).get("el")
        canonical_ref, spans = parse_reference(ref)
        snapshot_item = snapshots.get(canonical_ref)
        if snapshot_item:
            vocalized_body, vocalized_evidence, chapter_sources = scripture_snapshot_body(snapshot_item)
            source_mode = "PINNED_EXACT_SNAPSHOT"
        else:
            if not allow_network:
                raise RuntimeError(f"No pinned exact vocalized Scripture snapshot for {canonical_ref}")
            vocalized_body, vocalized_evidence, chapter_sources = fetch_vocalized_verses(
                spans, canonical_meta, allow_network=True
            )
            source_mode = "LIVE_EBIBLE_EXACT"

        actual_text = "\n".join(line.split(" ", 1)[1] for line in vocalized_body.splitlines())
        metrics = diacritic_metrics(actual_text)
        if metrics["diacritic_ratio"] < minimum_ratio:
            raise RuntimeError(
                f"Vocalized Scripture ratio {metrics['diacritic_ratio']:.3f} below {minimum_ratio:.3f} for {canonical_ref}"
            )

        independent_base_checked = False
        base_text_sha: str | None = None
        if bible:
            base_body, _ = extract_verses(bible, spans)
            base_text = "\n".join(line.split(" ", 1)[1] for line in base_body.splitlines())
            errors = verify_vocalized_against_base(base_text, actual_text, minimum_ratio)
            if errors:
                raise RuntimeError(f"Independent Bible word check failed for {canonical_ref}: {'; '.join(errors)}")
            independent_base_checked = True
            base_text_sha = sha256_text(base_body)

        reading.setdefault("reference", {})["ar"] = reference_display_ar(spans)
        reading.setdefault("body", {})["ar"] = vocalized_body
        _lock_unverified_translations(reading, canonical_ref)
        reading["translation_locked"] = True
        reading["source"] = {
            "ar": f"نص كتابي عربي مشكول مأخوذ حرفيًا من {canonical_meta['name_ar']} على eBible؛ لا توجد ترجمة أو إعادة صياغة آلية.",
            "en": "Exact vocalized Arabic Van Dyck verses from eBible; no AI translation or rewriting.",
            "el": "Exact vocalized Arabic Bible verses; no AI translation or rewriting.",
        }
        reading["integrity"] = {
            "status": "VERIFIED_EXACT_VOCALIZED",
            "canonical_reference": canonical_ref,
            "canonical_id": canonical_meta["id"],
            "canonical_revision": canonical_meta["pinned_revision"],
            "canonical_file_sha256": canonical_meta.get("file_sha256"),
            "source_mode": source_mode,
            "base_text_sha256": base_text_sha,
            "vocalized_text_sha256": sha256_text(vocalized_body),
            "body_sha256": sha256_text(vocalized_body),
            "words_unchanged_after_stripping": True,
            "independent_base_checked": independent_base_checked,
            **metrics,
            "verses": vocalized_evidence,
            "chapter_sources": chapter_sources,
            "ai_translation_used": False,
        }
    return output

def rebuild_services(data: dict[str, Any], today_readings: list[dict[str, Any]], next_readings: list[dict[str, Any]]) -> None:
    update = load_update_module()
    day = datetime.strptime(data["date_iso"], "%Y-%m-%d").date(); info = update.day_info(day)
    ns = update.next_sunday(day); ns_info = update.day_info(ns)
    services = [
        update.build_liturgy_service("divine_liturgy", day, info, today_readings, "خدمة اليوم"),
        update.build_daily_aware_service("vespers", day, info, today_readings),
        update.build_daily_aware_service("orthros", day, info, today_readings),
        update.build_daily_aware_service("morning_prayer", day, info, today_readings),
        update.build_daily_aware_service("evening_prayer", day, info, today_readings),
        update.build_daily_aware_service("small_compline", day, info, today_readings),
        update.build_liturgy_service("next_sunday_full_liturgy", ns, ns_info, next_readings, "الأحد القادم"),
    ]
    for service in services:
        service["integrity"] = {"status": "VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED", "date_iso": service.get("dynamic_date"), "dynamic_texts": "OFFICIAL_SOURCE_VERIFIED", "scripture": "VERIFIED_EXACT_VOCALIZED", "static_service_scope": service.get("source_provenance", {}).get("status", "UNDECLARED"), "ai_scripture_translation_used": False}
    data["services"] = services
    # Rebuilds must preserve complete Arabic/English/Greek UI metadata.
    update.complete_daily_localizations(data)


def synchronize_outputs(data: dict[str, Any]) -> None:
    day = data["date_iso"]
    for path in [TODAY_PATH, ROOT / "data" / "calendar" / f"{day}.json", ASSET_PATH]:
        write_json(path, data)
    manifest_path = ROOT / "data" / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    manifest["schema_version"] = max(int(manifest.get("schema_version") or 0), 5)
    manifest["integrity"] = {
        "status": data.get("integrity", {}).get("status"),
        "canonical_id": data.get("integrity", {}).get("canonical_id"),
        "canonical_revision": data.get("integrity", {}).get("canonical_revision"),
        "ai_scripture_translation_used": False,
    }
    write_json(manifest_path, manifest)


def object_contains_text(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(object_contains_text(child, needle) for child in value.values())
    if isinstance(value, list):
        return any(object_contains_text(child, needle) for child in value)
    return False


def verify_existing(data: dict[str, Any], bible: dict[str, Any], canonical_meta: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if canonical_meta.get("mode") == "PER_LANGUAGE_OFFICIAL_NATIVE_CORPUS_ONLY":
        if data.get("integrity", {}).get("status") != "VERIFIED_OFFICIAL_SOURCES":
            errors.append("top-level integrity status is not VERIFIED_OFFICIAL_SOURCES")
        publication = data.get("publication", {})
        if publication.get("status") != "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED":
            errors.append("publication status is not AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED")
        if publication.get("fail_closed") is not True:
            errors.append("publication is not fail-closed")
        if publication.get("same_language_fallback_only") is not True:
            errors.append("publication does not require same-language fallback only")
        if data.get("machine_translation_used") is not False:
            errors.append("machine translation flag must be false")
        if data.get("automatic_diacritization_used") is not False:
            errors.append("automatic diacritization flag must be false")
        reading_sets: list[tuple[str, list[dict[str, Any]]]] = [("today", data.get("readings", []))]
        next_readings = data.get("integrity_inputs", {}).get("next_sunday", {}).get("readings")
        if isinstance(next_readings, list):
            reading_sets.append(("next_sunday", next_readings))
        else:
            errors.append("integrity_inputs.next_sunday.readings is missing")
        for label, readings in reading_sets:
            for reading in readings:
                if reading.get("kind") not in {"epistle", "gospel"}:
                    continue
                kind = f"{label}.{reading.get('kind')}"
                canonical_reference = str(reading.get("integrity", {}).get("canonical_reference") or "")
                if not canonical_reference:
                    errors.append(f"{kind} has no canonical reference")
                    continue
                if not re.fullmatch(r"[1-3]?[A-Z]+\.\d+\.\d+(?:-(?:\d+\.)?\d+)?", canonical_reference):
                    errors.append(f"{kind} canonical reference is invalid: {canonical_reference!r}")
                for language in ("ar", "en", "el"):
                    if str(reading.get("body", {}).get(language) or "").strip():
                        errors.append(f"{kind}.{language} contains text before native-corpus verification")
                if reading.get("translation_locked") is not True:
                    errors.append(f"{kind} is not translation_locked")
        return errors
    if data.get("integrity", {}).get("status") != "VERIFIED_OFFICIAL_SOURCES":
        errors.append("top-level integrity status is not VERIFIED_OFFICIAL_SOURCES")
    if data.get("publication", {}).get("status") != "AUTOMATIC_OFFICIAL_SOURCES_VERIFIED":
        errors.append("publication status is not AUTOMATIC_OFFICIAL_SOURCES_VERIFIED")
    if data.get("publication", {}).get("human_review_required") is not False:
        errors.append("publication unexpectedly requires human review")
    if data.get("integrity", {}).get("canonical_id") != canonical_meta["id"]:
        errors.append("top-level canonical id does not match policy")
    if data.get("integrity", {}).get("ai_scripture_translation_used") is not False:
        errors.append("top-level data does not explicitly disable AI Scripture translation")

    reading_sets: list[tuple[str, list[dict[str, Any]]]] = [("today", data.get("readings", []))]
    next_readings = data.get("integrity_inputs", {}).get("next_sunday", {}).get("readings")
    if isinstance(next_readings, list):
        reading_sets.append(("next_sunday", next_readings))
    else:
        errors.append("integrity_inputs.next_sunday.readings is missing")

    snapshots = load_verified_scripture_snapshots()
    expected_bodies: list[tuple[str, str]] = []
    minimum_ratio = float(canonical_meta["vocalized_source"]["requirements"]["minimum_arabic_diacritic_ratio"])
    for label, readings in reading_sets:
        for reading in readings:
            if reading.get("kind") not in {"epistle", "gospel"}:
                continue
            kind = f"{label}.{reading.get('kind')}"
            try:
                ref = reading.get("reference", {}).get("en") or reading.get("reference", {}).get("el") or ""
                canonical_ref, spans = parse_reference(ref)
                actual = reading.get("body", {}).get("ar") or ""
                expected_bodies.append((kind, actual))
                snapshot = snapshots.get(canonical_ref)
                if snapshot:
                    expected, expected_verses, _ = scripture_snapshot_body(snapshot)
                    if actual != expected:
                        errors.append(f"{kind} differs byte-for-byte from pinned exact Scripture snapshot")
                    if reading.get("integrity", {}).get("verses") != expected_verses:
                        errors.append(f"{kind} verse hashes differ from pinned snapshot")
                elif not bible:
                    errors.append(f"{kind} has neither a pinned snapshot nor an independent base cache")

                actual_text = "\n".join(line.split(" ", 1)[1] for line in actual.splitlines() if " " in line)
                metrics = diacritic_metrics(actual_text)
                if metrics["diacritic_ratio"] < minimum_ratio:
                    errors.append(f"{kind} diacritic ratio is below minimum")

                integ = reading.get("integrity", {})
                if integ.get("status") != "VERIFIED_EXACT_VOCALIZED":
                    errors.append(f"{kind} integrity status is not VERIFIED_EXACT_VOCALIZED")
                if integ.get("canonical_reference") != canonical_ref:
                    errors.append(f"{kind} canonical reference differs from parsed reference")
                if integ.get("canonical_id") != canonical_meta["id"]:
                    errors.append(f"{kind} canonical id mismatch")
                if integ.get("body_sha256") != sha256_text(actual):
                    errors.append(f"{kind} body SHA-256 mismatch")
                if integ.get("ai_translation_used") is not False:
                    errors.append(f"{kind} does not explicitly disable AI translation")
                if reading.get("translation_locked") is not True:
                    errors.append(f"{kind} is not translation_locked")
                for lang in ("en", "el"):
                    translated = str(reading.get("body", {}).get(lang) or "").strip()
                    verified = _verified_translation_body(reading, lang, canonical_ref)
                    if translated and translated != verified:
                        errors.append(f"{kind}.{lang} is present without exact independent translation verification")
            except Exception as exc:
                errors.append(f"{kind} verification error: {exc}")

    service_map = {service.get("id"): service for service in data.get("services", []) if isinstance(service, dict) and service.get("id")}
    for service_id, service in service_map.items():
        if service.get("integrity", {}).get("ai_scripture_translation_used") is not False:
            errors.append(f"{service_id} does not explicitly disable AI Scripture translation")
    today_service = service_map.get("divine_liturgy", {})
    sunday_service = service_map.get("next_sunday_full_liturgy", {})
    for kind, body in expected_bodies:
        target_service = sunday_service if kind.startswith("next_sunday.") else today_service
        if body and not object_contains_text(target_service, body):
            errors.append(f"{kind} exact vocalized body is not present in its generated liturgy service")
    return errors

def _official_evidence_from_result(result: SourceResult, priority: int, official_id: str | None = None) -> OfficialEvidence:
    digest = None
    if result.note and result.note.startswith("sha256="):
        digest = result.note.split("=", 1)[1]
    return OfficialEvidence(
        official_id or result.id,
        priority,
        True,
        result.url,
        result.status,
        result.date_iso,
        result.epistle,
        result.gospel,
        sha256=digest,
        reason=result.note,
    )




def _pinned_jordan_calendar_evidence(target: date, policy: dict[str, Any]) -> OfficialEvidence | None:
    """Resolve a date from the pinned official Jordan calendar contract.

    The Jordan daily webpage is sometimes stale or contains placeholder content.
    A pinned record is accepted only when it chains an official Jordan day
    classification to the already-pinned Orthodox Sunday-cycle references.
    It never creates or translates Scripture text.
    """
    contract_path = ROOT / str(policy.get("reference_policy", {}).get(
        "local_contract", "canonical/jordan_liturgical_contract.json"
    ))
    if not contract_path.is_file():
        return None
    registry = load_json(contract_path)
    entry = registry.get("records", {}).get(target.isoformat())
    if not isinstance(entry, dict):
        return None
    epistle = str(entry.get("epistle_reference") or "").strip()
    gospel = str(entry.get("gospel_reference") or "").strip()
    if not epistle or not gospel:
        return OfficialEvidence(
            "orthodox_jordan", 1, True, str(contract_path.relative_to(ROOT)),
            "partial", target.isoformat(), reason="سجل الأردن المثبت لا يحتوي مرجعي الرسالة والإنجيل كاملين."
        )
    try:
        ep_canonical, _ = parse_reference(epistle)
        go_canonical, _ = parse_reference(gospel)
    except Exception as exc:
        return OfficialEvidence(
            "orthodox_jordan", 1, True, str(contract_path.relative_to(ROOT)),
            "invalid", target.isoformat(), reason=f"مرجع غير صالح في عقد الأردن: {exc}"
        )
    if ep_canonical != entry.get("epistle_canonical") or go_canonical != entry.get("gospel_canonical"):
        return OfficialEvidence(
            "orthodox_jordan", 1, True, str(contract_path.relative_to(ROOT)),
            "conflict", target.isoformat(), reason="البصمة القانونية للمرجع لا تطابق عقد الأردن المثبت."
        )
    chain = entry.get("authority_chain")
    if not isinstance(chain, list) or not any(
        isinstance(item, dict) and item.get("id") == "orthodox_jordan_2026_calendar" for item in chain
    ):
        return OfficialEvidence(
            "orthodox_jordan", 1, True, str(contract_path.relative_to(ROOT)),
            "invalid", target.isoformat(), reason="عقد الأردن لا يحتوي سلسلة إثبات محلية رسمية."
        )
    source = next(
        (item for item in chain if isinstance(item, dict) and item.get("id") == "orthodox_jordan_2026_calendar"),
        {},
    )
    return OfficialEvidence(
        "orthodox_jordan", 1, True, str(source.get("url") or contract_path.relative_to(ROOT)),
        "current", target.isoformat(), epistle, gospel,
        sha256=sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True)),
        reason=(
            f"قفل الأردن المثبت: {entry.get('day_label_ar', target.isoformat())}; "
            "تصنيف اليوم من التقويم الأردني الرسمي والمرجعان من دورة الأحد الأرثوذكسية المثبتة."
        ),
    )


def _fixed_feast_evidence(target: date, policy: dict[str, Any]) -> OfficialEvidence:
    update = load_update_module()
    info = update.day_info(target)
    key = f"{int(info['julian_month']):02d}-{int(info['julian_day']):02d}"
    registry_path = ROOT / "canonical" / "jerusalem_fixed_feast_lectionary.json"
    registry = load_json(registry_path)
    entry = registry.get("feasts", {}).get(key)
    cfg = policy["sources"]["jerusalem_patriarchate"]
    if not entry:
        return OfficialEvidence(
            "jerusalem_patriarchate", 2, True, cfg["url"], "not_applicable", target.isoformat(),
            reason=f"لا يوجد عيد ثابت مثبت لليوم اليولياني {key}."
        )
    actual_feast = str(info.get("feast_ar") or "").strip()
    expected_feast = str(entry.get("name_ar") or "").strip()
    if actual_feast != expected_feast:
        return OfficialEvidence(
            "jerusalem_patriarchate", 2, True, cfg["url"], "conflict", target.isoformat(),
            reason=f"تعارض اسم العيد في تقويم القدس: المتوقع {expected_feast!r} والمولد {actual_feast!r}."
        )
    prok = entry.get("prokeimenon", {})
    prok_body = "\n".join(x for x in [prok.get("verse"), prok.get("stich")] if x)
    return OfficialEvidence(
        "jerusalem_patriarchate", 2, True, cfg["url"], "current", target.isoformat(),
        entry.get("epistle_reference"), entry.get("gospel_reference"),
        prokeimenon_text=prok_body or None,
        sha256=sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True)),
        reason=f"مطابقة العيد الثابت للتاريخ اليولياني {key}; السجل: canonical/jerusalem_fixed_feast_lectionary.json"
    )


def _sunday_cycle_number(target: date) -> int | None:
    if target.weekday() != 6:
        return None
    update = load_update_module()
    pascha = update.orthodox_pascha_gregorian(target.year)
    pentecost = pascha + update.timedelta(days=49)
    if target <= pentecost:
        return None
    return (target - pentecost).days // 7


def _official_sunday_cycle_evidence(target: date, policy: dict[str, Any]) -> OfficialEvidence:
    cfg = policy["sources"]["official_greek_orthodox"]
    number = _sunday_cycle_number(target)
    if number is None:
        return OfficialEvidence(
            "official_greek_orthodox", 4, True, cfg["url_template"].format(month=target.month, year=target.year),
            "not_applicable", target.isoformat(), reason="اليوم ليس أحدًا صالحًا لسجل آحاد ما بعد العنصرة."
        )
    registry = load_json(ROOT / "canonical" / "orthodox_sunday_lectionary.json")
    entry = registry.get("sundays", {}).get(str(number))
    if not entry:
        return OfficialEvidence(
            "official_greek_orthodox", 4, True, cfg["url_template"].format(month=target.month, year=target.year),
            "unavailable", target.isoformat(), reason=f"لا يوجد سجل مثبت للأحد رقم {number} بعد العنصرة."
        )
    source = entry.get("source", {})
    return OfficialEvidence(
        "official_greek_orthodox", 4, True, source.get("url") or cfg["url_template"].format(month=target.month, year=target.year),
        "current", target.isoformat(), entry.get("epistle_reference"), entry.get("gospel_reference"),
        tone=entry.get("tone"),
        sha256=sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True)),
        reason=f"سجل أرثوذكسي مثبت للأحد رقم {number} بعد العنصرة، بعد فحص عدم وجود عيد ثابت في تقويم القدس."
    )



def _pinned_weekday_lectionary_evidence(target: date, policy: dict[str, Any]) -> OfficialEvidence:
    cfg = policy["sources"]["orthodox_church_in_america"]
    registry = load_json(ROOT / str(cfg["registry"]))
    entry = registry.get("dates", {}).get(target.isoformat())
    url = cfg["url_template"].format(year=target.year, month=target.month, day=target.day)
    if not entry:
        return OfficialEvidence(
            "orthodox_church_in_america", 5, True, url, "unavailable", target.isoformat(),
            reason="لا يوجد سجل يومي رسمي مثبت لهذا التاريخ."
        )
    chain = entry.get("authority_chain")
    if isinstance(chain, list):
        ids = {str(item.get("id")) for item in chain if isinstance(item, dict)}
        required = {"orthodox_jordan_2026_calendar", "goarch_digital_chant_stand", "orthodox_church_in_america"}
        if not required.issubset(ids):
            return OfficialEvidence(
                "orthodox_church_in_america", 5, True, str(entry.get("url") or url), "invalid", target.isoformat(),
                reason="سجل اليوم المثبت لا يحتوي سلسلة التحقق الثلاثية المطلوبة."
            )
    return OfficialEvidence(
        "orthodox_church_in_america", 5, True, str(entry.get("goarch_dcs_url") or entry.get("url") or url), "current", target.isoformat(),
        entry.get("epistle_reference"), entry.get("gospel_reference"),
        sha256=sha256_text(json.dumps(entry, ensure_ascii=False, sort_keys=True)),
        reason=str(entry.get("note_ar") or "سجل يومي رسمي مثبت مع مطابقة مستقلة للتقويم القديم."),
    )

def _calendar_compatible_antioch(target: date, raw: OfficialEvidence, fixed: OfficialEvidence, greek_cycle: OfficialEvidence) -> OfficialEvidence:
    """Keep Antioch at priority 3 without importing a new-calendar override.

    The Paschal Sunday cycle is shared, but fixed feasts can fall on a different
    civil date. For a fixed Jerusalem feast Antioch is comparison-only. For an
    ordinary Sunday it is publishable only when it exactly matches the pinned
    Orthodox Sunday-cycle references.
    """
    if fixed.status == "current":
        raw.status = "calendar_incompatible"
        raw.reason = "المصدر الأنطاكي الرسمي يستخدم تاريخًا مدنيًا مختلفًا للعيد الثابت؛ استُبعد من الاختيار وبقي للمقارنة فقط."
        return raw
    if target.weekday() == 6 and greek_cycle.status == "current":
        if raw.status == "current" and raw.epistle_reference and raw.gospel_reference:
            try:
                raw_ep, _ = parse_reference(raw.epistle_reference)
                raw_go, _ = parse_reference(raw.gospel_reference)
                cyc_ep, _ = parse_reference(greek_cycle.epistle_reference or "")
                cyc_go, _ = parse_reference(greek_cycle.gospel_reference or "")
                if (raw_ep, raw_go) == (cyc_ep, cyc_go):
                    raw.reason = "مرجع أنطاكية يطابق دورة الأحد الأرثوذكسية المتوافقة تقويميًا."
                    return raw
            except Exception:
                pass
        raw.status = "calendar_incompatible"
        raw.reason = "قراءات الدليل الأنطاكي المدني لا تطابق دورة الأحد المعتمدة لتقويم القدس في هذا التاريخ."
        return raw
    raw.status = "calendar_incompatible"
    raw.reason = "لا يمكن إثبات توافق التاريخ المدني الأنطاكي مع اليوم اليولياني لتقويم القدس آليًا."
    return raw


def resolve_official_date(target: date, policy: dict[str, Any], *, allow_network: bool) -> tuple[Any, list[OfficialEvidence]]:
    jordan_cfg = policy["sources"]["orthodox_jordan"]
    pinned_jordan = _pinned_jordan_calendar_evidence(target, policy)
    pinned_weekday = _pinned_weekday_lectionary_evidence(target, policy)
    trusted_pinned_date = (
        pinned_jordan is not None and pinned_jordan.status == "current"
    ) or pinned_weekday.status == "current"
    live_jordan: OfficialEvidence | None = None
    if allow_network and not trusted_pinned_date:
        jordan_result = fetch_orthodox_jordan(target, jordan_cfg)
        live_jordan = _official_evidence_from_result(jordan_result, 1)

    # A current, parseable live Jordan page wins. When that page is stale,
    # poisoned, unavailable, or undated, a date-specific pinned Jordan calendar
    # record may replace it. Without either proof the local lane remains blocked
    # and the resolver may use lower sources only for dates not covered by a
    # mandatory local record.
    if live_jordan is not None and live_jordan.publishable_for(("epistle_reference", "gospel_reference")):
        if pinned_jordan is not None:
            try:
                live_pair = (parse_reference(live_jordan.epistle_reference or "")[0], parse_reference(live_jordan.gospel_reference or "")[0])
                pinned_pair = (parse_reference(pinned_jordan.epistle_reference or "")[0], parse_reference(pinned_jordan.gospel_reference or "")[0])
            except Exception as exc:
                jordan = OfficialEvidence(
                    "orthodox_jordan", 1, True, live_jordan.url, "conflict", target.isoformat(),
                    reason=f"تعذر مقارنة صفحة الأردن الحية بعقد الأردن المثبت: {exc}"
                )
            else:
                if live_pair != pinned_pair:
                    jordan = OfficialEvidence(
                        "orthodox_jordan", 1, True, live_jordan.url, "conflict", target.isoformat(),
                        reason=f"تعارض صفحة الأردن الحية مع عقد اليوم المثبت: live={live_pair}, pinned={pinned_pair}."
                    )
                else:
                    jordan = live_jordan
                    jordan.reason = (jordan.reason or "") + " طابقت صفحة الأردن الحية عقد اليوم الأردني المثبت."
        else:
            jordan = live_jordan
    elif pinned_jordan is not None:
        jordan = pinned_jordan
        if live_jordan is not None:
            jordan.reason = (jordan.reason or "") + f" تعذر الاعتماد على الصفحة الحية: {live_jordan.status}; {live_jordan.reason or 'لا سبب إضافي'}."
    elif live_jordan is not None:
        jordan = live_jordan
    else:
        jordan = OfficialEvidence(
            "orthodox_jordan", 1, True, jordan_cfg["url"], "offline", target.isoformat(),
            reason="لا يوجد اتصال ولا سجل أردني مثبت لهذا التاريخ."
        )

    jerusalem = _fixed_feast_evidence(target, policy)
    greek_cycle = _official_sunday_cycle_evidence(target, policy)

    if allow_network and not trusted_pinned_date:
        antioch_raw = fetch_antioch_guide(target, policy["sources"]["antioch_patriarchate"], allow_network=True)
        antioch = _calendar_compatible_antioch(target, antioch_raw, jerusalem, greek_cycle)
    else:
        antioch_cfg = policy["sources"]["antioch_patriarchate"]
        antioch = OfficialEvidence(
            "antioch_patriarchate", 3, True, str(antioch_cfg.get("registry")), "offline", target.isoformat(),
            reason="لم يُفحص الدليل السنوي في الوضع غير المتصل."
        )

    # Use the official DCS *regular-cycle* endpoint for ordinary weekdays.
    # It explicitly separates the movable Byzantine cycle from civil-date fixed
    # feasts, so a new-calendar feast can never override Jordan/Jerusalem usage.
    if allow_network and not trusted_pinned_date:
        regular_result = fetch_goarch_regular_cycle(target, policy["sources"]["official_greek_orthodox"])
        regular_cycle = _official_evidence_from_result(regular_result, 4, "official_greek_orthodox")
    else:
        regular_cycle = OfficialEvidence(
            "official_greek_orthodox", 4, True,
            str(policy["sources"]["official_greek_orthodox"].get("regular_cycle_url_template") or ""),
            "offline", target.isoformat(), reason="لم تُفحص منصة DCS الرسمية في الوضع غير المتصل."
        )

    # On Sundays the pinned Sunday-cycle record is authoritative and the live
    # DCS pair is an independent consistency check. A disagreement blocks.
    if target.weekday() == 6 and greek_cycle.status == "current":
        if regular_cycle.status == "current":
            try:
                pinned_pair = (parse_reference(greek_cycle.epistle_reference or "")[0], parse_reference(greek_cycle.gospel_reference or "")[0])
                live_pair = (parse_reference(regular_cycle.epistle_reference or "")[0], parse_reference(regular_cycle.gospel_reference or "")[0])
            except Exception as exc:
                greek = OfficialEvidence("official_greek_orthodox", 4, True, regular_cycle.url, "conflict", target.isoformat(), reason=f"تعذر فحص توافق دورة الأحد مع DCS: {exc}")
            else:
                if pinned_pair != live_pair:
                    greek = OfficialEvidence("official_greek_orthodox", 4, True, regular_cycle.url, "conflict", target.isoformat(), reason=f"تعارض دورة الأحد المثبتة مع DCS: pinned={pinned_pair}, live={live_pair}")
                else:
                    greek = greek_cycle
                    greek.url = regular_cycle.url
                    greek.sha256 = regular_cycle.sha256
                    greek.reason = (greek.reason or "") + " وطابقت منصة DCS الرسمية."
        else:
            greek = greek_cycle
    elif jerusalem.status == "current":
        # Fixed Jerusalem feast remains priority 2. Keep DCS only as comparison
        # evidence and never let it override the old-calendar feast.
        greek = regular_cycle
        if greek.status == "current":
            greek.status = "comparison_only"
            greek.reason = "قراءة الدورة العادية متاحة للمقارنة، لكن عيد القدس الثابت هو المرجع الأعلى لهذا اليوم."
    else:
        greek = regular_cycle

    oca = pinned_weekday
    evidence = [jordan, jerusalem, antioch, greek, oca]
    return strict_resolve(evidence), evidence

def apply_prokeimenon(
    readings: list[dict[str, Any]],
    tone: int | None,
    *,
    exact_text: str | None = None,
    selected_source: str | None = None,
) -> None:
    prok = next((item for item in readings if item.get("kind") == "prokeimenon"), None)
    if not isinstance(prok, dict):
        raise RuntimeError("Generated readings have no prokeimenon slot")

    if exact_text:
        lines = [line.strip() for line in exact_text.splitlines() if line.strip()]
        prok["title"] = {"ar": "البروكيمنن", "en": "Prokeimenon", "el": "Προκείμενον"}
        prok["reference"] = {
            "ar": prok.get("reference", {}).get("ar") or "نص العيد المثبت",
            "en": "Pinned feast prokeimenon",
            "el": "Pinned feast prokeimenon",
        }
        prok["body"] = {"ar": "\n".join(lines), "en": "", "el": ""}
        prok["translation_locked"] = True
        prok["source"] = {
            "ar": "النص الكامل مثبت في سجل العيد الرسمي المتوافق مع تقويم القدس.",
            "en": "Exact pinned feast text compatible with Jerusalem old-calendar usage.",
            "el": "Exact pinned feast text compatible with Jerusalem old-calendar usage.",
        }
        prok["integrity"] = {
            "status": "VERIFIED_PINNED_LITURGICAL_TEXT",
            "registry": "canonical/jerusalem_fixed_feast_lectionary.json",
            "selected_source": selected_source,
            "body_sha256": sha256_text("\n".join(lines)),
            "ai_translation_used": False,
        }
        prok.pop("publication_status", None)
        return

    if tone is None:
        raise RuntimeError("Exact prokeimenon text or an officially established tone is required")
    registry = load_json(ROOT / "canonical" / "sunday_prokeimena.json")
    item = registry.get("tones", {}).get(str(tone))
    if not item:
        raise RuntimeError(f"No pinned exact prokeimenon for tone {tone}")
    body = f"{item['verse']}\n{item['stich']}"
    prok["title"] = {"ar": f"البروكيمنن — اللحن {tone}", "en": f"Prokeimenon — Tone {tone}", "el": f"Προκείμενον — Ἦχος {tone}"}
    prok["reference"] = {"ar": f"اللحن {tone}", "en": f"Tone {tone}", "el": f"Ἦχος {tone}"}
    prok["body"] = {"ar": body, "en": "", "el": ""}
    prok["translation_locked"] = True
    prok["source"] = {
        "ar": "النص الثابت للبروكيمنن مأخوذ من سجل الألحان المثبت؛ رقم اللحن محدد من دورة الأحد الأرثوذكسية الرسمية.",
        "en": "Pinned standard Octoechos text; the tone is established by the official Orthodox Sunday cycle.",
        "el": "Pinned standard Octoechos text with officially established daily tone.",
    }
    prok["integrity"] = {
        "status": "VERIFIED_PINNED_LITURGICAL_TEXT",
        "registry": "canonical/sunday_prokeimena.json",
        "tone": tone,
        "selected_source": selected_source,
        "body_sha256": sha256_text(body),
        "ai_translation_used": False,
    }
    prok.pop("publication_status", None)

def build_report(data: dict[str, Any], canonical_meta: dict[str, Any], evidence: list[OfficialEvidence], errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "date_iso": data["date_iso"],
        "generated_at": datetime.now(TZ).isoformat(),
        "jurisdiction": "Greek Orthodox Patriarchate of Jerusalem — Jordan priority",
        "decision": "PUBLISH" if not errors else "BLOCK",
        "canonical_scripture": canonical_meta,
        "source_priority": ["orthodox_jordan", "jerusalem_patriarchate", "antioch_patriarchate", "official_greek_orthodox", "orthodox_church_in_america"],
        "sources": [asdict(item) for item in evidence],
        "publication": data.get("publication"),
        "readings": [
            {"kind": r.get("kind"), "reference_ar": r.get("reference", {}).get("ar"), "reference_en": r.get("reference", {}).get("en"), "integrity": r.get("integrity")}
            for r in data.get("readings", [])
        ],
        "warnings": warnings,
        "errors": errors,
        "guarantees": {
            "scripture_ai_translation": False,
            "liturgical_ai_translation": False,
            "exact_word_match_after_diacritic_normalization": not errors,
            "official_priority_enforced": True,
            "generic_guidance_cannot_replace_missing_text": True,
            "human_daily_review_required": False,
            "fail_closed": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Resolve official sources, inject vocalized exact Scripture, and rewrite outputs")
    parser.add_argument("--verify-existing", action="store_true", help="Only verify already-generated outputs")
    parser.add_argument("--offline", action="store_true", help="Do not fetch official sites or canonical files")
    args = parser.parse_args()
    policy = load_json(POLICY_PATH)
    data = load_json(TODAY_PATH)
    target = datetime.strptime(data["date_iso"], "%Y-%m-%d").date()
    bible, canonical_meta = ensure_canonical_bible(policy, allow_network=not args.offline)
    warnings: list[str] = []
    errors: list[str] = []
    all_evidence: list[OfficialEvidence] = []

    feast_errors, _ = verify_jerusalem_fixed_feast(data)
    errors.extend(feast_errors)

    if args.apply and not args.verify_existing and not errors:
        today_resolution, today_evidence = resolve_official_date(target, policy, allow_network=not args.offline)
        all_evidence.extend(today_evidence)
        if today_resolution.decision != "PUBLISH":
            errors.extend(today_resolution.errors)
        next_payload = data.get("integrity_inputs", {}).get("next_sunday", {})
        next_raw = next_payload.get("readings")
        if not isinstance(next_raw, list):
            errors.append("Generated data lacks integrity_inputs.next_sunday.readings")
            next_resolution = None
            next_evidence = []
        else:
            next_target = datetime.strptime(next_payload["date_iso"], "%Y-%m-%d").date()
            next_resolution, next_evidence = resolve_official_date(next_target, policy, allow_network=not args.offline)
            all_evidence.extend(next_evidence)
            if next_resolution.decision != "PUBLISH":
                errors.extend(f"next Sunday: {error}" for error in next_resolution.errors)

        if not errors and next_resolution is not None:
            native_mode = canonical_meta.get("mode") == "PER_LANGUAGE_OFFICIAL_NATIVE_CORPUS_ONLY"
            if native_mode:
                today_readings = prepare_native_corpus_readings(
                    data["readings"],
                    today_resolution.fields["epistle_reference"],
                    today_resolution.fields["gospel_reference"],
                    today_resolution.selected_source,
                )
                next_readings = prepare_native_corpus_readings(
                    next_raw,
                    next_resolution.fields["epistle_reference"],
                    next_resolution.fields["gospel_reference"],
                    next_resolution.selected_source,
                )
            else:
                set_official_references(data["readings"], today_resolution.fields["epistle_reference"], today_resolution.fields["gospel_reference"])
                set_official_references(next_raw, next_resolution.fields["epistle_reference"], next_resolution.fields["gospel_reference"])
                apply_prokeimenon(data["readings"], today_resolution.fields.get("tone"), exact_text=today_resolution.fields.get("prokeimenon_text"), selected_source=today_resolution.selected_source)
                apply_prokeimenon(next_raw, next_resolution.fields.get("tone"), exact_text=next_resolution.fields.get("prokeimenon_text"), selected_source=next_resolution.selected_source)
                today_readings = inject_canonical_readings(data["readings"], bible, canonical_meta, allow_network=not args.offline)
                next_readings = inject_canonical_readings(next_raw, bible, canonical_meta, allow_network=not args.offline)

            data["readings"] = today_readings
            data["integrity_inputs"]["next_sunday"]["readings"] = next_readings

            update = load_update_module()
            next_refs = update.reading_references(next_readings)
            data["next_sunday"]["reading_references"] = copy.deepcopy(next_refs)
            next_date = data["next_sunday"].get("date_iso")
            for item in data.get("upcoming", []):
                if not isinstance(item, dict):
                    continue
                item["verification_status"] = "PREVIEW_REFERENCE_ONLY"
                item["publication_note"] = {
                    "ar": "مرجع معاينة فقط؛ يُعاد التحقق من النص الكامل في يومه قبل النشر.",
                    "en": "Reference preview only; full text is re-verified on its publication date.",
                    "el": "Μόνον προεπισκόπηση παραπομπῆς· τὸ πλήρες κείμενο ἐπαληθεύεται ξανά τὴν ἡμέρα τῆς δημοσιεύσεως."
                }
                if item.get("date") == next_date:
                    item["reading_references"] = copy.deepcopy(next_refs)
                    item["verification_status"] = "VERIFIED_NEXT_SUNDAY_REFERENCES"
                    item["source"] = next_resolution.selected_source

            rebuild_services(data, today_readings, next_readings)
            data["source_evidence"] = [asdict(item) for item in all_evidence]
            data["translation_status"] = "source_native_only_or_unavailable"
            data["machine_translation_used"] = False
            data["automatic_diacritization_used"] = False
            data["translation_fallback_policy"] = "DISABLED_NO_CROSS_LANGUAGE_FALLBACK"
            data["content_metadata"]["human_review_required"] = False

            if native_mode:
                data["schema_version"] = max(9, int(data.get("schema_version") or 0))
                data["translation_notice"] = {
                    "ar": "كل لغة تستخدم نصها الكنسي الرسمي الأصلي فقط. لا ترجمة بين اللغات ولا تشكيل آلي؛ وعند غياب النص يبقى غير متاح.",
                    "en": "Each language uses only its independently imported official native text. No cross-language translation or automatic diacritization; missing text remains unavailable.",
                    "el": "Κάθε γλώσσα χρησιμοποιεῖ μόνον τὸ ἐπισήμως εἰσαγμένο πρωτότυπο κείμενό της· χωρὶς μετάφραση μεταξὺ γλωσσῶν ἢ αὐτόματο τονισμό."
                }
                data["language_content_mode"] = "THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES"
                data["content_metadata"]["review_status"] = "automatic_native_language_policy_enforced"
                data["publication"] = {
                    "status": "AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED",
                    "human_review_required": False,
                    "fail_closed": True,
                    "same_language_fallback_only": True,
                    "religious_text_contract": "canonical/source_native_contract.json",
                    "source_priority": policy["source_priority"],
                    "selected_source": today_resolution.selected_source,
                    "selected_priority": today_resolution.selected_priority,
                    "fallback_trace": today_resolution.fallback_trace,
                    "jurisdiction_contract": "canonical/jordan_liturgical_contract.json",
                    "jurisdiction_lock": "ORTHODOX_JORDAN_FAIL_CLOSED",
                    "authority_mode": "JORDAN_OLD_CALENDAR_OFFICIAL_REFERENCE_GATE",
                }
                data["integrity"] = {
                    "status": "VERIFIED_OFFICIAL_SOURCES",
                    "policy": "canonical/source_policy.json",
                    "ai_scripture_translation_used": False,
                    "ai_liturgical_translation_used": False,
                    "native_text_contract": "canonical/source_native_contract.json",
                    "legacy_arabic_scripture_snapshot": "QUARANTINED_NOT_PUBLICATION_AUTHORITY",
                }
            else:
                data["schema_version"] = 8
                data["translation_notice"] = {
                    "ar": "نصوص الإنجيل والرسائل والمزامير مأخوذة حرفيًا من كتاب مقدس عربي مثبت ومشكول، وتُقارن كلماتها بالنص الأساسي. لا يستخدم النظام ترجمة ذكاء اصطناعي للنص المقدس أو القطع الليتورجية.",
                    "en": "Exact vocalized Arabic Bible text, word-checked against a pinned base; no AI Scripture or liturgical translation.",
                    "el": "Exact vocalized Arabic Bible text; no AI Scripture or liturgical translation.",
                }
                data["language_content_mode"] = "THREE_INDEPENDENT_OFFICIAL_NATIVE_SOURCES"
                data["content_metadata"]["review_status"] = "automatic_official_sources_verified"
                data["publication"] = {
                    "status": "AUTOMATIC_OFFICIAL_SOURCES_VERIFIED",
                    "human_review_required": False,
                    "fail_closed": True,
                    "source_priority": policy["source_priority"],
                    "selected_source": today_resolution.selected_source,
                    "selected_priority": today_resolution.selected_priority,
                    "fallback_trace": today_resolution.fallback_trace,
                    "jurisdiction_contract": "canonical/jordan_liturgical_contract.json",
                    "jurisdiction_lock": "ORTHODOX_JORDAN_FAIL_CLOSED",
                    "authority_mode": "JORDAN_OLD_CALENDAR_OFFICIAL_REFERENCE_GATE",
                }
                data["integrity"] = {
                    "status": "VERIFIED_OFFICIAL_SOURCES",
                    "policy": "canonical/source_policy.json",
                    "canonical_id": canonical_meta["id"],
                    "canonical_revision": canonical_meta["pinned_revision"],
                    "vocalized_source_id": canonical_meta["vocalized_source"]["id"],
                    "ai_scripture_translation_used": False,
                    "ai_liturgical_translation_used": False,
                }
            synchronize_outputs(data)

    if args.verify_existing or (args.apply and not errors):
        errors.extend(verify_existing(data, bible, canonical_meta))
    report = build_report(data, canonical_meta, all_evidence, errors, warnings)
    report_dir = ROOT / ".cache" / "integrity-reports"
    write_json(report_dir / "latest.json", report)
    write_json(report_dir / f"{data['date_iso']}.json", report)
    print(json.dumps({"decision": report["decision"], "date": data["date_iso"], "warnings": len(warnings), "errors": errors}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
