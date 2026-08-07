from pathlib import Path
import importlib.util
import json
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_church_service_corpus.py"


def load_module():
    spec = importlib.util.spec_from_file_location("church_service_builder_v551", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_version_is_551():
    text = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'versionCode = 50501' in text
    assert 'versionName = "5.5.1"' in text


def test_goarch_403_uses_same_origin_curl_before_browser(monkeypatch, tmp_path):
    module = load_module()

    def blocked(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://www.goarch.org/-/marriage", 403, "Forbidden", {}, None
        )

    curl_html = (
        b"<!doctype html><html><body><p>PRIEST</p>"
        + b"<p>" + (b"Complete liturgical service text. " * 40) + b"</p></body></html>"
    )
    monkeypatch.setattr(module.urllib.request, "urlopen", blocked)
    monkeypatch.setattr(module, "_fetch_with_curl", lambda url: curl_html)
    monkeypatch.setattr(
        module, "_fetch_with_headless_browser",
        lambda url: (_ for _ in ()).throw(AssertionError("browser must not run after successful curl")),
    )

    result = module.fetch("https://www.goarch.org/-/marriage", tmp_path / "cache")
    assert result == curl_html
    assert list((tmp_path / "cache").glob("*.html"))


def test_goarch_403_uses_browser_when_curl_is_also_blocked(monkeypatch, tmp_path):
    module = load_module()

    def blocked(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://www.goarch.org/-/funeral-service", 403, "Forbidden", {}, None
        )

    browser_html = (
        b"<!doctype html><html><body><p>PRIEST</p>"
        + b"<p>" + (b"Complete funeral service text. " * 40) + b"</p></body></html>"
    )
    monkeypatch.setattr(module.urllib.request, "urlopen", blocked)
    monkeypatch.setattr(module, "_fetch_with_curl", lambda url: (_ for _ in ()).throw(RuntimeError("curl_failed:22:403")))
    monkeypatch.setattr(module, "_fetch_with_headless_browser", lambda url: browser_html)

    result = module.fetch("https://www.goarch.org/-/funeral-service", tmp_path / "cache")
    assert result == browser_html


def test_no_third_party_proxy_or_cross_language_fallback():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "r.jina.ai" not in text
    assert "translate" in text.lower()
    assert "cross_language_fallback" in text
    assert "_fetch_with_curl" in text
    assert "headless_browser" in text
    assert "Referer" in text


def test_bilingual_dcs_is_sliced_before_language_filter():
    module = load_module()
    raw = """<!doctype html><html><body>
      <p>Navigation</p>
      <p>ΑΚΟΛΟΥΘΙΑ ΤΟΥ ΑΓΙΟΥ ΒΑΠΤΙΣΜΑΤΟΣ | BAPTISM</p>
      <p>ΙΕΡΕΥΣ</p><p>PRIEST</p>
      <p>Εὐλογητὸς ὁ Θεός.</p><p>Blessed is our God.</p>
      <p>Ἀμήν.</p><p>Amen.</p>
    </body></html>""".encode("utf-8")
    spec = {
        "title": "Holy Baptism and Chrismation",
        "filter_script": "latin",
        "start_marker": ["ΑΚΟΛΟΥΘΙΑ ΤΟΥ ΑΓΙΟΥ ΒΑΠΤΙΣΜΑΤΟΣ", "BAPTISM"],
    }
    blocks = module.normalize_blocks(raw, "en", spec)
    joined = " ".join(blocks)
    assert "Blessed is our God" in joined
    assert "Εὐλογητὸς" not in joined


def test_manifest_prefers_static_dcs_for_baptism_and_memorial():
    data = json.loads((ROOT / "canonical/church_service_full_sources.json").read_text(encoding="utf-8"))
    for lang in ("en", "el"):
        by_id = {s["id"]: s for s in data["languages"][lang]["services"]}
        for service_id in ("church_baptism", "church_memorial"):
            svc = by_id[service_id]
            assert svc["url"].startswith("https://dcs.goarch.org/")
            assert svc["source_transport"] == "dcs_static"


def test_workflow_requires_browser_before_service_import():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    browser = workflow.index("Verify browser fallback for protected Church sources")
    importer = workflow.index("Prepare complete native church services")
    assert browser < importer
    assert "google-chrome" in workflow
    assert "chromium" in workflow
