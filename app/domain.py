"""机器人体验预约的跨页占位观察：目录卡片既有数据约定。"""
import re

# 档期候选状态
SLOT_AVAILABLE = 'available'
SLOT_TEMPORARY_HOLD = 'temporary_hold'
SLOT_UNOBSERVED = 'unobserved'

# 预约预览最终状态
PREVIEW_AWAITING_CONFIRMATION = 'awaiting_confirmation'
PREVIEW_PARTY_EXCEEDS = 'party_exceeds_capacity'
PREVIEW_TEMPORARY_HOLD = 'temporary_hold'
PREVIEW_UNOBSERVED = 'unobserved'

_PREVIEW_STATUS_TEXT = {
    '等待确认': PREVIEW_AWAITING_CONFIRMATION,
    '人数超出名额': PREVIEW_PARTY_EXCEEDS,
    '临时占位': PREVIEW_TEMPORARY_HOLD,
}

# 渲染未完成时的占位/骨架文本：不是业务结论，更不是售罄
SLOT_PENDING_TEXTS = ('', '加载中')
PREVIEW_PENDING_TEXTS = ('', '占位核对中')


def interpret_card(item):
    parts = item['summary'].split(' · ', 1)
    if len(parts) != 2:
        raise ValueError('卡片摘要格式无效')
    condition, observation = parts
    found = re.fullmatch(r"余 (?P<amount>\d+) 位", observation)
    if not found:
        raise ValueError('卡片状态未识别')
    amount = found.group('amount')
    return {'kind': 'trial', 'identity': item['id'], 'condition': condition, 'capacity_text': observation, 'places': int(amount) if amount.isdigit() else amount}

def interpret_entry(catalog_fact, signal):
    if signal['project'] != catalog_fact['identity'] or signal['party_size'] < 1:
        raise ValueError('booking project or party mismatch')
    return {'business_key': f"{signal['project']}:{signal['date']}:{signal['party_size']}", 'date': signal['date'], 'party_size': signal['party_size']}


def parse_slot_text(text):
    """解析档期行文本。骨架/空文本返回 None，避免把未渲染误判为售罄。

    形如“周六：余 4 位” -> {'status': 'available', 'date': '周六', 'places': 4}
    形如“周日：占位中” -> {'status': 'temporary_hold', 'date': '周日', 'places': None}
    """
    if text is None or text.strip() in SLOT_PENDING_TEXTS:
        return None
    available = re.fullmatch(r"(?P<date>[^：:]+)[：:]余 (?P<amount>\d+) 位", text.strip())
    if available:
        return {'status': SLOT_AVAILABLE, 'date': available.group('date'),
                'places': int(available.group('amount'))}
    held = re.fullmatch(r"(?P<date>[^：:]+)[：:]占位中", text.strip())
    if held:
        return {'status': SLOT_TEMPORARY_HOLD, 'date': held.group('date'), 'places': None}
    raise ValueError(f'档期文本未识别: {text!r}')


def parse_preview_text(text):
    """解析预约预览文本。骨架/空文本返回 None（未渲染不等于不可预约）。

    形如“周六 / 4 人：等待确认” -> {'status': ..., 'date': '周六', 'party_size': 4}
    形如“周六：临时占位”      -> {'status': 'temporary_hold', ...}
    """
    if text is None or text.strip() in PREVIEW_PENDING_TEXTS:
        return None
    bound = re.fullmatch(r"(?P<date>[^：:]+) / (?P<size>\d+) 人[：:](?P<state>.+)", text.strip())
    if bound:
        state = bound.group('state').strip()
        if state not in _PREVIEW_STATUS_TEXT:
            raise ValueError(f'预览状态未识别: {text!r}')
        return {'status': _PREVIEW_STATUS_TEXT[state], 'date': bound.group('date'),
                'party_size': int(bound.group('size'))}
    held = re.fullmatch(r"(?P<date>[^：:]+)[：:]临时占位", text.strip())
    if held:
        return {'status': PREVIEW_TEMPORARY_HOLD, 'date': held.group('date'),
                'party_size': None}
    raise ValueError(f'预览文本未识别: {text!r}')


def is_bookable_preview(status):
    """只有“等待确认”表示仍可预约；占位、超员、未观察都不是可预约结论。"""
    return status == PREVIEW_AWAITING_CONFIRMATION

