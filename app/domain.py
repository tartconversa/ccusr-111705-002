"""机器人体验预约的跨页占位观察：目录卡片既有数据约定。"""
import re

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
