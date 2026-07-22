#!/usr/bin/env python3
"""Build an official Jordan church directory from the source monitor or seed data."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import unicodedata
import urllib.parse
from datetime import date
from pathlib import Path
from typing import Any

from source_connectors import ROOT, TextAndLinksParser, compact_text, safe_fetch

SEED = ROOT / "canonical" / "jordan_church_directory_seed.json"
OUTPUT = ROOT / "data" / "directory" / "churches.json"
ASSET = ROOT / "app" / "src" / "main" / "assets" / "data" / "churches.json"
DIRECTORY_URL = "https://orthodoxjordan.org/%D8%A7%D9%84%D9%83%D9%86%D8%A7%D8%A6%D8%B3/"


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = normalized.translate(str.maketrans("أإآؤئىة", "اااوييه"))
    normalized = re.sub(r"[^\w]+", "-", normalized.lower(), flags=re.UNICODE).strip("-")
    return normalized[:80] or hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def likely_church(label: str, url: str) -> bool:
    text = compact_text(label)
    if len(text) < 8:
        return False
    if not urllib.parse.urlparse(url).netloc.endswith("orthodoxjordan.org"):
        return False
    markers = ("كنيسة", "كاتدرائية", "دير", "Church", "Cathedral", "Monastery")
    return any(marker.casefold() in text.casefold() for marker in markers)


def infer_city(name: str) -> str:
    separators = (" — ", " – ", " - ", " / ")
    for separator in separators:
        if separator in name:
            return compact_text(name.rsplit(separator, 1)[-1])
    known = ("عمان", "عمّان", "السلط", "الفحيص", "الزرقاء", "مادبا", "المفرق", "جرش", "عجلون", "الكرك", "اربد", "إربد", "العقبة")
    return next((city for city in known if city in name), "")


def parse_live(raw: bytes) -> list[dict[str, Any]]:
    parser = TextAndLinksParser(DIRECTORY_URL)
    parser.feed(raw.decode("utf-8", errors="replace"))
    unique: dict[str, dict[str, Any]] = {}
    for label, url in parser.links:
        if not likely_church(label, url):
            continue
        canonical_url = url.split("#", 1)[0]
        if canonical_url in unique:
            continue
        city = infer_city(label)
        unique[canonical_url] = {
            "id": slug(label),
            "name": {"ar": label, "en": "", "el": ""},
            "city": {"ar": city, "en": "", "el": ""},
            "url": canonical_url,
            "source_id": "orthodox_jordan",
            "official": True,
            "schedule_status": "OPEN_OFFICIAL_PAGE_FOR_CURRENT_SCHEDULE",
        }
    return sorted(unique.values(), key=lambda item: item["name"]["ar"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    target = date.fromisoformat(args.date)
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    churches = seed.get("churches", [])
    status = "seed_fallback"
    reason = "live official directory was not checked"
    try:
        if args.fixture:
            raw = args.fixture.read_bytes()
        elif args.offline:
            raw = b""
        else:
            _, raw, _ = safe_fetch(DIRECTORY_URL, 25, 2_500_000)
        parsed = parse_live(raw) if raw else []
        if len(parsed) >= 5:
            churches = parsed
            status = "live_official_directory"
            reason = "parsed from the official Orthodox Jordan directory"
        elif raw:
            reason = f"live page produced only {len(parsed)} church entries; seed retained"
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:400]

    payload = {
        "schema_version": 1,
        "date_iso": target.isoformat(),
        "authority": "orthodox_jordan",
        "directory_url": DIRECTORY_URL,
        "status": status,
        "reason": reason,
        "count": len(churches),
        "rights_mode": "official names and links only; schedules remain live-page data",
        "churches": churches,
        "live_resources": [
            {
                "id": "orthodox_jordan_live",
                "title": {"ar": "البث المباشر الأرثوذكسي الأردني", "en": "Orthodox Jordan live broadcast", "el": "Ζωντανὴ μετάδοση Ἰορδανίας"},
                "url": "https://orthodoxjo.tv/video/orthodox-station/"
            },
            {
                "id": "orthodox_jordan_calendar",
                "title": {"ar": "الرزنامة الكنسية الرسمية", "en": "Official church calendar", "el": "Ἐπίσημο ἐκκλησιαστικὸ ἡμερολόγιο"},
                "url": "https://orthodoxjordan.org/%D8%A7%D9%84%D8%B1%D8%B2%D9%86%D8%A7%D9%85%D8%A9-%D8%A7%D9%84%D9%83%D9%86%D8%B3%D9%8A%D8%A9/"
            }
        ]
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT, ASSET)
    print(f"CHURCH_DIRECTORY_OK status={status} count={len(churches)}")


if __name__ == "__main__":
    main()
