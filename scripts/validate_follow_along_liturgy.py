#!/usr/bin/env python3
"""Validate the compact believer-facing Liturgy profile."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from android_ui_resources import source_references_text

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "canonical/follow_along_liturgy_contract.json"
PACK_ROOT = ROOT / "app/src/main/assets/data/native"
LANGUAGES = ("ar", "en", "el")

SECTION_ANCHORS = {
    "ar": ("الدخول الصغير", "الدورة الكبرى", "المناولة", "الختام والصرف"),
    "en": ("THE ENTRANCE", "THE GREAT ENTRANCE", "HOLY COMMUNION", "THE DISMISSAL"),
    "el": ("Η ΜΙΚΡΑ ΕΙΣΟΔΟΣ", "Η ΜΕΓΑΛΗ ΕΙΣΟΔΟΣ", "Η ΘΕΙΑ ΜΕΤΑΛΗΨΙΣ", "ΑΠΟΛΥΣΙΣ"),
}


def service_by_id(pack: dict[str, Any], service_id: str) -> dict[str, Any] | None:
    for service in pack.get("services") or []:
        if isinstance(service, dict) and service.get("id") == service_id:
            return service
    return None


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []

    scope = contract.get("product_scope") or {}
    model = contract.get("content_model") or {}
    update = contract.get("update_policy") or {}
    text_rules = contract.get("religious_text_rules") or {}
    if scope.get("download_full_religious_book_libraries") is not False:
        errors.append("full religious book-library downloads must remain disabled")
    if model.get("fixed_template") != "library:divine_liturgy":
        errors.append("the one fixed Liturgy template is not configured")
    if update.get("timezone") != "Asia/Amman" or update.get("windows") != ["04:23", "16:43"]:
        errors.append("the update windows must be 04:23 and 16:43 Asia/Amman")
    for rule in (
        "translation_between_lanes",
        "machine_translation",
        "ai_generation_or_rewriting",
        "automatic_diacritization",
        "cross_language_fallback",
    ):
        if text_rules.get(rule) is not False:
            errors.append(f"religious_text_rules.{rule} must be false")

    required_slots = set((contract.get("dynamic_slots") or {}).get("required") or [])
    language_contracts = contract.get("language_lanes") or {}
    for language in LANGUAGES:
        path = PACK_ROOT / f"library_{language}.json"
        pack = json.loads(path.read_text(encoding="utf-8"))
        liturgy = service_by_id(pack, "divine_liturgy")
        if liturgy is None:
            errors.append(f"{language}: divine_liturgy is missing")
            continue
        source_id = str((liturgy.get("native_source") or {}).get("source_id") or "")
        allowed_static = set((language_contracts.get(language) or {}).get("static_sources") or [])
        if source_id not in allowed_static:
            errors.append(f"{language}: Liturgy source {source_id!r} is outside the focused profile")

        segments = [item for item in liturgy.get("segments") or [] if isinstance(item, dict)]
        slots = {str(item.get("dynamic_slot")) for item in segments if item.get("dynamic_slot")}
        missing_slots = sorted(required_slots - slots)
        if missing_slots:
            errors.append(f"{language}: missing daily slots: {', '.join(missing_slots)}")

        section_text = "\n".join(
            str((item.get("title") or {}).get(language) or "")
            for item in segments
            if item.get("type") == "section"
        )
        for anchor in SECTION_ANCHORS[language]:
            if anchor not in section_text:
                errors.append(f"{language}: Liturgy phase is missing: {anchor}")

        silent = [item for item in segments if item.get("delivery") == "silent"]
        actors = {str(item.get("delivery_actor") or "") for item in silent}
        if not {"priest", "faithful"}.issubset(actors):
            errors.append(f"{language}: explicit priest/faithful silent-text markers are incomplete")

        serialized = json.dumps(liturgy, ensure_ascii=False)
        if "******" in serialized:
            errors.append(f"{language}: imported source separator artifact remains")


    arabic_pack = json.loads((PACK_ROOT / "library_ar.json").read_text(encoding="utf-8"))
    proskomide = service_by_id(arabic_pack, "proskomide")
    if proskomide is None:
        errors.append("ar: proskomide is missing")
    else:
        proskomide_segments = [item for item in proskomide.get("segments") or [] if isinstance(item, dict)]
        visible = json.dumps(proskomide_segments, ensure_ascii=False)
        for marker in (
            "واثعنليمعشرصجولتاد",
            "هلماندهنسجد",
            "صلوة نصفالليل اليومية",
            "१ صلوة",
        ):
            if marker in visible:
                errors.append(f"ar: corrupt Horologion OCR remains after the Proskomide conclusion: {marker}")
        if len(proskomide_segments) != 77:
            errors.append(f"ar: Proskomide must end at its valid dismissal; got {len(proskomide_segments)} segments")
        final_title = str((proskomide_segments[-2].get("title") or {}).get("ar") or "") if len(proskomide_segments) >= 2 else ""
        if final_title != "ختام خدمة التقدمة":
            errors.append("ar: Proskomide does not end with ختام خدمة التقدمة")

    coordinator = (
        ROOT
        / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java"
    ).read_text(encoding="utf-8")
    repository = (
        ROOT
        / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"
    ).read_text(encoding="utf-8")
    home = (
        ROOT
        / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
    ).read_text(encoding="utf-8")
    if "MORNING_REFRESH_HOUR = 4" not in coordinator or "EVENING_REFRESH_HOUR = 16" not in coordinator:
        errors.append("Android twice-daily 04:23/16:43 scheduling is not wired")
    if "DailySnapshotRegressionGuard.firstRegression" not in repository:
        errors.append("same-day non-regression protection is not wired")
    if not source_references_text(home, "قداس اليوم الكامل", "ar") or '"divine_liturgy"' not in home:
        errors.append("the Home screen does not open the full Liturgy directly")
    if "specificCommemoration(today)" in home or "DayOfWeek.SUNDAY" in home:
        errors.append("the bottom Home card must remain a fixed complete St John Liturgy shortcut")
    if "thanksgivingSegmentsForLiturgy" not in repository or "arabicThanksgivingVariant" not in repository:
        errors.append("service-specific thanksgiving filtering is not wired")

    if errors:
        raise SystemExit("Follow-along Liturgy validation failed:\n- " + "\n- ".join(errors))
    print(
        "Follow-along Liturgy validated: one native-language service, daily slots, "
        "silent-role markers, and two non-regressing daily updates at 04:23 and 16:43"
    )


if __name__ == "__main__":
    main()
