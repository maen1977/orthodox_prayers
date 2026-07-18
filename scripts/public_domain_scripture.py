#!/usr/bin/env python3
"""Download and parse independent public-domain Scripture corpora from eBible.org.

The liturgical calendar decides *which* passage is appointed. This module only
resolves the appointed canonical USFM reference in an independently published
native-language Bible. It never translates, rewrites, or automatically adds
Arabic/Greek marks.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SOURCES: dict[str, dict[str, str]] = {
    "ar": {
        "source_id": "ebible_arabic_van_dyck",
        "archive_url": "https://ebible.org/Scriptures/arb-vd_usfm.zip",
        "browser_base": "https://ebible.org/arb-vd/",
        "archive_name": "arb-vd_usfm.zip",
        "title": "الكتاب المقدس باللغة العربية، فان دايك",
        "license": "Public Domain",
    },
    "en": {
        "source_id": "ebible_world_english_bible",
        "archive_url": "https://ebible.org/Scriptures/engwebp_usfm.zip",
        "browser_base": "https://ebible.org/engwebp/",
        "archive_name": "engwebp_usfm.zip",
        "title": "World English Bible",
        "license": "Public Domain",
    },
    "el": {
        "source_id": "ebible_greek_byzantine_1904",
        "archive_url": "https://ebible.org/Scriptures/grcbyz_usfm.zip",
        "browser_base": "https://ebible.org/grcbyz/",
        "archive_name": "grcbyz_usfm.zip",
        "title": "1904 Patriarchal Greek New Testament",
        "license": "Public Domain",
    },
}

NOTE_BLOCK = re.compile(r"\\(?P<kind>f|fe|x|fig)\b.*?\\(?P=kind)\*", re.DOTALL)
WORD_MARKER = re.compile(r"\\w\s+([^|\\]+?)(?:\|[^\\]*?)?\\w\*")
MILESTONE = re.compile(r"\\[A-Za-z0-9_-]+-(?:s|e)\b.*?\\\*")
CHAR_MARKER = re.compile(r"\\[A-Za-z0-9_-]+\*?")
MULTISPACE = re.compile(r"[ \t\u00a0]+")
VERSE_LINE = re.compile(r"^\\v\s+([^\s]+)\s*(.*)$")
CHAPTER_LINE = re.compile(r"^\\c\s+(\d+)")
BOOK_ID_LINE = re.compile(r"^\\id\s+([A-Z0-9]{3})")
TOC_LINE = re.compile(r"^\\toc1\s+(.+)$")

MAX_ARCHIVE_DOWNLOAD_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 512
MAX_MEMBER_UNCOMPRESSED_BYTES = 8 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
SCRIPTURE_EXTENSIONS = (".usfm", ".sfm", ".txt")


def _safe_scripture_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Validate ZIP metadata before any member is decompressed into memory."""
    files = [info for info in archive.infolist() if not info.is_dir()]
    if len(files) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(f"USFM archive contains too many files: {len(files)}")

    scripture: list[zipfile.ZipInfo] = []
    total_uncompressed = 0
    for info in files:
        raw_name = info.filename.replace("\\", "/")
        path = PurePosixPath(raw_name)
        if not raw_name or raw_name.startswith("/") or ".." in path.parts or "\x00" in raw_name:
            raise ValueError(f"unsafe ZIP member path: {info.filename!r}")
        if info.flag_bits & 0x1:
            raise ValueError(f"encrypted ZIP member is not supported: {info.filename}")
        if info.file_size < 0 or info.compress_size < 0:
            raise ValueError(f"invalid ZIP member size: {info.filename}")
        if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
            raise ValueError(f"ZIP member exceeds uncompressed safety limit: {info.filename}")

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("USFM archive exceeds total uncompressed safety limit")

        if info.file_size:
            if info.compress_size == 0:
                raise ValueError(f"ZIP member has an unsafe compression ratio: {info.filename}")
            ratio = info.file_size / info.compress_size
            if ratio > MAX_COMPRESSION_RATIO:
                raise ValueError(f"ZIP member compression ratio is too high: {info.filename}")

        if raw_name.lower().endswith(SCRIPTURE_EXTENSIONS):
            scripture.append(info)

    if not scripture:
        raise ValueError("USFM archive contains no Scripture files")
    return scripture


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def clean_usfm_text(value: str) -> str:
    """Remove USFM markup while preserving the source wording and Unicode marks."""
    text = value.replace("\ufeff", "")
    text = NOTE_BLOCK.sub("", text)
    text = MILESTONE.sub("", text)
    # Preserve the displayed word but drop lexical metadata.
    previous = None
    while previous != text:
        previous = text
        text = WORD_MARKER.sub(r"\1", text)
    text = text.replace("~", " ")
    text = CHAR_MARKER.sub("", text)
    text = MULTISPACE.sub(" ", text)
    return text.strip()


def _verse_numbers(token: str) -> list[int]:
    token = token.strip()
    match = re.match(r"^(\d+)(?:-(\d+))?", token)
    if not match:
        return []
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start or end - start > 10:
        return []
    return list(range(start, end + 1))


def parse_usfm_document(text: str) -> tuple[str, str, dict[tuple[int, int], str]]:
    """Return (book_id, localized book title, verse map) for one USFM file."""
    book_id = ""
    book_title = ""
    chapter = 0
    verses: dict[tuple[int, int], str] = {}
    active_keys: list[tuple[int, int]] = []

    def append_to_active(fragment: str) -> None:
        cleaned = clean_usfm_text(fragment)
        if not cleaned or not active_keys:
            return
        # Verse bridges are uncommon in the NT corpora used here. Keep the full
        # source wording on the first verse and mark later bridge verses as
        # present without duplicating the passage in display output.
        first = active_keys[0]
        verses[first] = (verses.get(first, "") + " " + cleaned).strip()
        for key in active_keys[1:]:
            verses.setdefault(key, "")

    for raw_line in text.splitlines():
        line = raw_line.strip("\r\n")
        if not line:
            continue
        match = BOOK_ID_LINE.match(line)
        if match:
            book_id = match.group(1).upper()
            continue
        match = TOC_LINE.match(line)
        if match and not book_title:
            book_title = clean_usfm_text(match.group(1))
            continue
        match = CHAPTER_LINE.match(line)
        if match:
            chapter = int(match.group(1))
            active_keys = []
            continue
        match = VERSE_LINE.match(line)
        if match and chapter:
            numbers = _verse_numbers(match.group(1))
            active_keys = [(chapter, number) for number in numbers]
            for key in active_keys:
                verses.setdefault(key, "")
            append_to_active(match.group(2))
            continue
        if line.startswith("\\"):
            # Paragraph and poetry markers can carry continuation text.
            marker_end = line.find(" ")
            if marker_end >= 0:
                append_to_active(line[marker_end + 1 :])
            continue
        append_to_active(line)

    verses = {key: value.strip() for key, value in verses.items() if value.strip()}
    return book_id, book_title or book_id, verses


def parse_usfm_archive(payload: bytes) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[str, str]]:
    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    titles: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = _safe_scripture_members(archive)
        for member in members:
            raw = archive.read(member)
            if len(raw) != member.file_size:
                raise ValueError(f"ZIP member size changed while reading: {member.filename}")
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("utf-8")
            book_id, title, verses = parse_usfm_document(text)
            if not book_id or not verses:
                continue
            titles[book_id] = title
            for (chapter, verse), wording in verses.items():
                key = (book_id, chapter, verse)
                if key in index:
                    raise ValueError(f"duplicate USFM verse {key}")
                index[key] = {
                    "book_id": book_id,
                    "book_name": title,
                    "chapter": chapter,
                    "verse": verse,
                    "text": wording,
                    "text_sha256": hashlib.sha256(wording.encode("utf-8")).hexdigest(),
                }
    if not index:
        raise ValueError("USFM archive produced an empty verse index")
    return index, titles


def _download(url: str, attempts: int = 3, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "OrthodoxPrayersDailyUpdater/5.0.1 (+https://github.com/maen1977/orthodox_prayers)",
                    "Accept": "application/zip,application/octet-stream,*/*;q=0.5",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(MAX_ARCHIVE_DOWNLOAD_BYTES + 1)
                if len(payload) > MAX_ARCHIVE_DOWNLOAD_BYTES:
                    raise ValueError("Scripture archive exceeds 25 MiB safety limit")
                if not payload.startswith(b"PK"):
                    raise ValueError("Scripture source did not return a ZIP archive")
                return payload
        except Exception as error:  # pragma: no cover - network variability
            last = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"could not download {url}: {last}")


def load_public_domain_corpus(language: str) -> tuple[dict[str, Any], dict[tuple[str, int, int], dict[str, Any]]]:
    if language not in SOURCES:
        raise ValueError(f"unsupported language: {language}")
    source = SOURCES[language]
    override_dir = os.environ.get("ORTHODOX_SCRIPTURE_ARCHIVE_DIR", "").strip()
    cache_dir = Path(override_dir) if override_dir else ROOT / ".cache" / "scripture"
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / source["archive_name"]
    downloaded = False
    if archive_path.is_file():
        payload = archive_path.read_bytes()
    else:
        payload = _download(source["archive_url"])
        downloaded = True
    try:
        index, titles = parse_usfm_archive(payload)
    except (ValueError, zipfile.BadZipFile):
        if override_dir:
            raise
        # A cancelled prior run must not poison every future update. Redownload
        # once and only replace the cache after the archive parses successfully.
        payload = _download(source["archive_url"])
        downloaded = True
        index, titles = parse_usfm_archive(payload)
    if downloaded:
        temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(archive_path)
    manifest = {
        "schema_version": 1,
        "language": language,
        "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
        "source_id": source["source_id"],
        "source_url": source["archive_url"],
        "browser_base": source["browser_base"],
        "title": source["title"],
        "license": source["license"],
        "archive_sha256": sha256_bytes(payload),
        "verse_count": len(index),
        "books": sorted(titles),
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "display_text_policy": "USFM_MARKUP_REMOVED_WITH_SOURCE_WORDING_AND_UNICODE_MARKS_PRESERVED",
    }
    return manifest, index
