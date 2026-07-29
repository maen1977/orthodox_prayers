#!/usr/bin/env python3
"""Build the user-visible source registry from active contracts and connector health."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "canonical/native_language_sources.json"
OFFICIAL = ROOT / "canonical/official_source_registry.json"
CONNECTORS = ROOT / "canonical/source_connectors.json"
SERVICE_MANIFEST = ROOT / "canonical/native_service_manifest.json"
STATIC = ROOT / "canonical/static_prayer_sources.json"
HEALTH = ROOT / "data/sources/health/current.json"
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
    "orthodox_jordan": "المرجع المحلي الأعلى للأردن: التقويم القديم، الصوم، الكنائس، الصلوات والمراجع اليومية.",
    "jerusalem_patriarchate_en": "سلطة الاختصاص الكنسي والأعياد الكبرى والتقويم المقدسي.",
    "antioch_patriarchate_ar": "مرجع عربي أرثوذكسي للمقارنة والخدمات والمقالات الليتورجية.",
    "goarch_digital_chant_stand_english": "روابط وبنية الغروب والسحر والقداس والقطع المتغيرة دون نسخ غير مرخص.",
    "goarch_digital_chant_stand_greek": "بنية الخدمات والقطع المتغيرة باللغة اليونانية.",
    "goarch_online_chapel": "مراجع القراءات والأعياد والقديسين باللغة الإنجليزية واليونانية.",
    "oca_official_english": "مرجع رسمي أخير لمراجع القراءات الإنجليزية؛ لا يعاد نشر نص NKJV.",
    "church_of_greece_apostoliki_diakonia": "مرجع يوناني رسمي أسبوعي ولغوي.",
    "ebible_arabic_van_dyck": "نص الرسالة والإنجيل بالعربية من مجموعة عامة الملكية.",
    "ebible_world_english_bible": "نص الرسالة والإنجيل بالإنجليزية من مجموعة عامة الملكية.",
    "ebible_greek_byzantine_1904": "نص الرسالة والإنجيل باليونانية من مجموعة عامة الملكية.",
}


def load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def connector_groups() -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for connector in load(CONNECTORS).get("connectors", []):
        source_id = ALIASES.get(str(connector.get("source_id") or ""), str(connector.get("source_id") or ""))
        if source_id:
            groups.setdefault(source_id, []).append(connector)
    return groups


def collect_active_ids(groups: dict[str, list[dict[str, Any]]]) -> set[str]:
    ids: set[str] = set(groups)
    manifest = load(SERVICE_MANIFEST)
    for service in manifest.get("services", {}).values():
        for lane in service.values():
            sid = str(lane.get("source_id") or "").strip()
            if sid:
                ids.add(ALIASES.get(sid, sid))
    static = load(STATIC)
    for record in static.get("services", {}).values():
        sid = str(record.get("source_id") or "").strip()
        if sid:
            ids.add(ALIASES.get(sid, sid))
    official = load(OFFICIAL)
    for record in official.get("ordered_sources", []):
        sid = str(record.get("id") or "").strip()
        if sid:
            ids.add(ALIASES.get(sid, sid))
    for path in SCRIPTURE.values():
        record = load(path)
        sid = str(record.get("source_id") or "").strip()
        if sid:
            ids.add(sid)
    ids.add("antioch_archdiocese_tripoli_ar")
    return ids


def health_by_source() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in load(HEALTH).get("observations", []):
        sid = ALIASES.get(str(item.get("source_id") or ""), str(item.get("source_id") or ""))
        if sid:
            result.setdefault(sid, []).append(item)
    return result


def fallback_record_from_connector(source_id: str, groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    candidates = groups.get(source_id, [])
    if not candidates:
        return {}
    first = sorted(candidates, key=lambda item: int(item.get("authority_tier", 99)))[0]
    name = first.get("name") or {}
    return {
        "name": name.get("en") or source_id,
        "languages": sorted({lang for item in candidates for lang in item.get("languages", [])}),
        "official": all(bool(item.get("official")) for item in candidates),
        "base_url": first.get("url_template", ""),
        "capabilities": sorted({capability for item in candidates for capability in item.get("capabilities", [])}),
        "permission_confirmed": False,
    }


def source_record(
    source_id: str,
    native: dict[str, Any],
    groups: dict[str, list[dict[str, Any]]],
    health: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    sources = native.get("sources", {})
    record = dict(sources.get(source_id, {}))
    if not record and source_id == "antioch_archdiocese_tripoli_ar":
        record = {
            "language": "ar", "official": True, "base_url": "https://archtripoli.org/",
            "capabilities": ["prokeimenon"], "permission_confirmed": True,
            "name": "Greek Orthodox Archdiocese of Tripoli, Koura and Dependencies",
        }
    if not record:
        record = fallback_record_from_connector(source_id, groups)
    if not record:
        record = {"language": "", "official": False, "base_url": "https://orthodoxjordan.org/", "capabilities": [], "name": source_id}

    connectors = groups.get(source_id, [])
    name = str(record.get("name") or source_id)
    ar = NAME_AR.get(source_id, name)
    languages = record.get("languages") or ([record.get("language")] if record.get("language") else [])
    usage_ar = USAGE_AR.get(source_id)
    if not usage_ar:
        capabilities = ", ".join(str(x) for x in record.get("capabilities", [])) or "مراجع المحتوى المسجلة"
        usage_ar = "يُستخدم في: " + capabilities + "."
    rights = "Permission confirmed by project owner" if record.get("permission_confirmed") else "Verify source terms before redistribution"
    observations = health.get(source_id, [])
    latest = max((str(item.get("checked_at_utc") or "") for item in observations), default="")
    health_statuses = sorted({str(item.get("status") or "unknown") for item in observations})
    authority_tier = min((int(item.get("authority_tier", 99)) for item in connectors), default=(5 if bool(record.get("official")) else 99))
    return {
        "id": source_id,
        "name": {"ar": ar, "en": name, "el": name},
        "url": str(record.get("base_url") or (connectors[0].get("url_template") if connectors else "")),
        "official": bool(record.get("official", bool(connectors))),
        "languages": [x for x in languages if x],
        "categories": sorted(set(record.get("capabilities", [])) | {cap for item in connectors for cap in item.get("capabilities", [])}),
        "used_for": {
            "ar": usage_ar,
            "en": "Used for registered Orthodox content, calendar, prayer, service, directory, or Scripture data.",
            "el": "Χρησιμοποιεῖται γιὰ καταχωρισμένο ὀρθόδοξο περιεχόμενο, ἡμερολόγιο ἢ ἀκολουθίες.",
        },
        "rights": rights,
        "permission_confirmed": bool(record.get("permission_confirmed")),
        # Do not invent a verification date merely because the registry was rebuilt.
        # Sources without a monitored observation remain undated in the user-facing list.
        "last_verified": latest[:10],
        "authority_tier": authority_tier,
        "connector_count": len(connectors),
        "connector_ids": [item.get("id") for item in connectors],
        "publication_roles": sorted({str(item.get("publication_role")) for item in connectors}),
        "health_statuses": health_statuses,
        "health": observations,
    }


def apply_scripture_details(entries: dict[str, dict[str, Any]]) -> None:
    for path in SCRIPTURE.values():
        manifest = load(path)
        sid = manifest["source_id"]
        entry = entries.setdefault(sid, {
            "id": sid,
            "name": {"ar": manifest.get("source_title", sid), "en": manifest.get("source_title", sid), "el": manifest.get("source_title", sid)},
            "url": manifest.get("source_url", ""), "official": False, "languages": [manifest.get("language", "")],
            "categories": ["scripture_corpus"],
            "used_for": {"ar": "نصوص الرسالة والإنجيل.", "en": "Epistle and Gospel text.", "el": "Κείμενο Ἀποστόλου καὶ Εὐαγγελίου."},
            "rights": manifest.get("license", ""), "permission_confirmed": True,
            "last_verified": manifest.get("retrieved_at", "")[:10], "connector_count": 0, "connector_ids": [], "health": [],
        })
        entry["url"] = manifest.get("source_url", entry.get("url", ""))
        entry["rights"] = manifest.get("license", entry.get("rights", ""))
        entry["distribution_status"] = manifest.get("distribution_status", "")
        entry["content_sha256"] = manifest.get("content_sha256", "")
        entry["source_snapshot_sha256"] = manifest.get("source_snapshot_sha256", "")
        entry["source_title"] = manifest.get("source_title", "")


def main() -> None:
    native = load(NATIVE)
    groups = connector_groups()
    health = health_by_source()
    entries = {sid: source_record(sid, native, groups, health) for sid in sorted(collect_active_ids(groups))}
    apply_scripture_details(entries)
    health_snapshot = load(HEALTH)
    payload = {
        "schema_version": 2,
        "generated_from": [
            "canonical/native_language_sources.json",
            "canonical/native_service_manifest.json",
            "canonical/official_source_registry.json",
            "canonical/source_connectors.json",
            "canonical/static_prayer_sources.json",
            "data/sources/health/current.json",
            "data/scripture/native/*/manifest.json",
        ],
        "policy": {
            "ar": "تعرض الصفحة المصادر والموصلات المسجلة فعليًا، مع سلّم السلطة وصحة الاتصال. وجود المصدر لا يعني نسخ كل محتواه؛ النصوص الدينية تبقى محكومة بالترخيص والتحقق واللغة الأصلية.",
            "en": "This page lists active sources and connectors with authority tier and health. Listing a source never means all content is copied; religious text remains license-, verification-, and native-language-gated.",
            "el": "Ἡ σελίδα παραθέτει ἐνεργὲς πηγὲς καὶ συνδέσεις μὲ βαθμίδα ἀρχῆς καὶ κατάσταση ἐλέγχου.",
        },
        "health_date": health_snapshot.get("date_iso", ""),
        "health_summary": health_snapshot.get("summary", {}),
        "sources": sorted(entries.values(), key=lambda x: (x.get("authority_tier") or 99, not x.get("official", False), x["id"])),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    DATA_OUTPUT.write_text(text, encoding="utf-8")
    print(f"Built public source registry with {len(payload['sources'])} sources and {len(groups)} monitored source groups")


if __name__ == "__main__":
    main()
