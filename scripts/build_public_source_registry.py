#!/usr/bin/env python3
"""Build the user-visible source registry from the project's active source contracts."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "canonical/native_language_sources.json"
OFFICIAL = ROOT / "canonical/official_source_registry.json"
SERVICE_MANIFEST = ROOT / "canonical/native_service_manifest.json"
STATIC = ROOT / "canonical/static_prayer_sources.json"
SCRIPTURE = {lang: ROOT / f"data/scripture/native/{lang}/manifest.json" for lang in ("ar", "en", "el")}
OUTPUT = ROOT / "app/src/main/assets/data/source_registry.json"
DATA_OUTPUT = ROOT / "data/sources/source_registry.json"

ALIASES = {
    "goarch_digital_chant_stand": "goarch_digital_chant_stand_english",
    "goarch_online_chapel_greek": "goarch_online_chapel",
    "official_greek_orthodox": "goarch_online_chapel",
    "jerusalem_patriarchate": "jerusalem_patriarchate_en",
    "antioch_patriarchate": "antioch_patriarchate_ar",
    "orthodox_church_in_america": "oca_official_english",
}

NAME_AR = {
    "orthodox_jordan": "مطرانية الروم الأرثوذكس في الأردن",
    "jerusalem_patriarchate_ar": "بطريركية الروم الأرثوذكس المقدسية — العربية",
    "jerusalem_patriarchate_en": "بطريركية الروم الأرثوذكس المقدسية — الإنجليزية",
    "jerusalem_patriarchate_el": "بطريركية الروم الأرثوذكس المقدسية — اليونانية",
    "antioch_patriarchate_ar": "بطريركية أنطاكية وسائر المشرق — العربية",
    "goarch_online_chapel": "المصلّى الإلكتروني لأبرشية الروم الأرثوذكس في أميركا",
    "goarch_digital_chant_stand_english": "منصة الترتيل الرقمية — الإنجليزية",
    "goarch_digital_chant_stand_greek": "منصة الترتيل الرقمية — اليونانية",
    "goarch_synekdemos": "كتاب الصلوات اليومية Synekdemos",
    "oca_official_english": "الكنيسة الأرثوذكسية في أميركا — الإنجليزية",
    "church_of_greece_apostoliki_diakonia": "خدمة الرسالة الرسولية التابعة لكنيسة اليونان",
    "church_of_greece_ecclesia": "كنيسة اليونان — الموقع الرسمي",
    "ebible_arabic_van_dyck": "الكتاب المقدس العربي — فان دايك",
    "ebible_world_english_bible": "الكتاب المقدس الإنجليزي العالمي",
    "ebible_greek_byzantine_1904": "العهد الجديد البطريركي اليوناني 1904",
    "metropolis_toronto_liturgy_en": "مطرانية تورونتو للروم الأرثوذكس — الإنجليزية",
    "metropolis_toronto_liturgy_el": "مطرانية تورونتو للروم الأرثوذكس — اليونانية",
    "antioch_archdiocese_tripoli_ar": "أبرشية طرابلس والكورة وتوابعهما للروم الأرثوذكس",
}

USAGE_AR = {
    "orthodox_jordan": "التقويم الأردني القديم، الصوم، أسماء الصلوات العربية، وصلوات المناولة والمراجع المحلية.",
    "goarch_digital_chant_stand_english": "بنية الخدمات اليومية والقطع المتغيرة والسحرية والقداس باللغة الإنجليزية.",
    "goarch_digital_chant_stand_greek": "بنية الخدمات اليومية والقطع المتغيرة والسحرية والقداس باللغة اليونانية.",
    "goarch_online_chapel": "مراجع القراءات والأعياد والنصوص الإنجليزية الرسمية المتاحة.",
    "church_of_greece_apostoliki_diakonia": "النصوص اليونانية الكنسية والكتابية الأصلية المتاحة.",
    "ebible_arabic_van_dyck": "نص الرسالة والإنجيل بالعربية من مجموعة عامة الملكية.",
    "ebible_world_english_bible": "نص الرسالة والإنجيل بالإنجليزية من مجموعة عامة الملكية.",
    "ebible_greek_byzantine_1904": "نص الرسالة والإنجيل باليونانية من مجموعة عامة الملكية.",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_active_ids() -> set[str]:
    ids: set[str] = set()
    manifest = load(SERVICE_MANIFEST)
    for service in manifest.get("services", {}).values():
        for lane in service.values():
            sid = str(lane.get("source_id") or "").strip()
            if sid: ids.add(sid)
    static = load(STATIC)
    for record in static.get("services", {}).values():
        sid = str(record.get("source_id") or "").strip()
        if sid: ids.add(sid)
    official = load(OFFICIAL)
    for record in official.get("ordered_sources", []):
        sid = str(record.get("id") or "").strip()
        if sid: ids.add(ALIASES.get(sid, sid))
    for path in SCRIPTURE.values():
        record = load(path)
        sid = str(record.get("source_id") or "").strip()
        if sid: ids.add(sid)
    # Daily content currently references this registered Arabic source for the Prokeimenon.
    ids.add("antioch_archdiocese_tripoli_ar")
    return ids


def source_record(source_id: str, native: dict[str, Any]) -> dict[str, Any]:
    sources = native.get("sources", {})
    record = dict(sources.get(source_id, {}))
    if not record and source_id == "antioch_archdiocese_tripoli_ar":
        record = {
            "language": "ar", "official": True, "base_url": "https://archtripoli.org/",
            "capabilities": ["prokeimenon"], "permission_confirmed": True,
            "name": "Greek Orthodox Archdiocese of Tripoli, Koura and Dependencies",
        }
    if not record:
        record = {"language": "", "official": False, "base_url": "", "capabilities": [], "name": source_id}
    name = str(record.get("name") or source_id)
    ar = NAME_AR.get(source_id, name)
    languages = record.get("languages") or ([record.get("language")] if record.get("language") else [])
    usage_ar = USAGE_AR.get(source_id)
    if not usage_ar:
        capabilities = ", ".join(str(x) for x in record.get("capabilities", [])) or "مراجع المحتوى المسجلة"
        usage_ar = "يُستخدم في: " + capabilities + "."
    rights = "Permission confirmed by project owner" if record.get("permission_confirmed") else "Verify source terms before redistribution"
    return {
        "id": source_id,
        "name": {"ar": ar, "en": name, "el": name},
        "url": str(record.get("base_url") or ""),
        "official": bool(record.get("official")),
        "languages": [x for x in languages if x],
        "categories": list(record.get("capabilities", [])),
        "used_for": {"ar": usage_ar, "en": "Used for registered Orthodox content, calendar, prayer, service, or Scripture data.", "el": "Χρησιμοποιεῖται γιὰ καταχωρισμένο ὀρθόδοξο περιεχόμενο."},
        "rights": rights,
        "permission_confirmed": bool(record.get("permission_confirmed")),
        "last_verified": "2026-07-20",
    }


def apply_scripture_details(entries: dict[str, dict[str, Any]]) -> None:
    for path in SCRIPTURE.values():
        manifest = load(path)
        sid = manifest["source_id"]
        entry = entries.setdefault(sid, {
            "id": sid, "name": {"ar": manifest.get("source_title", sid), "en": manifest.get("source_title", sid), "el": manifest.get("source_title", sid)},
            "url": manifest.get("source_url", ""), "official": False, "languages": [manifest.get("language", "")],
            "categories": ["scripture_corpus"], "used_for": {"ar": "نصوص الرسالة والإنجيل.", "en": "Epistle and Gospel text.", "el": "Κείμενο Ἀποστόλου καὶ Εὐαγγελίου."},
            "rights": manifest.get("license", ""), "permission_confirmed": True, "last_verified": manifest.get("retrieved_at", "")[:10],
        })
        entry["url"] = manifest.get("source_url", entry.get("url", ""))
        entry["rights"] = manifest.get("license", entry.get("rights", ""))
        entry["distribution_status"] = manifest.get("distribution_status", "")
        entry["content_sha256"] = manifest.get("content_sha256", "")
        entry["source_snapshot_sha256"] = manifest.get("source_snapshot_sha256", "")
        entry["source_title"] = manifest.get("source_title", "")


def main() -> None:
    native = load(NATIVE)
    entries = {sid: source_record(sid, native) for sid in sorted(collect_active_ids())}
    apply_scripture_details(entries)
    payload = {
        "schema_version": 1,
        "generated_from": [
            "canonical/native_language_sources.json",
            "canonical/native_service_manifest.json",
            "canonical/official_source_registry.json",
            "canonical/static_prayer_sources.json",
            "data/scripture/native/*/manifest.json",
        ],
        "policy": {
            "ar": "هذه الصفحة تعرض المصادر المسجلة فعليًا في عقود التطبيق. وجود المصدر لا يعني أن كل محتواه منسوخ داخل التطبيق؛ المحتوى يُنشر فقط وفق الترخيص وحالة التحقق.",
            "en": "This page lists sources actually registered in the app contracts. A listed source does not mean all of its content is copied into the app; publication remains license- and verification-gated.",
            "el": "Ἡ σελίδα παραθέτει τὶς πηγὲς ποὺ εἶναι πράγματι καταχωρισμένες στὰ συμβόλαια τῆς ἐφαρμογῆς.",
        },
        "sources": sorted(entries.values(), key=lambda x: (not x.get("official", False), x["id"])),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    DATA_OUTPUT.write_text(text, encoding="utf-8")
    print(f"Built public source registry with {len(payload['sources'])} sources")

if __name__ == "__main__":
    main()
