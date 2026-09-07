#!/usr/bin/env python3
"""Fail-closed structural audit for appointed liturgies.

This validates the ordered core from the opening blessing through dismissal in
all published native lanes. It does not claim ecclesiastical word-by-word
certification; it prevents missing/reordered sections from being published as
a complete service.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
SERVICES = ("divine_liturgy", "divine_liturgy_basil", "presanctified_liturgy")

ANCHORS = {
    "divine_liturgy": {
        "ar": [
            ("opening", ("الاستعداد وبداية القداس",)),
            ("antiphons", ("الطلبة السلامية الكبرى", "صلاة الأنتيفونا الأولى")),
            ("entrance", ("الدخول الصغير", "أثناء الدخول الصغير")),
            ("readings", ("القراءات: الرسالة", "القراءات")),
            ("gospel", ("الإنجيل المقدس",)),
            ("great_entrance", ("الدورة الكبرى", "الدخول الكبير")),
            ("creed", ("قانون الإيمان",)),
            ("anaphora", ("الأنافورا المقدسة",)),
            ("communion", ("المناولة المقدسة",)),
            ("dismissal", ("الختام والصرف",)),
        ],
        "en": [
            ("opening", ("THE GREAT LITANY",)),
            ("antiphons", ("THE FIRST ANTIPHON",)),
            ("entrance", ("THE ENTRANCE",)),
            ("readings", ("THE READINGS THE EPISTLE",)),
            ("gospel", ("THE HOLY GOSPEL",)),
            ("great_entrance", ("THE GREAT ENTRANCE",)),
            ("creed", ("THE CREED",)),
            ("anaphora", ("THE HOLY ANAPHORA",)),
            ("communion", ("HOLY COMMUNION",)),
            ("dismissal", ("THE DISMISSAL",)),
        ],
        "el": [
            ("opening", ("Η ΜΕΓΑΛΗ ΣΥΝΑΠΤΗ",)),
            ("antiphons", ("ΤΟ ΠΡΩΤΟΝ ΑΝΤΙΦΩΝΟΝ",)),
            ("entrance", ("Η ΜΙΚΡΑ ΕΙΣΟΔΟΣ",)),
            ("readings", ("ΤΑ ΑΝΑΓΝΩΣΜΑΤΑ", "Ο ΑΠΟΣΤΟΛΟΣ")),
            ("gospel", ("ΤΟ ΙΕΡΟΝ ΕΥΑΓΓΕΛΙΟΝ",)),
            ("great_entrance", ("Η ΜΕΓΑΛΗ ΕΙΣΟΔΟΣ",)),
            ("creed", ("ΣΥΜΒΟΛΟΝ ΤΗΣ ΠΙΣΤΕΩΣ",)),
            ("anaphora", ("Η ΑΓΙΑ ΑΝΑΦΟΡΑ",)),
            ("communion", ("Η ΘΕΙΑ ΜΕΤΑΛΗΨΙΣ",)),
            ("dismissal", ("ΑΠΟΛΥΣΙΣ",)),
        ],
    },
    "divine_liturgy_basil": {
        "ar": [
            ("opening", ("الاستعداد وبداية القداس",)),
            ("antiphons", ("الطلبة السلامية الكبرى", "صلاة الأنتيفونا الأولى")),
            ("entrance", ("الدخول الصغير", "أثناء الدخول الصغير")),
            ("readings", ("القراءات: الرسالة", "القراءات")),
            ("gospel", ("الإنجيل المقدس",)),
            ("great_entrance", ("الدورة الكبرى", "الدخول الكبير")),
            ("creed", ("قانون الإيمان",)),
            ("anaphora", ("الأنافورا المقدسة للقديس باسيليوس",)),
            ("communion", ("المناولة المقدسة",)),
            ("dismissal", ("الختام والصرف",)),
        ],
        "en": [
            ("opening", ("GREAT LITANY",)),
            ("antiphons", ("PRAYER OF FIRST ANTIPHON",)),
            ("entrance", ("THE SMALL ENTRANCE",)),
            ("readings", ("EPISTLE READING",)),
            ("gospel", ("THE GOSPEL",)),
            ("great_entrance", ("THE GREAT ENTRANCE",)),
            ("creed", ("THE CREED",)),
            ("anaphora", ("HOLY ANAPHORA",)),
            ("communion", ("COMMUNION",)),
            ("dismissal", ("DISMISSAL",)),
        ],
        "el": [
            ("opening", ("ΕΝΑΡΞΙΣ, ΕΙΡΗΝΙΚΑ",)),
            ("antiphons", ("ΕΥΧΗ Αʹ ΑΝΤΙΦΩΝΟΥ",)),
            ("entrance", ("Η ΕΙΣΟΔΟΣ",)),
            ("readings", ("Ὁ Ἀποστολος", "ΑΠΟΣΤΟΛΟΣ")),
            ("gospel", ("Τὸ Εὐαγγέλιον", "ΕΥΑΓΓΕΛΙΟΥ")),
            ("great_entrance", ("Η ΕΙΣΟΔΟΣ ΤΩΝ ΤΙΜΙΩΝ ΔΩΡΩΝ",)),
            ("creed", ("Σύμβολον τῆς Πίστεως",)),
            ("anaphora", ("Η ΑΓΙΑ ΑΝΑΦΟΡΑ",)),
            ("communion", ("ΜΕΤΑΛΗΨΙΣ", "ΚΟΙΝΩΝΙΑ")),
            ("dismissal", ("ΑΠΟΛΥΣΙΣ",)),
        ],
    },
    "presanctified_liturgy": {
        "ar": [
            ("opening", ("القداس السابق تقديسه", "وتسمى خدمةالمقدسات السابق تقديسها", "البرويجيازميني", "مباركة الملكوت")),
            ("psalmody", ("المزمور", "المزامير", "المزامير الملوكية")),
            ("readings", ("القراءة", "القراءات", "البروكيمن")),
            ("entrance", ("دخول الهدايا السابق تقديسها", "دخول الهدايا", "الدخول")),
            ("communion", ("المناولة", "التناول")),
            ("dismissal", ("الصرف", "الختام")),
        ],
        "en": [
            ("opening", ("LITURGY OF THE PRESANCTIFIED", "BLESSING OF THE KINGDOM")),
            ("psalmody", ("PSALM", "PSALMS", "KATHISMATA")),
            ("readings", ("READING", "READINGS", "PROKEIMENON")),
            ("entrance", ("ENTRANCE OF PRESANCTIFIED GIFTS",)),
            ("communion", ("COMMUNION",)),
            ("dismissal", ("DISMISSAL",)),
        ],
        "el": [
            ("opening", ("ΕΥΛΟΓΗΜΕΝΗ Η ΒΑΣΙΛΕΙΑ", "ΠΡΟΗΓΙΑΣΜΕΝΩΝ ΔΩΡΩΝ")),
            ("psalmody", ("ΨΑΛΜΟΣ", "ΚΑΘΙΣΜΑΤΟΣ")),
            ("readings", ("ΑΝΑΓΝΩΣΜΑ", "ΠΡΟΚΕΙΜΕΝΟΝ")),
            ("entrance", ("ΕΙΣΟΔΟΣ", "ΠΡΟΗΓΙΑΣΜΕΝΩΝ")),
            ("communion", ("ΚΟΙΝΩΝΙΑ", "ΜΕΤΑΛΗΨΙΣ")),
            ("dismissal", ("ΑΠΟΛΥΣΙΣ",)),
        ],
    },
}


def load(language: str) -> dict:
    path = ROOT / f"app/src/main/assets/data/native/library_{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFD", value.upper().replace("’", "'").replace("ʼ", "'"))
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"[\u064B-\u065F\u0670]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def segment_label(segment: dict, language: str) -> str:
    block = segment.get("title") if segment.get("type") == "section" else segment.get("text")
    return str((block or {}).get(language) or "") if isinstance(block, dict) else ""


def validate_service(service: dict, service_id: str, language: str, errors: list[str]) -> None:
    segments = service.get("segments") or []
    if not segments:
        errors.append(f"{language}.{service_id}: no segments")
        return
    previous = -1
    for name, alternatives in ANCHORS[service_id][language]:
        found = None
        for index in range(previous + 1, len(segments)):
            haystack = normalized(segment_label(segments[index], language))
            if any(normalized(option) in haystack for option in alternatives):
                found = index
                break
        if found is None:
            errors.append(f"{language}.{service_id}: missing_or_out_of_order:{name}")
        else:
            previous = found
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            errors.append(f"{language}.{service_id}: invalid_segment:{index}")
            continue
        key = "title" if segment.get("type") == "section" else "text"
        block = segment.get(key)
        if not isinstance(block, dict) or not str(block.get(language) or "").strip():
            errors.append(f"{language}.{service_id}: blank_native_text:{index}")


def main() -> None:
    errors: list[str] = []
    editions = json.loads((ROOT / "canonical" / "liturgy_service_editions.json").read_text(encoding="utf-8")).get("editions") or {}
    active_services = []
    for rite, edition in editions.items():
        if not isinstance(edition, dict):
            continue
        service_id = str(edition.get("service_id") or "")
        if edition.get("displayable") is True:
            if service_id in SERVICES:
                active_services.append(service_id)
        elif rite in {"basil", "presanctified", "james"}:
            status = str(edition.get("phase8_review_status") or "")
            if not status.startswith("BLOCKED_"):
                errors.append(f"{rite}: blocked publication lacks explicit BLOCKED status")
    for language in LANGUAGES:
        services = {str(s.get("id")): s for s in (load(language).get("services") or []) if isinstance(s, dict)}
        for service_id in active_services:
            service = services.get(service_id)
            if service is None:
                errors.append(f"{language}.{service_id}: missing_from_native_library")
                continue
            validate_service(service, service_id, language, errors)
    if errors:
        for error in errors[:100]:
            print("LITURGY_STRUCTURE_ERROR", error)
        raise SystemExit(f"LITURGY_STRUCTURE_INVALID errors={len(errors)}")
    print(f"LITURGY_STRUCTURE_OK active_services={len(active_services)} languages=3 ordered_core=true blocked_rites_fail_closed=true")


if __name__ == "__main__":
    main()
