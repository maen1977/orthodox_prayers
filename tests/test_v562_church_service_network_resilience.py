import json
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("church_importer_v562", ROOT / "scripts/prepare_church_service_corpus.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_required_arabic_network_failure_becomes_same_language_official_link_fallback(tmp_path, monkeypatch):
    manifest = {
        "schema_version": 2,
        "policy": "RIGHTS_AWARE_NATIVE_SOURCE_ONLY_NO_TRANSLATION",
        "runtime_network_required": False,
        "languages": {
            "ar": {
                "source_id": "orthodox_jordan",
                "source_name": "مطرانية الروم الأرثوذكس في الأردن",
                "services": [{
                    "id": "church_baptism",
                    "title": "خدمة العماد والميرون",
                    "url": "https://orthodoxjordan.org/خدمة-المعمودية/",
                    "required": True,
                    "allow_link_fallback": True,
                    "fallback_policy": "OFFICIAL_SOURCE_LINK_ONLY_WHEN_BUILD_SOURCE_UNAVAILABLE",
                    "max_chars": 80000,
                }],
            }
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    cache = tmp_path / "cache"

    def offline(*_args, **_kwargs):
        raise RuntimeError("download_failed:network_unreachable")

    monkeypatch.setattr(mod, "fetch_spec", offline)
    monkeypatch.setattr(sys, "argv", [
        "prepare_church_service_corpus.py",
        "--manifest", str(manifest_path),
        "--output-dir", str(out),
        "--cache-dir", str(cache),
    ])
    assert mod.main() == 0
    payload = json.loads((out / "full_services_ar.json").read_text(encoding="utf-8"))
    assert payload["services"] == []
    assert len(payload["fallbacks"]) == 1
    fb = payload["fallbacks"][0]
    assert fb["id"] == "church_baptism"
    assert fb["full_service"] is False
    assert fb["machine_translation_used"] is False
    assert fb["cross_language_fallback"] is False
    assert fb["official_source_url"].startswith("https://orthodoxjordan.org/")


def test_extractor_rejects_implausibly_large_single_service():
    spec = {
        "id": "church_betrothal",
        "title": "Service of Betrothal",
        "url": "https://example.invalid/source.txt",
        "required": True,
        "min_chars": 10,
        "max_chars": 100,
        "source_transport": "public_domain_plain_text",
        "start_marker": "START",
    }
    raw = ("START\n" + ("A liturgical line with enough content.\n" * 20)).encode()
    try:
        mod.build_service(spec, "en", "source", "Source", raw)
    except RuntimeError as exc:
        assert "service_too_large:en:church_betrothal" in str(exc)
    else:
        raise AssertionError("oversized service extraction must be rejected")


def test_current_manifest_arabic_required_services_fail_soft_only_to_official_link():
    manifest = json.loads((ROOT / "canonical/church_service_full_sources.json").read_text(encoding="utf-8"))
    for service in manifest["languages"]["ar"]["services"]:
        if not service.get("required"):
            continue
        assert service.get("allow_link_fallback") is True
        assert service.get("fallback_policy") == "OFFICIAL_SOURCE_LINK_ONLY_WHEN_BUILD_SOURCE_UNAVAILABLE"
        assert service.get("url", "").startswith("https://orthodoxjordan.org/")
        assert int(service.get("max_chars", 0)) <= 80000
