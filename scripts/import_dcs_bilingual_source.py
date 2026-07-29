#!/usr/bin/env python3
"""Split a locally saved official Greek-English DCS page without translation.

The command intentionally has no network client. Save the official gr-en page
locally, then run this tool. It emits separate exact-text lane files that can be
fed to import_native_liturgy_service.py and reviewed independently.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path


class TablePairParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.casefold()
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []
        elif self.in_cell and tag == "br":
            self.cell_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"td", "th"} and self.in_cell:
            value = re.sub(r"\s+", " ", html.unescape("".join(self.cell_parts))).strip()
            self.row.append(value)
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []


def script_ratio(text: str, token: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(token in unicodedata.name(ch, "") for ch in letters) / len(letters)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def parse_pairs(path: Path) -> list[tuple[str, str]]:
    raw = path.read_text(encoding="utf-8", errors="strict")
    rows: list[list[str]] = []
    if path.suffix.casefold() in {".html", ".htm"}:
        parser = TablePairParser()
        parser.feed(raw)
        rows.extend(parser.rows)
    for line in raw.splitlines():
        if " | " in line:
            rows.append([part.strip() for part in line.split(" | ", 1)])
        elif "\t" in line:
            rows.append([part.strip() for part in line.split("\t", 1)])
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if len(row) < 2:
            continue
        left, right = normalize(row[0]), normalize(row[1])
        if script_ratio(left, "GREEK") >= 0.45 and script_ratio(right, "LATIN") >= 0.60:
            pair = (left, right)
        elif script_ratio(right, "GREEK") >= 0.45 and script_ratio(left, "LATIN") >= 0.60:
            pair = (right, left)
        else:
            continue
        if pair not in seen:
            pairs.append(pair)
            seen.add(pair)
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-pairs", type=int, default=80)
    args = parser.parse_args()
    pairs = parse_pairs(args.source)
    if len(pairs) < args.minimum_pairs:
        raise SystemExit(f"Only {len(pairs)} reliable Greek-English pairs; refusing incomplete split")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    greek = "\n\n".join(pair[0] for pair in pairs) + "\n"
    english = "\n\n".join(pair[1] for pair in pairs) + "\n"
    (args.output_dir / "el.txt").write_text(greek, encoding="utf-8")
    (args.output_dir / "en.txt").write_text(english, encoding="utf-8")
    evidence = {
        "schema_version": 1,
        "source_file": args.source.name,
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "pair_count": len(pairs),
        "machine_translation_used": False,
        "outputs": {
            "el_sha256": hashlib.sha256(greek.encode("utf-8")).hexdigest(),
            "en_sha256": hashlib.sha256(english.encode("utf-8")).hexdigest()
        }
    }
    (args.output_dir / "split_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"DCS_BILINGUAL_SPLIT_OK pairs={len(pairs)} translation=false output={args.output_dir}")


if __name__ == "__main__":
    main()
