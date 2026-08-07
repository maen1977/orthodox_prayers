from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]

def test_legacy_403_scraping_is_not_a_release_dependency_anymore():
    data=json.loads((ROOT/"canonical/church_service_full_sources.json").read_text(encoding="utf-8"))
    for lang in ("en","el"):
        for svc in data["languages"][lang]["services"]:
            assert svc.get("source_transport") in {"public_domain_plain_text","cc_by_pdf_text","official_link_only"}
            assert "www.goarch.org" not in svc.get("url","")

def test_no_cross_language_or_proxy_fallback():
    text=(ROOT/"scripts/prepare_church_service_corpus.py").read_text(encoding="utf-8")
    assert "r.jina.ai" not in text
    assert "cross_language_fallback" in text
