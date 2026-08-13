import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_church_screen_has_progressive_card_routes():
    source = read('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ChurchesScreen.java')
    activity = read('app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java')
    for route in ('ROUTE_HOME', 'ROUTE_LIVE', 'ROUTE_SOURCES', 'ROUTE_DIRECTORY', 'ROUTE_GROUP', 'ROUTE_CITY'):
        assert route in source
    for method in ('createHomeView', 'createLiveResourcesView', 'createDirectorySourcesView',
                   'createDirectoryGroupsView', 'createGroupCitiesView', 'createCityChurchesView'):
        assert method in source
    assert 'case "churches": return new ChurchesScreen(this, entry.argument);' in activity
    assert 'data.officialLiveResources()' in source
    assert 'data.officialChurchDirectoryResources()' in source
    assert 'data.registeredChurches()' in source


def test_church_directory_data_supports_region_and_city_cards():
    data = json.loads((ROOT / 'app/src/main/assets/data/churches.json').read_text(encoding='utf-8'))
    groups = {item['country_group'] for item in data['churches']}
    assert {'jordan', 'palestine', 'jerusalem'} <= groups
    assert all(item.get('city', {}).get('ar') for item in data['churches'])
    assert all(item.get('country', {}).get('ar') for item in data['churches'])


def test_new_church_card_strings_exist_in_all_supported_lanes():
    names = {
        'ui_church_cards_choose_section_2d4b2f1a',
        'ui_church_live_card_subtitle_4d9b3d21',
        'ui_church_sources_card_subtitle_6b7a2c13',
        'ui_church_directory_card_subtitle_91a4f0d2',
        'ui_church_cards_choose_region_7f9e3a41',
        'ui_church_region_unavailable_0a42b8c1',
        'ui_churches_count_short_format_5f73c9b2',
        'ui_church_cards_choose_city_3c1d8e74',
        'ui_open_official_link_subtitle_8d2f6c10',
    }
    for lane in ('values', 'values-en', 'values-el'):
        root = ET.parse(ROOT / f'app/src/main/res/{lane}/ui_strings.xml').getroot()
        actual = {item.attrib.get('name') for item in root.findall('string')}
        assert names <= actual
