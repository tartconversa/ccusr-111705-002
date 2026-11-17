import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from test_browser import BrowserBaselineTest
from app.site import DATA
from app.observe import (
    observe_project,
    observe_portal,
    open_detail_from_catalog,
    wait_for_rendered,
    ensure_loopback_origin,
)
from app.domain import parse_slot_text, SLOT_AVAILABLE, SLOT_TEMPORARY_HOLD, SLOT_UNOBSERVED
from app.domain import (
    PREVIEW_AWAITING_CONFIRMATION,
    PREVIEW_PARTY_EXCEEDS,
    PREVIEW_TEMPORARY_HOLD,
    PREVIEW_UNOBSERVED,
)
from app.records import save_slot_observations, read_slot_observations
from app.review import build_difference_list, summarize_differences


class RenderWaitingTest(unittest.TestCase):
    def test_skeleton_then_real_text_resolves_to_observed_slot(self):
        queue = ['加载中', '周六：余 4 位']
        def read():
            return queue[0] if len(queue) == 1 else queue.pop(0)
        parsed, raw = wait_for_rendered(read, parse_slot_text, timeout_ms=2000)
        self.assertEqual(parsed['status'], SLOT_AVAILABLE)
        self.assertEqual(parsed['places'], 4)
        self.assertEqual(raw, '周六：余 4 位')

    def test_permanent_skeleton_is_unobserved_never_sold_out(self):
        parsed, raw = wait_for_rendered(
            lambda: '加载中', parse_slot_text, timeout_ms=60)
        self.assertIsNone(parsed)
        self.assertEqual(raw, '加载中')

    def test_unrecognized_real_text_raises_not_guessed(self):
        with self.assertRaises(ValueError):
            wait_for_rendered(lambda: '系统维护中', parse_slot_text,
                              timeout_ms=500)


class StaleFilterRecoveryTest(BrowserBaselineTest):
    def test_detail_opens_after_reload_when_list_filter_hides_card(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                calls = {'n': 0}

                def handle(route):
                    calls['n'] += 1
                    if calls['n'] == 1:
                        # 模拟返回列表保留上次筛选：目标卡片不在文档中
                        route.fulfill(
                            status=200,
                            content_type='text/html; charset=utf-8',
                            body='<!doctype html><html lang="zh">'
                                 '<main>筛选后的空列表</main></html>')
                    else:
                        route.continue_()

                page.route(self.origin + '**', handle)
                item_id = DATA['items'][0]['id']
                url, summary = open_detail_from_catalog(
                    page, self.origin, item_id)
                self.assertIn('detail', url)
                self.assertIn(item_id, url)
                self.assertIn('余', summary)
                self.assertGreaterEqual(calls['n'], 2)
            finally:
                browser.close()


class SlotObservationBrowserTest(BrowserBaselineTest):
    def _map_rows(self, rows):
        return {(r['item_id'], r['phase'], r['date'], r['party_size']): r
                for r in rows}

    def test_candidate_slots_linked_to_final_preview_status(self):
        item_id = DATA['items'][0]['id']  # robot-art：周六 4 / 周日 2
        rows = observe_project(self.origin, item_id)
        mapped = self._map_rows(rows)

        # 两个日期 x 两个人数 x 两个阶段，一条不缺
        self.assertEqual(len(rows), 2 * 2 * 2)
        self.assertEqual(len({r['observation_id'] for r in rows}), len(rows))

        saturday_one = mapped[(item_id, 'candidate', '周六', 1)]
        self.assertEqual(saturday_one['slot_status'], SLOT_AVAILABLE)
        self.assertEqual(saturday_one['slot_places'], 4)
        self.assertEqual(saturday_one['preview_status'],
                         PREVIEW_AWAITING_CONFIRMATION)
        self.assertEqual(saturday_one['slot_raw_text'], '周六：余 4 位')

        # 人数 4 在周日（余 2）超出名额
        sunday_four = mapped[(item_id, 'candidate', '周日', 4)]
        self.assertEqual(sunday_four['slot_status'], SLOT_AVAILABLE)
        self.assertEqual(sunday_four['preview_status'],
                         PREVIEW_PARTY_EXCEEDS)

        # 骨架渲染成功时不应出现“未观察”，且任何地方都不存在售罄结论
        self.assertTrue(all(r['slot_status'] != SLOT_UNOBSERVED for r in rows))
        self.assertTrue(all(r['preview_status'] != PREVIEW_UNOBSERVED
                            for r in rows))
        serialized = json.dumps(rows, ensure_ascii=False)
        self.assertNotIn('sold_out', serialized)
        self.assertNotIn('售罄', serialized)

    def test_hold_step_is_what_flips_slot_to_unavailable(self):
        item_id = DATA['items'][0]['id']
        rows = observe_project(self.origin, item_id)
        mapped = self._map_rows(rows)

        before = mapped[(item_id, 'candidate', '周六', 1)]
        after = mapped[(item_id, 'after_hold', '周六', 1)]
        self.assertEqual(before['slot_status'], SLOT_AVAILABLE)
        self.assertEqual(before['preview_status'],
                         PREVIEW_AWAITING_CONFIRMATION)
        # 同档期、同人数，仅因占位步骤翻转，差异可追溯到具体阶段
        self.assertEqual(after['slot_status'], SLOT_TEMPORARY_HOLD)
        self.assertEqual(after['preview_status'], PREVIEW_TEMPORARY_HOLD)
        self.assertIn('占位', after['slot_raw_text'])

        # 所有候选阶段都不应被占位污染
        self.assertTrue(all(r['slot_status'] == SLOT_AVAILABLE
                            for r in rows if r['phase'] == 'candidate'))

    def test_reused_slot_element_keeps_date_identity_after_switch(self):
        item_id = DATA['items'][0]['id']
        rows = observe_project(self.origin, item_id)
        for row in rows:
            # 同名元素复用后，档期原文必须属于当前所选日期
            self.assertTrue(row['slot_raw_text'].startswith(row['date']))

    def test_observation_never_sends_submitting_requests(self):
        item_id = DATA['items'][1]['id']
        rows = observe_project(self.origin, item_id)
        for row in rows:
            self.assertTrue(row['observed_requests'])
            methods = {req['method'] for req in row['observed_requests']}
            self.assertEqual(methods, {'GET'})
            for req in row['observed_requests']:
                if 'detail' in req['url']:
                    self.assertIn(item_id, req['url'])

    def test_each_project_uses_isolated_browser_session(self):
        catalog, rows = observe_portal(self.origin)
        self.assertEqual({c['id'] for c in catalog},
                         {item['id'] for item in DATA['items']})
        mapped = self._map_rows(rows)

        # robot-care 容量 周六 2 / 周日 1：周日 4 人必然超员；
        # 若与 robot-art（周日余 2）串用会话/状态，这里会得出错误结论
        care = mapped[('robot-care', 'candidate', '周日', 4)]
        self.assertEqual(care['preview_status'], PREVIEW_PARTY_EXCEEDS)
        care_ok = mapped[('robot-care', 'candidate', '周六', 1)]
        self.assertEqual(care_ok['preview_status'],
                         PREVIEW_AWAITING_CONFIRMATION)

        art = mapped[('robot-art', 'candidate', '周六', 4)]
        self.assertEqual(art['preview_status'],
                         PREVIEW_AWAITING_CONFIRMATION)

        # 每行请求轨迹只触碰本项目详情，不跨项目
        for row in rows:
            for req in row['observed_requests']:
                if 'detail' in req['url']:
                    self.assertIn(row['item_id'], req['url'])

    def test_origin_restricted_to_loopback(self):
        with self.assertRaises(ValueError):
            ensure_loopback_origin('https://example.com/')
        with self.assertRaises(ValueError):
            observe_project('http://example.com/', DATA['items'][0]['id'])


class ObservationReceiptAndDiffTest(BrowserBaselineTest):
    def test_observation_receipt_is_append_only_and_diff_is_traceable(self):
        rows = observe_project(self.origin, DATA['items'][0]['id'])
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'observations.sqlite3'
            self.assertEqual(save_slot_observations(database, rows), len(rows))
            save_slot_observations(database, rows[:2])
            with sqlite3.connect(database) as db:
                total = db.execute(
                    'SELECT count(*) FROM slot_observations').fetchone()[0]
            self.assertEqual(total, len(rows) + 2)

            loaded = read_slot_observations(database)
            differences = build_difference_list(loaded)
            self.assertEqual(len(differences), len(loaded))

            by_key = {(d['phase'], d['date'], d['party_size']): d
                      for d in differences}
            consistent = by_key[('candidate', '周六', 1)]
            self.assertFalse(consistent['is_difference'])
            self.assertEqual(consistent['difference_reasons'], [])

            oversize = by_key[('candidate', '周日', 4)]
            self.assertTrue(oversize['is_difference'])
            self.assertIn('party_exceeds_capacity',
                          oversize['difference_reasons'])

            held = by_key[('after_hold', '周六', 1)]
            self.assertIn('temporary_hold_blocks_preview',
                          held['difference_reasons'])

            # 可追溯字段齐全，且未观察绝不写成售罄
            for entry in differences:
                for field in ('observation_id', 'business_key', 'source',
                              'slot_raw_text', 'preview_raw_text',
                              'observed_requests', 'difference_reasons'):
                    self.assertIn(field, entry)
                self.assertNotIn('sold_out', entry['slot_status'])
                self.assertIn('detail', entry['source'])

            summary = summarize_differences(differences)
            self.assertEqual(summary[DATA['items'][0]['id']]['candidates'],
                             len(loaded))

    def test_unobserved_rows_are_flagged_not_counted_as_sold_out(self):
        # 直接构造一条骨架失败的观察行，验证差异清单如实标记
        good = observe_project(self.origin, DATA['items'][0]['id'])
        broken = dict(good[0])
        broken['observation_id'] = 'broken-skeleton-row'
        broken['slot_status'] = SLOT_UNOBSERVED
        broken['slot_places'] = None
        broken['slot_raw_text'] = '加载中'
        broken['preview_status'] = PREVIEW_UNOBSERVED
        broken['preview_raw_text'] = '占位核对中'
        differences = build_difference_list([broken])
        entry = differences[0]
        self.assertTrue(entry['is_difference'])
        self.assertIn('slot_unobserved', entry['difference_reasons'])
        self.assertIn('preview_unobserved', entry['difference_reasons'])
        self.assertNotIn('sold_out', json.dumps(entry, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
