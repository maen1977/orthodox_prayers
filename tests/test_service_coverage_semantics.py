from scripts.attach_source_intelligence import coverage

def test_services_without_daily_variables_are_not_applicable():
    result=coverage({'services':[{'id':'vespers','segment_replacements':{}}]})['services'][0]
    assert result['status']=='not_applicable'
    assert result['complete'] is None
    assert result['coverage_percent']==100

def test_required_daily_variables_remain_truthful():
    result=coverage({'services':[{'id':'divine_liturgy','segment_replacements':{}}]})['services'][0]
    assert result['status']=='incomplete'
    assert result['complete'] is False
    assert result['missing_variables']
