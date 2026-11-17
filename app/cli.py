"""公开目录采集与档期观察演示（只访问本地环回门户，不提交真实预约）。"""
import json
import sys

from .capture import read_catalog
from .observe import observe_portal
from .records import save_slot_observations
from .review import build_difference_list, summarize_differences

DEFAULT_ORIGIN = 'http://127.0.0.1:8765/'

_STATUS_LABELS = {
    'available': '可预约',
    'temporary_hold': '临时占位',
    'unobserved': '未观察（非售罄）',
    'awaiting_confirmation': '等待确认',
    'party_exceeds_capacity': '人数超出名额',
}


def _label(status):
    return _STATUS_LABELS.get(status, status)


def _print_catalog(origin):
    print(json.dumps(read_catalog(origin), ensure_ascii=False, indent=2))


def _print_observation(origin, database=None):
    catalog, rows = observe_portal(origin)
    differences = build_difference_list(rows)
    summary = summarize_differences(differences)
    if database is not None:
        save_slot_observations(database, rows)
        print(f'观察收据已追加：{database}（{len(rows)} 行）\n')
    print(f'目录项目 {len(catalog)} 个，观察行 {len(rows)} 条，'
          f'仅 GET 浏览，未提交任何预约。\n')
    for entry in differences:
        flag = '差异' if entry['is_difference'] else '一致'
        reasons = ('，原因：' + '、'.join(entry['difference_reasons'])) \
            if entry['is_difference'] else ''
        print(
            f"[{flag}] {entry['item_id']} {entry['business_key']} "
            f"（{entry['phase']}）档期={_label(entry['slot_status'])} "
            f"预览={_label(entry['preview_status'])}{reasons}")
        print(f"    溯源 {entry['observation_id']} {entry['source']} "
              f"档期原文={entry['slot_raw_text']!r} "
              f"预览原文={entry['preview_raw_text']!r}")
    print('\n汇总：')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'observe':
        database = argv[1] if len(argv) > 1 else None
        _print_observation(DEFAULT_ORIGIN, database)
    else:
        _print_catalog(DEFAULT_ORIGIN)


if __name__ == '__main__':
    main()
