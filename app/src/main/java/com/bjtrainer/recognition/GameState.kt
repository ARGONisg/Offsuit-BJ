package com.bjtrainer.recognition

import android.graphics.Rect
import com.bjtrainer.core.Card
import com.bjtrainer.core.PlayerHand

enum class Phase {
    IDLE, BETTING, PLAYING, DEALER_TURN_OR_SETTLING
}

data class GameState(
    val phase: Phase,
    val dealerUpcard: Card? = null,
    val playerHand: PlayerHand? = null,
    val hitBounds: Rect? = null,
    val standBounds: Rect? = null,
    val doubleBounds: Rect? = null,
    val splitBounds: Rect? = null
) {
    val canHit: Boolean get() = hitBounds != null
    val canStand: Boolean get() = standBounds != null
    val canDouble: Boolean get() = doubleBounds != null
    val canSplit: Boolean get() = splitBounds != null
}
