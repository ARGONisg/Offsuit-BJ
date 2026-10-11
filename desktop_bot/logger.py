"""
Session Logger for Desktop Blackjack Bot.
Tees terminal output to both console (preserving ANSI colors) and a
timestamped log file in desktop_bot/logs/ (stripping ANSI color codes).
"""

import os
import re
import sys
import time
from typing import Optional


class BotLogger:
    """
    Redirects sys.stdout and sys.stderr to both terminal and a session log file.
    """
    _ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), "logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(self.log_dir, f"bot_{timestamp}.log")
        self._file = open(self.log_file_path, "a", encoding="utf-8")
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    def start(self):
        """Attaches logger to sys.stdout and sys.stderr."""
        sys.stdout = self
        sys.stderr = self

    def stop(self):
        """Restores original stdout and stderr and closes file."""
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        if self._file and not self._file.closed:
            self._file.flush()
            self._file.close()

    def write(self, data: str):
        # Write to real terminal with color
        self._orig_stdout.write(data)
        self._orig_stdout.flush()

        # Write to log file without ANSI escape codes
        clean_data = self._ANSI_ESCAPE_RE.sub("", data)
        self._file.write(clean_data)
        self._file.flush()

    def flush(self):
        self._orig_stdout.flush()
        if self._file and not self._file.closed:
            self._file.flush()

    def isatty(self):
        return getattr(self._orig_stdout, "isatty", lambda: False)()
