#!/usr/bin/env python3
"""Fetch and normalize a perpetual Greek/Julian Orthodox reading baseline.

This is a *reference* bootstrap, not an authority override.  Existing pinned
Jerusalem/Jordan exact-date records and fixed-feast overrides keep higher
priority in ``build_internal_calendar_2050.py``.

The source endpoint returns the Byzantine Greek-tradition calendar in Julian
(old-calendar) mode.  We copy scripture references only; saint stories and
other copyrighted prose are deliberately ignored.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
import sys
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from orthodox_integrity import parse_reference  # noqa: E402

START_YEAR = 2026
END_YEAR = 2050
SOURCE_COMMIT = "393d5bb55d31bf14fa9c2a706e21c2f1bb48f400"
SOURCE_REPOSITORY = "https://github.com/brianglass/orthocal-python"
API_TEMPLATE = "https://orthocal.info/api/greek/julian/{year}/{month}/"
DEFAULT_CACHE = ROOT / "app" / "build" / "lectionary-download-cache" / "orthocal-greek-julian"
DEFAULT_OUTPUT = ROOT / "canonical" / "perpetual_lectionary_2026_2050.json"
USER_AGENT = "OrthodoxPrayers/5.6.4 R64 lectionary-bootstrap (+absolute coverage audit)"

BOOK_LOCALIZATION = {
    "Genesis": ("التكوين", "Γένεσις"), "Exodus": ("الخروج", "Ἔξοδος"),
    "Leviticus": ("اللاويين", "Λευιτικόν"), "Numbers": ("العدد", "Ἀριθμοί"),
    "Deuteronomy": ("التثنية", "Δευτερονόμιον"), "Joshua": ("يشوع", "Ἰησοῦς Ναυῆ"),
    "Judges": ("القضاة", "Κριταί"), "Ruth": ("راعوث", "Ῥούθ"),
    "1 Samuel": ("صموئيل الأول", "Α΄ Βασιλειῶν"), "2 Samuel": ("صموئيل الثاني", "Β΄ Βασιλειῶν"),
    "1 Kings": ("الملوك الأول", "Γ΄ Βασιλειῶν"), "2 Kings": ("الملوك الثاني", "Δ΄ Βασιλειῶν"),
    "Isaiah": ("إشعياء", "Ἠσαΐας"), "Jeremiah": ("إرميا", "Ἱερεμίας"),
    "Ezekiel": ("حزقيال", "Ἰεζεκιήλ"), "Daniel": ("دانيال", "Δανιήλ"),
    "Proverbs": ("الأمثال", "Παροιμίαι"), "Psalms": ("المزامير", "Ψαλμοί"),
    "Job": ("أيوب", "Ἰώβ"), "Joel": ("يوئيل", "Ἰωήλ"), "Zechariah": ("زكريا", "Ζαχαρίας"),
    "Wisdom of Solomon": ("حكمة سليمان", "Σοφία Σαλωμῶνος"),
    "Wisdom": ("الحكمة", "Σοφία"), "Sirach": ("يشوع بن سيراخ", "Σοφία Σειράχ"),
    "Baruch": ("باروخ", "Βαρούχ"), "1 Esdras": ("عزرا الأول", "Α΄ Ἔσδρας"),
    "2 Esdras": ("عزرا الثاني", "Β΄ Ἔσδρας"),
    "Romans": ("رومية", "Πρὸς Ῥωμαίους"), "Matthew": ("متى", "Κατὰ Ματθαῖον"),
    "Mark": ("مرقس", "Κατὰ Μᾶρκον"), "Luke": ("لوقا", "Κατὰ Λουκᾶν"),
    "John": ("يوحنا", "Κατὰ Ἰωάννην"), "Acts": ("أعمال الرسل", "Πράξεις Ἀποστόλων"),
    "1 Corinthians": ("كورنثوس الأولى", "Πρὸς Κορινθίους Α΄"),
    "2 Corinthians": ("كورنثوس الثانية", "Πρὸς Κορινθίους Β΄"),
    "Galatians": ("غلاطية", "Πρὸς Γαλάτας"), "Ephesians": ("أفسس", "Πρὸς Ἐφεσίους"),
    "Philippians": ("فيلبي", "Πρὸς Φιλιππησίους"), "Colossians": ("كولوسي", "Πρὸς Κολοσσαεῖς"),
    "1 Thessalonians": ("تسالونيكي الأولى", "Πρὸς Θεσσαλονικεῖς Α΄"),
    "2 Thessalonians": ("تسالونيكي الثانية", "Πρὸς Θεσσαλονικεῖς Β΄"),
    "1 Timothy": ("تيموثاوس الأولى", "Πρὸς Τιμόθεον Α΄"),
    "2 Timothy": ("تيموثاوس الثانية", "Πρὸς Τιμόθεον Β΄"),
    "Titus": ("تيطس", "Πρὸς Τίτον"), "Philemon": ("فليمون", "Πρὸς Φιλήμονα"),
    "Hebrews": ("العبرانيين", "Πρὸς Ἑβραίους"), "James": ("يعقوب", "Ἰακώβου"),
    "1 Peter": ("بطرس الأولى", "Πέτρου Α΄"), "2 Peter": ("بطرس الثانية", "Πέτρου Β΄"),
    "1 John": ("يوحنا الأولى", "Ἰωάννου Α΄"), "2 John": ("يوحنا الثانية", "Ἰωάννου Β΄"),
    "3 John": ("يوحنا الثالثة", "Ἰωάννου Γ΄"), "Jude": ("يهوذا", "Ἰούδα"),
}

def localized_reference(reference: str) -> dict[str, str]:
    value = str(reference or "").strip()
    ar, el = value, value
    for book in sorted(BOOK_LOCALIZATION, key=len, reverse=True):
        if value.startswith(book + " "):
            suffix = value[len(book):].strip()
            ar_name, el_name = BOOK_LOCALIZATION[book]
            ar, el = f"{ar_name} {suffix}", f"{el_name} {suffix}"
            break
    return {"ar": ar, "en": value, "el": el}

GOSPEL_BOOKS = {"MAT", "MRK", "LUK", "JHN"}
EPISTLE_BOOKS = {
    "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
    "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD",
}

# Some Byzantine/LXX readings are perfectly valid display references but are
# not represented by the project's current public-domain Bible corpora/parser.
# Recognize them as Old Testament readings without fabricating a canonical ID.
OLD_TESTAMENT_DISPLAY_PREFIXES = tuple(sorted({
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Psalm", "Proverbs", "Ecclesiastes", "Song of Songs",
    "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Wisdom of Solomon", "Wisdom", "Sirach", "Baruch", "1 Esdras", "2 Esdras",
}, key=len, reverse=True))


def _load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid JSON from {label}: {exc}") from exc


def _cache_file(cache_dir: Path, year: int, month: int) -> Path:
    return cache_dir / f"{year:04d}-{month:02d}.json"


def fetch_month(year: int, month: int, cache_dir: Path, *, refresh: bool = False, attempts: int = 3) -> list[dict]:
    cache = _cache_file(cache_dir, year, month)
    if cache.is_file() and not refresh:
        payload = _load_json_bytes(cache.read_bytes(), str(cache))
        if isinstance(payload, list) and payload:
            return payload
    url = API_TEMPLATE.format(year=year, month=month)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
            payload = _load_json_bytes(raw, url)
            if not isinstance(payload, list) or not payload:
                raise RuntimeError(f"unexpected month payload from {url}")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(raw)
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(8, 2 ** (attempt - 1)))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def normalize_display_reference(value: str) -> str:
    value = " ".join(str(value or "").replace("–", "-").replace("—", "-").split())
    # Orthocal normally exposes full English book names.  Keep a few safe
    # punctuation normalizations that parse_reference already understands.
    return value.strip(" ;")


def canonicalize(display: str) -> str:
    if not display:
        return ""
    try:
        return parse_reference(display)[0]
    except Exception:
        return ""


def classify(canonical: str, reading: dict, display: str = "") -> str:
    first = canonical.split(";", 1)[0].split(".", 1)[0] if canonical else ""
    if first in GOSPEL_BOOKS:
        return "gospel"
    if first in EPISTLE_BOOKS:
        return "epistle"
    if first:
        return "old_testament"
    # A display-only LXX book may not map into the app's Bible corpus.  It is
    # still an appointed OT reference and should be shown, not mislabelled as
    # an unknown reading just because no local verse corpus exists for it.
    if any(display.startswith(prefix + " ") for prefix in OLD_TESTAMENT_DISPLAY_PREFIXES):
        return "old_testament"
    description = str(reading.get("description") or reading.get("desc") or "").casefold()
    if "gospel" in description:
        return "gospel"
    if "epistle" in description or "apost" in description:
        return "epistle"
    if any(token in description for token in ("vesper", "paremi", "old testament", "prophe")):
        return "old_testament"
    return "appointed"


def reference_block(display: str, kind: str, *, source_index: int | None = None) -> dict:
    canonical = canonicalize(display)
    block = {
        "kind": kind,
        "canonical_reference": canonical,
        "display_reference": display,
        "reference": localized_reference(display) if display else {"ar": "", "en": "", "el": ""},
        "source": "orthocal_greek_julian_reference_baseline",
        "source_repo_commit": SOURCE_COMMIT,
    }
    if source_index is not None:
        block["source_index"] = source_index
    return block


def selected_readings(day_payload: dict) -> list[dict]:
    readings = day_payload.get("readings") or []
    if not isinstance(readings, list):
        return []
    indices = day_payload.get("abbreviated_reading_indices") or []
    selected: list[tuple[int, dict]] = []
    if isinstance(indices, list) and indices:
        for raw_index in indices:
            try:
                index = int(raw_index)
            except Exception:
                continue
            if 0 <= index < len(readings) and isinstance(readings[index], dict):
                selected.append((index, readings[index]))
    else:
        selected = [(i, item) for i, item in enumerate(readings) if isinstance(item, dict)]

    output = []
    seen = set()
    for index, item in selected:
        display = normalize_display_reference(item.get("display") or item.get("short_display") or "")
        if not display or display in seen:
            continue
        seen.add(display)
        canonical = canonicalize(display)
        output.append(reference_block(display, classify(canonical, item, display), source_index=index))
    return output


def normalize_month(year: int, month: int, payload: list[dict]) -> dict[str, dict]:
    # amonth_of_days() iterates civil dates in order even in Julian calendar mode.
    # The DaySchema year/month/day fields themselves are the shifted Julian date,
    # so derive the civil ISO date from request month + list position instead.
    from calendar import monthrange
    expected = monthrange(year, month)[1]
    if len(payload) != expected:
        raise RuntimeError(f"{year}-{month:02d}: expected {expected} days, got {len(payload)}")
    records: dict[str, dict] = {}
    for civil_day, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"{year}-{month:02d}-{civil_day:02d}: invalid day payload")
        iso = date(year, month, civil_day).isoformat()
        appointed = selected_readings(item)
        refs: dict[str, dict] = {}
        for reading in appointed:
            kind = reading.get("kind")
            if kind in {"epistle", "gospel"} and kind not in refs and reading.get("canonical_reference"):
                refs[kind] = {k: v for k, v in reading.items() if k not in {"kind", "source_index"}}
        records[iso] = {
            "date_iso": iso,
            "pascha_distance": item.get("pascha_distance"),
            "appointed_readings": appointed,
            "reading_references": refs,
            "reading_day_resolution": {
                "status": "APPOINTED_READINGS_PRESENT" if appointed else "NO_ABBREVIATED_READING_APPOINTED_BY_SOURCE",
                "reason": "The pinned Greek/Julian reference source returned no abbreviated appointed reading for this civil day." if not appointed else "",
                "source": "orthocal_greek_julian_reference_baseline",
                "source_repo_commit": SOURCE_COMMIT,
            },
            "source_status": "PERPETUAL_GREEK_JULIAN_REFERENCE_BASELINE",
        }
    return records


def build_payload(months: dict[tuple[int, int], list[dict]], start_year: int, end_year: int) -> dict:
    dates: dict[str, dict] = {}
    parse_failures: list[dict] = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            month_records = normalize_month(year, month, months[(year, month)])
            for iso, record in month_records.items():
                for reading in record["appointed_readings"]:
                    if not reading.get("canonical_reference"):
                        parse_failures.append({"date": iso, "display_reference": reading.get("display_reference"), "kind": reading.get("kind")})
                dates[iso] = record
    total = sum(1 for _ in dates)
    with_appointed = sum(1 for item in dates.values() if item["appointed_readings"])
    with_epistle = sum(1 for item in dates.values() if "epistle" in item["reading_references"])
    with_gospel = sum(1 for item in dates.values() if "gospel" in item["reading_references"])
    resolved_days = sum(1 for item in dates.values() if (item.get("reading_day_resolution") or {}).get("status"))
    no_appointed = sum(1 for item in dates.values() if (item.get("reading_day_resolution") or {}).get("status") == "NO_ABBREVIATED_READING_APPOINTED_BY_SOURCE")
    return {
        "schema_version": 1,
        "calendar": "greek_tradition_julian_old_calendar_reference_baseline",
        "jurisdiction_policy": "REFERENCE_BASELINE_ONLY; Jerusalem/Jordan pinned dates and fixed feasts override this source",
        "source": {
            "id": "orthocal_greek_julian",
            "api_template": API_TEMPLATE,
            "repository": SOURCE_REPOSITORY,
            "repository_commit": SOURCE_COMMIT,
            "license": "MIT",
            "copied_scope": "scripture references and structural metadata only; no saint stories or long prose",
        },
        "civil_range": {"start": f"{start_year}-01-01", "end": f"{end_year}-12-31", "day_count": total},
        "coverage": {
            "days": total,
            "days_with_appointed_readings": with_appointed,
            "days_with_epistle_reference": with_epistle,
            "days_with_gospel_reference": with_gospel,
            "days_with_reading_day_resolution": resolved_days,
            "days_resolved_without_abbreviated_appointed_reading": no_appointed,
            "reference_parse_failures": len(parse_failures),
        },
        "parse_failures": parse_failures,
        "dates": dates,
    }


def load_fixture_month(fixture_dir: Path, year: int, month: int) -> list[dict] | None:
    path = fixture_dir / f"{year:04d}-{month:02d}.json"
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError(f"fixture must be a month list: {path}")
        return payload
    return None


def build_from_network(start_year: int, end_year: int, cache_dir: Path, *, refresh: bool, workers: int, fixture_dir: Path | None) -> dict:
    keys = [(y, m) for y in range(start_year, end_year + 1) for m in range(1, 13)]
    months: dict[tuple[int, int], list[dict]] = {}

    def one(key: tuple[int, int]) -> tuple[tuple[int, int], list[dict]]:
        y, m = key
        fixture = load_fixture_month(fixture_dir, y, m) if fixture_dir else None
        return key, fixture if fixture is not None else fetch_month(y, m, cache_dir, refresh=refresh)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(one, key): key for key in keys}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            key, payload = future.result()
            months[key] = payload
            done += 1
            print(f"LECTIONARY_MONTH_OK {key[0]}-{key[1]:02d} ({done}/{len(keys)})", flush=True)
    return build_payload(months, start_year, end_year)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.end_year < args.start_year:
        raise SystemExit("end year is before start year")
    payload = build_from_network(args.start_year, args.end_year, args.cache_dir, refresh=args.refresh, workers=args.workers, fixture_dir=args.fixture_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    c = payload["coverage"]
    print(
        "PERPETUAL_LECTIONARY_BOOTSTRAP_OK "
        f"days={c['days']} appointed={c['days_with_appointed_readings']} "
        f"epistle={c['days_with_epistle_reference']} gospel={c['days_with_gospel_reference']} "
        f"parse_failures={c['reference_parse_failures']} output={args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output}"
    )


if __name__ == "__main__":
    main()
