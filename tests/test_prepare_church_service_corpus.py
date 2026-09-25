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


def test_legacy_body_flow_parser_reads_br_separated_liturgical_page():
    raw = '''<html><head><script>ignore()</script></head><body>
    <p><img src="seal.png" /></p>
    <br/><font color="#ff0000">ΑΚΟΛΟΥΘΙΑ ΤΟΥ ΑΓΙΟΥ ΒΑΠΤΙΣΜΑΤΟΣ</font>
    <br/>Ὁ Ἱερεὺς λέγει·
    <br/><b>Εὐλογητὸς ὁ Θεὸς ἡμῶν.</b>
    <script>do_not_capture()</script>
    </body></html>'''.encode('utf-8')
    blocks = mod.parse_blocks(raw)
    assert blocks[0] == 'ΑΚΟΛΟΥΘΙΑ ΤΟΥ ΑΓΙΟΥ ΒΑΠΤΙΣΜΑΤΟΣ'
    assert blocks[1].startswith('Ὁ Ἱερεὺς')
    assert blocks[2].startswith('Εὐλογητὸς')
    assert all('do_not_capture' not in block for block in blocks)


def test_open_source_end_marker_is_excluded_from_service_slice():
    raw = b"TABLE OF CONTENTS\n\nSERVICE A\n\nPriest: first prayer.\n\n<td\n\nSERVICE B\n\nPriest: next service.\n"
    spec = {
        'id': 'service_a',
        'source_transport': 'public_domain_plain_text',
        'start_marker': ['SERVICE A'],
        'end_marker': ['SERVICE B'],
        'marker_occurrence': 'first',
    }
    blocks = mod.normalize_open_source_blocks(raw, 'en', spec)
    assert blocks == ['SERVICE A', 'Priest: first prayer.']
    assert 'SERVICE B' not in blocks


def test_segment_has_only_native_language():
    seg = mod.block_to_segment('Priest: Blessed is our God.', 'en')
    assert seg['text']['en']
    assert seg['text']['ar'] == ''
    assert seg['text']['el'] == ''


def test_service_level_provenance_overrides_lane_default():
    spec = {
        'id': 'greek_test_service',
        'title': 'Δοκιμή',
        'url': 'https://glt.goarch.org/texts/Euch/Test.html',
        'min_chars': 1,
        'source_id': 'goarch_glt_greek_euchologion_pages',
        'source_name': 'GOARCH GLT',
        'permission_confirmed': True,
        'redistribution_review_required': False,
    }
    service = mod.build_service(spec, 'el', 'lane-source', 'Lane source', '<html><body><br/>Δοκιμή λειτουργικοῦ κειμένου.</body></html>'.encode('utf-8'))
    assert service['native_source']['source_id'] == 'goarch_glt_greek_euchologion_pages'
    assert service['native_source']['name'] == 'GOARCH GLT'
    assert service['native_source']['permission_confirmed'] is True


def test_prefetch_deduplicates_shared_source_and_preserves_lane(monkeypatch, tmp_path):
    calls = []
    def fake_fetch(spec, cache):
        calls.append((spec['url'], cache.name))
        return (spec['url'] + ':' + cache.name).encode()
    monkeypatch.setattr(mod, 'fetch_spec', fake_fetch)
    manifest = {
        'languages': {
            'en': {'services': [
                {'id':'a','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text','permission_confirmed':True,'redistribution_review_required':False},
                {'id':'b','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text','permission_confirmed':True,'redistribution_review_required':False},
            ]},
            'el': {'services': [
                {'id':'c','url':'https://example.test/book.txt','source_transport':'public_domain_plain_text','permission_confirmed':True,'redistribution_review_required':False},
            ]},
        }
    }
    result = mod.prefetch_registered_sources(manifest, tmp_path)
    assert len(result) == 2
    assert sorted(calls) == [('https://example.test/book.txt', 'el'), ('https://example.test/book.txt', 'en')]
