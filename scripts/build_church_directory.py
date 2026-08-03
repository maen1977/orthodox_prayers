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


def canonical_url_key(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(str(url or ""))
    return (
        parsed.netloc.casefold(),
        urllib.parse.unquote(parsed.path).rstrip("/").casefold(),
    )


def merge_verified_seed_localizations(
    live: list[dict[str, Any]],
    seed: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Enrich live official links with only the reviewed seed translations.

    The official directory is Arabic.  English and Greek names are copied only
    when the exact canonical parish URL exists in the reviewed seed, so the
    update never invents or machine-translates a church name.
    """
    verified = {canonical_url_key(item.get("url", "")): item for item in seed}
    enriched = 0
    for church in live:
        seed_item = verified.get(canonical_url_key(church.get("url", "")))
        if not seed_item:
            continue
        changed = False
        for field in ("name", "city"):
            target = church.setdefault(field, {"ar": "", "en": "", "el": ""})
            source = seed_item.get(field) or {}
            for language in ("ar", "en", "el"):
                if not str(target.get(language) or "").strip() and str(source.get(language) or "").strip():
                    target[language] = source[language]
                    changed = True
        if changed:
            enriched += 1
    return live, enriched


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
            churches, enriched = merge_verified_seed_localizations(parsed, seed.get("churches", []))
            status = "live_official_directory"
            reason = (
                "parsed from the official Orthodox Jordan directory; "
                f"merged {enriched} reviewed seed localizations by exact canonical URL"
            )
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
                "id": "orthodox_jordan_tv_live",
                "title": {"ar": "المحطة الأرثوذكسية الأردنية — مباشر", "en": "Orthodox Jordan TV — Live", "el": "Ὀρθόδοξη Τηλεόραση Ἰορδανίας — Ζωντανά"},
                "url": "https://orthodoxjo.tv/video/orthodox-station/"
            },
            {
                "id": "orthodox_jordan_live_fallback",
                "title": {"ar": "البث الرسمي لمطرانية الأردن — رابط احتياطي", "en": "Orthodox Jordan Metropolis live page — fallback", "el": "Σελίδα ζωντανῆς μεταδόσεως Μητροπόλεως Ἰορδανίας — ἐφεδρική"},
                "url": "https://orthodoxjordan.org/%D8%A7%D9%84%D8%A8%D8%AB-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B4%D8%B1/"
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
