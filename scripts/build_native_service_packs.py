#!/usr/bin/env python3
"""Build three independent native-language service packs from the reviewed library.

The application never translates one pack into another. Each non-empty language pack
is tied to an official source entry and the project owner's recorded permission.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/services/library.json"
MANIFEST = ROOT / "canonical/native_service_manifest.json"
REGISTRY = ROOT / "canonical/native_language_sources.json"
OUTPUTS = [ROOT / "data/services/native", ROOT / "app/src/main/assets/data/native"]
OVERRIDE_ROOT = ROOT / "data/services/native_overrides"
LANGS = ("ar", "el", "en")

NATIVE_SOURCE_NOTICES = {
    "ar": "النص المعروض في هذه الحزمة مأخوذ من مصدر عربي أصلي مسجل، وليس ناتجًا عن ترجمة آلية.",
    "en": "The text displayed in this pack comes from a registered native English source and is not machine-translated.",
    "el": "Τὸ κείμενο αὐτοῦ τοῦ πακέτου προέρχεται ἀπὸ καταχωρισμένη πρωτότυπη ἑλληνικὴ πηγὴ καὶ δὲν εἶναι μηχανικὴ μετάφραση.",
}


DYNAMIC_SLOT_ANCHORS: dict[str, dict[str, tuple[str, str, str]]] = {
    "ar": {
        "[طروبارية اليوم]": ("daily_troparion", "replace", "المرتل"),
        "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]": ("church_troparion", "replace", "المرتل"),
        "[القنداق]": ("daily_kontakion", "replace", "المرتل"),
        "[البروكيمنن]": ("prokeimenon", "replace", "القارئ"),
        "[فصل من رسالة اليوم]": ("epistle", "replace", "القارئ"),
        "[فصل الإنجيل المعيّن لهذا اليوم]": ("gospel", "replace", "الكاهن"),
        "[آية المناولة]": ("communion_hymn", "replace", "المرتل"),
    },
    "en": {
        "(The Bishop and all the Clergy enter the Sanctuary. The Apolytikia of the day, the Troparion of the Church and the Kontakion are sung.)":
            ("daily_hymns", "after", "Chanter"),
        "(The Reader reads the verses from the Psalms.)": ("prokeimenon", "after", "Reader"),
        "(The Reader reads the designated Apostolic text.)": ("epistle", "after", "Reader"),
        "(The Deacon reads the designated text of the Holy Gospel.)": ("gospel", "after", "Deacon"),
    },
    "el": {
        "(Ὁ Ἀρχιερεύς μεθ’ ὅλου τοῦ Ἱερατείου εἰσέρχονται εἰς τό ἅγιον Βῆμα. Ψάλλονται δέ, τὰ ἀπολυτίκια τῆς ἡμέρας, τό τροπάριον τοῦ ναοῦ καί τό κοντάκιον).":
            ("daily_hymns", "after", "Ψάλτης"),
        "(Ὁ Ἀναγνώστης τό Προκείμενον τοῦ Ἀποστόλου).": ("prokeimenon", "after", "Ἀναγνώστης"),
        "(Ὁ Ἀναγνώστης ἀναγινώσκει τὴν τεταγμένην Ἀποστολικὴν περικοπήν).":
            ("epistle", "after", "Ἀναγνώστης"),
        "Δόξα σοι, Κύριε, Δόξα σοι. Ὁ Διάκονος ἀναγινώσκει τὴν τεταγμένην περικοπὴν τοῦ ἁγίου Εὐαγγελίου.":
            ("gospel", "after", "Διάκονος"),
    },
}

GOSPEL_NAME_MARKERS = {
    "ar": "[اسم الإنجيلي]",
    "en": "(Name)",
    "el": "(Ὂνομα)",
}


def annotate_dynamic_slots(service: dict[str, Any], lang: str) -> None:
    """Attach stable semantic slots to the reviewed native Liturgy.

    Daily data used to target Arabic placeholder strings. Native English and
    Greek editions have no Arabic placeholders, so their verified readings
    could never appear inside the service. These annotations are metadata only:
    they do not alter a single source word.
    """
    if service.get("id") != "divine_liturgy":
        return
    anchors = DYNAMIC_SLOT_ANCHORS[lang]
    found: set[str] = set()
    inline_found = False
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        localized = segment.get("text")
        text = str(localized.get(lang) or "") if isinstance(localized, dict) else ""
        match = anchors.get(text)
        if match:
            slot, mode, speaker = match
            segment["dynamic_slot"] = slot
            segment["dynamic_slot_mode"] = mode
            segment["dynamic_slot_speaker"] = {
                key: speaker if key == lang else "" for key in LANGS
            }
            found.add(slot)
        marker = GOSPEL_NAME_MARKERS[lang]
        if marker in text:
            segment["dynamic_inline_slot"] = "gospel_evangelist_name"
            segment["dynamic_inline_marker"] = marker
            inline_found = True

    required = {"daily_hymns", "prokeimenon", "epistle", "gospel"} if lang != "ar" else {
        "daily_troparion", "church_troparion", "daily_kontakion",
        "prokeimenon", "epistle", "gospel",
    }
    missing = sorted(required - found)
    if missing or not inline_found:
        detail = ", ".join(missing) if missing else "gospel_evangelist_name"
        raise SystemExit(f"divine_liturgy.{lang}: dynamic slot anchor missing: {detail}")


def localized_for_language(value: Any, lang: str) -> Any:
    if isinstance(value, list):
        return [localized_for_language(item, lang) for item in value]
    if not isinstance(value, dict):
        return value
    if any(key in value for key in LANGS):
        result = copy.deepcopy(value)
        for key in LANGS:
            result[key] = str(value.get(key) or "") if key == lang else ""
        return result
    return {key: localized_for_language(child, lang) for key, child in value.items()}


def text_hash(service: dict[str, Any], lang: str) -> str:
    pieces: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if lang in value and any(key in value for key in LANGS):
                text = str(value.get(lang) or "").strip()
                if text:
                    pieces.append(text)
            else:
                for child in value.values():
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(service)
    return hashlib.sha256("\n".join(pieces).encode("utf-8")).hexdigest()



def localized_counts(value: Any, lang: str) -> tuple[int, int]:
    total = 0
    filled = 0
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            total += 1
            if str(value.get(lang) or "").strip():
                filled += 1
        else:
            for child in value.values():
                child_total, child_filled = localized_counts(child, lang)
                total += child_total
                filled += child_filled
    elif isinstance(value, list):
        for child in value:
            child_total, child_filled = localized_counts(child, lang)
            total += child_total
            filled += child_filled
    return total, filled

def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    services_manifest = manifest["services"]
    sources = registry["sources"]

    source_services = source.get("services", [])
    missing = sorted({item.get("id") for item in source_services} - set(services_manifest))
    if missing:
        raise SystemExit("Native source manifest is missing services: " + ", ".join(missing))

    for lang in LANGS:
        pack = {
            "schema_version": 1,
            "language": lang,
            "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY",
            "machine_translation_used": False,
            "permission_basis": registry["permission_basis"],
            "categories": localized_for_language(source.get("categories", []), lang),
            "services": [],
        }
        pack_total = 0
        pack_filled = 0
        for raw in source_services:
            service_id = raw["id"]
            entry = services_manifest[service_id][lang]
            source_id = entry["source_id"]
            source_info = sources[source_id]
            if source_info["language"] != lang:
                raise SystemExit(f"{service_id}.{lang} points to a {source_info['language']} source")
            override_path = OVERRIDE_ROOT / lang / f"{service_id}.json"
            if override_path.exists():
                service = json.loads(override_path.read_text(encoding="utf-8"))
                if service.get("id") != service_id:
                    raise SystemExit(f"{override_path}: service id mismatch")
            else:
                service = localized_for_language(raw, lang)
                if "notice" in service:
                    service["notice"] = {
                        key: NATIVE_SOURCE_NOTICES[lang] if key == lang else ""
                        for key in LANGS
                    }
            annotate_dynamic_slots(service, lang)
            service.pop("translation_status", None)
            service["source_language"] = lang
            service["content_mode"] = "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY"
            service_total, service_filled = localized_counts(service, lang)
            pack_total += service_total
            pack_filled += service_filled
            service["native_content_status"] = {
                "filled_fields": service_filled,
                "total_fields": service_total,
                "complete": service_filled == service_total,
            }
            service["native_source"] = {
                "source_id": source_id,
                "name": source_info["name"],
                "official": source_info["official"],
                "native_language": lang,
                "url": entry["url"],
                "permission_confirmed": source_info["permission_confirmed"],
                "machine_translation_used": False,
                "content_sha256": text_hash(service, lang),
                "import_status": "AUTHORIZED_NATIVE_SOURCE_IMPORT" if service_filled else "AUTHORIZED_SOURCE_REGISTERED_TEXT_PENDING"
            }
            # Old service-wide provenance is retained only as audit history.
            if "source_provenance" in service:
                service["legacy_provenance_audit"] = service.pop("source_provenance")
            pack["services"].append(service)

        pack["native_content_status"] = {
            "filled_fields": pack_filled,
            "total_fields": pack_total,
            "percent": 100 if pack_total == 0 else round(pack_filled * 100 / pack_total, 1),
            "complete": pack_filled == pack_total,
        }
        payload = json.dumps(pack, ensure_ascii=False, indent=2) + "\n"
        for output_dir in OUTPUTS:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"library_{lang}.json").write_text(payload, encoding="utf-8")
        print(f"Built native {lang} service pack with {len(pack['services'])} services")


if __name__ == "__main__":
    main()
