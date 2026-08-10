import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(rel): return json.loads((ROOT/rel).read_text(encoding='utf-8'))

def lane_value(obj,lang):
    return str((obj or {}).get(lang,'')).strip() if isinstance(obj,dict) else ''

def test_every_native_service_card_opens_with_nonempty_native_content():
    for lang in ('ar','en','el'):
        pack=load(f'app/src/main/assets/data/native/library_{lang}.json')
        assert len(pack['services']) == 37
        for service in pack['services']:
            assert lane_value(service.get('title'),lang), (lang,service.get('id'),'title')
            assert service.get('segments'), (lang,service.get('id'),'segments')
            for i,seg in enumerate(service['segments']):
                assert lane_value(seg.get('title'),lang) or lane_value(seg.get('text'),lang), (lang,service.get('id'),i)

def test_core_navigation_categories_are_populated_in_every_lane():
    expected={'basic':4,'daily':6,'communion':2,'liturgy':12,'church_service':13}
    for lang in ('ar','en','el'):
        services=load(f'app/src/main/assets/data/native/library_{lang}.json')['services']
        got={k:sum(s.get('category')==k for s in services) for k in expected}
        assert got == expected

def test_search_documents_have_visible_title_and_text_in_each_lane():
    for lang in ('ar','en','el'):
        docs=load(f'app/src/main/assets/data/search/search_index_{lang}.json')['documents']
        assert len(docs) > 2700
        assert all(str(d.get('title','')).strip() for d in docs)
        assert all(str(d.get('display_text','')).strip() for d in docs)

def test_every_church_catalog_card_has_exact_official_catalog_link():
    for lang in ('ar','en','el'):
        services=load(f'app/src/main/assets/data/native/library_{lang}.json')['services']
        cards=[s for s in services if s.get('category')=='church_service']
        assert len(cards)==13
        for card in cards:
            source=card.get('catalog_source') or {}
            assert source.get('source_id') == 'orthodox_jordan'
            assert str(source.get('url','')).startswith('https://orthodoxjordan.org/')
