"""
Session Bankroll and Win/Loss/Push Tracker for Offsuit Blackjack Bot.
Tracks hands played, wins, losses, pushes, win percentage, and net chips profit.
"""

from typing import Optional, Dict, Any


class BankrollTracker:
    def __init__(self, initial_chips: Optional[int] = None):
        self.start_bankroll: Optional[int] = initial_chips
        self.last_bankroll: Optional[int] = initial_chips
        self.current_bankroll: Optional[int] = initial_chips
        self.hands_played: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.pushes: int = 0

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

    def update(self, chips: int, hand_completed: bool = False) -> Optional[Dict[str, Any]]:
        """
        Updates tracker with new detected chip balance.
        If hand_completed is True and delta is 0, records a PUSH.
        Returns a dict describing the outcome if a hand completed, else None.
        """
        if chips <= 0:
            return None

        # Initial reading
        if self.start_bankroll is None:
            self.start_bankroll = chips
            self.last_bankroll = chips
            self.current_bankroll = chips
            return None

        self.current_bankroll = chips

        # Check delta against last recorded hand
        delta = chips - self.last_bankroll
        if delta == 0:
            if hand_completed:
                self.hands_played += 1
                self.pushes += 1
                return {
                    "outcome": "PUSH",
                    "delta": 0,
                    "chips": chips,
                    "net_profit": self.net_profit,
                    "win_rate": self.win_rate,
                    "hands": self.hands_played,
                }
            return None

        self.hands_played += 1
        if delta > 0:
            outcome = "WIN"
            self.wins += 1
        else:
            outcome = "LOSS"
            self.losses += 1

        self.last_bankroll = chips

        return {
            "outcome": outcome,
            "delta": delta,
            "chips": chips,
            "net_profit": self.net_profit,
            "win_rate": self.win_rate,
            "hands": self.hands_played,
        }

    def record_push(self, chips: int):
        """Records a completed push (tie) where chip balance did not change."""
        self.hands_played += 1
        self.pushes += 1
        self.current_bankroll = chips
        self.last_bankroll = chips

    def format_summary(self) -> str:
        """Returns a formatted summary dashboard block."""
        c_start = f"{self.start_bankroll:,}" if self.start_bankroll is not None else "N/A"
        c_curr = f"{self.current_bankroll:,}" if self.current_bankroll is not None else "N/A"
        sign = "+" if self.net_profit > 0 else ""
        profit_str = f"{sign}{self.net_profit:,}"
        
        lines = [
            "--------------------------------------------------",
            f" [SESSION STATS] Hands: {self.hands_played} | W: {self.wins} | L: {self.losses} | P: {self.pushes}",
            f" Win Rate: {self.win_rate:.1f}% | Net Profit: {profit_str} chips",
            f" Starting: {c_start} | Current: {c_curr}",
            "--------------------------------------------------"
        ]
        return "\n".join(lines)
