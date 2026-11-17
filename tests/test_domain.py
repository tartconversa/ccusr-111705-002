import unittest
from app.site import DATA
from app.domain import (
    interpret_card,
    parse_slot_text,
    parse_preview_text,
    is_bookable_preview,
    SLOT_AVAILABLE,
    SLOT_TEMPORARY_HOLD,
    PREVIEW_AWAITING_CONFIRMATION,
    PREVIEW_PARTY_EXCEEDS,
    PREVIEW_TEMPORARY_HOLD,
)


class DomainCardTest(unittest.TestCase):
    def test_catalog_fact_keeps_business_condition(self):
        item = DATA['items'][0]
        fact = interpret_card(item)
        self.assertEqual(fact['identity'], item['id'])
        self.assertEqual(fact['condition'], item['choices'][0])
        self.assertEqual(fact['kind'], 'trial')

    def test_malformed_card_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            interpret_card({'id':'unknown','summary':'incomplete'})


class SlotTextParsingTest(unittest.TestCase):
    def test_available_slot_text_is_parsed_with_identity(self):
        parsed = parse_slot_text('周六：余 4 位')
        self.assertEqual(parsed, {'status': SLOT_AVAILABLE,
                                  'date': '周六', 'places': 4})

    def test_held_slot_text_is_not_mistaken_for_sold_out(self):
        parsed = parse_slot_text('周日：占位中')
        self.assertEqual(parsed['status'], SLOT_TEMPORARY_HOLD)
        self.assertIsNone(parsed['places'])

    def test_skeleton_and_empty_text_means_unobserved_not_sold_out(self):
        for text in ('', '加载中', '   ', None):
            with self.subTest(text=text):
                self.assertIsNone(parse_slot_text(text))

    def test_unrecognized_real_text_raises_instead_of_sold_out(self):
        with self.assertRaises(ValueError):
            parse_slot_text('系统维护中')


class PreviewTextParsingTest(unittest.TestCase):
    def test_three_final_preview_states_are_classified(self):
        cases = {
            '周六 / 1 人：等待确认': PREVIEW_AWAITING_CONFIRMATION,
            '周日 / 4 人：人数超出名额': PREVIEW_PARTY_EXCEEDS,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_preview_text(text)['status'], expected)

    def test_hold_preview_keeps_date_identity(self):
        parsed = parse_preview_text('周六：临时占位')
        self.assertEqual(parsed['status'], PREVIEW_TEMPORARY_HOLD)
        self.assertEqual(parsed['date'], '周六')

    def test_preview_skeleton_is_unobserved(self):
        for text in ('', '占位核对中', None):
            with self.subTest(text=text):
                self.assertIsNone(parse_preview_text(text))

    def test_bookable_judgement_is_strict(self):
        self.assertTrue(is_bookable_preview(PREVIEW_AWAITING_CONFIRMATION))
        self.assertFalse(is_bookable_preview(PREVIEW_TEMPORARY_HOLD))
        self.assertFalse(is_bookable_preview(PREVIEW_PARTY_EXCEEDS))
        self.assertFalse(is_bookable_preview('unobserved'))

    def test_unrecognized_preview_text_raises(self):
        with self.assertRaises(ValueError):
            parse_preview_text('周六 / 2 人：未知结论')


if __name__ == '__main__':
    unittest.main()
