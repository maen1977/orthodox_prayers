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
GROUPING = ROOT / "canonical" / "church_directory_grouping.json"


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


def normalize_city(value: str) -> str:
    value = compact_text(value or "")
    return value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")


def load_grouping() -> dict[str, Any]:
    try:
        payload = json.loads(GROUPING.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def directory_source_ids(church: dict[str, Any], original_group: str) -> list[str]:
    """Map each reviewed record to the official directory pages that cover it."""
    source_id = str(church.get("source_id") or "").strip()
    record_id = str(church.get("id") or "").strip().lower()
    if source_id in {"orthodox_jordan", "orthodox_jordan_official_directory"}:
        return ["orthodox_jordan_churches"]
    if record_id.startswith("jordan_") or original_group == "jordan":
        return ["jerusalem_jordan_churches"]
    if record_id.startswith("jerusalem_") or original_group == "jerusalem":
        city = church.get("city") if isinstance(church.get("city"), dict) else {}
        city_ar = str(city.get("ar") or "").strip()
        if city_ar in {"القدس", "جبل الزيتون"}:
            return ["jerusalem_city_churches"]
        return ["holy_land_outside_jerusalem"]
    if record_id.startswith("palestine_") or original_group == "palestine":
        return ["jerusalem_west_bank_churches"]
    return []


def apply_display_grouping(churches: list[dict[str, Any]], grouping: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply reviewed display geography without deleting, translating, or deduplicating records."""
    palestine = grouping.get("palestine_group") or {}
    palestine_title = palestine.get("title") or {
        "ar": "دولة فلسطين", "en": "State of Palestine", "el": "Κράτος τῆς Παλαιστίνης"
    }
    jordan_groups = grouping.get("jordan_groups") or []
    city_map: dict[str, dict[str, Any]] = {}
    for item in jordan_groups:
        if not isinstance(item, dict):
            continue
        for city in item.get("cities") or []:
            city_map[normalize_city(str(city))] = item
    other = next(
        (item for item in jordan_groups if isinstance(item, dict) and item.get("id") == "jordan_other"),
        {"id": "jordan_other", "order": 99, "title": {"ar": "مناطق أردنية أخرى", "en": "Other Jordanian areas", "el": "Ἄλλες περιοχὲς Ἰορδανίας"}},
    )
    for church in churches:
        if not isinstance(church, dict):
            continue
        record_id = str(church.get("id") or "").strip().lower()
        original_group = str(church.get("original_country_group") or church.get("country_group") or "").strip().lower()
        if record_id.startswith("jerusalem_"):
            original_group = "jerusalem"
        elif record_id.startswith("palestine_") and original_group != "jerusalem":
            original_group = "palestine"
        if original_group:
            church["original_country_group"] = original_group
        source_ids = directory_source_ids(church, original_group)
        if source_ids:
            church["directory_source_ids"] = source_ids
        country = church.get("country") if isinstance(church.get("country"), dict) else {}
        country_ar = str(country.get("ar") or "")
        is_palestine = original_group in {"palestine", "jerusalem"} or "فلسطين" in country_ar or "القدس" in country_ar
        if is_palestine:
            # Preserve the source-level country grouping for compatibility and audit
            # contracts; the UI uses region_id to present one unified Palestine card.
            church["country_group"] = original_group if original_group in {"palestine", "jerusalem"} else "palestine"
            church["region_id"] = "palestine"
            church["region"] = dict(palestine_title)
            church["region_order"] = int(palestine.get("order", 20))
            church["country"] = dict(palestine_title)
            continue
        city = church.get("city") if isinstance(church.get("city"), dict) else {}
        city_ar = str(city.get("ar") or "")
        selected = city_map.get(normalize_city(city_ar), other)
        church["country_group"] = "jordan"
        church["region_id"] = str(selected.get("id") or "jordan_other")
        church["region"] = dict(selected.get("title") or other.get("title") or {})
        church["region_order"] = int(selected.get("order", 99))
    return churches


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



def load_best_reviewed_fallback(seed_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    """Return the largest committed official snapshot instead of regressing to the tiny seed.

    ``update.py`` normally runs this builder offline.  Older revisions always
    fell back to the five-entry canonical seed, which could silently replace a
    much larger audited directory.  Prefer a committed audited/generated
    snapshot when it is structurally valid, while keeping the seed as the
    last-resort bootstrap for a brand-new checkout.
    """
    best = list(seed_payload.get("churches") or [])
    best_status = "seed_fallback"
    best_date = ""
    best_metadata: dict[str, Any] = {}
    for candidate in (OUTPUT, ASSET):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if "orthodox_jordan" not in str(payload.get("authority") or ""):
            continue
        churches = payload.get("churches")
        if not isinstance(churches, list) or len(churches) <= len(best):
            continue
        trusted_hosts = {"orthodoxjordan.org", "ar.jerusalem-patriarchate.info"}
        if not all(
            isinstance(item, dict)
            and urllib.parse.urlsplit(str(item.get("url") or "")).scheme == "https"
            and urllib.parse.urlsplit(str(item.get("url") or "")).netloc.casefold() in trusted_hosts
            for item in churches
        ):
            continue
        best = churches
        best_status = str(payload.get("status") or "audited_snapshot_fallback")
        best_date = str(payload.get("date_iso") or "")
        best_metadata = payload
    return best, best_status, best_date, best_metadata

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
    churches, status, fallback_date, fallback_metadata = load_best_reviewed_fallback(seed)
    fallback_count = len(churches)
    snapshot_label = "committed audited snapshot" if fallback_count > len(seed.get("churches", [])) else "canonical seed"
    reason = f"live official directory was not checked; {snapshot_label} retained"
    output_date = fallback_date or target.isoformat()
    live_accepted = False
    try:
        if args.fixture:
            raw = args.fixture.read_bytes()
        elif args.offline:
            raw = b""
        else:
            _, raw, _ = safe_fetch(DIRECTORY_URL, 25, 2_500_000)
        parsed = parse_live(raw) if raw else []
        # A sudden large shrink usually means the official page markup changed
        # and the parser only captured a fragment.  Keep the audited snapshot
        # unless the live result retains at least 70% of it (and at least 5).
        minimum_safe_live_count = max(5, (fallback_count * 7 + 9) // 10)
        if len(parsed) >= minimum_safe_live_count:
            churches, enriched = merge_verified_seed_localizations(parsed, churches)
            status = "live_official_directory"
            output_date = target.isoformat()
            live_accepted = True
            reason = (
                "parsed from the official Orthodox Jordan directory; "
                f"merged {enriched} reviewed localizations by exact canonical URL"
            )
        elif raw:
            reason = (
                f"live page produced only {len(parsed)} church entries below the safe threshold "
                f"{minimum_safe_live_count}; {snapshot_label} retained"
            )
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}; {snapshot_label} retained"[:400]

    grouping = load_grouping()
    churches = apply_display_grouping(churches, grouping)

    payload = {
        "schema_version": 2,
        "date_iso": output_date,
        "authority": "orthodox_jordan" if live_accepted else str(fallback_metadata.get("authority") or "orthodox_jordan"),
        "directory_url": DIRECTORY_URL,
        "status": status,
        "reason": reason,
        "count": len(churches),
        "rights_mode": str(fallback_metadata.get("rights_mode") or "official names and links only; schedules remain live-page data"),
        "directory_grouping": {
            "name_ar": "دولة فلسطين",
            "grouping_asset": "canonical/church_directory_grouping.json",
            "jordan_groups": grouping.get("jordan_groups") or [],
            "palestine_group": grouping.get("palestine_group") or {},
            "policy": "Display grouping only; all reviewed church records and official source links are retained.",
        },
        "churches": churches,
        "live_resources": [
            {
                "id": "orthodox_tv_official",
                "title": {
                    "ar": "المحطة الأرثوذكسية الرسمية — الأردن وفلسطين",
                    "en": "Official Orthodox TV — Jordan and Palestine",
                    "el": "Ἐπίσημος Ὀρθόδοξος Τηλεοπτικὸς Σταθμός — Ἰορδανία καὶ Παλαιστίνη",
                },
                "url": "https://orthodoxjo.tv/",
                "status": "verified_official_2026_08_11",
            },
            {
                "id": "orthodox_tv_radio",
                "title": {
                    "ar": "إذاعة صوت الكنيسة — بث رسمي",
                    "en": "Voice of the Church Radio — official stream",
                    "el": "Ραδιόφωνο «Φωνὴ τῆς Ἐκκλησίας» — ἐπίσημη μετάδοση",
                },
                "url": "https://orthodoxjo.tv/audio/%D8%B5%D9%88%D8%AA-%D8%A7%D9%84%D9%83%D9%86%D9%8A%D8%B3%D8%A9/",
                "status": "verified_official_2026_08_11",
            },
            {
                "id": "jerusalem_patriarchate_radio",
                "title": {
                    "ar": "راديو بطريركية القدس — البث المباشر الرسمي",
                    "en": "Jerusalem Patriarchate Radio — official live page",
                    "el": "Ραδιόφωνο Πατριαρχείου Ἱεροσολύμων — ἐπίσημη ζωντανὴ σελίδα",
                },
                "url": "https://ar.jerusalem-patriarchate.info/%D8%A7%D9%84%D8%A8%D8%AB-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B4%D8%B1-%D8%B1%D8%A7%D8%AF%D9%8A%D9%88-%D8%A8%D8%B7%D8%B1%D9%8A%D8%B1%D9%83%D9%8A%D8%A9-%D8%A7%D9%84%D8%B1%D9%88%D9%85-%D8%A7/",
                "status": "verified_official_2026_08_11",
            },
        ]
    }
    if not live_accepted and isinstance(fallback_metadata.get("source_directories"), list):
        payload["source_directories"] = fallback_metadata["source_directories"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT, ASSET)
    print(f"CHURCH_DIRECTORY_OK status={status} count={len(churches)}")


if __name__ == "__main__":
    main()
