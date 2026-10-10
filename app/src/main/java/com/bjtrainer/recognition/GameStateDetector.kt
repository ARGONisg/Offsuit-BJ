package com.bjtrainer.recognition

import android.content.res.Resources
import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import com.bjtrainer.core.Card
import com.bjtrainer.core.PlayerHand

object GameStateDetector {

    fun detect(rootNode: AccessibilityNodeInfo?): GameState {
        if (rootNode == null) return GameState(Phase.IDLE)
        
        val displayMetrics = Resources.getSystem().displayMetrics
        val screenHeight = displayMetrics.heightPixels
        val screenWidth = displayMetrics.widthPixels

        var hitBounds: Rect? = null
        var standBounds: Rect? = null
        var doubleBounds: Rect? = null
        var splitBounds: Rect? = null
        var dealerCardStr: String? = null
        var playerTotalStr: String? = null
        val playerCards = mutableListOf<String>()

        fun traverse(node: AccessibilityNodeInfo) {
            val text = node.text?.toString() ?: node.contentDescription?.toString()
            val rect = Rect()
            node.getBoundsInScreen(rect)

            if (!text.isNullOrBlank()) {
                val upper = text.uppercase().trim()
                val centerY = rect.centerY()

                // Bottom area (Action buttons)
                if (centerY > screenHeight * 0.70f) {
                    if (upper.contains("HIT") || upper == "+") {
                        hitBounds = Rect(rect)
                    }
                    if (upper.contains("STAND")) {
                        standBounds = Rect(rect)
                    }
                    if (upper.contains("DOUBLE")) {
                        doubleBounds = Rect(rect)
                    }
                    if (upper.contains("SPLIT")) {
                        splitBounds = Rect(rect)
                    }
                }

                // Top-middle area (Dealer card / total: between 12% and 45% screen height)
                if (centerY in (screenHeight * 0.12f).toInt()..(screenHeight * 0.45f).toInt()) {
                    if (upper.matches(Regex("^[2-9]$|^10$|^J$|^Q$|^K$|^A$"))) {
                        dealerCardStr = upper
                    }
                }

                // Center/Lower-middle area (Player hand total: between 50% and 82% screen height)
                if (centerY in (screenHeight * 0.50f).toInt()..(screenHeight * 0.82f).toInt()) {
                    if (upper.contains("/")) {
                        playerTotalStr = upper
                    } else if (upper.matches(Regex("^[0-9]{1,2}$"))) {
                        // Avoid bankroll or single chip counts
                        val num = upper.toIntOrNull()
                        if (num != null && num in 4..21) {
                            playerTotalStr = upper
                        }
                    } else if (upper.matches(Regex("^[2-9]$|^10$|^J$|^Q$|^K$|^A$"))) {
                        playerCards.add(upper)
                    }
                }
            }

            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { traverse(it) }
            }
        }

        traverse(rootNode)

        val phase = if (hitBounds != null || standBounds != null) Phase.PLAYING else Phase.IDLE
        val dealerCard = dealerCardStr?.let { Card.fromString(it) }

        val cardCount = if (playerCards.isNotEmpty()) playerCards.size else 2

        val totalStr = playerTotalStr
        val playerHand: PlayerHand? = when {
            // Check for Pair first if two cards detected and split is available
            playerCards.size == 2 && playerCards[0] == playerCards[1] && splitBounds != null -> {
                val card = Card.fromString(playerCards[0])
                PlayerHand.Pair(card?.value ?: 10, cardCount = 2)
            }
            totalStr != null && totalStr.contains("/") -> {
                val parts = totalStr.split("/")
                val softVal = parts[0].trim().toIntOrNull() ?: 0
                // e.g. "7/17" -> other card is 7 - 1 = 6 (A + 6)
                PlayerHand.Soft(otherCardValue = (softVal - 1).coerceAtLeast(1), cardCount = cardCount)
            }
            totalStr != null -> {
                val total = totalStr.toIntOrNull() ?: 0
                PlayerHand.Hard(total = total, cardCount = cardCount)
            }
            else -> null
        }

        return GameState(
            phase = phase,
            dealerUpcard = dealerCard,
            playerHand = playerHand,
            hitBounds = hitBounds,
            standBounds = standBounds,
            doubleBounds = doubleBounds,
            splitBounds = splitBounds
        )
    }
}
