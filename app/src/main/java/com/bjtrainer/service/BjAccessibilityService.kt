package com.bjtrainer.service

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.bjtrainer.automation.AutoPlayer
import com.bjtrainer.overlay.OverlayManager
import com.bjtrainer.recognition.GameStateDetector

class BjAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "BjAccessibility"
        var instance: BjAccessibilityService? = null
    }

    val autoPlayer by lazy { AutoPlayer(this) }
    private var overlayManager: OverlayManager? = null
    private var dumpCount = 0

    // Polling mechanism
    private val pollHandler = Handler(Looper.getMainLooper())
    private val pollInterval = 800L
    private val pollRunnable = object : Runnable {
        override fun run() {
            if (autoPlayer.isRunning) {
                pollScreen()
            }
            pollHandler.postDelayed(this, pollInterval)
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        overlayManager = OverlayManager(this, isAccessibilityService = true)
        pollHandler.postDelayed(pollRunnable, pollInterval)
        Log.d(TAG, "Service connected, polling started")
    }

    fun showOverlay() {
        if (overlayManager == null) {
            overlayManager = OverlayManager(this, isAccessibilityService = true)
        }
        overlayManager?.show(autoPlayer)
    }

    fun hideOverlay() {
        overlayManager?.hide()
    }

    private fun pollScreen() {
        try {
            val rootNode = rootInActiveWindow ?: run {
                Log.d(TAG, "rootInActiveWindow is NULL")
                return
            }

            // Dump full tree every 5th poll (to avoid log spam)
            dumpCount++
            if (dumpCount % 5 == 1) {
                Log.d(TAG, "===== ACCESSIBILITY TREE DUMP (poll #$dumpCount) =====")
                dumpNode(rootNode, 0)
                Log.d(TAG, "===== END DUMP =====")
            }

            val state = GameStateDetector.detect(rootNode)
            Log.d(TAG, "State: phase=${state.phase}, dealer=${state.dealerUpcard?.rank}, hand=${state.playerHand}, hit=${state.hitBounds != null}, stand=${state.standBounds != null}, double=${state.doubleBounds != null}, split=${state.splitBounds != null}")
            autoPlayer.processState(state)
            rootNode.recycle()
        } catch (e: Exception) {
            Log.e(TAG, "Poll error: ${e.message}", e)
        }
    }

    private fun dumpNode(node: AccessibilityNodeInfo, depth: Int) {
        val indent = "  ".repeat(depth)
        val rect = android.graphics.Rect()
        node.getBoundsInScreen(rect)
        val cls = node.className?.toString() ?: "null"
        val text = node.text?.toString()
        val desc = node.contentDescription?.toString()
        val viewId = node.viewIdResourceName?.toString()
        val clickable = node.isClickable
        val enabled = node.isEnabled

        val info = buildString {
            append("${indent}[$cls]")
            if (viewId != null) append(" id=$viewId")
            if (text != null) append(" text=\"$text\"")
            if (desc != null) append(" desc=\"$desc\"")
            append(" bounds=$rect")
            if (clickable) append(" CLICKABLE")
            if (!enabled) append(" DISABLED")
        }
        Log.d(TAG, info)

        for (i in 0 until node.childCount) {
            val child = node.getChild(i)
            if (child != null) {
                dumpNode(child, depth + 1)
            }
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (autoPlayer.isRunning) {
            pollScreen()
        }
    }

    override fun onInterrupt() {
        autoPlayer.stop()
    }

    override fun onUnbind(intent: Intent?): Boolean {
        pollHandler.removeCallbacks(pollRunnable)
        overlayManager?.hide()
        overlayManager = null
        autoPlayer.stop()
        instance = null
        return super.onUnbind(intent)
    }
}
