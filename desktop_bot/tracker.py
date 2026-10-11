"""
Session Bankroll and Win/Loss/Push Tracker for Offsuit Blackjack Bot.

Reads bankroll at PLAYING phase (when HIT/STAND buttons are visible) so
the bet is already deducted and the previous hand's payout is settled.
Delta between consecutive readings = true profit from each hand.
"""

from typing import Optional, Dict, Any


class BankrollTracker:
    def __init__(self, bet_size: int = 10):
        self.bet_size = bet_size
        self.start_bankroll: Optional[int] = None
        self.last_bankroll: Optional[int] = None
        self.current_bankroll: Optional[int] = None
        self.hands_played: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.pushes: int = 0
        self.blackjacks: int = 0
        self.doubles_won: int = 0
        self.doubles_lost: int = 0

    @property
    def net_profit(self) -> int:
        if self.start_bankroll is None or self.current_bankroll is None:
            return 0
        return self.current_bankroll - self.start_bankroll

    @property
    def win_rate(self) -> float:
        decided = self.wins + self.losses
        if decided == 0:
            return 0.0
        return (self.wins / decided) * 100.0

    def update(self, chips: int) -> Optional[Dict[str, Any]]:
        """
        Called once per hand at PLAYING phase start (buttons visible).
        Delta between consecutive calls = true profit from previous hand.
        Returns a result dict if a hand completed, else None (first reading).
        """
        if chips <= 0:
            return None

        # OCR sanity filter: reject readings wildly different from last
        if self.last_bankroll is not None:
            delta = chips - self.last_bankroll
            if abs(delta) > self.bet_size * 50:
                return None  # Skip obvious OCR misread

        # First reading — initialise baseline
        if self.start_bankroll is None:
            self.start_bankroll = chips
            self.last_bankroll = chips
            self.current_bankroll = chips
            return None

        self.current_bankroll = chips
        delta = chips - self.last_bankroll
        self.last_bankroll = chips

        self.hands_played += 1

        # Classify outcome from delta
        if delta == 0:
            self.pushes += 1
            outcome = "PUSH"
        elif delta > 0:
            self.wins += 1
            outcome = self._classify_win(delta)
        else:
            self.losses += 1
            outcome = self._classify_loss(delta)

        return {
            "outcome": outcome,
            "delta": delta,
            "chips": chips,
            "net_profit": self.net_profit,
            "win_rate": self.win_rate,
            "hands": self.hands_played,
        }

    def _classify_win(self, delta: int) -> str:
        """Infer win type from delta/bet ratio."""
        if self.bet_size <= 0:
            return "WIN"
        ratio = delta / self.bet_size
        if 1.3 <= ratio <= 1.7:
            self.blackjacks += 1
            return "BLACKJACK"
        if 1.8 <= ratio <= 2.2:
            self.doubles_won += 1
            return "DOUBLE WIN"
        return "WIN"

    def _classify_loss(self, delta: int) -> str:
        """Infer loss type from delta/bet ratio."""
        if self.bet_size <= 0:
            return "LOSS"
        ratio = abs(delta) / self.bet_size
        if 1.8 <= ratio <= 2.2:
            self.doubles_lost += 1
            return "DOUBLE LOSS"
        return "LOSS"

    def format_summary(self) -> str:
        """Returns a formatted summary dashboard block."""
        c_start = f"{self.start_bankroll:,}" if self.start_bankroll is not None else "N/A"
        c_curr = f"{self.current_bankroll:,}" if self.current_bankroll is not None else "N/A"
        sign = "+" if self.net_profit > 0 else ""
        profit_str = f"{sign}{self.net_profit:,}"

        lines = [
            "--------------------------------------------------",
            f" [SESSION STATS] Hands: {self.hands_played} | W: {self.wins} | L: {self.losses} | P: {self.pushes}",
            f" BJ: {self.blackjacks} | Dbl W: {self.doubles_won} | Dbl L: {self.doubles_lost}",
            f" Win Rate: {self.win_rate:.1f}% | Net Profit: {profit_str} chips",
            f" Starting: {c_start} | Current: {c_curr}",
            "--------------------------------------------------"
        ]
        return "\n".join(lines)
