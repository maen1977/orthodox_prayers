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
