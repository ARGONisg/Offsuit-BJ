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
    raw_buttons_text: str = ""
    available_buttons: dict = None

    def __post_init__(self):
        if self.available_buttons is None:
            self.available_buttons = {}


class OcrDetector:
    # Region crops used for reading the game state (not tapping).
    # Normalized bboxes (ymin, xmin, ymax, xmax) on a 0.0 .. 1.0 scale.
    DEALER_BOX = (0.180, 0.390, 0.220, 0.607)
    PLAYER_SCORE_BOX = (0.776, 0.390, 0.816, 0.607)
    BET_AREA_BOX = (0.330, 0.200, 0.450, 0.800)
    BUTTONS_ROW_BOX = (0.830, 0.050, 0.940, 0.950)

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

    def run_ocr_tsv(self, img_path: str, psm: int = 11) -> list:
        """
        Executes Tesseract on image file and returns word-level bounding boxes.
        Each entry: {"text": str, "left": int, "top": int, "width": int, "height": int}
        Coordinates are pixels in the given image. psm 11 = sparse text, which
        finds individual words anywhere on screen regardless of layout.
        """
        try:
            cmd = [self.tesseract_path, img_path, "stdout", "--psm", str(psm), "tsv"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            lines = res.stdout.decode("utf-8").strip().splitlines()
            if not lines:
                return []

            header = lines[0].split("\t")
            words = []
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) < len(header):
                    continue
                row = dict(zip(header, parts))
                text = row.get("text", "").strip()
                # Skip empty/null words with noise confidence
                if not text or text in ("", " "):
                    continue
                try:
                    conf = float(row.get("conf", "-1"))
                except ValueError:
                    conf = -1.0
                # Only keep reasonably confident words (Tesseract uses -1 for noise)
                if conf < 0:
                    continue
                try:
                    words.append({
                        "text": text,
                        "left": int(row.get("left", 0)),
                        "top": int(row.get("top", 0)),
                        "width": int(row.get("width", 0)),
                        "height": int(row.get("height", 0)),
                    })
                except ValueError:
                    continue
            return words
        except Exception:
            return []

    def parse_dealer(self, text: str) -> Optional[Card]:
        clean = text.strip().upper().replace(" ", "")
        if not clean:
            return None

        # Soft total, e.g. "1/11" (Ace), "7/17". OCR sometimes reads "/"
        # as "I", "l", "|", so accept those separators too.
        m_soft = re.search(r"(\d+)[\/\|IL](\d+)", clean)
        if m_soft:
            try:
                high_val = int(m_soft.group(2))
            except ValueError:
                high_val = 0
            if high_val == 11:
                return Card.ACE
            if high_val == 10:
                return Card.TEN
            if 2 <= high_val <= 9:
                return Card(high_val)
            # High totals like 13..21 are full-hand totals (post-reveal),
            # not an upcard rank -> fall through to letter search.
            try:
                low_val = int(m_soft.group(1))
            except ValueError:
                low_val = 0
            if low_val == 1 and high_val in (11,):
                return Card.ACE
            if low_val == 1:
                # e.g. OCR garbled "1/1?" where high failed -> likely Ace
                pass

        # Lone "1" or "11" almost always means an Ace total was OCR'd
        # without the slash (e.g. "1/11" read as "111" or "1").
        if clean in ("1", "11", "A", "ACE"):
            return Card.ACE
        if re.fullmatch(r"1+", clean) and len(clean) <= 3:
            return Card.ACE

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

        buttons_upper = buttons_text.upper()
        # Scan the ENTIRE screen for button words -> exact tap coordinates.
        available_buttons = self.detect_available_buttons(screenshot_path)
        if available_buttons:
            has_buttons = True
        else:
            has_buttons = any(b in buttons_upper for b in ["STAND", "HIT", "DOUBLE", "SPLIT"])

        if dealer_card is not None and player_total > 0 and has_buttons:
            can_split = "SPLIT" in available_buttons or "SPLIT" in buttons_upper
            can_double = "DOUBLE" in available_buttons or "DOUBLE" in buttons_upper

            return GameState(
                phase="PLAYING",
                dealer_card=dealer_card,
                player_total=player_total,
                is_soft=is_soft,
                is_pair=False,
                pair_val=0,
                can_double=can_double,
                can_split=can_split,
                raw_dealer_text=dealer_text,
                raw_player_text=player_text,
                raw_buttons_text=buttons_text,
                available_buttons=available_buttons,
            )

        if has_buttons:
            # Buttons are visible but cards still rendering / OCR misread
            return GameState(
                phase="WAITING",
                dealer_card=dealer_card,
                player_total=player_total,
                is_soft=is_soft,
                raw_dealer_text=dealer_text,
                raw_player_text=player_text,
                raw_buttons_text=buttons_text,
                available_buttons=available_buttons,
            )

        return GameState(
            phase="BETTING",
            raw_dealer_text=dealer_text,
            raw_player_text=player_text,
            raw_buttons_text=buttons_text,
            available_buttons=available_buttons,
        )

    @staticmethod
    def _button_text_matches(button_name: str, text: str) -> bool:
        """Fuzzy match OCR'd word to a button (tolerates common misreads)."""
        upper = text.upper().strip()
        if button_name == upper:
            return True
        if button_name == "STAND":
            return upper in ("STAN", "TAND", "STND")
        if button_name == "HIT":
            return upper in ("H1T", "HIT")
        if button_name == "DOUBLE":
            return upper in ("DOUB", "OUBLE", "D0UBLE", "DOUBL")
        if button_name == "SPLIT":
            return upper in ("SPL", "PLIT", "SPL1T")
        return False

    def detect_available_buttons(self, screenshot_path: str) -> dict:
        """
        Scans the ENTIRE screenshot for button words via Tesseract TSV output.
        Returns: {button_name: (normalized_x, normalized_y)} where the tap
        point is the center of the OCR'd word's bounding box, normalized to
        0.0..1.0 so it works on any device resolution. No hardcoded zones.
        """
        # Query image size to normalize box coordinates.
        w, h = self.get_image_size(screenshot_path)
        if not w or not h:
            return {}

        words = self.run_ocr_tsv(screenshot_path, psm=11)
        available_buttons = {}

        for word in words:
            upper = word["text"].upper().strip().replace(",", "").replace(".", "")
            if not upper:
                continue
            for btn_name in ("SPLIT", "STAND", "HIT", "DOUBLE"):
                if btn_name in available_buttons:
                    continue
                if self._button_text_matches(btn_name, upper):
                    # Tap the center of the word box, in normalized coords.
                    center_x = (word["left"] + word["width"] / 2) / w
                    center_y = (word["top"] + word["height"] / 2) / h
                    available_buttons[btn_name] = (center_x, center_y)
                    break

        return available_buttons

    def get_image_size(self, image_path: str) -> Tuple[int, int]:
        """Returns (width, height) of an image using PIL or sips."""
        if self.has_pil:
            try:
                from PIL import Image
                with Image.open(image_path) as img:
                    return img.size
            except Exception:
                pass
        try:
            res = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", image_path],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            out = res.stdout.decode()
            w_match = re.search(r"pixelWidth:\s*(\d+)", out)
            h_match = re.search(r"pixelHeight:\s*(\d+)", out)
            if w_match and h_match:
                return int(w_match.group(1)), int(h_match.group(1))
        except Exception:
            pass
        return 0, 0
