"""
ADB Controller for Android Device Automation.
Handles device detection, screen resolution query, fast screenshot capture,
and physical input taps.
"""

import os
import re
import subprocess
from typing import Optional, Tuple


class AdbController:
    def __init__(self, adb_path: Optional[str] = None):
        self.adb_path = adb_path or self._find_adb()
        self.width = 1080
        self.height = 2400
        self._update_screen_size()

    def _find_adb(self) -> str:
        candidates = [
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            "/opt/homebrew/bin/adb",
            "/usr/local/bin/adb",
            "adb"
        ]
        for c in candidates:
            if os.path.isabs(c) and os.path.exists(c) and os.access(c, os.X_OK):
                return c
        # Fallback to whatever is on PATH
        return "adb"

    def run_cmd(self, args: list, check: bool = True) -> subprocess.CompletedProcess:
        cmd = [self.adb_path] + args
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)

    def is_connected(self) -> bool:
        try:
            res = self.run_cmd(["devices"])
            lines = res.stdout.decode().strip().splitlines()
            # First line is 'List of devices attached'
            devices = [l for l in lines[1:] if "\tdevice" in l]
            return len(devices) > 0
        except Exception:
            return False

    def _update_screen_size(self):
        try:
            res = self.run_cmd(["shell", "wm", "size"])
            out = res.stdout.decode()
            # Physical size: 1080x2400 or Override size: ...
            match = re.search(r"(\d+)x(\d+)", out)
            if match:
                self.width = int(match.group(1))
                self.height = int(match.group(2))
        except Exception:
            pass

    def get_screen_size(self) -> Tuple[int, int]:
        return self.width, self.height

    def capture_screenshot(self, output_png_path: str) -> bool:
        """Captures raw screen directly into a PNG file via adb exec-out."""
        try:
            with open(output_png_path, "wb") as f:
                cmd = [self.adb_path, "exec-out", "screencap", "-p"]
                subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
            return os.path.exists(output_png_path) and os.path.getsize(output_png_path) > 0
        except Exception as e:
            print(f"[ADB Error] Screencap failed: {e}")
            return False

    def tap(self, x: int, y: int):
        """Dispatches an instant hardware-level touch event."""
        cmd = ["shell", "input", "tap", str(int(x)), str(int(y))]
        self.run_cmd(cmd, check=False)

    def tap_normalized(self, norm_x: float, norm_y: float):
        """Converts normalized (0.0 .. 1.0) coordinates to screen pixels and taps."""
        px_x = int(norm_x * self.width)
        px_y = int(norm_y * self.height)
        self.tap(px_x, px_y)
