import json
import sys
from calendar import monthrange
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import bootstrap_perpetual_lectionary_2050 as boot
import build_internal_calendar_2050 as calendar_builder


def month_payload(year,month):
    count=monthrange(year,month)[1]
    data=[]
    for i in range(count):
        item={
            # Deliberately shifted source date values: normalize_month must use
            # the requested civil month/list order, not these Julian fields.
            'year':year-1,'month':12,'day':19+i,
            'readings':[], 'abbreviated_reading_indices':[]
        }
        data.append(item)
    data[0]['readings']=[{'display':'Romans 1:1-7'},{'display':'Matthew 1:1-17'}]
    data[0]['abbreviated_reading_indices']=[0,1]
    data[1]['readings']=[{'display':'Isaiah 1:1-20'},{'display':'Genesis 1:1-13'},{'display':'Proverbs 1:1-20'}]
    data[1]['abbreviated_reading_indices']=[0,1,2]
    return data


def test_month_normalizer_keeps_civil_dates_and_classifies_appointed_readings():
    records=boot.normalize_month(2027,1,month_payload(2027,1))
    assert set(records) >= {'2027-01-01','2027-01-02'}
    first=records['2027-01-01']
    assert first['reading_references']['epistle']['canonical_reference']=='ROM.1.1-7'
    assert first['reading_references']['gospel']['canonical_reference']=='MAT.1.1-17'
    second=records['2027-01-02']
    assert [r['kind'] for r in second['appointed_readings']]==['old_testament']*3
    assert second['reading_references']=={}
    assert second['appointed_readings'][0]['reference']['ar'].startswith('إشعياء ')
    assert second['appointed_readings'][0]['reference']['el'].startswith('Ἠσαΐας ')


def test_baseline_never_imports_saints_or_stories():
    months={(2027,m):month_payload(2027,m) for m in range(1,13)}
    payload=boot.build_payload(months,2027,2027)
    text=json.dumps(payload,ensure_ascii=False)
    assert '"saints"' not in text
    assert '"stories"' not in text
    assert payload['source']['repository_commit']==boot.SOURCE_COMMIT
    assert payload['civil_range']['day_count']==365


def test_calendar_priority_exact_then_fixed_then_perpetual():
    day=__import__('datetime').date(2035,8,14)
    baseline={day.isoformat():{
        'reading_references':{
            'epistle':{'canonical_reference':'ROM.1.1-7','display_reference':'Romans 1:1-7','reference':{'ar':'رومية 1:1-7','en':'Romans 1:1-7','el':'Πρὸς Ῥωμαίους 1:1-7'}},
            'gospel':{'canonical_reference':'MAT.1.1-17','display_reference':'Matthew 1:1-17','reference':{'ar':'متى 1:1-17','en':'Matthew 1:1-17','el':'Κατὰ Ματθαῖον 1:1-17'}},
        },
        'appointed_readings':[{'kind':'epistle','canonical_reference':'ROM.1.1-7'}],
    }}
    refs,appointed,status,resolution=calendar_builder.compact_readings(day,{}, {},baseline)
    assert status=='PERPETUAL_GREEK_JULIAN_REFERENCE_BASELINE'
    assert refs['epistle']['canonical_reference']=='ROM.1.1-7'
    assert appointed
    assert resolution['status']=='APPOINTED_READINGS_PRESENT'

    exact={day.isoformat():{'reading_references':{'epistle':{'canonical_reference':'HEB.1.1-4'}}}}
    refs,appointed,status,resolution=calendar_builder.compact_readings(day,exact,{},baseline)
    assert status=='PINNED_EXACT_DATE_REFERENCE'
    assert refs['epistle']['canonical_reference']=='HEB.1.1-4'


def test_commemoration_acquisition_queue_reduces_6987_days_to_old_calendar_slots():
    q=json.loads((ROOT/'canonical/jordan_jerusalem_commemoration_acquisition_queue.json').read_text(encoding='utf-8'))
    assert q['slot_count']==366
    assert q['unresolved_civil_days']==6987
    pending=[s for s in q['slots'] if s['unresolved_civil_day_count']]
    assert 300 < len(pending) <= 366
    assert q['machine_translation_allowed'] is False
    for item in pending[:10]:
        assert item['promotion_contract']['long_synaxarion_prose_copied'] is False
        assert item['preferred_sources'][0]['id']=='orthodox_jordan_daily'



def test_display_only_lxx_books_remain_old_testament_and_localized():
    block=boot.reference_block('Wisdom of Solomon 3:1-9', boot.classify('', {}, 'Wisdom of Solomon 3:1-9'))
    assert block['kind']=='old_testament'
    assert block['canonical_reference']==''
    assert block['reference']['ar'].startswith('حكمة سليمان ')
    assert block['reference']['el'].startswith('Σοφία Σαλωμῶνος ')


def test_calendar_lock_updater_preserves_legacy_h2_compatibility_asset():
    updater=(ROOT/'scripts/update_calendar_2050_lock.py').read_text(encoding='utf-8')
    lock=json.loads((ROOT/'canonical/calendar_2026_2050_lock.json').read_text(encoding='utf-8'))
    assert 'LEGACY_H2_ASSET' in updater
    assert any(item['path']=='app/src/main/assets/data/calendar_2026_h2.json' for item in lock['files'])

def test_android_reader_supports_appointed_old_testament_references():
    engine=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java').read_text(encoding='utf-8')
    day_screen=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java').read_text(encoding='utf-8')
    upcoming=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java').read_text(encoding='utf-8')
    assert 'appointed_readings' in engine
    assert '"old_testament".equals(kind)' in engine
    assert 'addAppointedReadingReferences' in day_screen
    assert 'ui_old_testament_reading_r63' in day_screen
    assert 'ui_old_testament_reading_r63' in upcoming


def test_workflow_bootstraps_and_caches_perpetual_readings_before_release_gate():
    workflow=(ROOT/'.github/workflows/church-prayers.yml').read_text(encoding='utf-8')
    assert 'Restore perpetual lectionary cache' in workflow
    assert 'bootstrap_perpetual_lectionary_2050.py --workers 8' in workflow
    assert 'update_calendar_2050_lock.py --approve-r63-perpetual-lectionary' in workflow
    assert workflow.index('Bootstrap perpetual 2026-2050 appointed readings') < workflow.index('Check content, languages, security, and calendar')
