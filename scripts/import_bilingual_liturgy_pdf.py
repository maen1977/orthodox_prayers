#!/usr/bin/env python3
"""Import the official Greek/English Divine Liturgy PDF into independent native packs.

The expected document is the bilingual text published by the Greek Orthodox
Metropolis of Toronto (Canada), 2017.  Greek and English pages alternate.  The
script does not translate: it parses each language's native pages independently
and writes reproducible per-language service overrides.

Usage:
  python scripts/import_bilingual_liturgy_pdf.py /path/to/Divine-Liturgy.pdf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE_ROOT = ROOT / "data" / "services" / "native_overrides"

PAGE_CONFIG = {
    # pdftotext page numbers are 1-based. Core service ends before appendices.
    "el": range(4, 89, 2),
    "en": range(5, 90, 2),
}

SPEAKERS = {
    "en": {
        "Priest",
        "Bishop or Priest",
        "Bishop or the Priest",
        "Deacon",
        "People",
        "Reader",
        "Clergy",
        "Clergy and People",
        "Bishop",
        "Priests",
    },
    "el": {
        "Ἱερεὺς",
        "Ὁ Ἱερεὺς",
        "Ὁ Ἀρχιερεύς ἢ ὁ Ἱερεὺς",
        "Ὁ Ἀρχιερεύς ἢ ὁ Ἱερεύς",
        "Διάκονος",
        "Λαός",
        "Ἀναγνώστης",
        "Κλῆρος",
        "Κλῆρος καί Λαός",
        "Ὁ Ἀρχιερεύς",
        "Ἱερεῖς",
    },
}

TITLE = {
    "en": "The Divine Liturgy of Saint John Chrysostom",
    "el": "Ἡ Θεία Λειτουργία τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου",
}
SUMMARY = {
    "en": "Complete native English order of the Divine Liturgy of Saint John Chrysostom, including clergy prayers, litanies, responses, readings placeholders, Holy Communion, and dismissal.",
    "el": "Πλήρης ἑλληνικὴ τάξη τῆς Θείας Λειτουργίας τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου, μὲ εὐχές, συναπτές, ἀποκρίσεις, θέσεις ἀναγνωσμάτων, Θεία Μετάληψη καὶ ἀπόλυση.",
}
NOTICE = {
    "en": "The fixed service text is stored offline. Variable hymns and appointed readings are supplied by the verified daily-data layer when available.",
    "el": "Τὸ σταθερὸ κείμενο φυλάσσεται ἐκτὸς σύνδεσης. Τὰ μεταβλητὰ τροπάρια καὶ τὰ καθορισμένα ἀναγνώσματα παρέχονται ἀπὸ τὸ ἐπαληθευμένο καθημερινὸ πακέτο δεδομένων, ὅταν εἶναι διαθέσιμα.",
}


def pdf_page_text(pdf: Path, page: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(pdf), "-"],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.replace("\f", "")


def normalize_line(line: str) -> str:
    line = unicodedata.normalize("NFC", line)
    line = line.replace("\u00ad", "")
    line = line.replace("ﬀ", "ff").replace("ﬁ", "fi").replace("ﬂ", "fl")
    # OCR occasionally substitutes Greek capital iota for Latin I on English pages.
    line = line.replace("Ιnvisibly", "Invisibly")
    line = re.sub(r"[ \t]+", " ", line.strip())
    return line


def is_heading(line: str, lang: str) -> bool:
    if not line or ":" in line or line.startswith("("):
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters or len(line) > 95:
        return False
    # PDF headings are uppercase; accents/case work with Unicode upper().
    return line == line.upper()


def join_wrapped(lines: Iterable[str]) -> str:
    out = ""
    for raw in lines:
        line = normalize_line(raw)
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        else:
            out += " " + line
    out = re.sub(r" {2,}", " ", out)
    # Strip printed footnote markers, while retaining real numbers in the prose.
    out = re.sub(r"(?<=[A-Za-zΑ-Ωα-ωάέήίόύώϊϋΐΰ.)])(?:[¹²³⁴⁵⁶⁷⁸⁹]|\d+)(?=($|[.,;:]))", "", out)
    return out.strip()


def clean_page_lines(text: str) -> list[str]:
    raw = text.splitlines()
    # A footnote marker near the lower margin is followed by the note and page number.
    # Truncate that footer block, but do not mistake the final page number for a note.
    nonempty_after = [any(normalize_line(x) for x in raw[i + 1:]) for i in range(len(raw))]
    cut = len(raw)
    for index, line in enumerate(raw):
        s = normalize_line(line)
        if index > len(raw) * 0.55 and re.fullmatch(r"(?:\d|[¹²³⁴⁵⁶⁷⁸⁹])", s) and nonempty_after[index]:
            cut = index
            break
    raw = raw[:cut]
    cleaned: list[str] = []
    # Remove running page numbers and isolated markers.
    for line in raw:
        s = normalize_line(line)
        if re.fullmatch(r"\d{1,3}", s) or re.fullmatch(r"[¹²³⁴⁵⁶⁷⁸⁹]", s):
            continue
        cleaned.append(s)
    # Trim empty page margins.
    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return cleaned


def parse_language(pdf: Path, lang: str) -> list[dict]:
    lines: list[str] = []
    for page in PAGE_CONFIG[lang]:
        page_lines = clean_page_lines(pdf_page_text(pdf, page))
        lines.extend(page_lines)
        lines.append("")

    segments: list[dict] = []
    speaker: str | None = None
    buffer: list[str] = []
    pending_heading: list[str] = []

    def loc(value: str) -> dict[str, str]:
        return {"ar": "", "el": value if lang == "el" else "", "en": value if lang == "en" else ""}

    def flush_heading() -> None:
        nonlocal pending_heading
        if not pending_heading:
            return
        title = join_wrapped(pending_heading)
        if title and title.casefold() not in {TITLE[lang].casefold(), "of saint john\nchrysostom"}:
            segments.append({"type": "section", "title": loc(title.replace("\n", " "))})
        pending_heading = []

    def flush_text() -> None:
        nonlocal buffer, speaker
        text = join_wrapped(buffer)
        buffer = []
        if not text:
            return
        # Standalone rubrics are displayed as collapsible notes.
        rubric = speaker is None and (text.startswith("(") or text.startswith("["))
        item = {
            "type": "note" if rubric else "text",
            "speaker": loc(speaker or ("Rubric" if lang == "en" else "Τυπικόν")),
            "text": loc(text),
        }
        if rubric:
            item["collapsed_by_default"] = True
        segments.append(item)

    for line in lines:
        if not line:
            if buffer:
                buffer.append("")
            continue

        if is_heading(line, lang):
            flush_text()
            speaker = None
            pending_heading.append(line)
            continue
        flush_heading()

        match = re.match(r"^([^:]{1,70}):\s*(.*)$", line)
        if match and normalize_line(match.group(1)) in SPEAKERS[lang]:
            flush_text()
            speaker = normalize_line(match.group(1))
            rest = normalize_line(match.group(2))
            if rest:
                buffer.append(rest)
            continue

        # Parenthetical instruction after a completed spoken block: keep it as rubric.
        if line.startswith("(") and buffer:
            flush_text()
            speaker = None
            buffer.append(line)
            continue

        buffer.append(line)

    flush_text()
    flush_heading()

    # Remove accidental duplicate adjacent headings and empty items.
    compact: list[dict] = []
    for item in segments:
        key = "title" if item["type"] == "section" else "text"
        value = str(item[key].get(lang) or "").strip()
        if not value:
            continue
        if compact and item["type"] == "section" and compact[-1]["type"] == "section":
            previous = compact[-1]["title"].get(lang, "")
            if value.casefold() == previous.casefold():
                continue
        compact.append(item)
    if compact and compact[0].get("type") == "section":
        first = str(compact[0].get("title", {}).get(lang) or "").upper()
        if "DIVINE LITURGY" in first or "ΘΕΙΑ ΛΕΙΤΟΥΡΓΙΑ" in first:
            compact.pop(0)
    return compact


def make_service(lang: str, segments: list[dict], source_sha: str) -> dict:
    loc = lambda value: {"ar": "", "el": value if lang == "el" else "", "en": value if lang == "en" else ""}
    return {
        "id": "divine_liturgy",
        "category": "liturgy",
        "icon": "⛪",
        "title": loc(TITLE[lang]),
        "summary": loc(SUMMARY[lang]),
        "source_language": lang,
        "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
        "notice": loc(NOTICE[lang]),
        "segments": segments,
        "source_document": {
            "publisher": "Greek Orthodox Metropolis of Toronto (Canada)",
            "publication_year": 2017,
            "document_title": "The Divine Liturgy of Saint John Chrysostom / Ἡ Θεία Λειτουργία τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου",
            "document_sha256": source_sha,
            "page_lane": "alternating native-language pages",
            "machine_translation_used": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pdf = args.pdf.resolve()
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    if not shutil_which("pdftotext"):
        raise SystemExit("pdftotext is required")

    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    for lang in ("en", "el"):
        segments = parse_language(pdf, lang)
        if len(segments) < 150:
            raise SystemExit(f"Parsed only {len(segments)} {lang} segments; refusing incomplete import")
        service = make_service(lang, segments, source_sha)
        output = OVERRIDE_ROOT / lang / "divine_liturgy.json"
        if not args.dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(service, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{lang}: {len(segments)} segments -> {output.relative_to(ROOT)}")


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    main()
