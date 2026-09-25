"""Build a truthful offline inventory for daily Liturgy propers.

The inventory is intentionally stricter than the legacy year audit. It records
text presence separately from source attribution, registered hashes, rights
metadata, and language-script isolation. Nothing is inferred across languages
or dates, and no network is used.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
SLOTS = {
    "troparion": "daily_troparion",
    "kontakion": "daily_kontakion",
    "communion": "communion_hymn",
}

ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("daily_propers_inventory_updater", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def localized_text(value: Any, lang: str) -> str:
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def script_isolated(text: str, lang: str) -> bool:
    if not text:
        return False
    has_ar = bool(ARABIC_RE.search(text))
    has_el = bool(GREEK_RE.search(text))
    has_en = bool(LATIN_RE.search(text))
    if lang == "ar":
        return has_ar and not has_el and not has_en
    if lang == "el":
        return has_el and not has_ar and not has_en
    if lang == "en":
        return has_en and not has_ar and not has_el
    return False


def source_entry(sources: Any, lang: str) -> dict:
    entry = sources.get(lang) if isinstance(sources, dict) else None
    return entry if isinstance(entry, dict) else {}


def has_rights_metadata(source: dict) -> bool:
    """Only explicit rights fields count; a URL alone is never permission."""
    if source.get("permission_confirmed") is True:
        return True
    for key in (
        "authorization_record",
        "rights_attestation",
        "attestation_id",
        "license",
        "license_url",
        "permission_record",
    ):
        if str(source.get(key) or "").strip():
            return True
    return False


def selected_registry_entry(update, info: dict, day: date) -> tuple[str, dict | None]:
    dated = update.dated_liturgical_proper_entry(day)
    if dated:
        return "dated", dated
    movable = update.paschal_cycle_proper_entry(day, info)
    if movable:
        return "paschal", movable
    fixed = update.fixed_proper_entry(info)
    if fixed:
        return "fixed", fixed
    tone = update.resurrection_tone(day, info["pascha"])
    resurrectional = update.resurrectional_proper_entry(tone)
    if resurrectional:
        return "resurrectional", resurrectional
    return "none", None


def registered_verification(entry: dict | None, slot: str, lang: str) -> dict:
    if not isinstance(entry, dict):
        return {}
    verification = entry.get("verification")
    if isinstance(verification, dict):
        slot_verification = verification.get(slot)
        if isinstance(slot_verification, dict):
            lane = slot_verification.get(lang)
            if isinstance(lane, dict):
                return lane
    # Some registries store source verification under native_source_verification
    # for readings, but this inventory deliberately does not treat that as a
    # proper-text hash.
    return {}


def build_slot_record(
    *,
    update,
    entry: dict | None,
    inserts: dict,
    slot: str,
    lang: str,
    source_kind: str,
) -> dict:
    text = localized_text(inserts.get(slot), lang)
    source = source_entry(inserts.get("sources"), lang)
    verification = registered_verification(entry, slot, lang)
    bundled_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    registered_hash = str(verification.get("text_sha256") or "") or None
    hash_matches = bool(bundled_hash and registered_hash and bundled_hash == registered_hash)
    source_registered = bool(str(source.get("source_id") or "").strip() and str(source.get("url") or "").strip())
    rights_attested = has_rights_metadata(source)
    text_present = nonempty(text)
    script_ok = script_isolated(text, lang) if text_present else False
    verified = bool(text_present and source_registered and registered_hash and hash_matches and rights_attested and script_ok)
    reasons: list[str] = []
    if not text_present:
        reasons.append("no_text")
    if not source_registered:
        reasons.append("no_source_id_and_url")
    if not registered_hash:
        reasons.append("no_registered_text_sha256")
    elif not hash_matches:
        reasons.append("registered_hash_mismatch")
    if not rights_attested:
        reasons.append("no_explicit_rights_metadata")
    if text_present and not script_ok:
        reasons.append("language_script_isolation_failed")
    return {
        "text_present": text_present,
        "bundled_text_sha256": bundled_hash,
        "source_registered": source_registered,
        "source_id": source.get("source_id") or None,
        "source_url": source.get("url") or None,
        "source_kind": source_kind,
        "registered_text_sha256": registered_hash,
        "hash_matches_bundled_text": hash_matches,
        "rights_attested": rights_attested,
        "script_isolated": script_ok,
        "verified": verified,
        "status": "verified" if verified else "incomplete",
        "reasons": reasons,
    }


def audit_day(update, day: date) -> dict:
    os.environ["ORTHODOX_DISABLE_DISCOVERY_NETWORK"] = "1"
    info = update.day_info(day)
    selection = update.liturgy_service_selection(day, info)
    inserts = update.feast_inserts(info, day)
    source_kind, entry = selected_registry_entry(update, info, day)
    lanes = {}
    for lang in LANGS:
        lanes[lang] = {
            target: build_slot_record(
                update=update,
                entry=entry,
                inserts=inserts,
                slot=slot,
                lang=lang,
                source_kind=source_kind,
            )
            for slot, target in SLOTS.items()
        }
    selected_service_type = str(selection.get("service_type") or "")
    liturgy_eligible = (
        selected_service_type not in {"no_divine_liturgy", "typikon_override_required"}
        and bool(selection.get("displayable"))
    )
    return {
        "civil_date": day.isoformat(),
        "julian_date": f"{info['julian_year']:04d}-{info['julian_month']:02d}-{info['julian_day']:02d}",
        "weekday": day.weekday(),
        "pascha_offset": (day - info["pascha"]).days,
        "service_type": selected_service_type,
        "service_rule_id": selection.get("rule_id"),
        "service_displayable": bool(selection.get("displayable")),
        "liturgy_eligible": liturgy_eligible,
        "proper_id": inserts.get("proper_id"),
        "proper_provenance": inserts.get("proper_provenance") or source_kind,
        "lanes": lanes,
        "fail_closed": True,
    }


def build_inventory(start_year: int = 2026, end_year: int = 2050) -> dict:
    update = load_updater()
    start = date(start_year, 1, 1)
    end = date(end_year + 1, 1, 1)
    days = []
    current = start
    while current < end:
        days.append(audit_day(update, current))
        current += timedelta(days=1)
    eligible_days = [item for item in days if item["liturgy_eligible"]]
    summary = {
        "civil_days": len(days),
        "language_count": len(LANGS),
        "slot_count": len(SLOTS),
        "records": len(days) * len(LANGS) * len(SLOTS),
        "eligible_liturgy_days": len(eligible_days),
        "eligible_liturgy_records": len(eligible_days) * len(LANGS) * len(SLOTS),
        "service_days_with_displayable_liturgy": len(eligible_days),
        "by_language_and_slot": {},
    }
    for lang in LANGS:
        for target in SLOTS.values():
            all_records = [item["lanes"][lang][target] for item in days]
            eligible_records = [item["lanes"][lang][target] for item in eligible_days]
            summary["by_language_and_slot"][f"{lang}:{target}"] = {
                "all_civil_days": {
                    "text_present_days": sum(r["text_present"] for r in all_records),
                    "source_registered_days": sum(r["source_registered"] for r in all_records),
                    "registered_hash_days": sum(bool(r["registered_text_sha256"]) for r in all_records),
                    "rights_attested_days": sum(r["rights_attested"] for r in all_records),
                    "script_isolated_days": sum(r["script_isolated"] for r in all_records),
                    "verified_days": sum(r["verified"] for r in all_records),
                },
                "eligible_liturgy_days": {
                    "text_present_days": sum(r["text_present"] for r in eligible_records),
                    "source_registered_days": sum(r["source_registered"] for r in eligible_records),
                    "registered_hash_days": sum(bool(r["registered_text_sha256"]) for r in eligible_records),
                    "rights_attested_days": sum(r["rights_attested"] for r in eligible_records),
                    "script_isolated_days": sum(r["script_isolated"] for r in eligible_records),
                    "verified_days": sum(r["verified"] for r in eligible_records),
                },
            }
    return {
        "schema_version": 1,
        "status": "INVENTORY_ONLY_NOT_A_COMPLETION_CLAIM",
        "calendar": "civil_dates_with_julian_old_calendar_context_and_local_pascha",
        "range": {"start": f"{start_year}-01-01", "end": f"{end_year}-12-31"},
        "languages": list(LANGS),
        "slots": list(SLOTS.values()),
        "policy": {
            "same_language_source_only": True,
            "machine_translation_allowed": False,
            "cross_language_fallback_allowed": False,
            "network_fetch_used": False,
            "verified_requires_text_source_registered_hash_rights_and_script_isolation": True,
            "url_alone_is_not_permission": True,
            "fail_closed": True,
        },
        "summary": summary,
        "days": days,
        "completion_claim": "unproven_complete",
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_daily_liturgy_propers_inventory.py OUTPUT.json")
    output = Path(sys.argv[1])
    inventory = build_inventory()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
