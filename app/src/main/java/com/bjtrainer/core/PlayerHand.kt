package com.bjtrainer.core

sealed interface PlayerHand {
    val cardCount: Int

    data class Hard(val total: Int, override val cardCount: Int) : PlayerHand
    data class Soft(val otherCardValue: Int, override val cardCount: Int) : PlayerHand // e.g., Soft(7) represents (A, 7)
    data class Pair(val cardValue: Int, override val cardCount: Int) : PlayerHand     // e.g., Pair(8) represents (8, 8)
}
