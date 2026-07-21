#!/usr/bin/env python3
"""Validate the user-visible source registry and truthful Liturgy/Communion declarations."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "app/src/main/assets/data/source_registry.json"
DATA = ROOT / "data/sources/source_registry.json"
LIBRARIES = [ROOT / "data/services/library.json", ROOT / "app/src/main/assets/data/library.json"]
REQUIRED_SOURCES = {
    "orthodox_jordan",
    "goarch_online_chapel",
    "church_of_greece_apostoliki_diakonia",
    "ebible_arabic_van_dyck",
    "ebible_world_english_bible",
    "ebible_greek_byzantine_1904",
    "jerusalem_patriarchate_en",
    "antioch_patriarchate_ar",
    "oca_official_english",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require_https(url: str, context: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"{context}: source URL must be absolute HTTPS")


def main() -> None:
    if not ASSET.is_file() or not DATA.is_file():
        raise SystemExit("public source registry is missing")
    if ASSET.read_bytes() != DATA.read_bytes():
        raise SystemExit("asset and data source registries differ")
    registry = load(ASSET)
    sources = registry.get("sources", [])
    if registry.get("schema_version") != 2 or len(sources) < 14:
        raise SystemExit("public source registry is incomplete")
    by_id = {}
    for index, source in enumerate(sources):
        sid = str(source.get("id") or "").strip()
        if not sid or sid in by_id:
            raise SystemExit(f"source[{index}] has a missing or duplicate id")
        by_id[sid] = source
        require_https(str(source.get("url") or ""), sid)
        names = source.get("name") or {}
        if not all(str(names.get(lang) or "").strip() for lang in ("ar", "en", "el")):
            raise SystemExit(f"{sid}: localized source name is incomplete")
        used_for = source.get("used_for") or {}
        if not all(str(used_for.get(lang) or "").strip() for lang in ("ar", "en", "el")):
            raise SystemExit(f"{sid}: user-facing usage explanation is incomplete")
        if not str(source.get("rights") or "").strip():
            raise SystemExit(f"{sid}: rights/license state is missing")
        if source.get("official") and not isinstance(source.get("authority_tier"), int):
            raise SystemExit(f"{sid}: official source authority tier is missing")
        if not isinstance(source.get("connector_ids"), list) or not isinstance(source.get("health"), list):
            raise SystemExit(f"{sid}: connector/health metadata is missing")
    missing = REQUIRED_SOURCES - set(by_id)
    if missing:
        raise SystemExit("public source registry is missing required entries: " + ", ".join(sorted(missing)))

    for path in LIBRARIES:
        library = load(path)
        services = {item["id"]: item for item in library.get("services", [])}
        for sid in ("pre_communion_prayers", "thanksgiving_after_communion", "divine_liturgy"):
            if sid not in services:
                raise SystemExit(f"{path.name}: {sid} service is missing")
        liturgy = services["divine_liturgy"]
        title = liturgy.get("title") or {}
        if "الكامل" in str(title.get("ar") or "") or "Full" in str(title.get("en") or ""):
            raise SystemExit(f"{path.name}: Divine Liturgy must not claim completeness before the gate passes")
        if liturgy.get("source_provenance", {}).get("complete_service_claim") is not False:
            raise SystemExit(f"{path.name}: complete_service_claim must be false")
        if any(segment.get("type") == "quiet_prayer" for segment in liturgy.get("segments", [])):
            raise SystemExit(f"{path.name}: unregistered quiet prayers remain inside the Liturgy")
        related = {x.get("service_id") for x in liturgy.get("related_services", [])}
        if not {"pre_communion_prayers", "thanksgiving_after_communion", "orthros"}.issubset(related):
            raise SystemExit(f"{path.name}: Liturgy related-service links are incomplete")
        for sid in ("pre_communion_prayers", "thanksgiving_after_communion"):
            service = services[sid]
            provenance = service.get("source_provenance") or {}
            if provenance.get("source_id") != "orthodox_jordan":
                raise SystemExit(f"{path.name}:{sid}: Jordan source link is missing")
            require_https(str(provenance.get("official_url") or ""), f"{path.name}:{sid}")
            if provenance.get("complete_text") is not False:
                raise SystemExit(f"{path.name}:{sid}: incomplete text must be declared truthfully")
            if "COMPLETE" in str(service.get("completion_status") or "") and "NOT" not in str(service.get("completion_status") or ""):
                raise SystemExit(f"{path.name}:{sid}: completion status is misleading")

    settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
    main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
    reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
    prayer_hub = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/PrayerHubScreen.java").read_text(encoding="utf-8")
    if 'host.navigate("sources", null)' not in settings or 'case "sources"' not in main:
        raise SystemExit("Settings source-registry navigation is missing")
    if 'relatedServicesBox' not in reader or 'فتح المصدر الرسمي' not in reader:
        raise SystemExit("Reader source and related-prayer controls are missing")
    if '"communion"' not in prayer_hub:
        raise SystemExit("Communion-prayer category is missing from PrayerHub")
    print(f"Public source registry validated: {len(sources)} sources; Liturgy and Communion completeness declarations are truthful")

if __name__ == "__main__":
    main()
