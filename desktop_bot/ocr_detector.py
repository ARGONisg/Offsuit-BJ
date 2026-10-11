"""
Vision and OCR Game State Detector.
Extracts dealer upcard, player score/hand type, and game phase
using Tesseract OCR and macOS built-in sips / PIL.
"""

import os
import re
import shutil
import subprocess
import tempfile
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
    player_hands: list = None
    bankroll: Optional[int] = None

    def __post_init__(self):
        if self.available_buttons is None:
            self.available_buttons = {}
        if self.player_hands is None:
            self.player_hands = []  # [(is_soft, total), ...] left->right


class OcrDetector:
    # Region crops used for reading the game state (not tapping).
    # Normalized bboxes (ymin, xmin, ymax, xmax) on a 0.0 .. 1.0 scale.
    DEALER_BOX = (0.180, 0.390, 0.220, 0.607)
    PLAYER_SCORE_BOX = (0.776, 0.390, 0.816, 0.607)
    BET_AREA_BOX = (0.330, 0.200, 0.450, 0.800)
    BUTTONS_ROW_BOX = (0.830, 0.050, 0.940, 0.950)
    BANKROLL_BOX = (0.065, 0.350, 0.115, 0.650)

    # Full-width search bands for TSV whole-screen scanning. Wider than the
    # fixed crop boxes so values are found wherever the layout puts them
    # (e.g. a split hand's score sits on the left, not center).
    DEALER_BAND = (0.12, 0.05, 0.32, 0.95)      # (ymin, xmin, ymax, xmax)
    PLAYER_BAND = (0.70, 0.05, 0.865, 0.95)     # above the buttons row

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
        self._last_frame_bytes = None
        self._last_state: Optional[GameState] = None

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

    def preprocess_for_ocr(self, img_path: str, out_path: str, scale: int = 4, invert: bool = False) -> str:
        """
        Preprocesses an image crop for better OCR: upscales and binarizes.
        Returns the path to the preprocessed image, or the original if PIL is unavailable.
        """
        if not self.has_pil:
            return img_path
        try:
            from PIL import Image, ImageOps
            img = Image.open(img_path)
            # Upscale so characters are tall enough for Tesseract (needs ~30px+)
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
            img = img.convert("L")
            if invert:
                img = ImageOps.invert(img)
            # Binarize with a threshold
            img = img.point(lambda x: 255 if x > 140 else 0)
            img.save(out_path)
            return out_path
        except Exception:
            return img_path

    def is_screen_static(self, screenshot_path: str, threshold: float = 1.5) -> bool:
        """
        Computes lightweight perceptual difference against previous frame in RAM.
        Returns True if the screen is virtually identical (< threshold diff),
        allowing the bot loop to skip heavy full-screen OCR passes.
        """
        if not self.has_pil or not os.path.exists(screenshot_path):
            return False
        try:
            from PIL import Image
            with Image.open(screenshot_path) as img:
                thumb = img.resize((32, 32)).convert("L")
                cur_bytes = list(thumb.getdata())

            if self._last_frame_bytes is None:
                self._last_frame_bytes = cur_bytes
                return False

            diff = sum(abs(a - b) for a, b in zip(cur_bytes, self._last_frame_bytes)) / 1024.0
            self._last_frame_bytes = cur_bytes
            return diff < threshold
        except Exception:
            return False

    def read_bankroll(self, screenshot_path: str) -> Optional[int]:
        """
        Extracts current chips bankroll total from the top area.
        Returns parsed integer (e.g. 22345 from '22,345'), or None.
        """
        if not os.path.exists(screenshot_path):
            return None
        crop_path = os.path.join(self.work_dir, "crop_bankroll.png")
        self.crop_region(screenshot_path, self.BANKROLL_BOX, crop_path)
        if not os.path.exists(crop_path):
            return None

        text = self.run_ocr(crop_path, psm=7, digits_only=True)
        digits = re.sub(r"[^\d]", "", text)
        if digits:
            try:
                val = int(digits)
                if val > 0:
                    return val
            except ValueError:
                pass
        return None

    def run_ocr(self, img_path: str, psm: int = 7, digits_only: bool = False) -> str:
        """Executes Tesseract on image file and returns cleaned text."""
        try:
            cmd = [self.tesseract_path, img_path, "stdout", "--psm", str(psm)]
            if digits_only:
                cmd += ["-c", "tessedit_char_whitelist=0123456789/"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return res.stdout.decode("utf-8").strip()
        except Exception:
            return ""

    def run_ocr_digits(self, img_path: str) -> str:
        """
        Optimized numeric OCR with fast-path early return.
        Tries preprocessed 4x upscale with PSM 7 first; if a clean digit/soft total
        is found, exits immediately without spawning additional Tesseract processes.
        """
        if not os.path.exists(img_path):
            return ""

        base = os.path.splitext(img_path)
        processed_4x = base[0] + "_processed" + base[1]
        self.preprocess_for_ocr(img_path, processed_4x, scale=4)

        # Fast path 1: Preprocessed 4x with single-line PSM 7
        text_4x = self.run_ocr(processed_4x, psm=7, digits_only=True).strip().replace(" ", "")
        if re.fullmatch(r"\d{1,2}", text_4x) or re.fullmatch(r"\d{1,2}[\/|IL]\d{1,2}", text_4x):
            return text_4x

        # Fast path 2: Raw crop with PSM 7
        text_raw = self.run_ocr(img_path, psm=7, digits_only=True).strip().replace(" ", "")
        if re.fullmatch(r"\d{1,2}", text_raw) or re.fullmatch(r"\d{1,2}[\/|IL]\d{1,2}", text_raw):
            return text_raw

        # Fallback only when fast paths fail: try 6x and additional PSM modes
        processed_6x = base[0] + "_processed6x" + base[1]
        self.preprocess_for_ocr(img_path, processed_6x, scale=6)

        candidates = [text_4x, text_raw]
        for path in [processed_4x, processed_6x]:
            for psm in [10, 13]:
                text = self.run_ocr(path, psm=psm, digits_only=True).strip().replace(" ", "")
                if text and re.search(r"\d", text):
                    if re.fullmatch(r"\d{1,2}", text) or re.fullmatch(r"\d{1,2}[\/|IL]\d{1,2}", text):
                        return text
                    candidates.append(text)

        for c in candidates:
            if c and re.fullmatch(r"\d{1,2}", c):
                return c
        for c in candidates:
            if c and re.fullmatch(r"\d{1,2}[\/|IL]\d{1,2}", c):
                return c
        return candidates[0] if candidates and candidates[0] else ""

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
        Uses one full-screen TSV scan for buttons, dealer, and player hands.
        Falls back to multi-pass digit OCR on crops for reliability.
        """
        # Crops retained for bet-phase detection, fallback parsing and logs.
        dealer_crop = os.path.join(self.work_dir, "crop_dealer.png")
        player_crop = os.path.join(self.work_dir, "crop_player.png")
        bet_crop = os.path.join(self.work_dir, "crop_bet.png")
        buttons_crop = os.path.join(self.work_dir, "crop_buttons.png")

        self.crop_region(screenshot_path, self.DEALER_BOX, dealer_crop)
        self.crop_region(screenshot_path, self.PLAYER_SCORE_BOX, player_crop)
        self.crop_region(screenshot_path, self.BET_AREA_BOX, bet_crop)
        self.crop_region(screenshot_path, self.BUTTONS_ROW_BOX, buttons_crop)

        # Multi-pass digit-focused OCR on the small crops.
        dealer_text = self.run_ocr_digits(dealer_crop) or self.run_ocr(dealer_crop, psm=7)
        player_text = self.run_ocr_digits(player_crop) or self.run_ocr(player_crop, psm=7)
        bet_text = self.run_ocr(bet_crop, psm=6)
        buttons_text = self.run_ocr(buttons_crop, psm=6)

        # Check for BETTING phase
        if "PLACE" in bet_text.upper() or "BET" in bet_text.upper():
            bankroll = self.read_bankroll(screenshot_path)
            return GameState(
                phase="BETTING",
                raw_dealer_text=dealer_text,
                raw_player_text=player_text,
                raw_buttons_text=buttons_text,
                bankroll=bankroll,
            )

        # ONE full-screen scan; every detector reuses these words.
        w, h = self.get_image_size(screenshot_path)
        words = self.run_ocr_tsv(screenshot_path, psm=11) if w and h else []

        available_buttons = self._buttons_from_words(words, w, h)
        dealer_card = self._dealer_from_words(words, w, h) or self.parse_dealer(dealer_text)
        player_hands = self._player_hands_from_words(words, w, h)

        # TSV sparse mode sometimes misses tiny scores (e.g. a small "9").
        # Crop the full-width player band and run multi-pass OCR.
        if not player_hands:
            wide_crop = os.path.join(self.work_dir, "crop_player_wide.png")
            self.crop_region(screenshot_path, self.PLAYER_BAND, wide_crop)
            wide_text = self.run_ocr_digits(wide_crop) or self.run_ocr(wide_crop, psm=6)
            is_soft_w, total_w = self.parse_player(wide_text)
            if total_w > 0:
                player_hands = [(is_soft_w, total_w)]

        # Final fallback to the narrow fixed-box crop.
        is_soft, player_total = self.parse_player(player_text)
        if player_hands:
            is_soft, player_total = player_hands[0]
        elif player_total > 0:
            player_hands = [(is_soft, player_total)]

        buttons_upper = buttons_text.upper()
        has_buttons = bool(available_buttons) or any(
            b in buttons_upper for b in ["STAND", "HIT", "DOUBLE", "SPLIT"]
        )

        if dealer_card is not None and player_total > 0 and has_buttons:
            can_split = "SPLIT" in available_buttons or "SPLIT" in buttons_upper
            can_double = "DOUBLE" in available_buttons or "DOUBLE" in buttons_upper

            # The game only shows SPLIT for a pair, so it's safe to infer one:
            # a soft pair (A+A) is pair of aces; a hard total / 2 gives the rank.
            is_pair = can_split
            pair_val = 11 if (can_split and is_soft) else (player_total // 2 if can_split else 0)

            return GameState(
                phase="PLAYING",
                dealer_card=dealer_card,
                player_total=player_total,
                is_soft=is_soft,
                is_pair=is_pair,
                pair_val=pair_val,
                can_double=can_double,
                can_split=can_split,
                raw_dealer_text=dealer_text,
                raw_player_text=player_text,
                raw_buttons_text=buttons_text,
                available_buttons=available_buttons,
                player_hands=player_hands,
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
                player_hands=player_hands,
            )

        bankroll = self.read_bankroll(screenshot_path)
        return GameState(
            phase="BETTING",
            raw_dealer_text=dealer_text,
            raw_player_text=player_text,
            raw_buttons_text=buttons_text,
            available_buttons=available_buttons,
            player_hands=player_hands,
            bankroll=bankroll,
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
        """Scans the ENTIRE screenshot for button words -> exact tap coords."""
        w, h = self.get_image_size(screenshot_path)
        if not w or not h:
            return {}
        words = self.run_ocr_tsv(screenshot_path, psm=11)
        return self._buttons_from_words(words, w, h)

    def _buttons_from_words(self, words: list, w: int, h: int) -> dict:
        """Maps button words -> (normalized_x, normalized_y) tap points."""
        available_buttons = {}
        for word in words:
            upper = word["text"].upper().strip().replace(",", "").replace(".", "")
            if not upper:
                continue
            for btn_name in ("SPLIT", "STAND", "HIT", "DOUBLE"):
                if btn_name in available_buttons:
                    continue
                if self._button_text_matches(btn_name, upper):
                    # Centre of the word box, in normalized coords.
                    center_x = (word["left"] + word["width"] / 2) / w
                    center_y = (word["top"] + word["height"] / 2) / h
                    available_buttons[btn_name] = (center_x, center_y)
                    break
        return available_buttons

    @staticmethod
    def _card_rank_from_text(text: str) -> Optional[Card]:
        """Returns a Card rank for a word, or None. Accepts 2-9, 10, A, K, Q, J."""
        clean = text.upper().strip().replace(" ", "")
        if clean in ("A", "ACE"):
            return Card.ACE
        if clean in ("10", "K", "Q", "J"):
            return Card.TEN
        if re.fullmatch(r"[2-9]", clean):
            return Card(int(clean))
        # Ace shown as a soft total like "1/11" or "111"
        m_soft = re.search(r"1?[/|IL]11", clean)
        if m_soft and re.fullmatch(r"1[\/|IL]11", clean):
            return Card.ACE
        if re.fullmatch(r"1{1,3}", clean):
            return Card.ACE
        return None

    def _dealer_from_words(self, words: list, w: int, h: int) -> Optional[Card]:
        """Finds the dealer upcard anywhere in the dealer band (whole width)."""
        ymin, xmin, ymax, xmax = self.DEALER_BAND
        for word in words:
            cx = (word["left"] + word["width"] / 2) / w
            cy = (word["top"] + word["height"] / 2) / h
            if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
                continue
            card = self._card_rank_from_text(word["text"])
            if card is not None:
                return card
        return None

    def _player_hands_from_words(self, words: list, w: int, h: int) -> list:
        """
        Finds ALL player hand totals in the player band (whole width), left->right.
        Returns a list of (is_soft, total). Soft totals may appear as "X/Y"
        or as two separate close numbers (low + high).
        """
        ymin, xmin, ymax, xmax = self.PLAYER_BAND
        tokens = []
        for word in words:
            cx = (word["left"] + word["width"] / 2) / w
            cy = (word["top"] + word["height"] / 2) / h
            if not (xmin <= cx <= xmax and ymin <= cy <= ymax):
                continue
            clean = word["text"].upper().strip().replace(",", "").replace(".", "")
            if not clean:
                continue
            # Soft form "7/17" (slash sometimes OCR'd as I, l, |).
            m_soft = re.search(r"^(\d{1,2})[\/|IL](\d{1,2})$", clean)
            if m_soft:
                low, high = int(m_soft.group(1)), int(m_soft.group(2))
                if 12 <= high <= 21 and low <= 10:
                    tokens.append({"type": "soft", "total": high, "x": cx, "y": cy})
                    continue
            # Plain number (hard total).
            if re.fullmatch(r"\d{1,2}", clean):
                v = int(clean)
                if 4 <= v <= 21:
                    tokens.append({"type": "hard", "total": v, "x": cx, "y": cy})

        # Soft splits: a high number (12-21) with a low companion (<=10) a
        # couple of pixels away is really "7 / 17". Consume both, keep high.
        consumed = set()
        hands = []  # (is_soft, total, norm_x)
        for i, t in enumerate(tokens):
            if t["type"] == "hard" and 12 <= t["total"] <= 21:
                for j, c in enumerate(tokens):
                    if i == j or j in consumed:
                        continue
                    if c["total"] <= 10 and abs(c["x"] - t["x"]) < 0.07 and abs(c["y"] - t["y"]) < 0.02:
                        consumed.add(i)
                        consumed.add(j)
                        hands.append((True, t["total"], t["x"]))
                        break
                else:
                    hands.append((False, t["total"], t["x"]))
            elif i not in consumed:
                hands.append((t["type"] == "soft", t["total"], t["x"]))

        hands.sort(key=lambda hh: hh[2])  # left -> right
        return [(is_soft, total) for is_soft, total, _x in hands]

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
