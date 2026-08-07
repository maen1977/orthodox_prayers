#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

BASE_URLS = (
    "https://ebible.org/Scriptures/",
    "https://ftp.ebible.org/Scriptures/",
)

@dataclass(frozen=True)
class Source:
    output_name: str
    archive_name: str
    min_verses: int
    source_id: str

SOURCES = (
    Source("arb-arb-vd.tsv", "arb-vd_usfm.zip", 30000, "arb-vd"),
    Source("eng-eng-webbe.tsv", "eng-webbe_usfm.zip", 36000, "eng-webbe"),
    Source("grc-grcbrent.tsv", "grcbrent_usfm.zip", 25000, "grcbrent"),
    Source("grc-grcbyz.tsv", "grcbyz_usfm.zip", 7800, "grcbyz"),
)

BOOK_ORDER = [
    "GEN","EXO","LEV","NUM","DEU","JOS","JDG","RUT","1SA","2SA","1KI","2KI","1CH","2CH",
    "EZR","NEH","EST","JOB","PSA","PRO","ECC","SNG","ISA","JER","LAM","EZK","DAN","HOS",
    "JOL","AMO","OBA","JON","MIC","NAM","HAB","ZEP","HAG","ZEC","MAL",
    "TOB","JDT","ESG","WIS","SIR","BAR","LJE","S3Y","SUS","BEL","1MA","2MA","3MA","4MA",
    "1ES","2ES","MAN","PS2","ODA","PSS",
    "MAT","MRK","LUK","JHN","ACT","ROM","1CO","2CO","GAL","EPH","PHP","COL","1TH","2TH",
    "1TI","2TI","TIT","PHM","HEB","JAS","1PE","2PE","1JN","2JN","3JN","JUD","REV",
]
BOOK_INDEX = {book: i for i, book in enumerate(BOOK_ORDER)}

ID_RE = re.compile(r"^\\id\s+([0-9A-Z]{3})\b")
CHAPTER_RE = re.compile(r"^\\c\s+(\d+)\b")
VERSE_RE = re.compile(r"^\\v\s+([^\s]+)\s*(.*)$")
FOOTNOTE_RE = re.compile(r"\\f\b.*?\\f\*", re.DOTALL)
XREF_RE = re.compile(r"\\x\b.*?\\x\*", re.DOTALL)
FIG_RE = re.compile(r"\\fig\b.*?\\fig\*", re.DOTALL)
WORD_RE = re.compile(r"\\w\s+([^|\\]+)(?:\|[^\\]*)?\\w\*")
MILESTONE_RE = re.compile(r"\\(?:zaln-s|zaln-e|qt-s|qt-e)\b.*?\\\*", re.DOTALL)
MARKER_RE = re.compile(r"\\[A-Za-z0-9+\-]+\*?(?:\s+)?")
ATTR_RE = re.compile(r"\|[A-Za-z][^\s]*")
SPACE_RE = re.compile(r"\s+")

NON_VERSE_MARKERS = (
    "\\id", "\\ide", "\\h", "\\toc", "\\mt", "\\mte", "\\ms", "\\mr", "\\s", "\\sr",
    "\\r", "\\d", "\\sp", "\\cl", "\\cp", "\\rem", "\\sts", "\\periph", "\\cat",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_archive(source: Source, cache_dir: Path) -> tuple[bytes, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / source.archive_name
    if cached.is_file() and cached.stat().st_size > 1024:
        data = cached.read_bytes()
        if zipfile.is_zipfile(io.BytesIO(data)):
            return data, "cache"
        cached.unlink(missing_ok=True)

    errors: list[str] = []
    headers = {"User-Agent": "OrthodoxPrayers-BibleBuilder/5.4 (+https://github.com/maen1977/orthodox_prayers)"}
    for base in BASE_URLS:
        url = base + source.archive_name
        for attempt in range(1, 4):
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read()
                if len(data) < 1024 or not zipfile.is_zipfile(io.BytesIO(data)):
                    raise RuntimeError(f"Downloaded payload is not a valid ZIP ({len(data)} bytes)")
                cached.write_bytes(data)
                return data, url
            except Exception as exc:  # network errors are reported with every attempted endpoint
                errors.append(f"{url} attempt {attempt}: {type(exc).__name__}: {exc}")
                if attempt < 3:
                    time.sleep(attempt * 2)
    raise RuntimeError("Unable to download Bible source archive:\n" + "\n".join(errors))


def decode_usfm(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("~", " ")
    value = FOOTNOTE_RE.sub(" ", value)
    value = XREF_RE.sub(" ", value)
    value = FIG_RE.sub(" ", value)
    value = MILESTONE_RE.sub(" ", value)
    value = WORD_RE.sub(lambda m: m.group(1), value)
    value = ATTR_RE.sub("", value)
    value = MARKER_RE.sub(" ", value)
    value = value.replace("\\*", " ")
    return SPACE_RE.sub(" ", value).strip()


def verse_numbers(token: str) -> list[int]:
    # USFM can contain values such as 3, 3a, 3-4, or 3,4. We preserve the
    # first textual verse and mark following members of a range as <range>,
    # matching the old corpus behaviour without duplicating Scripture text.
    nums = [int(x) for x in re.findall(r"\d+", token)]
    if not nums:
        return []
    start = nums[0]
    if "-" in token and len(nums) >= 2 and nums[1] >= start:
        return list(range(start, nums[1] + 1))
    return [start]


def parse_usfm_zip(data: bytes) -> dict[tuple[str, int, int], str]:
    verses: dict[tuple[str, int, int], str] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith((".usfm", ".sfm")) and not n.endswith("/")]
        if not names:
            raise RuntimeError("USFM ZIP contains no .usfm/.sfm files")
        for name in names:
            content = decode_usfm(archive.read(name)).replace("\r\n", "\n").replace("\r", "\n")
            book: str | None = None
            chapter = 0
            active_keys: list[tuple[str, int, int]] = []
            active_text: list[str] = []

            def flush() -> None:
                nonlocal active_keys, active_text
                if not active_keys:
                    active_text = []
                    return
                text = clean_text(" ".join(active_text))
                if text:
                    verses[active_keys[0]] = text
                    for extra in active_keys[1:]:
                        verses.setdefault(extra, "<range>")
                active_keys = []
                active_text = []

            for raw_line in content.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                match = ID_RE.match(line)
                if match:
                    flush()
                    book = match.group(1)
                    chapter = 0
                    continue
                match = CHAPTER_RE.match(line)
                if match:
                    flush()
                    chapter = int(match.group(1))
                    continue
                match = VERSE_RE.match(line)
                if match:
                    flush()
                    if not book or chapter <= 0:
                        continue
                    numbers = verse_numbers(match.group(1))
                    active_keys = [(book, chapter, number) for number in numbers]
                    active_text = [match.group(2)]
                    continue
                if active_keys:
                    if line.startswith(NON_VERSE_MARKERS):
                        continue
                    # Paragraph/poetry/character markers may carry continuation text.
                    active_text.append(line)
            flush()
    return verses


def sorted_items(verses: dict[tuple[str, int, int], str]):
    return sorted(
        verses.items(),
        key=lambda item: (BOOK_INDEX.get(item[0][0], 999), item[0][0], item[0][1], item[0][2]),
    )


def write_tsv(path: Path, verses: dict[tuple[str, int, int], str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for (book, chapter, verse), text in sorted_items(verses):
            clean = text.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
            if not clean:
                continue
            handle.write(f"{book}\t{chapter}\t{verse}\t{clean}\n")
            if clean != "<range>":
                count += 1
    return count


def prepare(output_dir: Path, cache_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"schemaVersion": 1, "format": "book-tab-chapter-tab-verse-tab-text", "sources": []}
    for source in SOURCES:
        archive, used_url = download_archive(source, cache_dir)
        verses = parse_usfm_zip(archive)
        target = output_dir / source.output_name
        verse_count = write_tsv(target, verses)
        if verse_count < source.min_verses:
            raise RuntimeError(
                f"Bible source {source.source_id} is incomplete: {verse_count} textual verses; expected at least {source.min_verses}"
            )
        manifest["sources"].append({
            "id": source.source_id,
            "archive": source.archive_name,
            "output": source.output_name,
            "verseCount": verse_count,
            "archiveSha256": sha256_bytes(archive),
            "downloadedFrom": used_url,
        })
        print(f"BIBLE_CORPUS_OK {source.source_id} verses={verse_count} output={target}")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public-domain eBible USFM archives and compile offline TSV assets.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        prepare(args.output_dir.resolve(), args.cache_dir.resolve())
    except Exception as exc:
        print(f"BIBLE_CORPUS_FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
