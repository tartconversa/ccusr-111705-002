"""只审阅已观察的详情入口，不把候选记录当作已完成的业务。"""
from .domain import (
    SLOT_AVAILABLE,
    SLOT_UNOBSERVED,
    PREVIEW_TEMPORARY_HOLD,
    PREVIEW_PARTY_EXCEEDS,
    PREVIEW_UNOBSERVED,
    is_bookable_preview,
)


def review_entries(entries):
    candidates = []
    for entry in entries:
        choice = entry['detail_fact']
        advertised = entry['catalog_fact']['places']
        candidates.append({'slot_request': choice['business_key'], 'advertised_places': advertised,
                           'party_size': choice['party_size'], 'hold_status': 'not_observed',
                           'advertised_shortfall': choice['party_size'] > advertised})
    return candidates


def _reasons(row):
    """一条观察行与目录承诺、与可预约结论之间的差异原因；空列表表示一致。"""
    reasons = []
    advertised = row['catalog_fact']['places']
    advertised_date = row['catalog_fact']['condition']

    if row['slot_status'] == SLOT_UNOBSERVED:
        # 未渲染/占位失败只能如实记录，不能当作售罄，也不能参与一致性结论
        reasons.append('slot_unobserved')
    elif row['slot_status'] != SLOT_AVAILABLE:
        reasons.append('slot_not_available_on_detail')
    elif row['date'] == advertised_date and row['slot_places'] != advertised:
        reasons.append('detail_places_differ_from_catalog')

    if row['preview_status'] == PREVIEW_UNOBSERVED:
        reasons.append('preview_unobserved')
    elif not is_bookable_preview(row['preview_status']):
        if row['preview_status'] == PREVIEW_TEMPORARY_HOLD:
            reasons.append('temporary_hold_blocks_preview')
        elif row['preview_status'] == PREVIEW_PARTY_EXCEEDS:
            reasons.append('party_exceeds_capacity')
        else:
            reasons.append('preview_not_bookable')
    return reasons


def build_difference_list(rows):
    """把候选档期与最终预览状态关联，输出接待员可追溯的差异清单。

    每行都带观察编号、项目身份、业务键、日期、人数、观察阶段、来源 URL、
    原始页面文本和请求轨迹，保证结论可回溯到具体观察步骤；
    unobserved 与 sold_out 严格区分，绝不把未渲染写成售罄。
    """
    differences = []
    for row in rows:
        reasons = _reasons(row)
        differences.append({
            'observation_id': row['observation_id'],
            'item_id': row['item_id'],
            'business_key': row['business_key'],
            'source': row['source'],
            'phase': row['phase'],
            'date': row['date'],
            'party_size': row['party_size'],
            'catalog_condition': row['catalog_fact']['condition'],
            'advertised_places': row['catalog_fact']['places'],
            'slot_status': row['slot_status'],
            'slot_places': row['slot_places'],
            'preview_status': row['preview_status'],
            'slot_raw_text': row['slot_raw_text'],
            'preview_raw_text': row['preview_raw_text'],
            'difference_reasons': reasons,
            'is_difference': bool(reasons),
            'observed_requests': row['observed_requests'],
        })
    return differences


def summarize_differences(differences):
    """按项目汇总：多少候选、多少差异、各预览状态计数。"""
    summary = {}
    for entry in differences:
        bucket = summary.setdefault(entry['item_id'], {
            'candidates': 0, 'differences': 0, 'preview_statuses': {},
            'slot_statuses': {}})
        bucket['candidates'] += 1
        bucket['differences'] += 1 if entry['is_difference'] else 0
        bucket['preview_statuses'][entry['preview_status']] = \
            bucket['preview_statuses'].get(entry['preview_status'], 0) + 1
        bucket['slot_statuses'][entry['slot_status']] = \
            bucket['slot_statuses'].get(entry['slot_status'], 0) + 1
    return summary
