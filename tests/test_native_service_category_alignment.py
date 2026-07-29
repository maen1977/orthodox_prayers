import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def services(payload):
    return {item["id"]: item for item in payload.get("services", []) if isinstance(item, dict) and item.get("id")}


def test_native_service_categories_match_reviewed_source_library():
    source = services(load("data/services/library.json"))
    for language in ("ar", "en", "el"):
        native = services(load(f"data/services/native/library_{language}.json"))
        for service_id, native_service in native.items():
            assert service_id in source, f"{service_id}:{language}"
            assert native_service.get("category") == source[service_id].get("category"), (
                service_id, language, native_service.get("category"), source[service_id].get("category")
            )


def test_small_compline_remains_in_daily_category_for_runtime_overlay_compatibility():
    source = services(load("data/services/library.json"))
    assert source["small_compline"]["category"] == "daily"
    for language in ("ar", "en", "el"):
        native = services(load(f"app/src/main/assets/data/native/library_{language}.json"))
        assert native["small_compline"]["category"] == "daily"


def test_builder_forces_structural_category_from_source_library():
    builder = (ROOT / "scripts/build_native_service_packs.py").read_text(encoding="utf-8")
    assert 'service["category"] = source_category' in builder
