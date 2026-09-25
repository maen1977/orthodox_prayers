"""Build the verified partial daily-propers overlay used by Android.

Only entries whose present native-language slots have explicit source metadata,
matching per-text SHA-256 values, project-owner republication permission, and
language-script isolation are emitted. Partial entries are allowed only when
all three language lanes expose the same non-empty verified slot set. Missing
slots remain absent; there is no fallback, translation, or date inference.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
SLOT_MAP = {
    "troparion": "daily_troparion",
    "kontakion": "daily_kontakion",
    "communion": "communion_hymn",
}
ATTESTATION = "USER_CONFIRMED_REPUBLICATION_PERMISSION_FOR_ORTHODOX_DAILY_PROPERS_SOURCES_2026_08_24"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


inventory = load_module(ROOT / "scripts" / "build_daily_liturgy_propers_inventory.py", "verified_overlay_inventory")
update = inventory.load_updater()


def text(value: Any, lang: str) -> str:
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def source(value: Any, lang: str) -> dict:
    return value.get(lang) if isinstance(value, dict) and isinstance(value.get(lang), dict) else {}


def verification(entry: dict, slot: str, lang: str) -> dict:
    value = ((entry.get("verification") or {}).get(slot) or {}).get(lang)
    return value if isinstance(value, dict) else {}


def selected_entry(info: dict, day: date) -> tuple[str, dict | None]:
    dated = update.dated_liturgical_proper_entry(day)
    if dated:
        return "dated", dated
    movable = update.paschal_cycle_proper_entry(day, info)
    if movable:
        return "paschal", movable
    fixed = update.fixed_proper_entry(info)
    if fixed:
        return "fixed", fixed
    return "none", None


def verified_lane(entry: dict, inserts: dict, lang: str) -> dict | None:
    result: dict[str, dict] = {}
    for source_slot, overlay_slot in SLOT_MAP.items():
        value = text(inserts.get(source_slot), lang).strip()
        if not value:
            # A missing source-backed slot stays absent. It is not a blank
            # replacement and it is never filled from another language.
            continue
        source_meta = source(inserts.get("sources"), lang)
        check = verification(entry, source_slot, lang)
        actual_hash = hashlib.sha256(value.encode("utf-8")).hexdigest()
        if not inventory.script_isolated(value, lang):
            return None
        if not source_meta.get("source_id") or not source_meta.get("url"):
            return None
        if source_meta.get("permission_confirmed") is not True:
            return None
        if source_meta.get("redistribution_review_required") is not False:
            return None
        if source_meta.get("authorization_reference") != ATTESTATION:
            return None
        if check.get("text_sha256") != actual_hash:
            return None
        if check.get("ai_translation_used") is not False:
            return None
        if check.get("automatic_diacritization_used") is not False:
            return None
        result[overlay_slot] = {
            "text": value,
            "text_sha256": actual_hash,
            "source_id": str(source_meta["source_id"]),
            "source_url": str(source_meta["url"]),
            "permission_confirmed": True,
            "redistribution_review_required": False,
            "authorization_reference": ATTESTATION,
            "machine_translation_used": False,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
            "script_isolated": True,
        }
    return result or None


def build(start_year: int = 2026, end_year: int = 2050) -> dict:
    entries: dict[str, dict] = {}
    current = date(start_year, 1, 1)
    end = date(end_year + 1, 1, 1)
    while current < end:
        info = update.day_info(current)
        selection = update.liturgy_service_selection(current, info)
        service_type = str(selection.get("service_type") or "")
        if (
            service_type not in {"no_divine_liturgy", "typikon_override_required"}
            and bool(selection.get("displayable"))
        ):
            source_kind, entry = selected_entry(info, current)
            if entry is not None and source_kind in {"fixed", "paschal"}:
                inserts = update.feast_inserts(info, current)
                lanes = {lang: verified_lane(entry, inserts, lang) for lang in LANGS}
                slot_sets = {
                    frozenset((lane or {}).keys())
                    for lane in lanes.values()
                }
                if all(lanes.values()) and len(slot_sets) == 1 and next(iter(slot_sets)):
                    verified_slots = sorted(next(iter(slot_sets)))
                    entries[current.isoformat()] = {
                        "civil_date": current.isoformat(),
                        "julian_date": f"{info['julian_year']:04d}-{info['julian_month']:02d}-{info['julian_day']:02d}",
                        "pascha_offset": (current - info["pascha"]).days,
                        "weekday": current.weekday(),
                        "service_type": service_type,
                        "service_rule_id": selection.get("rule_id"),
                        "proper_id": inserts.get("proper_id"),
                        "proper_provenance": source_kind,
                        "verified_slots": verified_slots,
                        "complete_three_slot_entry": set(verified_slots) == set(SLOT_MAP.values()),
                        "languages": lanes,
                        "fail_closed": True,
                    }
        current += timedelta(days=1)
    return {
        "schema_version": 1,
        "status": "VERIFIED_PARTIAL_DAILY_LITURGY_PROPERS_OVERLAY",
        "calendar": "civil_dates_with_julian_old_calendar_context_and_local_pascha",
        "range": {"start": f"{start_year}-01-01", "end": f"{end_year}-12-31"},
        "languages": list(LANGS),
        "slots": list(SLOT_MAP.values()),
        "policy": {
            "same_language_source_only": True,
            "machine_translation_allowed": False,
            "cross_language_fallback_allowed": False,
            "network_fetch_used": False,
            "verified_requires_matching_text_sha256_rights_and_script_isolation": True,
            "url_alone_is_not_permission": True,
            "partial_dates_omitted": False,
            "partial_entry_slots_allowed": True,
            "all_language_lanes_must_share_same_verified_slots": True,
            "fail_closed": True,
        },
        "entry_count": len(entries),
        "entries": entries,
        "completion_claim": "unproven_complete",
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_verified_daily_propers_overlay.py OUTPUT.json")
    output = Path(sys.argv[1])
    payload = build()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entry_count": payload["entry_count"], "path": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
