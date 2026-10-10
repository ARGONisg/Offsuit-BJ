"""
8-Deck Blackjack Strategy Engine.
Includes:
- 8 decks shuffled fresh before each hand
- Double Down rules with intelligent fallback
- Pair splits with NO RESPLIT constraint
- 5-Card Charlie rule (auto-win on 5 cards under 22; safe hit on 4 cards)
- Fallback actions when Double or Split is disallowed
"""

from enum import Enum
from typing import Optional


class Action(str, Enum):
    HIT = "HIT"
    STAND = "STAND"
    DOUBLE_DOWN = "DOUBLE"
    SPLIT = "SPLIT"


class Card(int, Enum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    ACE = 11

    @classmethod
    def from_str(cls, text: str) -> "Card":
        clean = text.strip().upper()
        if clean in ("A", "ACE", "1", "11"):
            return cls.ACE
        if clean in ("K", "Q", "J", "10", "TEN"):
            return cls.TEN
        val_map = {
            "2": cls.TWO, "3": cls.THREE, "4": cls.FOUR,
            "5": cls.FIVE, "6": cls.SIX, "7": cls.SEVEN,
            "8": cls.EIGHT, "9": cls.NINE
        }
        return val_map.get(clean, cls.TEN)


def get_hard_action(total: int, dealer_card: Card) -> Action:
    if total >= 17:
        return Action.STAND
    if 13 <= total <= 16:
        if dealer_card in (Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX):
            return Action.STAND
        return Action.HIT
    if total == 12:
        if dealer_card in (Card.FOUR, Card.FIVE, Card.SIX):
            return Action.STAND
        return Action.HIT
    if total == 11:
        # 8-deck: double vs 2-10 only; HIT vs Ace
        if dealer_card == Card.ACE:
            return Action.HIT
        return Action.DOUBLE_DOWN
    if total == 10:
        if dealer_card in (Card.TEN, Card.ACE):
            return Action.HIT
        return Action.DOUBLE_DOWN
    if total == 9:
        # 8-deck: double vs 3-6 only
        if dealer_card in (Card.THREE, Card.FOUR, Card.FIVE, Card.SIX):
            return Action.DOUBLE_DOWN
        return Action.HIT
    # Hard 8 and below: always HIT in 8-deck (no doubling)
    return Action.HIT  # 5..8


def get_soft_action(other_card: int, dealer_card: Card) -> Action:
    # other_card is total - 11 (e.g. for Soft 17, other_card = 6; for Soft 18, other_card = 7)
    if other_card >= 9:  # Soft 20, 21
        return Action.STAND
    if other_card == 8:  # Soft 19
        # 8-deck: stand (do not double Soft 19)
        return Action.STAND
    if other_card == 7:  # Soft 18
        # 8-deck: double vs 2-6, stand vs 7-8, hit vs 9-10-A
        if dealer_card in (Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX):
            return Action.DOUBLE_DOWN
        if dealer_card in (Card.SEVEN, Card.EIGHT):
            return Action.STAND
        return Action.HIT  # vs 9, 10, Ace
    if other_card == 6:  # Soft 17
        # 8-deck: double vs 3-6 only
        if dealer_card in (Card.THREE, Card.FOUR, Card.FIVE, Card.SIX):
            return Action.DOUBLE_DOWN
        return Action.HIT
    if other_card == 5 or other_card == 4:  # Soft 15, 16
        # 8-deck: double vs 4-6
        if dealer_card in (Card.FOUR, Card.FIVE, Card.SIX):
            return Action.DOUBLE_DOWN
        return Action.HIT
    if other_card == 3 or other_card == 2:  # Soft 13, 14
        # 8-deck: double vs 5-6 only
        if dealer_card in (Card.FIVE, Card.SIX):
            return Action.DOUBLE_DOWN
        return Action.HIT
    return Action.HIT  # Soft 12 (A,A)


def get_pair_action(card_value: int, dealer_card: Card) -> Action:
    if card_value in (1, 11, 8):  # Aces or 8s — always split
        return Action.SPLIT
    if card_value == 10:
        return Action.STAND
    if card_value == 9:
        # 8-deck: split vs 2-6, 8-9; stand vs 7, 10, Ace
        if dealer_card in (Card.SEVEN, Card.TEN, Card.ACE):
            return Action.STAND
        return Action.SPLIT
    if card_value == 7:
        # 8-deck: split vs 2-7; hit otherwise
        if dealer_card in (Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX, Card.SEVEN):
            return Action.SPLIT
        return Action.HIT
    if card_value == 6:
        # 8-deck: split vs 2-6; hit otherwise
        if dealer_card in (Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX):
            return Action.SPLIT
        return Action.HIT
    if card_value == 5:
        # Treat 5,5 as Hard 10 — never split
        if dealer_card in (Card.TEN, Card.ACE):
            return Action.HIT
        return Action.DOUBLE_DOWN
    if card_value == 4:
        # 8-deck: never split 4s; always HIT
        return Action.HIT
    if card_value in (2, 3):
        # 8-deck: split vs 2-7
        if dealer_card in (Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX, Card.SEVEN):
            return Action.SPLIT
        return Action.HIT
    return Action.HIT


def get_action(
    is_soft: bool,
    total: int,
    dealer_card: Card,
    is_pair: bool = False,
    pair_val: int = 0,
    card_count: int = 2,
    can_double: bool = True,
    can_split: bool = True,
    has_split_already: bool = False
) -> Action:
    """
    Evaluates optimal action considering 5-card Charlie, no-resplit, and fallbacks.
    """
    # 5-Card Charlie: 5 cards without busting is an automatic win
    if card_count >= 5 and total <= 21:
        return Action.STAND

    # Safe pursuit of 5-card Charlie
    if card_count == 4 and total <= 11:
        return Action.HIT

    # Pairs
    if is_pair and can_split and not has_split_already:
        action = get_pair_action(pair_val, dealer_card)
        if action == Action.SPLIT:
            return Action.SPLIT
        # If strategy said DOUBLE/STAND/HIT on pair:
        if action == Action.DOUBLE_DOWN and not can_double:
            return Action.HIT
        return action

    # Soft hand
    if is_soft:
        other_card = total - 11
        action = get_soft_action(other_card, dealer_card)
        if action == Action.DOUBLE_DOWN and not can_double:
            # Fallback for soft double
            if other_card >= 7:  # Soft 18
                return Action.STAND
            return Action.HIT
        return action

    # Hard hand
    action = get_hard_action(total, dealer_card)
    if action == Action.DOUBLE_DOWN and not can_double:
        return Action.HIT
    return action
