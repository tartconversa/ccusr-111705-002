"""档期观察：只走公开浏览与预览，绝不提交真实预约。

流程对应接待员的人工核对：目录卡片 -> 项目详情 -> 日期选择 ->
档期候选 -> 选择人数 -> 占位预览，并可复现“模拟临时占位”步骤，
把候选档期与最终预览状态关联成可追溯的观察行。

关键纪律：
- 加载骨架（加载中/占位核对中）和空文本一律视为“未观察”，从不推断为售罄；
- 日期切换会复用同名档期元素，读取时校验渲染结果中的日期身份；
- 每个项目使用独立的浏览器上下文（独立会话/cookie/存储），互不串用；
- 只允许环回来源，并登记全部请求，任何非 GET 的提交式请求直接中止报错。
"""
import time
import uuid
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from .domain import (
    interpret_card,
    interpret_entry,
    parse_slot_text,
    parse_preview_text,
    SLOT_UNOBSERVED,
    PREVIEW_UNOBSERVED,
)

RENDER_TIMEOUT_MS = 4000
POLL_INTERVAL_S = 0.02


def ensure_loopback_origin(origin):
    parts = urlsplit(origin)
    if parts.hostname not in ('127.0.0.1', 'localhost') or parts.scheme != 'http':
        raise ValueError('只允许本地演练来源')
    return origin


def wait_for_rendered(read_text, parse, timeout_ms=RENDER_TIMEOUT_MS):
    """轮询等待分步内容渲染完成。

    骨架/空文本由 parse 返回 None，继续等待；出现无法识别的真实文本则
    抛错而不是静默当作售罄；超时返回 (None, 最后一次原文)，由调用方
    记为“未观察”。
    """
    deadline = time.monotonic() + timeout_ms / 1000
    raw = ''
    while time.monotonic() <= deadline:
        raw = read_text()
        parsed = parse(raw)
        if parsed is not None:
            return parsed, raw
        time.sleep(POLL_INTERVAL_S)
    return None, raw


def open_detail_from_catalog(page, origin, item_id):
    """从目录卡片进入详情。

    返回列表可能保留上次筛选导致目标卡片不在文档里；重新导航目录
    （重新加载而非沿用保留的筛选视图），仍找不到才报错。
    """
    page.goto(origin, wait_until='domcontentloaded')
    card = page.locator(f'.card[data-key="{item_id}"]')
    if card.count() != 1:
        page.goto(origin, wait_until='domcontentloaded')
        card = page.locator(f'.card[data-key="{item_id}"]')
    if card.count() != 1:
        raise ValueError(f'目录中项目身份不唯一或已被筛选隐藏: {item_id}')
    summary = card.locator('p').inner_text()
    card.locator('a').click()
    page.wait_for_selector('main[data-key]')
    if page.locator('main').get_attribute('data-key') != item_id:
        raise ValueError('详情页身份与目录卡片不一致')
    return page.url, summary


def _options(locator):
    return locator.locator('option').evaluate_all(
        '(nodes) => nodes.map((n) => n.value)')


def _row(item_id, catalog_fact, source, date, party_size, slot, preview,
         phase, slot_raw, preview_raw, requests):
    """构造一条观察行；slot/preview 为 None 时记“未观察”而非售罄。"""
    signal = {'project': item_id, 'date': date, 'party_size': party_size}
    entry = interpret_entry(catalog_fact, signal)
    return {
        'observation_id': uuid.uuid4().hex,
        'item_id': item_id,
        'source': source,
        'phase': phase,
        'business_key': entry['business_key'],
        'date': date,
        'party_size': party_size,
        'slot_status': slot['status'] if slot else SLOT_UNOBSERVED,
        'slot_places': slot['places'] if slot else None,
        'slot_raw_text': slot_raw,
        'preview_status': preview['status'] if preview else PREVIEW_UNOBSERVED,
        'preview_raw_text': preview_raw,
        'catalog_fact': catalog_fact,
        'observed_requests': list(requests),
    }


def _observe_in_context(page, origin, item_id):
    """在单个项目专属上下文里完成完整观察；调用方负责上下文隔离。"""
    requests_seen = []
    violations = []

    def on_request(request):
        requests_seen.append({'method': request.method, 'url': request.url})
        if request.method.upper() != 'GET':
            violations.append(
                f'观察流程出现提交式请求，已中止: {request.method} {request.url}')

    page.on('request', on_request)

    source, card_summary = open_detail_from_catalog(page, origin, item_id)
    catalog_fact = interpret_card({'id': item_id, 'summary': card_summary})

    date_select = page.locator('#date')
    party_select = page.locator('#party-size')
    slot_text = page.locator('#slot-text')
    preview_box = page.locator('#hold-preview')
    dates = _options(date_select)
    party_sizes = [int(value) for value in _options(party_select)]

    rows = []

    def select_date_expecting(date_value):
        # 同名档期元素跨日期复用：先切日期，再等到渲染结果带本日期身份，
        # 杜绝读到上一个日期残留的“余 N 位”。
        date_select.select_option(date_value)
        slot, raw = wait_for_rendered(
            lambda: slot_text.inner_text(), parse_slot_text)
        if slot is not None and slot['date'] != date_value:
            raise ValueError(
                f'档期元素仍显示旧日期 {slot["date"]}，期望 {date_value}')
        return slot, raw

    # 第一轮：不触发临时占位，观察自然档期与各人数的预览结论
    for date in dates:
        slot, slot_raw = select_date_expecting(date)
        for size in party_sizes:
            party_select.select_option(str(size))
            page.locator('#preview').click()
            preview, preview_raw = wait_for_rendered(
                lambda: preview_box.inner_text(), parse_preview_text)
            if preview is not None and preview.get('date') not in (date, None):
                raise ValueError('预览日期与当前所选日期不一致')
            rows.append(_row(item_id, catalog_fact, source, date, size,
                             slot, preview, 'candidate', slot_raw,
                             preview_raw, requests_seen))

    # 第二轮：复现“模拟临时占位”步骤，定位可预约 -> 不可预约由哪一步造成
    for date in dates:
        slot, slot_raw = select_date_expecting(date)
        page.locator('#hold').click()
        held_slot, held_raw = wait_for_rendered(
            lambda: slot_text.inner_text(), parse_slot_text)
        for size in party_sizes:
            party_select.select_option(str(size))
            page.locator('#preview').click()
            preview, preview_raw = wait_for_rendered(
                lambda: preview_box.inner_text(), parse_preview_text)
            rows.append(_row(item_id, catalog_fact, source, date, size,
                             held_slot or slot, preview, 'after_hold',
                             held_raw, preview_raw, requests_seen))

    if violations:
        raise ValueError('; '.join(violations))
    return rows


def observe_project(origin, item_id):
    """观察单个项目：独立浏览器、独立上下文，会话不与任何项目共享。"""
    ensure_loopback_origin(origin)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            try:
                page = context.new_page()
                return _observe_in_context(page, origin, item_id)
            finally:
                context.close()
        finally:
            browser.close()


def observe_portal(origin):
    """观察目录里的全部项目。

    每个项目在同一浏览器进程内拿到全新且用后即关的上下文，cookie、
    localStorage 等会话存储完全隔离，并行项目不会互用浏览器会话。
    返回 (catalog_items, rows)。
    """
    ensure_loopback_origin(origin)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            catalog = _read_catalog(browser, origin)
            rows = []
            for item in catalog:
                context = browser.new_context()
                try:
                    page = context.new_page()
                    rows.extend(
                        _observe_in_context(page, origin, item['id']))
                finally:
                    context.close()
            return catalog, rows
        finally:
            browser.close()


def _read_catalog(browser, origin):
    context = browser.new_context()
    try:
        page = context.new_page()
        page.goto(origin, wait_until='domcontentloaded')
        if not page.locator('main').count():
            raise ValueError('来源目录未加载')
        return page.locator('.card').evaluate_all(
            '(nodes) => nodes.map((n) => ({'
            'id: n.dataset.key, '
            'name: n.querySelector("h2").textContent, '
            'summary: n.querySelector("p").textContent, '
            'href: n.querySelector("a").getAttribute("href")}))')
    finally:
        context.close()
