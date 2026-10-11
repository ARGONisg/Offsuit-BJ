# Offsuit BJ - Desktop Automation Bot

An automated computer-vision and ADB-driven Blackjack bot designed to play Blackjack on connected Android devices with optimal basic strategy and real-time bankroll tracking.

---

## Key Features

- **Optimal Basic Strategy Engine**: Complete 8-deck strategy lookup table handling Hard totals, Soft hands, Pairs (Splits), and Double Downs.
- **Deal-to-Deal Bankroll Tracking**: Accurately tracks profit deltas at the start of each player action (`PLAYING` phase), automatically detecting **Wins**, **Losses**, and **Pushes** while supporting continuous Auto-Deal without ante timing errors.
- **Dual-Pass OCR & Robust Button Detection**: Combines full-screen TSV page segmentation with targeted button-band OCR (`BUTTONS_ROW_BOX`) and geometric fallback to ensure 100% button hit rates (`STAND`, `HIT`, `DOUBLE`, `SPLIT`).
- **Atomic Screenshot Pipeline**: Thread-safe temporary file writes and atomic renames prevent partial frame reads and image corruption.
- **Thermal & CPU Pacing**: Static frame perceptual diffing skips redundant OCR invocations during static screens, keeping CPU temperatures cool during extended sessions.
- **Session & Master Logging**: Real-time console output, individual session logs (`desktop_bot/logs/bot_<timestamp>.log`), and an auto-updating cumulative master summary (`desktop_bot/logs/master_summary.log`).

---

## Prerequisites

1. **Python**: Python 3.9 or newer.
2. **Android Debug Bridge (ADB)**:
   - macOS (Homebrew): `brew install android-platform-tools`
   - Linux: `sudo apt install adb`
   - Windows: Install Android SDK Platform Tools and add to `PATH`.
   - Ensure **USB Debugging** is enabled on your Android phone and authorized.
3. **Tesseract OCR**:
   - macOS (Homebrew): `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`

---

## Installation

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/ARGONisg/Offsuit-BJ.git
cd Offsuit-BJ
pip install -r requirements.txt
```

---

## Usage

### 1. Run Live Bot
Ensure your Android device is connected via USB and the Blackjack game is open on screen:

```bash
python3 desktop_bot/bot.py
```

### 2. Coordinate Calibration & Detection Check
Inspect detection bounds and verify that dealer cards, player totals, buttons, and bankroll are properly recognized:

```bash
python3 desktop_bot/bot.py --calibrate
```

### 3. Test Button Taps
Verify hardware-level ADB touch events on available buttons:

```bash
python3 desktop_bot/bot.py --test-tap hit
python3 desktop_bot/bot.py --test-tap stand
python3 desktop_bot/bot.py --test-tap double
python3 desktop_bot/bot.py --test-tap split
```

### 4. Run Automated Test Suite
Run unit tests for the strategy engine, bankroll tracking, and OCR detectors:

```bash
python3 -m unittest desktop_bot/test_bot.py
```

---

## Logging & Statistics

- **Session Logs**: Stored under `desktop_bot/logs/bot_<timestamp>.log`. ANSI color codes are stripped for clean plaintext reading.
- **Master Summary**: Located at `desktop_bot/logs/master_summary.log`. Automatically tracks cumulative lifetime wins, losses, pushes, net profit, and win rates across sessions.
