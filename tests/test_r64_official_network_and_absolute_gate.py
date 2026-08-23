import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import harvest_official_source_network_r64 as h
import audit_absolute_coverage_r64 as audit


def test_r64_network_is_strictly_jerusalem_jordan_and_expanded():
    cfg=json.loads((ROOT/'canonical/r64_official_source_network.json').read_text(encoding='utf-8'))
    suffixes=set(cfg['allowed_domain_suffixes'])
    assert {'orthodoxjordan.org','orthodoxjo.tv','jerusalem-patriarchate.info'} <= suffixes
    roots={x['id'] for x in cfg['roots']}
    assert {'orthodox_jordan_ar','orthodox_tv_ar','jerusalem_patriarchate_ar','jerusalem_patriarchate_en','jerusalem_patriarchate_el','jerusalem_patriarchate_radio'} <= roots
    assert cfg['crawl_policy']['authentication_bypass'] is False
    assert cfg['crawl_policy']['captcha_bypass'] is False
    assert 800 <= cfg['crawl_policy']['default_max_pages'] <= 2000
    assert cfg['crawl_policy']['default_max_depth'] <= 2
    assert 'commemorations' in cfg['relevance_keywords']
    direct = {x['id']: x for x in cfg.get('direct_documents', [])}
    assert direct['jerusalem_patriarchate_calendar_2026_ar']['language'] == 'ar'
    assert direct['jerusalem_patriarchate_calendar_2026_ar']['url'].endswith('/arabic_2026.pdf')
    assert 'evidence_only' in direct['jerusalem_patriarchate_calendar_2026_ar']['promotion']


def test_subdomains_are_allowed_but_lookalikes_are_not():
    suffixes=['orthodoxjordan.org','jerusalem-patriarchate.info']
    assert h.host_allowed('services.orthodoxjordan.org',suffixes)
    assert h.host_allowed('radio.jerusalem-patriarchate.info',suffixes)
    assert not h.host_allowed('orthodoxjordan.org.example.com',suffixes)
    assert not h.host_allowed('fakejerusalem-patriarchate.info.example',suffixes)


def test_sitemap_and_html_parser_support_recursive_discovery():
    pages,nested=h.sitemap_urls(b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://orthodoxjordan.org/prayer/</loc></url></urlset>')
    assert pages==['https://orthodoxjordan.org/prayer/'] and not nested
    p=h.LinkTextParser(); p.feed('<html><title>صلاة اليوم</title><body><a href="/x">تذكار القديس</a><iframe src="https://youtube.com/a"></iframe></body></html>')
    assert '/x' in p.links and 'https://youtube.com/a' in p.links
    cats=h.classify(p.text,'https://orthodoxjordan.org/x',json.loads((ROOT/'canonical/r64_official_source_network.json').read_text(encoding='utf-8'))['relevance_keywords'])
    assert 'prayers' in cats or 'daily' in cats or 'commemorations' in cats


def test_r64_absolute_gate_is_in_release_gate_and_workflow_strict_after_bootstrap():
    gate=(ROOT/'scripts/run_local_daily_release_gate.py').read_text(encoding='utf-8')
    workflow=(ROOT/'.github/workflows/church-prayers.yml').read_text(encoding='utf-8')
    assert 'audit_absolute_coverage_r64.py' in gate
    assert 'Harvest focused official Jerusalem/Jordan liturgical source network' in workflow
    assert 'audit_absolute_coverage_r64.py --require-complete' in workflow
    assert 'audit_absolute_coverage_r64.py --require-complete --require-named-commemorations' in workflow
    assert '::notice title=R64 content advisory::' in workflow
    assert '::warning::R64 named commemoration coverage is incomplete' not in workflow
    assert workflow.index('Harvest focused official Jerusalem/Jordan liturgical source network') < workflow.index('Check content, languages, security, and calendar')


def test_perpetual_bootstrap_resolves_every_day_even_when_source_has_no_abbreviated_reading():
    import bootstrap_perpetual_lectionary_2050 as boot
    payload=[{'readings':[],'abbreviated_reading_indices':[]} for _ in range(31)]
    records=boot.normalize_month(2027,1,payload)
    assert len(records)==31
    assert records['2027-01-01']['reading_day_resolution']['status']=='NO_ABBREVIATED_READING_APPOINTED_BY_SOURCE'


def test_absolute_audit_script_requires_named_commemoration_separately_and_writes_report():
    text=(ROOT/'scripts/audit_absolute_coverage_r64.py').read_text(encoding='utf-8')
    assert '--require-named-commemorations' in text
    assert 'old_calendar_date_baseline' in text
    assert 'generic_commemoration' in text
    assert audit.EXPECTED==9131



def test_r64_sitemap_filter_prevents_archive_queue_explosion():
    roots=['https://orthodoxjordan.org/','https://ar.jerusalem-patriarchate.info/']
    # High-value ecclesiastical URLs survive.
    assert h.is_relevant_candidate_url('https://orthodoxjordan.org/صلاة-اليوم/', roots)
    assert h.is_relevant_candidate_url('https://orthodoxjordan.org/downloads/كتاب-الصلوات.pdf', roots)
    assert h.is_relevant_candidate_url('https://ar.jerusalem-patriarchate.info/الكنائس-المقدسة-في-الأردن/', roots)
    # Common WordPress explosion sources do not.
    assert not h.is_relevant_candidate_url('https://orthodoxjordan.org/tag/news/page/44/', roots)
    assert not h.is_relevant_candidate_url('https://orthodoxjordan.org/wp-content/uploads/2026/01/photo.jpg', roots)
    assert not h.is_relevant_candidate_url('https://orthodoxjordan.org/?s=church', roots)
    # A synthetic 60k sitemap-like URL collection must collapse dramatically.
    urls=[f'https://orthodoxjordan.org/tag/archive-{i}/page/{i%90+1}/' for i in range(59000)]
    urls += [f'https://orthodoxjordan.org/صلاة-اليوم-{i}/' for i in range(700)]
    accepted=[u for u in urls if h.is_relevant_candidate_url(u, roots)]
    assert len(accepted)==700
