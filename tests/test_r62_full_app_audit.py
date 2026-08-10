import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def load(rel):
    return json.loads(read(rel))


def test_prayer_of_day_is_clock_based_not_day_rotation():
    home = read('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java')
    selector = read('app/src/main/java/com/orthodoxprayers/privateapp/data/PrayerOfDaySelector.java')
    assert 'DAILY_PRAYER_ROTATION' not in home
    assert 'PrayerOfDaySelector.forTime' in home
    assert 'Asia/Amman' in home
    for service in ('morning_prayer','thanksgiving','evening_prayer','small_compline'):
        assert service in selector
    assert '4 * 60' in selector
    assert '12 * 60' in selector
    assert '17 * 60 + 30' in selector
    assert '21 * 60 + 30' in selector


def test_official_church_directory_is_expanded_and_grouped():
    data = load('app/src/main/assets/data/churches.json')
    churches = data['churches']
    assert data['status'] == 'official_directory_audited'
    assert data['count'] == len(churches)
    assert len(churches) >= 57
    groups = {c['country_group'] for c in churches}
    assert {'jordan','palestine','jerusalem'} <= groups
    assert sum(c['country_group']=='jordan' for c in churches) >= 42
    assert sum(c['country_group']=='palestine' for c in churches) >= 9
    assert len(data.get('source_directories',[])) >= 5
    for c in churches:
        for field in ('name','city','country'):
            assert set(c[field]) >= {'ar','en','el'}
            assert all(str(c[field][lang]).strip() for lang in ('ar','en','el'))
        assert c['url'].startswith('https://')
        assert c['source_id'] in {'jerusalem_patriarchate_official_directory','orthodox_jordan_official_directory'}


def test_visible_live_resources_only_use_verified_official_pages():
    data = load('app/src/main/assets/data/churches.json')
    live = data['live_resources']
    assert len(live) == 3
    urls = {x['url'] for x in live}
    assert 'https://orthodoxjo.tv/' in urls
    assert any('jerusalem-patriarchate.info' in x for x in urls)
    assert not any('/video/orthodox-station/' in x for x in urls)
    for item in live:
        assert item['status'] == 'verified_official_2026_08_10'
        for lang in ('ar','en','el'):
            assert item['title'][lang].strip()


def test_church_screen_groups_entries_and_separates_verified_directories():
    source = read('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ChurchesScreen.java')
    assert 'data.officialLiveResources()' in source
    assert 'mergeResources(data.officialLiveResources(), data.officialServiceLinks())' not in source
    assert 'data.officialChurchDirectoryResources()' in source
    assert 'country_group' in source


def test_audit_report_truthfully_records_known_content_gaps():
    audit = load('canonical/r62_full_app_audit.json')
    assert audit['metrics']['calendar_days'] == 9131
    assert audit['metrics']['reading_counts']['epistle'] < 9131
    assert audit['metrics']['reading_counts']['gospel'] < 9131
    assert audit['metrics']['generic_commemoration_days'] > 0
    assert audit['metrics']['church_service_pending_full_text']['ar'] == 13
    assert audit['release_claim'].startswith('AUDITED_WITH_KNOWN_CONTENT_GAPS')
    status = {x['id']: x['status'] for x in audit['checks']}
    assert status['daily_readings'] == 'INCOMPLETE'
    assert status['commemorations'] == 'INCOMPLETE'
    assert status['church_services'] == 'CATALOG_COMPLETE_TEXT_INCOMPLETE'
    assert status['daily_prayers'] == 'PARTIAL_WITH_OFFICIAL_LINKS'
    assert status['church_directory'] == 'PARTIAL_WITH_FULL_DIRECTORY_LINKS'
    assert audit['metrics']['official_daily_prayer_links'] >= 4
    assert audit['metrics']['arabic_church_build_rights_pending'] >= 10
    assert status['orthros_ar'] == 'INCOMPLETE_FAIL_CLOSED'


def test_new_directory_localization_has_no_arabic_leakage_in_non_arabic_lanes():
    data = load('app/src/main/assets/data/churches.json')
    arabic = re.compile(r'[\u0600-\u06FF]')
    for c in data['churches']:
        assert not arabic.search(c['name']['en'])
        assert not arabic.search(c['name']['el'])
        assert not arabic.search(c['city']['en'])
        assert not arabic.search(c['city']['el'])
        assert not arabic.search(c['country']['en'])
        assert not arabic.search(c['country']['el'])
    for item in data['live_resources'] + data['source_directories']:
        assert not arabic.search(item['title']['en'])
        assert not arabic.search(item['title']['el'])
