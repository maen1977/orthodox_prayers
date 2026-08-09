import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('church_importer', ROOT / 'scripts/prepare_church_service_corpus.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_iri_to_uri_encodes_arabic_path():
    value = mod.iri_to_uri('https://orthodoxjordan.org/خدمة-المعمودية/')
    assert value.startswith('https://orthodoxjordan.org/%D8%AE')
    assert 'خدمة' not in value


def test_parser_keeps_service_and_removes_navigation():
    raw = '''<html><header>MENU</header><body><h1>خدمة المعمودية</h1>
    <div>ديسمبر 2023</div><p>الكاهن: تبارك الله إلهنا.</p>
    <h3>الرسالة</h3><p>القارئ: قراءة من الرسالة.</p><footer>FOOT</footer></body></html>'''.encode()
    spec = {'title':'خدمة المعمودية','start_marker':'الكاهن:','id':'church_baptism'}
    blocks = mod.normalize_blocks(raw, 'ar', spec)
    assert blocks[0].startswith('الكاهن:')
    assert any('الرسالة' in x for x in blocks)
    assert all('MENU' not in x and 'FOOT' not in x for x in blocks)


def test_segment_has_only_native_language():
    seg = mod.block_to_segment('Priest: Blessed is our God.', 'en')
    assert seg['text']['en']
    assert seg['text']['ar'] == ''
    assert seg['text']['el'] == ''


def test_prefetch_deduplicates_shared_source_and_preserves_lane(monkeypatch, tmp_path):
    calls = []
    def fake_fetch(spec, cache):
        calls.append((spec['url'], cache.name))
        return (spec['url'] + ':' + cache.name).encode()
    monkeypatch.setattr(mod, 'fetch_spec', fake_fetch)
    manifest = {
        'languages': {
            'en': {'services': [
                {'id':'a','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text'},
                {'id':'b','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text'},
            ]},
            'el': {'services': [
                {'id':'c','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text'},
            ]},
        }
    }
    result = mod.prefetch_registered_sources(manifest, tmp_path)
    assert len(result) == 2
    assert sorted(calls) == [('https://example.test/book.txt', 'el'), ('https://example.test/book.txt', 'en')]
