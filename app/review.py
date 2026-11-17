"""只审阅已观察的详情入口，不把候选记录当作已完成的业务。"""

def review_entries(entries):
    candidates = []
    for entry in entries:
        choice = entry['detail_fact']
        advertised = entry['catalog_fact']['places']
        candidates.append({'slot_request': choice['business_key'], 'advertised_places': advertised,
                           'party_size': choice['party_size'], 'hold_status': 'not_observed',
                           'advertised_shortfall': choice['party_size'] > advertised})
    return candidates
