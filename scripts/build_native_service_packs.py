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
        "[إنجيل السَحَر المعيّن لهذا اليوم]": ("matins_gospel", "replace", "القارئ"),
        "[طروبارية اليوم]": ("daily_troparion", "replace", "المرتل"),
        "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]": ("church_troparion", "replace", "المرتل"),
        "[القنداق]": ("daily_kontakion", "replace", "المرتل"),
        "[البروكيمنن]": ("prokeimenon", "replace", "القارئ"),
        "[فصل من رسالة اليوم]": ("epistle", "replace", "القارئ"),
        "[فصل الإنجيل المعيّن لهذا اليوم]": ("gospel", "replace", "الكاهن"),
        "[آية المناولة]": ("communion_hymn", "replace", "المرتل"),
        "سبحوا الرب من السماوات، سبحوه في الأعالي. هللويا.":
            ("communion_hymn", "replace_if_present", "المرتل"),
    },
    "en": {
        "[Matins Gospel appointed for today]": ("matins_gospel", "replace", "Reader"),
        "(The Bishop and all the Clergy enter the Sanctuary. The Apolytikia of the day, the Troparion of the Church and the Kontakion are sung.)":
            ("daily_hymns", "after", "Chanter"),
        "(The Reader reads the verses from the Psalms.)": ("prokeimenon", "after", "Reader"),
        "(The Reader reads the designated Apostolic text.)": ("epistle", "after", "Reader"),
        "(The Deacon reads the designated text of the Holy Gospel.)": ("gospel", "after", "Deacon"),
        "Praise the Lord from the Heavens; praise Him in the highest. Alleluia (3)":
            ("communion_hymn", "replace_if_present", "Chanter"),
    },
    "el": {
        "[Τὸ Ἑωθινὸν Εὐαγγέλιον τῆς ἡμέρας]": ("matins_gospel", "replace", "Ἀναγνώστης"),
        "(Ὁ Ἀρχιερεύς μεθ’ ὅλου τοῦ Ἱερατείου εἰσέρχονται εἰς τό ἅγιον Βῆμα. Ψάλλονται δέ, τὰ ἀπολυτίκια τῆς ἡμέρας, τό τροπάριον τοῦ ναοῦ καί τό κοντάκιον).":
            ("daily_hymns", "after", "Ψάλτης"),
        "(Ὁ Ἀναγνώστης τό Προκείμενον τοῦ Ἀποστόλου).": ("prokeimenon", "after", "Ἀναγνώστης"),
        "(Ὁ Ἀναγνώστης ἀναγινώσκει τὴν τεταγμένην Ἀποστολικὴν περικοπήν).":
            ("epistle", "after", "Ἀναγνώστης"),
        "Δόξα σοι, Κύριε, Δόξα σοι. Ὁ Διάκονος ἀναγινώσκει τὴν τεταγμένην περικοπὴν τοῦ ἁγίου Εὐαγγελίου.":
            ("gospel", "after", "Διάκονος"),
        "Αἰνεῖτε τόν Κύριον ἐκ τῶν οὐρανῶν. Αἰνεῖτε Αὐτόν ἐν τοῖς ὑψίστοις. Ἀλληλούϊα (3)":
            ("communion_hymn", "replace_if_present", "Ψάλτης"),
    },
}

MATINS_GOSPEL_FRONT_MATTER = {
    "ar": {
        "title": "إنجيل السَحَر قبل القداس",
        "speaker": "القارئ",
        "marker": "[إنجيل السَحَر المعيّن لهذا اليوم]",
    },
    "en": {
        "title": "MATINS GOSPEL BEFORE THE LITURGY",
        "speaker": "Reader",
        "marker": "[Matins Gospel appointed for today]",
    },
    "el": {
        "title": "ΤΟ ΕΩΘΙΝΟΝ ΕΥΑΓΓΕΛΙΟΝ ΠΡΟ ΤΗΣ ΘΕΙΑΣ ΛΕΙΤΟΥΡΓΙΑΣ",
        "speaker": "Ἀναγνώστης",
        "marker": "[Τὸ Ἑωθινὸν Εὐαγγέλιον τῆς ἡμέρας]",
    },
}

GOSPEL_NAME_MARKERS = {
    "ar": "[اسم الإنجيلي]",
    "en": "(Name)",
    "el": "(Ὂνομα)",
}


def _native_text(segment: dict[str, Any], lang: str) -> str:
    value = segment.get("text")
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def _native_title(segment: dict[str, Any], lang: str) -> str:
    value = segment.get("title")
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def _native_speaker(segment: dict[str, Any], lang: str) -> str:
    value = segment.get("speaker")
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def _mark_group(
    segments: list[dict[str, Any]],
    indices: list[int],
    slot: str,
    emit_index: int,
) -> None:
    if not indices or emit_index not in indices:
        raise SystemExit(f"divine_liturgy: cannot annotate group {slot}")
    group_id = f"liturgy:{slot}"
    for index in indices:
        segment = segments[index]
        segment["dynamic_slot"] = slot
        segment["dynamic_slot_mode"] = "replace_group_if_present"
        segment["dynamic_slot_group"] = group_id
        segment["dynamic_slot_group_emit"] = index == emit_index


def annotate_phase4_variable_slots(service: dict[str, Any], lang: str) -> set[str]:
    if service.get("id") != "divine_liturgy":
        return set()
    segments = service.get("segments") or []
    found: set[str] = set()
    people = {
        "ar": {"الشعب", "المرتل", "الشعب بصوت هادئ"},
        "en": {"People", "Chanter"},
        "el": {"Λαός", "Ψάλτης"},
    }[lang]
    section_titles = {
        "ar": {"first": "صلاة الأنتيفونا الأولى", "second": "صلاة الأنتيفونا الثانية", "entrance": "أثناء الدخول الصغير", "trisagion": "صلاة التريصاجيون"},
        "en": {"first": "THE FIRST ANTIPHON", "second": "THE SECOND ANTIPHON", "third": "THE THIRD ANTIPHON", "entrance": "THE ENTRANCE", "trisagion": "THE TRISAGION HYMN"},
        "el": {"first": "ΤΟ ΠΡΩΤΟΝ ΑΝΤΙΦΩΝΟΝ", "second": "ΤΟ ΔΕΥΤΕΡΟΝ ΑΝΤΙΦΩΝΟΝ", "third": "ΤΟ ΤΡΙΤΟΝ ΑΝΤΙΦΩΝΟΝ", "entrance": "Η ΜΙΚΡΑ ΕΙΣΟΔΟΣ", "trisagion": "Ο ΤΡΙΣΑΓΙΟΣ ΥΜΝΟΣ"},
    }[lang]

    def section_index(title: str) -> int:
        for i, segment in enumerate(segments):
            if _native_title(segment, lang) == title:
                return i
        return -1

    def sung_group_after(title: str) -> list[int]:
        start = section_index(title)
        if start < 0:
            return []
        result: list[int] = []
        begun = False
        for i in range(start + 1, len(segments)):
            segment = segments[i]
            if segment.get("type") == "section":
                break
            speaker = _native_speaker(segment, lang)
            text = _native_text(segment, lang).strip()
            eligible = bool(text) and speaker in people
            if eligible:
                result.append(i)
                begun = True
            elif begun:
                break
        return result

    for key, slot in (("first", "first_antiphon"), ("second", "second_antiphon")):
        indices = sung_group_after(section_titles[key])
        _mark_group(segments, indices, slot, indices[0])
        found.add(slot)

    if lang == "ar":
        entrance_section = section_index(section_titles["entrance"])
        if entrance_section < 0:
            raise SystemExit("divine_liturgy.ar: entrance section missing")
        ordinary = {
            key: "هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه." if key == "ar" else ""
            for key in LANGS
        }
        segments.insert(entrance_section, {
            "type": "text",
            "speaker": {key: "المرتل" if key == "ar" else "" for key in LANGS},
            "text": ordinary,
        })
    third_indices = sung_group_after(section_titles.get("third", section_titles["entrance"])) if lang != "ar" else []
    if lang == "ar":
        third_indices = [i for i, segment in enumerate(segments) if _native_text(segment, lang) == "هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه."]
    _mark_group(segments, third_indices, "third_antiphon", third_indices[0])
    found.add("third_antiphon")

    entrance_phrases = {
        "ar": "هلمّ نسجد ونركع للمسيح.",
        "en": "Come, let us worship and bow before Christ.",
        "el": "Δεῦτε προσκυνήσωμεν, καὶ προσπέσωμεν Χριστῷ",
    }
    entrance_indices = [i for i, segment in enumerate(segments) if _native_text(segment, lang).startswith(entrance_phrases[lang])]
    _mark_group(segments, entrance_indices, "entrance_hymn", entrance_indices[-1])
    found.add("entrance_hymn")

    tri_start = section_index(section_titles["trisagion"])
    tri_indices: list[int] = []
    tri_started = False
    tri_markers = {
        "ar": ("قدوس الله", "المجد للآب والابن", "قدوس الذي لا يموت"),
        "en": ("Holy God", "Glory to the Father", "Strength."),
        "el": ("Ἅγιος ὁ Θεός", "Δόξα Πατρὶ", "Δύναμις."),
    }[lang]
    for i in range(tri_start + 1, len(segments)):
        segment = segments[i]
        if segment.get("type") == "section":
            break
        text = _native_text(segment, lang).strip()
        if any(text.startswith(marker) for marker in tri_markers):
            tri_indices.append(i)
            tri_started = True
        elif tri_started and _native_speaker(segment, lang) not in people and text not in {"Strength.", "Δύναμις."}:
            break
    _mark_group(segments, tri_indices, "trisagion_hymn", tri_indices[0])
    found.add("trisagion_hymn")

    alleluia_prefix = {"ar": "هللويا، هللويا، هللويا", "en": "Alleluia. Alleluia. Alleluia", "el": "Ἀλληλούια, Ἀλληλούια, Ἀλληλούια"}[lang]
    alleluia_index = next((i for i, segment in enumerate(segments) if _native_text(segment, lang).startswith(alleluia_prefix)), -1)
    if alleluia_index < 0:
        raise SystemExit(f"divine_liturgy.{lang}: Alleluia anchor missing")
    segments[alleluia_index]["dynamic_slot"] = "alleluia_verses"
    segments[alleluia_index]["dynamic_slot_mode"] = "replace_if_present"
    found.add("alleluia_verses")

    theotokos_prefix = {"ar": "بواجب الاستئهال", "en": "It is truly right", "el": "Ἄξιόν ἐστιν"}[lang]
    theotokos_index = next((i for i, segment in enumerate(segments) if _native_text(segment, lang).startswith(theotokos_prefix)), -1)
    if theotokos_index < 0:
        raise SystemExit(f"divine_liturgy.{lang}: Theotokos hymn anchor missing")
    segments[theotokos_index]["dynamic_slot"] = "theotokos_hymn"
    segments[theotokos_index]["dynamic_slot_mode"] = "replace_if_present"
    found.add("theotokos_hymn")

    dismissal_prefix = {
        "ar": "المسيح إلهنا الحقيقي",
        "en": "May Christ our true God who rose from the dead",
        "el": "Ὁ ἀναστὰς ἐκ νεκρῶν, Χριστὸς ὁ ἀληθινὸς Θεὸς ἡμῶν",
    }[lang]
    dismissal_index = next((i for i, segment in enumerate(segments) if _native_text(segment, lang).startswith(dismissal_prefix)), -1)
    if dismissal_index < 0:
        raise SystemExit(f"divine_liturgy.{lang}: dismissal anchor missing")
    segments[dismissal_index]["dynamic_slot"] = "dismissal"
    segments[dismissal_index]["dynamic_slot_mode"] = "replace_if_present"
    found.add("dismissal")
    return found


def annotate_dynamic_slots(service: dict[str, Any], lang: str) -> None:
    """Attach stable semantic slots to the reviewed native Liturgy.

    Daily data used to target Arabic placeholder strings. Native English and
    Greek editions have no Arabic placeholders, so their verified readings
    could never appear inside the service. These annotations are metadata only:
    they do not alter a single source word.
    """
    if service.get("id") != "divine_liturgy":
        return
    front = MATINS_GOSPEL_FRONT_MATTER[lang]
    segments = service.setdefault("segments", [])
    if not any(
        isinstance(segment, dict) and segment.get("dynamic_slot") == "matins_gospel"
        for segment in segments
    ):
        segments[0:0] = [
            {
                "type": "section",
                "follow_along_phase": "matins_gospel",
                "title": {key: front["title"] if key == lang else "" for key in LANGS},
            },
            {
                "type": "text",
                "follow_along_phase": "matins_gospel",
                "speaker": {key: front["speaker"] if key == lang else "" for key in LANGS},
                "text": {key: front["marker"] if key == lang else "" for key in LANGS},
            },
        ]
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

    found.update(annotate_phase4_variable_slots(service, lang))

    required = {"matins_gospel", "daily_hymns", "prokeimenon", "epistle", "gospel", "communion_hymn",
        "first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn", "trisagion_hymn",
        "alleluia_verses", "theotokos_hymn", "dismissal"} if lang != "ar" else {
        "matins_gospel",
        "daily_troparion", "church_troparion", "daily_kontakion",
        "prokeimenon", "epistle", "gospel", "communion_hymn",
        "first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn", "trisagion_hymn",
        "alleluia_verses", "theotokos_hymn", "dismissal",
    }
    missing = sorted(required - found)
    if missing or not inline_found:
        detail = ", ".join(missing) if missing else "gospel_evangelist_name"
        raise SystemExit(f"divine_liturgy.{lang}: dynamic slot anchor missing: {detail}")


def annotate_delivery(service: dict[str, Any], lang: str) -> None:
    """Mark only silence explicitly stated by the native source text."""
    if service.get("id") != "divine_liturgy":
        return
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        speaker_obj = segment.get("speaker")
        text_obj = segment.get("text")
        speaker = str(speaker_obj.get(lang) or "") if isinstance(speaker_obj, dict) else ""
        text = str(text_obj.get(lang) or "") if isinstance(text_obj, dict) else ""
        combined = f"{speaker}\n{text}".casefold()
        silent = (
            ("سراً" in combined or "بصوت هادئ" in combined)
            if lang == "ar"
            else (
                "silently" in combined or "in a low voice" in combined
                if lang == "en"
                else (
                    "χαμηλοφώνως".casefold() in combined
                    or "κατ’ἰδίαν".casefold() in combined
                )
            )
        )
        if not silent:
            continue
        faithful = (
            ("الشعب" in speaker)
            if lang == "ar"
            else (
                "those who will receive holy communion" in combined
                if lang == "en"
                else "ὃσους θα μεταλάβουν".casefold() in combined
            )
        )
        segment["delivery"] = "silent"
        segment["delivery_actor"] = "faithful" if faithful else "priest"


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
            annotate_delivery(service, lang)
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
