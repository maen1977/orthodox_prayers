#!/usr/bin/env python3
"""Build the compact offline Jerusalem/Jordan calendar horizon through 2050.

The asset is a fail-safe calendar, not a replacement for signed source corrections.
It guarantees civil/Julian dates, Paschal-cycle occasions, major fixed feasts,
fasting, appointed service selection, and a non-empty localized commemoration
label for every civil day through 2050 without network. Named saints are never
invented: when no pinned named feast/occasion is available, the baseline identifies
the commemoration by its Old Calendar date and signed/native sources may enrich it.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# Avoid a generated asset feeding itself while it is being rebuilt.
os.environ["ORTHODOX_DISABLE_INTERNAL_CALENDAR"] = "1"

from orthodox_integrity import parse_reference  # noqa: E402
from update_liturgical_data import (  # noqa: E402
    AR_DAYS,
    EN_DAYS,
    EL_DAYS,
    day_info,
    gregorian_to_julian_date,
    julian_to_gregorian_date,
    liturgy_service_selection,
    localized_feast,
    orthodox_pascha_gregorian,
)

START = date(2026, 1, 1)
END = date(2050, 12, 31)
OUT_CANONICAL = ROOT / "canonical" / "internal_calendar_2026_2050.json"
OUT_ASSET_DIR = ROOT / "app" / "src" / "main" / "assets" / "data" / "calendar"
OUT_ASSET_INDEX = OUT_ASSET_DIR / "calendar_index.json"
H2_PATH = ROOT / "canonical" / "jordan_2026_h2_lectionary.json"
FIXED_LECTIONARY_PATH = ROOT / "canonical" / "jerusalem_fixed_feast_lectionary.json"
PERPETUAL_LECTIONARY_PATH = ROOT / "canonical" / "perpetual_lectionary_2026_2050.json"
NATIVE_COMM_MEMORATIONS_PATH = ROOT / "canonical" / "jerusalem_jordan_fixed_commemorations_native.json"


AR_MONTHS = {
    1: "كانون الثاني", 2: "شباط", 3: "آذار", 4: "نيسان",
    5: "أيار", 6: "حزيران", 7: "تموز", 8: "آب",
    9: "أيلول", 10: "تشرين الأول", 11: "تشرين الثاني", 12: "كانون الأول",
}
EN_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}
EL_MONTHS_GENITIVE = {
    1: "Ἰανουαρίου", 2: "Φεβρουαρίου", 3: "Μαρτίου", 4: "Ἀπριλίου",
    5: "Μαΐου", 6: "Ἰουνίου", 7: "Ἰουλίου", 8: "Αὐγούστου",
    9: "Σεπτεμβρίου", 10: "Ὀκτωβρίου", 11: "Νοεμβρίου", 12: "Δεκεμβρίου",
}


def dated_commemoration_label(day: date) -> dict[str, str]:
    """Localized fail-safe commemoration label tied to the Old Calendar date.

    This deliberately does not fabricate saint names. It gives every day a stable,
    language-isolated commemoration identity while named fixed/movable occasions
    continue to take precedence whenever the internal calendar has one.
    """
    _jy, jm, jd = gregorian_to_julian_date(day)
    return loc(
        f"تذكار قديسي يوم {jd} {AR_MONTHS[jm]} حسب التقويم الكنسي القديم",
        f"Commemoration of the saints of {EN_MONTHS[jm]} {jd} on the Old Church Calendar",
        f"Μνήμη τῶν Ἁγίων τῆς {jd}ης {EL_MONTHS_GENITIVE[jm]} κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο",
    )

AR_ORDINALS = {
    1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس",
    6: "السادس", 7: "السابع", 8: "الثامن", 9: "التاسع", 10: "العاشر",
    11: "الحادي عشر", 12: "الثاني عشر", 13: "الثالث عشر", 14: "الرابع عشر",
    15: "الخامس عشر", 16: "السادس عشر", 17: "السابع عشر", 18: "الثامن عشر",
    19: "التاسع عشر", 20: "العشرون", 21: "الحادي والعشرون", 22: "الثاني والعشرون",
    23: "الثالث والعشرون", 24: "الرابع والعشرون", 25: "الخامس والعشرون",
    26: "السادس والعشرون", 27: "السابع والعشرون", 28: "الثامن والعشرون",
    29: "التاسع والعشرون", 30: "الثلاثون", 31: "الحادي والثلاثون",
    32: "الثاني والثلاثون", 33: "الثالث والثلاثون", 34: "الرابع والثلاثون",
    35: "الخامس والثلاثون", 36: "السادس والثلاثون", 37: "السابع والثلاثون",
    38: "الثامن والثلاثون", 39: "التاسع والثلاثون", 40: "الأربعون",
}


def loc(ar: str, en: str, el: str) -> dict[str, str]:
    return {"ar": ar, "en": en, "el": el}


def en_ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def sunday_after_pentecost_label(day: date) -> dict[str, str] | None:
    if day.weekday() != 6:
        return None
    candidates = []
    for year in (day.year - 1, day.year):
        pentecost = orthodox_pascha_gregorian(year) + timedelta(days=49)
        first = pentecost + timedelta(days=7)
        if day >= first:
            candidates.append(first)
    if not candidates:
        return None
    first = max(candidates)
    number = (day - first).days // 7 + 1
    if not 1 <= number <= 40:
        return None
    ar_ord = AR_ORDINALS.get(number, str(number))
    return loc(
        f"الأحد {ar_ord} بعد العنصرة",
        f"{en_ordinal(number)} Sunday after Pentecost",
        f"{number}η Κυριακὴ μετὰ τὴν Πεντηκοστή",
    )


MOVABLE_OFFSETS: dict[int, dict[str, str]] = {
    -70: loc("أحد الفريسي والعشار — بدء التريودي", "Sunday of the Publican and the Pharisee — Triodion begins", "Κυριακὴ τοῦ Τελώνου καὶ Φαρισαίου — Ἀρχὴ Τριῳδίου"),
    -63: loc("أحد الابن الشاطر", "Sunday of the Prodigal Son", "Κυριακὴ τοῦ Ἀσώτου"),
    -57: loc("سبت الراقدين الأول", "First Saturday of Souls", "Α΄ Ψυχοσάββατο"),
    -56: loc("أحد الدينونة — مرفع اللحم", "Sunday of the Last Judgment — Meatfare", "Κυριακὴ τῆς Ἀπόκρεω"),
    -50: loc("سبت الراقدين الثاني", "Second Saturday of Souls", "Β΄ Ψυχοσάββατο"),
    -49: loc("أحد الغفران — مرفع الجبن", "Forgiveness Sunday — Cheesefare", "Κυριακὴ τῆς Τυρινῆς"),
    -48: loc("الاثنين النظيف — بدء الصوم الكبير", "Clean Monday — Beginning of Great Lent", "Καθαρὰ Δευτέρα — Ἀρχὴ Μεγάλης Τεσσαρακοστῆς"),
    -43: loc("سبت الراقدين الثالث", "Third Saturday of Souls", "Γ΄ Ψυχοσάββατο"),
    -42: loc("أحد الأرثوذكسية", "Sunday of Orthodoxy", "Κυριακὴ τῆς Ὀρθοδοξίας"),
    -35: loc("أحد القديس غريغوريوس بالاماس", "Sunday of Saint Gregory Palamas", "Κυριακὴ τοῦ Ἁγίου Γρηγορίου Παλαμᾶ"),
    -28: loc("أحد السجود للصليب", "Sunday of the Veneration of the Cross", "Κυριακὴ τῆς Σταυροπροσκυνήσεως"),
    -21: loc("أحد القديس يوحنا السلمي", "Sunday of Saint John Climacus", "Κυριακὴ τοῦ Ἁγίου Ἰωάννου τῆς Κλίμακος"),
    -14: loc("أحد القديسة مريم المصرية", "Sunday of Saint Mary of Egypt", "Κυριακὴ τῆς Ὁσίας Μαρίας τῆς Αἰγυπτίας"),
    -8: loc("سبت لعازر", "Lazarus Saturday", "Σάββατο τοῦ Λαζάρου"),
    -7: loc("أحد الشعانين", "Palm Sunday", "Κυριακὴ τῶν Βαΐων"),
    -6: loc("الاثنين العظيم المقدس", "Great and Holy Monday", "Μεγάλη καὶ Ἁγία Δευτέρα"),
    -5: loc("الثلاثاء العظيم المقدس", "Great and Holy Tuesday", "Μεγάλη καὶ Ἁγία Τρίτη"),
    -4: loc("الأربعاء العظيم المقدس", "Great and Holy Wednesday", "Μεγάλη καὶ Ἁγία Τετάρτη"),
    -3: loc("الخميس العظيم المقدس", "Great and Holy Thursday", "Μεγάλη καὶ Ἁγία Πέμπτη"),
    -2: loc("الجمعة العظيمة المقدسة", "Great and Holy Friday", "Μεγάλη καὶ Ἁγία Παρασκευή"),
    -1: loc("السبت العظيم المقدس", "Great and Holy Saturday", "Μέγα καὶ Ἅγιο Σάββατο"),
    0: loc("عيد قيامة ربنا يسوع المسيح — الفصح المقدس", "Holy Pascha — Resurrection of our Lord Jesus Christ", "Ἅγιον Πάσχα — Ἀνάστασις τοῦ Κυρίου"),
    1: loc("الاثنين المشرق", "Bright Monday", "Δευτέρα τῆς Διακαινησίμου"),
    2: loc("الثلاثاء المشرق", "Bright Tuesday", "Τρίτη τῆς Διακαινησίμου"),
    3: loc("الأربعاء المشرق", "Bright Wednesday", "Τετάρτη τῆς Διακαινησίμου"),
    4: loc("الخميس المشرق", "Bright Thursday", "Πέμπτη τῆς Διακαινησίμου"),
    5: loc("الجمعة المشرقة — ينبوع الحياة", "Bright Friday — Life-giving Spring", "Παρασκευὴ τῆς Διακαινησίμου — Ζωοδόχος Πηγή"),
    6: loc("السبت المشرق", "Bright Saturday", "Σάββατο τῆς Διακαινησίμου"),
    7: loc("أحد توما", "Sunday of Thomas", "Κυριακὴ τοῦ Θωμᾶ"),
    14: loc("أحد حاملات الطيب", "Sunday of the Myrrh-bearing Women", "Κυριακὴ τῶν Μυροφόρων"),
    21: loc("أحد المخلع", "Sunday of the Paralytic", "Κυριακὴ τοῦ Παραλύτου"),
    24: loc("منتصف الخمسين", "Mid-Pentecost", "Μεσοπεντηκοστή"),
    28: loc("أحد السامرية", "Sunday of the Samaritan Woman", "Κυριακὴ τῆς Σαμαρείτιδος"),
    35: loc("أحد الأعمى", "Sunday of the Blind Man", "Κυριακὴ τοῦ Τυφλοῦ"),
    39: loc("عيد صعود ربنا", "Ascension of our Lord", "Ἀνάληψις τοῦ Κυρίου"),
    42: loc("أحد آباء المجمع المسكوني الأول", "Sunday of the Fathers of the First Ecumenical Council", "Κυριακὴ τῶν Πατέρων τῆς Α΄ Οἰκουμενικῆς Συνόδου"),
    48: loc("سبت الراقدين قبل العنصرة", "Saturday of Souls before Pentecost", "Ψυχοσάββατο πρὸ τῆς Πεντηκοστῆς"),
    49: loc("عيد العنصرة المقدسة", "Holy Pentecost", "Ἁγία Πεντηκοστή"),
    50: loc("اثنين الروح القدس", "Monday of the Holy Spirit", "Δευτέρα τοῦ Ἁγίου Πνεύματος"),
    56: loc("أحد جميع القديسين", "Sunday of All Saints", "Κυριακὴ τῶν Ἁγίων Πάντων"),
    57: loc("بدء صوم الرسل", "Beginning of the Apostles’ Fast", "Ἀρχὴ Νηστείας τῶν Ἁγίων Ἀποστόλων"),
}


def movable_occasion(day: date) -> dict[str, str] | None:
    for year in (day.year - 1, day.year, day.year + 1):
        pascha = orthodox_pascha_gregorian(year)
        offset = (day - pascha).days
        if offset in MOVABLE_OFFSETS:
            return copy.deepcopy(MOVABLE_OFFSETS[offset])
    return None


def relative_fixed_occasion(day: date) -> dict[str, str] | None:
    """Return important Saturday/Sunday relationships around fixed feasts."""
    for old_month, old_day, key in ((9, 14, "cross"), (12, 25, "nativity"), (1, 6, "theophany")):
        for old_year in (day.year - 1, day.year, day.year + 1):
            feast = julian_to_gregorian_date(old_year, old_month, old_day)
            prev_sunday = feast - timedelta(days=(feast.weekday() - 6) % 7 or 7)
            next_sunday = feast + timedelta(days=(6 - feast.weekday()) % 7 or 7)
            prev_saturday = feast - timedelta(days=(feast.weekday() - 5) % 7 or 7)
            next_saturday = feast + timedelta(days=(5 - feast.weekday()) % 7 or 7)
            labels = {
                ("cross", prev_sunday): loc("الأحد قبل رفع الصليب الكريم", "Sunday before the Exaltation of the Cross", "Κυριακὴ πρὸ τῆς Ὑψώσεως τοῦ Σταυροῦ"),
                ("cross", next_sunday): loc("الأحد بعد رفع الصليب الكريم", "Sunday after the Exaltation of the Cross", "Κυριακὴ μετὰ τὴν Ὕψωσιν τοῦ Σταυροῦ"),
                ("cross", prev_saturday): loc("السبت قبل رفع الصليب الكريم", "Saturday before the Exaltation of the Cross", "Σάββατο πρὸ τῆς Ὑψώσεως τοῦ Σταυροῦ"),
                ("cross", next_saturday): loc("السبت بعد رفع الصليب الكريم", "Saturday after the Exaltation of the Cross", "Σάββατο μετὰ τὴν Ὕψωσιν τοῦ Σταυροῦ"),
                ("nativity", prev_sunday): loc("أحد الآباء القديسين قبل الميلاد", "Sunday of the Holy Fathers before Nativity", "Κυριακὴ τῶν Ἁγίων Πατέρων πρὸ τῶν Χριστουγέννων"),
                ("nativity", next_sunday): loc("الأحد بعد الميلاد", "Sunday after Nativity", "Κυριακὴ μετὰ τὰ Χριστούγεννα"),
                ("theophany", prev_sunday): loc("الأحد قبل الظهور الإلهي", "Sunday before Theophany", "Κυριακὴ πρὸ τῶν Φώτων"),
                ("theophany", next_sunday): loc("الأحد بعد الظهور الإلهي", "Sunday after Theophany", "Κυριακὴ μετὰ τὰ Φῶτα"),
            }
            value = labels.get((key, day))
            if value:
                return value
    return None


def load_exact_2026() -> dict[str, dict]:
    if not H2_PATH.is_file():
        return {}
    payload = json.loads(H2_PATH.read_text(encoding="utf-8"))
    return {str(item.get("date_iso")): item for item in payload.get("days", []) if isinstance(item, dict)}


def load_fixed_lectionary() -> dict[str, dict]:
    if not FIXED_LECTIONARY_PATH.is_file():
        return {}
    return json.loads(FIXED_LECTIONARY_PATH.read_text(encoding="utf-8")).get("feasts", {})


def load_perpetual_lectionary() -> dict[str, dict]:
    if not PERPETUAL_LECTIONARY_PATH.is_file():
        return {}
    payload = json.loads(PERPETUAL_LECTIONARY_PATH.read_text(encoding="utf-8"))
    return payload.get("dates", {}) if isinstance(payload.get("dates"), dict) else {}


def load_native_commemorations() -> dict[str, dict]:
    if not NATIVE_COMM_MEMORATIONS_PATH.is_file():
        return {}
    payload = json.loads(NATIVE_COMM_MEMORATIONS_PATH.read_text(encoding="utf-8"))
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return {
        str(record.get("old_calendar_month_day")): record
        for record in records
        if isinstance(record, dict) and record.get("old_calendar_month_day")
    }


def verified_native_lanes(day: date, records: dict[str, dict]) -> dict[str, dict]:
    _jy, jm, jd = gregorian_to_julian_date(day)
    record = records.get(f"{jm:02d}-{jd:02d}")
    if not isinstance(record, dict) or not isinstance(record.get("lanes"), dict):
        return {}
    accepted_status = {
        "ar": "VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE",
        "en": "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE",
        "el": "VERIFIED_NATIVE_LOCAL_GREEK_SOURCE",
    }
    accepted = {}
    for language, expected_status in accepted_status.items():
        entry = record["lanes"].get(language)
        if not isinstance(entry, dict):
            continue
        if entry.get("evidence_status") != expected_status:
            continue
        if entry.get("jurisdiction") not in {"jerusalem_patriarchate", "jerusalem_jordan"}:
            continue
        if entry.get("comparative") is not False:
            continue
        if entry.get("fixed_slot_eligible") is not True:
            continue
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        accepted[language] = copy.deepcopy(entry)
    return accepted


def appointed_from_refs(refs: dict) -> list[dict]:
    output = []
    for kind in ("epistle", "gospel", "matins_gospel"):
        item = refs.get(kind) if isinstance(refs, dict) else None
        if not isinstance(item, dict):
            continue
        output.append({
            "kind": kind,
            "canonical_reference": str(item.get("canonical_reference") or ""),
            "display_reference": str(item.get("display_reference") or ""),
            "reference": copy.deepcopy(item.get("reference") or {}),
            "source": "pinned_calendar_reference",
        })
    return output


def compact_readings(
    day: date, exact: dict[str, dict], fixed_lectionary: dict[str, dict], perpetual: dict[str, dict]
) -> tuple[dict, list[dict], str, dict]:
    entry = exact.get(day.isoformat())
    if isinstance(entry, dict):
        refs = copy.deepcopy(entry.get("reading_references") or {})
        appointed = appointed_from_refs(refs)
        return refs, appointed, "PINNED_EXACT_DATE_REFERENCE", {
            "status": "APPOINTED_READINGS_PRESENT" if appointed else "PINNED_EXACT_DATE_WITHOUT_APPOINTED_READING",
            "reason": "", "source": "jordan_pinned_exact_date_reference"
        }
    _jy, jm, jd = gregorian_to_julian_date(day)
    fixed = fixed_lectionary.get(f"{jm:02d}-{jd:02d}")
    if isinstance(fixed, dict):
        result = {}
        for kind in ("epistle", "gospel"):
            ref = str(fixed.get(f"{kind}_reference") or "").strip()
            if ref:
                canonical, _ = parse_reference(ref)
                result[kind] = {
                    "canonical_reference": canonical,
                    "display_reference": ref,
                    "reference": {"ar": ref, "en": ref, "el": ref},
                }
        appointed = appointed_from_refs(result)
        return result, appointed, "PINNED_FIXED_FEAST_REFERENCE", {
            "status": "APPOINTED_READINGS_PRESENT" if appointed else "PINNED_FIXED_FEAST_WITHOUT_APPOINTED_READING",
            "reason": "", "source": "jerusalem_fixed_feast_reference"
        }
    baseline = perpetual.get(day.isoformat())
    if isinstance(baseline, dict):
        refs = copy.deepcopy(baseline.get("reading_references") or {})
        appointed = copy.deepcopy(baseline.get("appointed_readings") or [])
        resolution = copy.deepcopy(baseline.get("reading_day_resolution") or {})
        if not resolution:
            resolution = {
                "status": "APPOINTED_READINGS_PRESENT" if appointed else "NO_ABBREVIATED_READING_APPOINTED_BY_SOURCE",
                "reason": "" if appointed else "Pinned perpetual source returned no abbreviated appointed reading for this civil day.",
                "source": "orthocal_greek_julian_reference_baseline",
            }
        return refs, appointed, "PERPETUAL_GREEK_JULIAN_REFERENCE_BASELINE", resolution
    return {}, [], "REFERENCE_PENDING_TWICE_DAILY_VERIFICATION", {
        "status": "UNRESOLVED",
        "reason": "No pinned exact, fixed-feast, or perpetual reference record is available for this civil day.",
        "source": "none",
    }


def primary_and_occasions(day: date, info: dict) -> tuple[dict[str, str], list[dict]]:
    occasions: list[dict] = []
    movable = movable_occasion(day)
    relative = relative_fixed_occasion(day)
    fixed = None
    # Preserve every verified named feast selected by day_info, including an
    # exact annual record such as the 2026 Transfiguration entry. Do not treat
    # unavailable or generic daily placeholders as named occasions.
    if info.get("feast_status") in {"PINNED_FIXED_FEAST", "PINNED_REVIEWED_ANNUAL_ENTRY"}:
        fixed = loc(info["feast_ar"], info["feast_en"], info["feast_el"])
    for kind, value, priority in (
        ("movable", movable, 100),
        ("fixed_major", fixed, 90),
        ("relative_fixed", relative, 80),
    ):
        if value:
            occasions.append({"kind": kind, "priority": priority, "title": value})
    if not occasions:
        sunday = sunday_after_pentecost_label(day)
        if sunday:
            occasions.append({"kind": "sunday_cycle", "priority": 50, "title": sunday})
    occasions.sort(key=lambda item: int(item["priority"]), reverse=True)
    if occasions:
        return copy.deepcopy(occasions[0]["title"]), occasions
    return dated_commemoration_label(day), []


def build() -> dict:
    exact = load_exact_2026()
    fixed_lectionary = load_fixed_lectionary()
    perpetual_lectionary = load_perpetual_lectionary()
    native_commemorations = load_native_commemorations()
    days = []
    cursor = START
    exact_reading_days = 0
    occasion_days = 0
    native_lane_days = 0
    while cursor <= END:
        info = day_info(cursor)
        primary, occasions = primary_and_occasions(cursor, info)
        native_lanes = verified_native_lanes(cursor, native_commemorations)
        native_lane_refs = {
            language: {
                "text": entry["text"],
                "source_id": entry.get("source_id", ""),
                "evidence_status": entry.get("evidence_status", ""),
            }
            for language, entry in native_lanes.items()
        }
        # A verified local lane may enrich an ordinary date without replacing a
        # movable or major fixed occasion. Missing language lanes remain the
        # existing same-language baseline; no cross-language fallback is used.
        if native_lanes and not occasions:
            primary = copy.deepcopy(primary)
            for language, entry in native_lanes.items():
                primary[language] = entry["text"]
        if native_lanes:
            native_lane_days += 1
        readings, appointed_readings, reference_status, reading_day_resolution = compact_readings(cursor, exact, fixed_lectionary, perpetual_lectionary)
        if readings:
            exact_reading_days += 1
        if occasions:
            occasion_days += 1
        jy, jm, jd = gregorian_to_julian_date(cursor)
        selection = liturgy_service_selection(cursor, info)
        commemoration_status = "PINNED_INTERNAL_RULE" if occasions else "PINNED_INTERNAL_OLD_CALENDAR_DATE"
        days.append({
            "date": cursor.isoformat(),
            "date_iso": cursor.isoformat(),
            "civil_weekday": {"ar": AR_DAYS[cursor.weekday()], "en": EN_DAYS[cursor.weekday()], "el": EL_DAYS[cursor.weekday()]},
            "julian_date": f"{jy:04d}-{jm:02d}-{jd:02d}",
            "commemoration": {
                "name": copy.deepcopy(primary),
                "status": commemoration_status,
                "source_kind": "internal_named_occasion" if occasions else "old_calendar_date_baseline",
            },
            "commemoration_status": commemoration_status,
            "feast": primary,
            "occasions": occasions,
            "occasion_status": commemoration_status,
            "fasting": {
                "code": info["fasting"].get("code"),
                "title": copy.deepcopy(info["fasting"].get("title") or {}),
                "detail": copy.deepcopy(info["fasting"].get("detail") or {}),
                "is_fast": bool(info["fasting"].get("is_fast")),
                "display_icons": copy.deepcopy(info["fasting"].get("display_icons") or []),
                "items": copy.deepcopy(info["fasting"].get("items") or []),
                "guidance": copy.deepcopy(info["fasting"].get("guidance") or {}),
                "abstinence": copy.deepcopy(info["fasting"].get("abstinence") or {}),
                "verification": copy.deepcopy(info["fasting"].get("verification") or {}),
            },
            "reading_references": readings,
            "appointed_readings": appointed_readings,
            "reference_status": reference_status,
            "reading_day_resolution": reading_day_resolution,
            "liturgy_service_selection": {
                "service_type": selection.get("service_type"),
                "service_form": selection.get("service_form"),
                "rule_id": selection.get("rule_id"),
                "label": copy.deepcopy(selection.get("label") or {}),
                "displayable": bool(selection.get("displayable")),
                "wrong_liturgy_fallback_allowed": False,
            },
            "source_policy": "INTERNAL_BASELINE_PLUS_TWICE_DAILY_SIGNED_CORRECTIONS",
        })
        cursor += timedelta(days=1)
    return {
        "schema_version": 1,
        "calendar": "jerusalem_jordan_julian_old_calendar",
        "civil_range": {"start": START.isoformat(), "end": END.isoformat(), "day_count": len(days)},
        "visible_window_days": 9,
        "update_schedule": {"timezone": "Asia/Amman", "times": ["04:23", "16:43"]},
        "policy": {
            "offline_baseline": True,
            "major_fixed_and_movable_occasions": True,
            "daily_commemoration_label_offline": True,
            "named_saints_require_verified_native_source": True,
            "exact_readings_require_pinned_or_signed_source": True,
            "perpetual_reference_baseline": bool(perpetual_lectionary),
            "perpetual_baseline_is_not_jurisdiction_override": True,
            "machine_translation": False,
        "cross_language_fallback": False,
        "native_fixed_commemoration_source": "canonical/jerusalem_jordan_fixed_commemorations_native.json",
        "strict_named_local_three_language_gate": False,
        "future_synodal_changes_applied_by_signed_update": True,
        },
        "coverage": {
            "structural_days": len(days),
            "days_with_named_internal_occasion": occasion_days,
            "days_with_offline_commemoration": len(days),
            "days_with_verified_native_language_lane": native_lane_days,
            "days_with_pinned_reading_references": exact_reading_days,
            "days_with_appointed_readings": sum(1 for item in days if item.get("appointed_readings")),
            "days_with_epistle_and_gospel": sum(1 for item in days if {"epistle", "gospel"}.issubset((item.get("reading_references") or {}).keys())),
            "days_with_reading_day_resolution": sum(1 for item in days if (item.get("reading_day_resolution") or {}).get("status") not in {"", "UNRESOLVED", None}),
            "days_resolved_without_abbreviated_appointed_reading": sum(1 for item in days if (item.get("reading_day_resolution") or {}).get("status") == "NO_ABBREVIATED_READING_APPOINTED_BY_SOURCE"),
            "end_of_horizon": END.isoformat(),
        },
        "days": days,
    }


def _compact_fasting(item: dict) -> dict:
    fasting = item.get("fasting") if isinstance(item.get("fasting"), dict) else {}
    return {
        "code": fasting.get("code"),
        "title": fasting.get("title") or {},
        "detail": fasting.get("detail") or {},
        "is_fast": bool(fasting.get("is_fast")),
        "display_icons": fasting.get("display_icons") or [],
        "items": fasting.get("items") or [],
        "verification": {
            "status": str((fasting.get("verification") or {}).get("status") or "TYPICON_BASELINE"),
            "policy": str((fasting.get("verification") or {}).get("policy") or "canonical/fasting_policy.json"),
            "rule": str((fasting.get("verification") or {}).get("rule") or ""),
        },
        "abstinence": (
            fasting.get("abstinence")
            if isinstance(fasting.get("abstinence"), dict)
            and bool(fasting.get("abstinence").get("applies"))
            else {}
        ),
    }


def _fasting_profile_id(fasting: dict) -> str:
    serialized = json.dumps(fasting, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "fasting_" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _asset_day(item: dict, fasting_profile_id: str) -> dict:
    # Keep provenance compact. User-facing fasting guidance is de-duplicated in
    # fasting_profiles and resolved by DataRepository before a screen consumes it.
    fasting = item.get("fasting") if isinstance(item.get("fasting"), dict) else {}
    selection = item.get("liturgy_service_selection") if isinstance(item.get("liturgy_service_selection"), dict) else {}
    appointed = item.get("appointed_readings") if isinstance(item.get("appointed_readings"), list) else []
    occasions = item.get("occasions") if isinstance(item.get("occasions"), list) else []
    kind_counts = {}
    for reading in appointed:
        if isinstance(reading, dict):
            kind = str(reading.get("kind") or "appointed")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
    # The ordinary one-Epistle/one-Gospel case is already represented by
    # reading_references. Keep appointed_readings in the APK only when they add
    # information (OT/Lenten readings, multiple appointed passages, etc.).
    appointed_asset = appointed if (
        any(kind not in {"epistle", "gospel", "matins_gospel"} for kind in kind_counts)
        or any(count > 1 for count in kind_counts.values())
    ) else []
    return {
        "date": item["date"],
        "date_iso": item["date_iso"],
        "civil_weekday": item["civil_weekday"],
        "julian_date": item["julian_date"],
        # The compact Android year asset reuses feast + occasion_status as the
        # commemoration fallback to avoid duplicating the same three-language text.
        "feast": item["feast"],
        "occasions": occasions if len(occasions) > 1 else [],
        "occasion_status": item["occasion_status"],
        "status": fasting.get("title") or {},
        "fast": fasting.get("title") or {},
        "fasting": {"profile_id": fasting_profile_id},
        "reading_references": item.get("reading_references") or {},
        "appointed_readings": appointed_asset,
        "reference_status": item.get("reference_status"),
        "reading_day_resolution": item.get("reading_day_resolution") or {},
        "liturgy_service_selection": {
            "service_type": selection.get("service_type"),
            "service_form": selection.get("service_form"),
            "rule_id": selection.get("rule_id"),
            "label": selection.get("label") or {},
            "displayable": bool(selection.get("displayable")),
            "wrong_liturgy_fallback_allowed": False,
        },
    }


def write(payload: dict) -> None:
    OUT_CANONICAL.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    by_year: dict[int, list[dict]] = {}
    for item in payload["days"]:
        year = int(str(item["date_iso"])[:4])
        by_year.setdefault(year, []).append(item)
    index = {
        "schema_version": 1,
        "calendar": payload["calendar"],
        "civil_range": payload["civil_range"],
        "visible_window_days": payload["visible_window_days"],
        "update_schedule": payload["update_schedule"],
        "years": {},
    }
    for year, days in sorted(by_year.items()):
        name = f"calendar_{year}.json"
        profiles: dict[str, dict] = {}
        asset_days = []
        for item in days:
            fasting = _compact_fasting(item)
            profile_id = _fasting_profile_id(fasting)
            profiles[profile_id] = fasting
            asset_days.append(_asset_day(item, profile_id))
        year_payload = {
            "schema_version": 1,
            "calendar": payload["calendar"],
            "year": year,
            "civil_range": {"start": asset_days[0]["date_iso"], "end": asset_days[-1]["date_iso"], "day_count": len(asset_days)},
            "fasting_profiles": {key: profiles[key] for key in sorted(profiles)},
            "days": asset_days,
        }
        target = OUT_ASSET_DIR / name
        target.write_text(json.dumps(year_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        index["years"][str(year)] = {"asset": f"data/calendar/{name}", "day_count": len(asset_days), "bytes": target.stat().st_size}
    OUT_ASSET_INDEX.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    payload = build()
    write(payload)
    asset_bytes = sum(int(item["bytes"]) for item in json.loads(OUT_ASSET_INDEX.read_text(encoding="utf-8"))["years"].values())
    print(
        "INTERNAL_CALENDAR_2050_OK "
        f"start={payload['civil_range']['start']} end={payload['civil_range']['end']} "
        f"days={payload['civil_range']['day_count']} asset_bytes={asset_bytes}"
    )


if __name__ == "__main__":
    main()
