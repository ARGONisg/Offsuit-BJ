#!/usr/bin/env python3
"""
Blackjack Automation Bot (Desktop ADB + Tesseract OCR).
Executes basic single-deck strategy, 5-card charlie, and auto-play
over ADB for any Android Blackjack game.
"""

import argparse
import os
import sys
import time
from adb_controller import AdbController
from ocr_detector import OcrDetector, GameState
from strategy import Action, Card, get_action

# Terminal color formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


class BlackjackBot:
    def __init__(self, adb_path: str = None, tesseract_path: str = None):
        self.adb = AdbController(adb_path)
        work_dir = os.path.join(os.path.dirname(__file__), "work")
        self.detector = OcrDetector(tesseract_path, work_dir=work_dir)
        self.screen_png = os.path.join(work_dir, "screen.png")
        self.last_action_time = 0.0
        self.action_cooldown = 1.2  # Seconds to wait after an action for animation

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

        print(f"\n{BOLD}Detection Results:{RESET}")
        print(f"  Phase:        {GREEN if state.phase == 'PLAYING' else YELLOW}{state.phase}{RESET}")
        print(f"  Dealer Card:  {BOLD}{state.dealer_card.name if state.dealer_card else 'None'}{RESET} (raw: '{state.raw_dealer_text}')")
        hand_type = "Soft" if state.is_soft else "Hard"
        print(f"  Player Total: {BOLD}{state.player_total} ({hand_type}){RESET} (raw: '{state.raw_player_text}')")
        print(f"  Buttons Text: '{state.raw_buttons_text}'")
        print(f"  Avail Btns:   {sorted(state.available_buttons.keys()) if state.available_buttons else []}")
        print(f"  Can Double:   {state.can_double}")
        print(f"  Can Split:    {state.can_split}")

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
        print(f"Rules:               {CYAN}Single Deck, Double Down, No Resplit, 5-Card Charlie{RESET}")
        print(f"\n{YELLOW}Bot is running. Press Ctrl+C to stop at any time.{RESET}\n")

        consecutive_betting_ticks = 0
        consecutive_waiting_ticks = 0

        try:
            while True:
                # 1. Capture screen
                success = self.adb.capture_screenshot(self.screen_png)
                if not success:
                    time.sleep(0.5)
                    continue

                # 2. Analyze state
                state = self.detector.detect(self.screen_png)

                # 3. Handle state
                if state.phase == "BETTING":
                    consecutive_betting_ticks += 1
                    consecutive_waiting_ticks = 0
                    if consecutive_betting_ticks % 6 == 1:
                        print(f"[{time.strftime('%H:%M:%S')}] {YELLOW}[BETTING]{RESET} Waiting for deal... (chips untouched)")
                    time.sleep(0.5)
                    continue

                consecutive_betting_ticks = 0

                if state.phase == "WAITING":
                    consecutive_waiting_ticks += 1
                    if consecutive_waiting_ticks == 1 or consecutive_waiting_ticks % 5 == 0:
                        print(
                            f"[{time.strftime('%H:%M:%S')}] [WAITING] Cards dealing or animating... "
                            f"(dealer_raw='{state.raw_dealer_text}' player_raw='{state.raw_player_text}' "
                            f"buttons_raw='{state.raw_buttons_text}' btns={sorted(state.available_buttons.keys())})"
                        )
                    time.sleep(0.3)
                    continue

                consecutive_waiting_ticks = 0

                if state.phase == "PLAYING" and state.dealer_card and state.player_total > 0:
                    now = time.time()
                    if now - self.last_action_time < self.action_cooldown:
                        time.sleep(0.2)
                        continue

                    # Decide action
                    action = get_action(
                        is_soft=state.is_soft,
                        total=state.player_total,
                        dealer_card=state.dealer_card,
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
                        print(
                            f"{RED}>> No '{action.value}' button found on screen "
                            f"(found: {sorted(available_buttons.keys())}). Skipping.{RESET}"
                        )
                        time.sleep(1.0)
                        continue

                    norm_x, norm_y = available_buttons[btn_key]
                    px, py = int(norm_x * width), int(norm_y * height)

                    hand_desc = f"{'Soft' if state.is_soft else 'Hard'} {state.player_total}"
                    print(
                        f"[{time.strftime('%H:%M:%S')}] {BOLD}{GREEN}>> DECISION: {action.value}{RESET} "
                        f"({hand_desc} vs Dealer {state.dealer_card.name}) "
                        f"-> Tapping {btn_key} at ({px}, {py})"
                    )

                    self.adb.tap(px, py)
                    self.last_action_time = time.time()
                    time.sleep(self.action_cooldown)

                time.sleep(0.3)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bot stopped by user.{RESET}")


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
