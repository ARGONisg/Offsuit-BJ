"""
Session Bankroll and Win/Loss/Push Tracker for Offsuit Blackjack Bot.

Reads bankroll at PLAYING phase (when HIT/STAND buttons are visible) so
the bet is already deducted and the previous hand's payout is settled.
Delta between consecutive readings = true profit from each hand.
"""

from typing import Optional, Dict, Any


class BankrollTracker:
    def __init__(self, bet_size: int = 10, auto_decompose: bool = True):
        self.bet_size = bet_size
        self.auto_decompose = auto_decompose
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

    def update(self, chips: int, was_double: bool = False) -> Optional[Dict[str, Any]]:
        """
        Called once per hand at PLAYING phase start (buttons visible).
        Delta between consecutive calls = true profit from previous hand(s).
        Returns a result dict if a hand completed, else None (first reading / invalid).
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

        if not self.auto_decompose:
            self.hands_played += 1
            if delta == 0:
                self.pushes += 1
                outcome = "PUSH"
            elif delta > 0:
                self.wins += 1
                outcome = self._classify_win(delta)
            else:
                self.losses += 1
                outcome = self._classify_loss(delta)
        else:
            outcome = self._decompose_delta(delta, was_double=was_double)

        return {
            "outcome": outcome,
            "delta": delta,
            "chips": chips,
            "net_profit": self.net_profit,
            "win_rate": self.win_rate,
            "hands": self.hands_played,
        }

    def _decompose_delta(self, delta: int, was_double: bool = False) -> str:
        """
        Decomposes composite deltas into individual hands, wins, losses, blackjacks, and pushes.
        Handles fast auto-deal sequences (e.g. -50 = 5 losses, +45 = BJ + 3 wins).
        """
        if delta == 0:
            self.pushes += 1
            self.hands_played += 1
            return "PUSH"

        b = self.bet_size
        if b <= 0:
            if delta > 0:
                self.wins += 1
                self.hands_played += 1
                return "WIN"
            else:
                self.losses += 1
                self.hands_played += 1
                return "LOSS"

        # Check for explicit Double Down outcome on a single hand
        if was_double:
            if delta == 2 * b:
                self.doubles_won += 1
                self.wins += 1
                self.hands_played += 1
                return "DOUBLE WIN"
            elif delta == -2 * b:
                self.doubles_lost += 1
                self.losses += 1
                self.hands_played += 1
                return "DOUBLE LOSS"

        # Check for 3:2 Blackjack remainder (+1.5 * bet_size, e.g. +15 chips on 10 bet)
        bj_value = int(1.5 * b)
        bj_rem = bj_value % b  # e.g. 5 when b=10
        bj_count = 0
        rem_delta = delta

        if bj_rem != 0 and (abs(delta) % b == bj_rem):
            # A 3:2 payout accounts for the fractional bet remainder
            bj_count = 1
            self.blackjacks += 1
            self.wins += 1
            self.hands_played += 1
            rem_delta = delta - bj_value

        # Integer number of standard bet units in remainder (using round to tolerate minor OCR noise)
        n_bets = int(round(rem_delta / b))

        if n_bets > 0:
            self.wins += n_bets
            self.hands_played += n_bets
        elif n_bets < 0:
            n_losses = abs(n_bets)
            self.losses += n_losses
            self.hands_played += n_losses

        # Format descriptive outcome string
        parts = []
        if bj_count > 0:
            parts.append("BLACKJACK")
        if n_bets > 0:
            if n_bets == 1 and bj_count == 0:
                parts.append("WIN")
            elif n_bets == 2 and bj_count == 0 and was_double:
                self.doubles_won += 1
                parts.append("DOUBLE WIN")
            else:
                parts.append(f"{n_bets}x WIN")
        elif n_bets < 0:
            n_losses = abs(n_bets)
            if n_losses == 1 and bj_count == 0:
                parts.append("LOSS")
            elif n_losses == 2 and bj_count == 0 and was_double:
                self.doubles_lost += 1
                parts.append("DOUBLE LOSS")
            else:
                parts.append(f"{n_losses}x LOSS")

        return " + ".join(parts) if parts else "PUSH"

    def record_push(self, chips: Optional[int] = None) -> Optional[dict]:
        """Record a push outcome (either explicitly or via same-chip update)."""
        if chips is not None:
            return self.update(chips)
        self.pushes += 1
        self.hands_played += 1
        return None

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
