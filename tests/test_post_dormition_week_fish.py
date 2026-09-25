import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_liturgical_data as calendar  # noqa: E402


def expected_allowed(profile):
    return {item['key'] for item in profile['items'] if item.get('allowed')}


def test_reported_2026_dates_are_fish_allowed():
    for iso in ('2026-09-02', '2026-09-04'):
        fasting = calendar.day_info(date.fromisoformat(iso))['fasting']
        assert fasting['code'] == 'fish_allowed'
        assert fasting['verification']['rule'] == 'post_dormition_week_fish'
        assert expected_allowed(fasting) == {'fish', 'wine', 'oil'}


def test_rule_is_fixed_old_calendar_august_20_and_22_through_2050():
    for year in range(2026, 2051):
        for old_month_day in ((8, 20), (8, 22)):
            civil = calendar.julian_to_gregorian_date(year, *old_month_day)
            fasting = calendar.day_info(civil)['fasting']
            assert fasting['code'] == 'fish_allowed'
            assert fasting['verification']['rule'] == 'post_dormition_week_fish'


def test_generated_assets_match_source_rule():
    asset = json.loads((ROOT / 'app/src/main/assets/data/calendar/calendar_2026.json').read_text())
    profiles = asset['fasting_profiles']
    for iso in ('2026-09-02', '2026-09-04'):
        day = next(item for item in asset['days'] if item['date_iso'] == iso)
        profile = profiles[day['fasting']['profile_id']]
        assert profile['code'] == 'fish_allowed'
        assert profile['verification']['rule'] == 'post_dormition_week_fish'
        assert expected_allowed(profile) == {'fish', 'wine', 'oil'}
