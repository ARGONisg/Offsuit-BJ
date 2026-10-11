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

1. **Python 3.9+**: Install the single external dependency: `pip install "Pillow>=10.0.0"` (or `pip install -r requirements.txt`).
2. **Android Debug Bridge (ADB)** (USB or Wireless):
   - macOS: `brew install android-platform-tools`
   - Linux: `sudo apt install adb`
   - Windows: Install Android SDK Platform Tools and add `adb` to your `PATH`.
   - **USB Connection**: Enable **USB Debugging** in Developer Options and connect your device.
   - **Wireless ADB**:
     - *Android 11+*: Enable **Wireless debugging** in Developer Options, then pair and connect:
       ```bash
       adb pair <device-ip>:<pairing-port> <pairing-code>
       adb connect <device-ip>:<port>
       ```
     - *Classic TCP/IP*: Connect device via USB once, start TCP mode:
       ```bash
       adb tcpip 5555
       # Unplug USB cable, then connect wirelessly:
       adb connect <device-ip>:5555
       ```
3. **Tesseract OCR**:
   - macOS: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
   - Windows: Install Tesseract binary and add to `PATH` (or pass `--tesseract-path`).

---

## Installation

### For Humans

```bash
git clone https://github.com/ARGONisg/Offsuit-BJ.git
cd Offsuit-BJ
pip install -r requirements.txt
```

### For AI Agents & Autonomous Runners

```bash
# 1. Install dependencies non-interactively
pip install -q -r requirements.txt

# 2. Verify environment & toolchain
python3 -c "import PIL; print('Pillow OK')"
adb version
tesseract --version

# 3. Verify device connection (if physical device attached)
adb devices

# 4. Run automated test suite to validate strategy engine and OCR detectors
python3 -m unittest desktop_bot/test_bot.py
```

---

## Usage

### 1. Run Live Bot
Ensure your Android device is connected via ADB by running `adb devices` and the Blackjack game is open on screen:

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

---

## Disclaimer

> **DISCLAIMER**: This software is provided strictly for educational, research, and algorithmic analysis purposes. Automating gameplay may violate the Terms of Service of third-party platforms or mobile applications. The author(s) and contributor(s) assume no responsibility or liability for account penalties, suspensions, or financial losses incurred through the use of this software. No real-money gambling guarantees or warranties are expressed or implied. Tested only on MacBook Air. Use entirely at your own risk.


