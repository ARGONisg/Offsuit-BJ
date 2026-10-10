package com.bjtrainer.core

object BlackjackStrategy {

    // Evaluates strategy handling 5-card charlie and fallback options
    fun getAction(
        hand: PlayerHand, 
        dealerCard: Card, 
        canDouble: Boolean, 
        canSplit: Boolean
    ): Action {
        
        // 5-Card Charlie rule: if we have 5 cards without busting, we auto-win / stand.
        if (hand.cardCount >= 5) {
            return Action.STAND
        }

        // 5-Card Charlie pursuit: if we have 4 cards and total is low enough, hit is safe and good.
        if (hand.cardCount == 4) {
            val currentTotal = when (hand) {
                is PlayerHand.Hard -> hand.total
                is PlayerHand.Soft -> hand.otherCardValue + 11 // Soft max
                is PlayerHand.Pair -> hand.cardValue * 2
            }
            if (currentTotal <= 11) {
                return Action.HIT
            }
        }

        val action = when (hand) {
            is PlayerHand.Hard -> getHardAction(hand.total, dealerCard)
            is PlayerHand.Soft -> getSoftAction(hand.otherCardValue, dealerCard)
            is PlayerHand.Pair -> {
                if (canSplit) {
                    getPairAction(hand.cardValue, dealerCard)
                } else {
                    // Fallback to Hard/Soft if we cannot split (no resplit rule)
                    if (hand.cardValue == 11) {
                        getSoftAction(11, dealerCard) // A,A -> Soft 12 (11 + 1) -> Actually A,A is soft 12 so otherCard=1
                    } else {
                        getHardAction(hand.cardValue * 2, dealerCard)
                    }
                }
            }
        }

        return fallback(action, canDouble, canSplit)
    }

    private fun fallback(action: Action, canDouble: Boolean, canSplit: Boolean): Action {
        if (action == Action.DOUBLE_DOWN && !canDouble) {
            return Action.HIT // Simplification: standard hit fallback, actual soft 18 fallback is STAND against 2-8
        }
        if (action == Action.SPLIT && !canSplit) {
            return Action.HIT // Usually pair splits fallback to hit/stand based on hard total
        }
        return action
    }

    private fun getHardAction(total: Int, dealerCard: Card): Action = when {
        total >= 17 -> Action.STAND
        total in 13..16 -> when (dealerCard) {
            Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX -> Action.STAND
            else -> Action.HIT
        }
        total == 12 -> when (dealerCard) {
            Card.FOUR, Card.FIVE, Card.SIX -> Action.STAND
            else -> Action.HIT
        }
        total == 11 -> Action.DOUBLE_DOWN
        total == 10 -> when (dealerCard) {
            Card.TEN, Card.ACE -> Action.HIT
            else -> Action.DOUBLE_DOWN
        }
        total == 9 -> when (dealerCard) {
            Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            else -> Action.HIT
        }
        total == 8 -> when (dealerCard) {
            Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            else -> Action.HIT
        }
        else -> Action.HIT // Hard totals 5 through 7
    }

    private fun getSoftAction(otherCard: Int, dealerCard: Card): Action = when (otherCard) {
        9, 10 -> Action.STAND
        8 -> if (dealerCard == Card.SIX) Action.DOUBLE_DOWN else Action.STAND
        7 -> when (dealerCard) {
            Card.THREE, Card.FOUR, Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            Card.TWO, Card.SEVEN, Card.EIGHT, Card.ACE -> Action.STAND
            else -> Action.HIT // 9, 10
        }
        6 -> when (dealerCard) {
            Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            else -> Action.HIT
        }
        in 2..5 -> when (dealerCard) {
            Card.FOUR, Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            else -> Action.HIT
        }
        1 -> Action.HIT // Soft 12 (A,A) fallback
        else -> Action.HIT
    }

    private fun getPairAction(cardValue: Int, dealerCard: Card): Action = when (cardValue) {
        1, 11, 8 -> Action.SPLIT // Ace-Ace or 8-8
        10 -> Action.STAND        // 10-10
        9 -> when (dealerCard) {
            Card.SEVEN, Card.TEN, Card.ACE -> Action.STAND
            else -> Action.SPLIT
        }
        7 -> when (dealerCard) {
            Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX, Card.SEVEN -> Action.SPLIT
            Card.TEN -> Action.STAND
            else -> Action.HIT
        }
        6 -> when (dealerCard) {
            Card.TWO, Card.THREE, Card.FOUR, Card.FIVE, Card.SIX -> Action.SPLIT
            else -> Action.HIT
        }
        5 -> when (dealerCard) {
            Card.TEN, Card.ACE -> Action.HIT
            else -> Action.DOUBLE_DOWN
        }
        4 -> when (dealerCard) {
            Card.FIVE, Card.SIX -> Action.DOUBLE_DOWN
            else -> Action.HIT
        }
        3 -> when (dealerCard) {
            Card.FOUR, Card.FIVE, Card.SIX, Card.SEVEN -> Action.SPLIT
            else -> Action.HIT
        }
        2 -> when (dealerCard) {
            Card.THREE, Card.FOUR, Card.FIVE, Card.SIX, Card.SEVEN -> Action.SPLIT
            else -> Action.HIT
        }
        else -> Action.HIT
    }
}
