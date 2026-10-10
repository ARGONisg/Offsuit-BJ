"""
Verification tests for strategy engine and OCR detector.
"""

import unittest
from strategy import Action, Card, get_action
from ocr_detector import OcrDetector


class TestStrategy(unittest.TestCase):
    def test_hard_totals(self):
        # 17 vs 10 -> STAND
        self.assertEqual(get_action(False, 17, Card.TEN), Action.STAND)
        # 16 vs 10 -> HIT
        self.assertEqual(get_action(False, 16, Card.TEN), Action.HIT)
        # 16 vs 6 -> STAND
        self.assertEqual(get_action(False, 16, Card.SIX), Action.STAND)
        # 11 vs 5 -> DOUBLE
        self.assertEqual(get_action(False, 11, Card.FIVE, can_double=True), Action.DOUBLE_DOWN)
        # 11 vs 5 (no double) -> HIT
        self.assertEqual(get_action(False, 11, Card.FIVE, can_double=False), Action.HIT)

    def test_soft_totals(self):
        # Soft 17 (7/17) vs 10 -> HIT
        self.assertEqual(get_action(True, 17, Card.TEN), Action.HIT)
        # Soft 18 vs 6 -> DOUBLE
        self.assertEqual(get_action(True, 18, Card.SIX, can_double=True), Action.DOUBLE_DOWN)
        # Soft 18 vs 6 (no double) -> STAND
        self.assertEqual(get_action(True, 18, Card.SIX, can_double=False), Action.STAND)
        # Soft 18 vs 10 -> HIT
        self.assertEqual(get_action(True, 18, Card.TEN), Action.HIT)

    def test_five_card_charlie(self):
        # 5 cards with 18 -> STAND (Auto win)
        self.assertEqual(get_action(False, 18, Card.TEN, card_count=5), Action.STAND)
        # 4 cards with 10 -> HIT (Safe pursuit)
        self.assertEqual(get_action(False, 10, Card.TEN, card_count=4), Action.HIT)

    def test_pairs_and_no_resplit(self):
        # Aces vs 10 -> SPLIT
        self.assertEqual(get_action(True, 12, Card.TEN, is_pair=True, pair_val=11, can_split=True), Action.SPLIT)
        # Aces vs 10 when already split (no resplit rule) -> Soft 12 -> HIT
        self.assertEqual(get_action(True, 12, Card.TEN, is_pair=True, pair_val=11, can_split=True, has_split_already=True), Action.HIT)


class TestOcr(unittest.TestCase):
    def test_sample_screenshots(self):
        detector = OcrDetector()

        # Play screen
        play_img = "/Users/parth/.gemini/antigravity/brain/062cfa4b-f325-45ba-a7d5-4deb3d49b768/.user_uploaded/media_1788872421307.png"
        state = detector.detect(play_img)
        print(f"\n[Test OCR Play Screen] Phase: {state.phase}, Dealer: {state.dealer_card}, Total: {state.player_total}, Soft: {state.is_soft}")
        self.assertEqual(state.phase, "PLAYING")
        self.assertEqual(state.dealer_card, Card.TEN)
        self.assertEqual(state.player_total, 17)
        self.assertTrue(state.is_soft)

        # Bet screen
        bet_img = "/Users/parth/.gemini/antigravity/brain/062cfa4b-f325-45ba-a7d5-4deb3d49b768/.user_uploaded/media_1788872404757.png"
        state_bet = detector.detect(bet_img)
        print(f"[Test OCR Bet Screen] Phase: {state_bet.phase}")
        self.assertEqual(state_bet.phase, "BETTING")


if __name__ == "__main__":
    unittest.main()
