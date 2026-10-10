"""
Vision and OCR Game State Detector.
Extracts dealer upcard, player score/hand type, and game phase
using Tesseract OCR and macOS built-in sips / PIL.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple
from strategy import Card


@dataclass
class GameState:
    phase: str  # "BETTING", "PLAYING", "WAITING", "UNKNOWN"
    dealer_card: Optional[Card] = None
    player_total: int = 0
    is_soft: bool = False
    is_pair: bool = False
    pair_val: int = 0
    can_double: bool = True
    can_split: bool = False
    raw_dealer_text: str = ""
    raw_player_text: str = ""


class OcrDetector:
    # Normalized bounding boxes (ymin, xmin, ymax, xmax) on a 0.0 .. 1.0 scale
    # Calibrated against 461x1024 / standard Android 20:9 screens
    DEALER_BOX = (0.180, 0.390, 0.220, 0.607)
    PLAYER_SCORE_BOX = (0.776, 0.390, 0.816, 0.607)
    BET_AREA_BOX = (0.330, 0.200, 0.450, 0.800)
    BUTTONS_ROW_BOX = (0.830, 0.050, 0.940, 0.950)

    # Calibrated normalized button tap coordinates
    BUTTON_COORDS_3 = {
        "STAND": (0.241, 0.880),
        "HIT": (0.500, 0.880),
        "DOUBLE": (0.759, 0.880),
    }

    BUTTON_COORDS_4 = {
        "SPLIT": (0.160, 0.880),
        "STAND": (0.380, 0.880),
        "HIT": (0.620, 0.880),
        "DOUBLE": (0.840, 0.880),
    }

    def __init__(self, tesseract_path: Optional[str] = None, work_dir: Optional[str] = None):
        self.tesseract_path = tesseract_path or self._find_tesseract()
        self.work_dir = work_dir or os.path.join(os.path.dirname(__file__), "work")
        os.makedirs(self.work_dir, exist_ok=True)
        self.has_pil = False
        try:
            from PIL import Image
            self.has_pil = True
        except ImportError:
            self.has_pil = False

    def _find_tesseract(self) -> str:
        candidates = ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "tesseract"]
        for c in candidates:
            if shutil.which(c):
                return c
        return "tesseract"

    def crop_region(self, image_path: str, bbox: Tuple[float, float, float, float], out_path: str):
        """
        Crops a normalized bbox (ymin, xmin, ymax, xmax) from image_path.
        Uses PIL if installed, otherwise uses macOS built-in sips tool.
        """
        ymin, xmin, ymax, xmax = bbox

        if self.has_pil:
            from PIL import Image
            with Image.open(image_path) as img:
                w, h = img.size
                crop_box = (int(xmin * w), int(ymin * h), int(xmax * w), int(ymax * h))
                cropped = img.crop(crop_box)
                cropped.save(out_path)
            return

        # Fallback to macOS built-in `sips`
        # First get image size with sips
        try:
            res = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", image_path],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            out = res.stdout.decode()
            w_match = re.search(r"pixelWidth:\s*(\d+)", out)
            h_match = re.search(r"pixelHeight:\s*(\d+)", out)
            if not (w_match and h_match):
                return
            w = int(w_match.group(1))
            h = int(h_match.group(1))

            crop_x = int(xmin * w)
            crop_y = int(ymin * h)
            crop_w = int((xmax - xmin) * w)
            crop_h = int((ymax - ymin) * h)

            subprocess.run([
                "sips", "-c", str(crop_h), str(crop_w),
                "--cropOffset", str(crop_y), str(crop_x),
                image_path, "--out", out_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as e:
            print(f"[Crop Error] sips failed: {e}")

    def run_ocr(self, img_path: str, psm: int = 7) -> str:
        """Executes Tesseract on image file and returns cleaned text."""
        try:
            cmd = [self.tesseract_path, img_path, "stdout", "--psm", str(psm)]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return res.stdout.decode("utf-8").strip()
        except Exception:
            return ""

    def parse_dealer(self, text: str) -> Optional[Card]:
        clean = text.strip().upper()
        # Look for 10, A, J, Q, K, or single digits 2..9
        m = re.search(r"(10|[2-9]|A|K|Q|J)", clean)
        if m:
            val = m.group(1)
            if val in ("10", "K", "Q", "J"):
                return Card.TEN
            if val == "A":
                return Card.ACE
            return Card(int(val))
        return None

    def parse_player(self, text: str) -> Tuple[bool, int]:
        """
        Returns (is_soft, total).
        Examples:
          "7/17" -> (True, 17)
          "8 / 18" -> (True, 18)
          "16" -> (False, 16)
          "20" -> (False, 20)
        """
        clean = text.strip().replace(" ", "")
        # Soft hand: X/Y
        m_soft = re.search(r"(\d+)/(\d+)", clean)
        if m_soft:
            high_val = int(m_soft.group(2))
            return True, high_val

        # Hard hand: single integer between 4 and 21
        m_hard = re.search(r"\b(\d{1,2})\b", clean)
        if m_hard:
            val = int(m_hard.group(1))
            if 4 <= val <= 21:
                return False, val

        return False, 0

    def detect(self, screenshot_path: str) -> GameState:
        """
        Analyzes a screenshot and returns the current GameState.
        """
        # Crop regions
        dealer_crop = os.path.join(self.work_dir, "crop_dealer.png")
        player_crop = os.path.join(self.work_dir, "crop_player.png")
        bet_crop = os.path.join(self.work_dir, "crop_bet.png")
        buttons_crop = os.path.join(self.work_dir, "crop_buttons.png")

        self.crop_region(screenshot_path, self.DEALER_BOX, dealer_crop)
        self.crop_region(screenshot_path, self.PLAYER_SCORE_BOX, player_crop)
        self.crop_region(screenshot_path, self.BET_AREA_BOX, bet_crop)
        self.crop_region(screenshot_path, self.BUTTONS_ROW_BOX, buttons_crop)

        dealer_text = self.run_ocr(dealer_crop, psm=7)
        player_text = self.run_ocr(player_crop, psm=7)
        bet_text = self.run_ocr(bet_crop, psm=6)
        buttons_text = self.run_ocr(buttons_crop, psm=6)

        # Check for BETTING phase
        if "PLACE" in bet_text.upper() or "BET" in bet_text.upper():
            return GameState(
                phase="BETTING",
                raw_dealer_text=dealer_text,
                raw_player_text=player_text
            )

        dealer_card = self.parse_dealer(dealer_text)
        is_soft, player_total = self.parse_player(player_text)

        # Determine phase
        has_buttons = any(b in buttons_text.upper() for b in ["STAND", "HIT", "DOUBLE", "SPLIT"])

        if dealer_card is not None and player_total > 0:
            can_split = "SPLIT" in buttons_text.upper()
            can_double = "DOUBLE" in buttons_text.upper()
            return GameState(
                phase="PLAYING",
                dealer_card=dealer_card,
                player_total=player_total,
                is_soft=is_soft,
                can_double=can_double,
                can_split=can_split,
                raw_dealer_text=dealer_text,
                raw_player_text=player_text
            )

        if has_buttons:
            # Buttons are visible but cards still rendering
            return GameState(
                phase="WAITING",
                dealer_card=dealer_card,
                player_total=player_total,
                is_soft=is_soft,
                raw_dealer_text=dealer_text,
                raw_player_text=player_text
            )

        return GameState(
            phase="BETTING",
            raw_dealer_text=dealer_text,
            raw_player_text=player_text
        )
