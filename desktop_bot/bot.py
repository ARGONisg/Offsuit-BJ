#!/usr/bin/env python3
"""
Blackjack Automation Bot (Desktop ADB + Tesseract OCR).
Executes basic 8-deck strategy, 5-card charlie, and auto-play
over ADB for Offsuit Blackjack game.
"""

import argparse
import os
import shutil
import sys
import time
from adb_controller import AdbController
from logger import BotLogger
from ocr_detector import OcrDetector, GameState
from strategy import Action, Card, get_action
from tracker import BankrollTracker

# Terminal color formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


class ErrorScreenshotTracker:
    """
    Tracks repeated terminal messages and saves a debug screenshot
    when any single message repeats more than `threshold` times in a row.
    """

    def __init__(self, screen_png_src: str, save_dir: str, threshold: int = 5):
        self.screen_png_src = screen_png_src  # Live screenshot path to copy
        self.save_dir = save_dir              # Where to persist error screenshots
        self.threshold = threshold
        self._last_msg: str = ""
        self._count: int = 0
        os.makedirs(self.save_dir, exist_ok=True)

    def check(self, message: str):
        """Call after every print() in the main loop with the same string.
        Saves a screenshot if the message has repeated > threshold times."""
        if message == self._last_msg:
            self._count += 1
        else:
            self._last_msg = message
            self._count = 1

        if self._count == self.threshold + 1:  # Trigger exactly once at threshold+1
            self._save_screenshot(message)

    def _save_screenshot(self, message: str):
        if not os.path.exists(self.screen_png_src):
            print(f"{RED}[ErrorTracker] No screenshot to save (source missing).{RESET}")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        # Sanitise message for a filename (keep alphanumeric + spaces, truncate)
        safe_msg = "".join(c if c.isalnum() or c in " _-" else "_" for c in message[:60]).strip()
        dest = os.path.join(self.save_dir, f"error_{ts}_{safe_msg}.png")
        shutil.copy2(self.screen_png_src, dest)
        print(
            f"{RED}[ErrorTracker] ⚠️  Message repeated {self._count}x — "
            f"debug screenshot saved:\n  {dest}{RESET}"
        )


class BlackjackBot:
    def __init__(self, adb_path: str = None, tesseract_path: str = None, log_dir: str = None):
        self.logger = BotLogger(log_dir)
        self.logger.start()
        self.tracker = BankrollTracker(bet_size=10)
        self.adb = AdbController(adb_path)
        work_dir = os.path.join(os.path.dirname(__file__), "work")
        self.detector = OcrDetector(tesseract_path, work_dir=work_dir)
        self.screen_png = os.path.join(work_dir, "screen.png")
        self.last_action_time = 0.0
        self.action_cooldown = 1.2  # Seconds to wait after an action for animation
        self.active_hand_index = 0  # Which split hand to play next
        self.advance_hand = False   # Move to next split hand after STAND/DOUBLE
        self.hand_pending_resolution = False  # Set when terminal action ends player turn
        self.last_hand_signature = None       # (dealer_card, is_soft, player_total)
        self.last_action_was_double = False   # Helps tracker distinguish Double Win from 2x Win
        self._bankroll_recorded_this_hand = False  # Set True after PLAYING-phase bankroll read
        error_shots_dir = os.path.join(work_dir, "error_screenshots")
        self.error_tracker = ErrorScreenshotTracker(
            screen_png_src=self.screen_png,
            save_dir=error_shots_dir,
            threshold=5,
        )

    def calibrate(self, sample_image: str = None):
        print(f"\n{BOLD}{CYAN}=== RUNNING COORDINATE CALIBRATION ==={RESET}")
        
        if sample_image and os.path.exists(sample_image):
            img_path = sample_image
            print(f"Using provided image: {img_path}")
            width, height = 461, 1024
        else:
            if not self.adb.is_connected():
                print(f"{RED}[Error] No Android device detected via ADB!{RESET}")
                print("Make sure USB debugging is enabled on your phone and device is connected.")
                return
            width, height = self.adb.get_screen_size()
            print(f"Device connected. Physical resolution: {BOLD}{width}x{height}{RESET}")
            print("Capturing live screenshot...")
            self.adb.capture_screenshot(self.screen_png)
            img_path = self.screen_png

        print("\nExtracting regions and running OCR...")
        state = self.detector.detect(img_path)
        if not state.bankroll:
            state.bankroll = self.detector.read_bankroll(img_path)

        print(f"\n{BOLD}Detection Results:{RESET}")
        print(f"  Phase:        {GREEN if state.phase == 'PLAYING' else YELLOW}{state.phase}{RESET}")
        print(f"  Dealer Card:  {BOLD}{state.dealer_card.name if state.dealer_card else 'None'}{RESET} (raw: '{state.raw_dealer_text}')")
        hand_type = "Soft" if state.is_soft else "Hard"
        print(f"  Player Total: {BOLD}{state.player_total} ({hand_type}){RESET} (raw: '{state.raw_player_text}')")
        print(f"  Player Hands: {state.player_hands}")
        print(f"  Buttons Text: '{state.raw_buttons_text}'")
        print(f"  Avail Btns:   {sorted(state.available_buttons.keys()) if state.available_buttons else []}")
        print(f"  Can Double:   {state.can_double}")
        print(f"  Can Split:    {state.can_split}")
        print(f"  Bankroll:     {state.bankroll if state.bankroll else 'None'}")

        print(f"\n{GREEN}Calibration files saved to {self.detector.work_dir}/{RESET}\n")

    def test_tap(self, button_name: str):
        btn = button_name.upper()
        
        if btn not in ["STAND", "HIT", "DOUBLE", "SPLIT"]:
            print(f"{RED}Unknown button: {button_name}. Available: STAND, HIT, DOUBLE, SPLIT{RESET}")
            return

        if not self.adb.is_connected():
            print(f"{RED}[Error] No Android device detected via ADB!{RESET}")
            return

        # Take a screenshot first to detect available buttons
        if not self.adb.capture_screenshot(self.screen_png):
            print(f"{RED}[Error] Screenshot failed.{RESET}")
            return
        w, h = self.adb.get_screen_size()

        # Scan whole screen for the button -> exact tap coordinates
        available_buttons = self.detector.detect_available_buttons(self.screen_png)

        if btn in available_buttons:
            nx, ny = available_buttons[btn]
            px, py = int(nx * w), int(ny * h)
            print(f"{CYAN}Tapping {BOLD}{btn}{RESET} at pixel ({px}, {py}) [found on screen]...{RESET}")
            self.adb.tap(px, py)
            print(f"{GREEN}Tap dispatched! Check your phone.{RESET}")
        else:
            print(f"{RED}Button '{btn}' not found on screen. Found: {sorted(available_buttons.keys())}{RESET}")

    def run(self):
        print(f"\n{BOLD}{CYAN}=========================================={RESET}")
        print(f"{BOLD}{CYAN}    BLACKJACK AUTOMATION BOT ACTIVE      {RESET}")
        print(f"{BOLD}{CYAN}=========================================={RESET}")

        if not self.adb.is_connected():
            print(f"{RED}[Error] No Android device connected via ADB!{RESET}")
            print("Please enable USB debugging, connect phone, and verify with 'adb devices'.")
            sys.exit(1)

        width, height = self.adb.get_screen_size()
        print(f"Connected to device: {GREEN}{width}x{height}{RESET}")
        print(f"Tesseract OCR:       {GREEN}{self.detector.tesseract_path}{RESET}")
        print(f"Rules:               {CYAN}8 Decks (shuffled each hand), Double Down, No Resplit, 5-Card Charlie{RESET}")
        print(f"Session Log:         {GREEN}{self.logger.log_file_path}{RESET}")
        print(f"\n{YELLOW}Bot is running. Press Ctrl+C to stop at any time.{RESET}\n")

        consecutive_betting_ticks = 0
        consecutive_waiting_ticks = 0
        last_state = None

        try:
            while True:
                # 1. Capture screen
                success = self.adb.capture_screenshot(self.screen_png)
                if not success:
                    msg = "[ADB Error] Screenshot capture failed"
                    print(f"{RED}{msg}{RESET}")
                    self.error_tracker.check(msg)
                    time.sleep(0.5)
                    continue

                # 2. Check for static screen to eliminate redundant OCR
                is_static = self.detector.is_screen_static(self.screen_png)
                if is_static and last_state and last_state.phase in ("BETTING", "WAITING"):
                    time.sleep(0.8)
                    continue

                # 3. Analyze state
                state = self.detector.detect(self.screen_png)
                last_state = state

                # 4. Handle state
                if state.phase == "BETTING":
                    consecutive_betting_ticks += 1
                    consecutive_waiting_ticks = 0
                    self.active_hand_index = 0
                    self.advance_hand = False
                    self._bankroll_recorded_this_hand = False
                    self.hand_pending_resolution = False
                    self.last_hand_signature = None

                    if consecutive_betting_ticks % 6 == 1:
                        chips_info = f"{state.bankroll:,}" if state.bankroll else "chips untouched"
                        msg = f"[BETTING] Waiting for deal... ({chips_info})"
                        print(f"[{time.strftime('%H:%M:%S')}] {YELLOW}{msg}{RESET}")
                    # Relaxed pacing in betting phase to prevent CPU heat
                    time.sleep(1.5)
                    continue

                consecutive_betting_ticks = 0

                if state.phase == "WAITING":
                    consecutive_waiting_ticks += 1
                    # Only reset hand if the previous hand reached terminal resolution
                    if self.hand_pending_resolution:
                        self._bankroll_recorded_this_hand = False
                        self.hand_pending_resolution = False
                        self.active_hand_index = 0
                        self.advance_hand = False
                        self.last_hand_signature = None

                    if consecutive_waiting_ticks == 1 or consecutive_waiting_ticks % 5 == 0:
                        msg = (
                            f"[WAITING] Cards dealing or animating... "
                            f"(dealer_raw='{state.raw_dealer_text}' player_raw='{state.raw_player_text}' "
                            f"hands={state.player_hands} "
                            f"buttons_raw='{state.raw_buttons_text}' btns={sorted(state.available_buttons.keys())})"
                        )
                        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
                        # Only trigger error tracker if stuck for an excessively long time (~16s)
                        if consecutive_waiting_ticks >= 20:
                            self.error_tracker.check(f"[WAITING] Stuck in animation loop ({consecutive_waiting_ticks} ticks)")
                    # Relaxed pacing while waiting for deal animations
                    time.sleep(0.8)
                    continue

                consecutive_waiting_ticks = 0

                if state.phase == "PLAYING" and state.dealer_card and state.player_total > 0:
                    # Detect new hand under auto-deal (without visiting BETTING):
                    # 1. Previous hand finished its player turn (hand_pending_resolution)
                    # 2. Dealer upcard changed (dealer card never changes mid-hand)
                    # 3. Player score dropped/reset without advance_hand
                    current_sig = (state.dealer_card, state.is_soft, state.player_total)
                    is_new_hand = False
                    if self.hand_pending_resolution:
                        is_new_hand = True
                    elif self.last_hand_signature is not None:
                        last_dealer, last_soft, last_total = self.last_hand_signature
                        if state.dealer_card != last_dealer:
                            is_new_hand = True
                        elif not self.advance_hand and state.player_total < last_total and not last_soft:
                            is_new_hand = True

                    if is_new_hand:
                        self._bankroll_recorded_this_hand = False
                        self.hand_pending_resolution = False
                        self.active_hand_index = 0
                        self.advance_hand = False

                    self.last_hand_signature = current_sig

                    # Read bankroll once per hand when buttons are visible (post-ante).
                    # Delta between consecutive readings = true profit.
                    # Only mark recorded if tracker successfully accepted the reading (or initialized baseline).
                    if not self._bankroll_recorded_this_hand and state.bankroll is not None:
                        initial_check = self.tracker.start_bankroll is None
                        result = self.tracker.update(state.bankroll, was_double=self.last_action_was_double)
                        self.last_action_was_double = False
                        if result is not None or initial_check:
                            self._bankroll_recorded_this_hand = True
                            if result:
                                oc = result["outcome"]
                                outcome_color = GREEN if ("WIN" in oc or "BLACKJACK" in oc) else (
                                    YELLOW if oc == "PUSH" else RED)
                                print(
                                    f"[{time.strftime('%H:%M:%S')}] {BOLD}{outcome_color}"
                                    f">> HAND RESULT: {oc} ({result['delta']:+,} chips) | "
                                    f"Bankroll: {result['chips']:,} | Net: {result['net_profit']:+,} | "
                                    f"Win Rate: {result['win_rate']:.1f}% ({self.tracker.wins}W-{self.tracker.losses}L-{self.tracker.pushes}P)"
                                    f"{RESET}"
                                )

                    now = time.time()
                    if now - self.last_action_time < self.action_cooldown:
                        time.sleep(0.2)
                        continue

                    # ---- Multi-hand (post-split) handling --------------------
                    hands = state.player_hands or [(state.is_soft, state.player_total)]
                    if self.advance_hand:
                        self.active_hand_index += 1
                        self.advance_hand = False
                    if self.active_hand_index >= len(hands):
                        # Hand already resolved this detection; reset.
                        self.active_hand_index = 0
                    is_soft, total = hands[min(self.active_hand_index, len(hands) - 1)]

                    # A busted hand needs no action; wait for the game to move on.
                    if total > 21:
                        if self.active_hand_index + 1 >= len(hands):
                            self.hand_pending_resolution = True
                        else:
                            self.advance_hand = True
                        time.sleep(0.3)
                        continue

                    # Decide action
                    action = get_action(
                        is_soft=is_soft,
                        total=total,
                        dealer_card=state.dealer_card,
                        is_pair=state.is_pair,
                        pair_val=state.pair_val,
                        can_double=state.can_double,
                        can_split=state.can_split
                    )

                    # Reuse detected buttons from state (detected during detect()).
                    available_buttons = state.available_buttons
                    btn_key = action.value

                    # If the desired button isn't available, try alternatives.
                    # With full-screen detection this is rare, but a guard is
                    # safer than tapping empty screen.
                    if btn_key not in available_buttons:
                        if btn_key == "DOUBLE" or btn_key == "SPLIT":
                            btn_key = "HIT"

                    if btn_key not in available_buttons:
                        # Geometric fallback if button was read in text or buttons row is active
                        raw_btns = state.raw_buttons_text.upper()
                        if btn_key in raw_btns or (btn_key in ("HIT", "STAND") and ("HIT" in raw_btns or "STAND" in raw_btns)):
                            layout_coords = {
                                "STAND": (0.37, 0.91),
                                "HIT": (0.63, 0.91),
                                "DOUBLE": (0.75, 0.91),
                                "SPLIT": (0.85, 0.91),
                            }
                            if btn_key in layout_coords:
                                available_buttons[btn_key] = layout_coords[btn_key]

                    if btn_key not in available_buttons:
                        msg = (
                            f">> No '{action.value}' button found on screen "
                            f"(found: {sorted(available_buttons.keys())}). Skipping."
                        )
                        print(f"{RED}{msg}{RESET}")
                        self.error_tracker.check(msg)
                        time.sleep(1.0)
                        continue

                    norm_x, norm_y = available_buttons[btn_key]
                    px, py = int(norm_x * width), int(norm_y * height)

                    hand_desc = f"{'Soft' if is_soft else 'Hard'} {total}"
                    hand_tag = f" [hand {self.active_hand_index + 1}/{len(hands)}]" if len(hands) > 1 else ""
                    print(
                        f"[{time.strftime('%H:%M:%S')}] {BOLD}{GREEN}>> DECISION: {action.value}{RESET} "
                        f"({hand_desc} vs Dealer {state.dealer_card.name}){hand_tag} "
                        f"-> Tapping {btn_key} at ({px}, {py})"
                    )

                    self.adb.tap(px, py)
                    self.last_action_time = time.time()

                    # STAND / DOUBLE end the current hand -> next split hand.
                    if action is Action.DOUBLE_DOWN:
                        self.last_action_was_double = True
                    if action in (Action.STAND, Action.DOUBLE_DOWN):
                        self.advance_hand = True
                        if self.active_hand_index + 1 >= len(hands):
                            self.hand_pending_resolution = True
                    elif action is Action.SPLIT:
                        # Split creates two fresh hands; start from the left.
                        self.active_hand_index = 0
                        self.advance_hand = False
                        self.hand_pending_resolution = False

                    time.sleep(self.action_cooldown)

                time.sleep(0.3)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot stopped by user.{RESET}")
        finally:
            if self.tracker.hands_played > 0:
                print(f"\n{self.tracker.format_summary()}\n")
                self._append_to_master_summary()
            self.logger.stop()

    def _append_to_master_summary(self):
        """Appends the completed session summary to the master log file."""
        try:
            master_log = os.path.join(self.logger.log_dir, "master_summary.log")
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            log_name = os.path.basename(self.logger.log_file_path)
            entry = (
                f"\n--------------------------------------------------------------------------------\n"
                f" SESSION: {log_name}\n"
                f" Recorded:            {ts}\n"
                f" Hands Played:        {self.tracker.hands_played}\n"
                f" Outcomes:            {self.tracker.wins} Wins | {self.tracker.losses} Losses | {self.tracker.pushes} Pushes\n"
                f" Win Rate:            {self.tracker.win_rate:.1f}%\n"
                f" Net Profit:          {self.tracker.net_profit:+,} chips\n"
                f" Starting Bankroll:   {self.tracker.start_bankroll:,}\n"
                f" Ending Bankroll:     {self.tracker.current_bankroll:,}\n"
            )
            with open(master_log, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"{YELLOW}[Warning] Could not update master summary: {e}{RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Desktop Python Blackjack Bot")
    parser.add_argument("--calibrate", action="store_true", help="Calibrate coordinates and run test detection")
    parser.add_argument("--image", type=str, help="Optional image to calibrate against offline")
    parser.add_argument("--test-tap", type=str, help="Dispatch a test tap to a button (stand, hit, double, split)")
    parser.add_argument("--adb-path", type=str, help="Custom path to ADB binary")
    parser.add_argument("--tesseract-path", type=str, help="Custom path to Tesseract binary")

    args = parser.parse_args()
    bot = BlackjackBot(adb_path=args.adb_path, tesseract_path=args.tesseract_path)

    if args.calibrate:
        bot.calibrate(sample_image=args.image)
    elif args.test_tap:
        bot.test_tap(args.test_tap)
    else:
        bot.run()
