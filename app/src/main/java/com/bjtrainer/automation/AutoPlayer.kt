package com.bjtrainer.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.util.Log
import com.bjtrainer.core.Action
import com.bjtrainer.core.BlackjackStrategy
import com.bjtrainer.recognition.GameState
import com.bjtrainer.recognition.Phase

class AutoPlayer(private val service: AccessibilityService) {

    companion object {
        private const val TAG = "AutoPlayer"
    }

    var isRunning = false
    var onStatusChange: ((String) -> Unit)? = null

    // Debounce: prevent acting on the same state twice
    private var lastActionTime = 0L
    private val ACTION_COOLDOWN_MS = 1500L

    fun start() {
        if (isRunning) return
        isRunning = true
        onStatusChange?.invoke("Status: RUNNING")
        Log.d(TAG, "AutoPlayer STARTED")
    }

    fun stop() {
        isRunning = false
        onStatusChange?.invoke("Status: PAUSED")
        Log.d(TAG, "AutoPlayer STOPPED")
    }

    fun processState(state: GameState) {
        if (!isRunning) return

        if (state.phase != Phase.PLAYING) {
            onStatusChange?.invoke("Status: WAITING FOR DEAL")
            return
        }

        val hand = state.playerHand
        val dealer = state.dealerUpcard

        if (hand == null || dealer == null) {
            onStatusChange?.invoke("Status: READING CARDS...")
            return
        }

        // Cooldown check
        val now = System.currentTimeMillis()
        if (now - lastActionTime < ACTION_COOLDOWN_MS) {
            return
        }

        val action = BlackjackStrategy.getAction(hand, dealer, state.canDouble, state.canSplit)
        val statusMsg = "Action: $action vs Dealer ${dealer.rank}"
        onStatusChange?.invoke(statusMsg)
        Log.d(TAG, statusMsg)
        Log.d(TAG, "Hand=$hand, Dealer=${dealer.rank}, canDouble=${state.canDouble}, canSplit=${state.canSplit}")
        Log.d(TAG, "Bounds -> Hit=${state.hitBounds}, Stand=${state.standBounds}, Double=${state.doubleBounds}, Split=${state.splitBounds}")

        val targetBounds: Rect? = when (action) {
            Action.HIT -> state.hitBounds
            Action.STAND -> state.standBounds
            Action.DOUBLE_DOWN -> state.doubleBounds ?: state.hitBounds
            Action.SPLIT -> state.splitBounds ?: state.hitBounds
        }

        if (targetBounds != null) {
            lastActionTime = now
            val x = targetBounds.centerX().toFloat()
            val y = targetBounds.centerY().toFloat()
            Log.d(TAG, "TAPPING $action at ($x, $y) bounds=$targetBounds")
            tap(x, y)
        } else {
            Log.w(TAG, "No bounds found for action $action!")
            onStatusChange?.invoke("WARN: No button for $action")
        }
    }

    private fun tap(x: Float, y: Float) {
        val path = Path()
        path.moveTo(x, y)
        val stroke = GestureDescription.StrokeDescription(path, 0, 100)
        val gesture = GestureDescription.Builder()
            .addStroke(stroke)
            .build()

        service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Gesture COMPLETED at ($x, $y)")
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                Log.w(TAG, "Gesture CANCELLED at ($x, $y)")
            }
        }, null)
    }
}
