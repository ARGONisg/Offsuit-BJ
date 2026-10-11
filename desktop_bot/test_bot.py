import os
import sys
import unittest

# Ensure desktop_bot package is on sys.path regardless of execution CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy import Action, Card, get_action
from ocr_detector import OcrDetector
from tracker import BankrollTracker


class TestTracker(unittest.TestCase):
    def test_bankroll_tracker_outcomes(self):
        tracker = BankrollTracker()
        
        # First reading: initializes baseline
        res1 = tracker.update(1000)
        self.assertIsNone(res1)
        self.assertEqual(tracker.start_bankroll, 1000)
        self.assertEqual(tracker.hands_played, 0)

        # Hand 1: +100 -> WIN
        res2 = tracker.update(1100)
        self.assertIsNotNone(res2)
        self.assertEqual(res2["outcome"], "WIN")
        self.assertEqual(res2["delta"], 100)
        self.assertEqual(tracker.wins, 1)
        self.assertEqual(tracker.losses, 0)
        self.assertEqual(tracker.net_profit, 100)
        self.assertEqual(tracker.win_rate, 100.0)

        # Hand 2: -50 -> LOSS
        res3 = tracker.update(1050)
        self.assertIsNotNone(res3)
        self.assertEqual(res3["outcome"], "LOSS")
        self.assertEqual(res3["delta"], -50)
        self.assertEqual(tracker.wins, 1)
        self.assertEqual(tracker.losses, 1)
        self.assertEqual(tracker.net_profit, 50)
        self.assertEqual(tracker.win_rate, 50.0)

        # Hand 3: Push
        tracker.record_push(1050)
        self.assertEqual(tracker.pushes, 1)
        self.assertEqual(tracker.hands_played, 3)
        self.assertEqual(tracker.win_rate, 50.0)

        summary = tracker.format_summary()
        self.assertIn("SESSION STATS", summary)
        self.assertIn("W: 1 | L: 1 | P: 1", summary)
        self.assertIn("+50 chips", summary)


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
    def test_bankroll_ocr(self):
        sample1 = "desktop_bot/Split6.png"
        sample2 = "desktop_bot/After Split 5.png"
        if not os.path.exists(sample1) or not os.path.exists(sample2):
            self.skipTest("Sample split screenshots not present on disk.")
        detector = OcrDetector()
        chips1 = detector.read_bankroll(sample1)
        self.assertEqual(chips1, 22345)
        chips2 = detector.read_bankroll(sample2)
        self.assertEqual(chips2, 23393)

    def test_sample_screenshots(self):
        sample = "desktop_bot/Split6.png"
        if not os.path.exists(sample):
            self.skipTest(f"{sample} not present on disk.")
        detector = OcrDetector()
        state = detector.detect(sample)
        self.assertEqual(state.phase, "PLAYING")
        self.assertEqual(state.dealer_card, Card.TWO)
        self.assertEqual(state.player_total, 12)
        self.assertFalse(state.is_soft)
        self.assertTrue(state.can_split)

    def test_error_screenshots_button_detection(self):
        import glob
        detector = OcrDetector()
        error_shots = sorted(glob.glob("desktop_bot/work/error_screenshots/*.png"))
        if not error_shots:
            self.skipTest("No error screenshots found to test.")
        for shot in error_shots:
            state = detector.detect(shot)
            self.assertEqual(state.phase, "PLAYING")
            self.assertIn("HIT", state.available_buttons, f"HIT missing in {shot}")
            self.assertIn("STAND", state.available_buttons, f"STAND missing in {shot}")


if __name__ == "__main__":
    unittest.main()
