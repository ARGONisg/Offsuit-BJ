package com.bjtrainer.overlay

import android.content.Context
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import com.bjtrainer.R
import com.bjtrainer.automation.AutoPlayer

class OverlayManager(
    private val context: Context,
    private val isAccessibilityService: Boolean = true
) {
    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var overlayView: View? = null
    private var autoPlayer: AutoPlayer? = null

    val isShowing: Boolean
        get() = overlayView != null

    fun show(player: AutoPlayer?) {
        if (overlayView != null) return
        this.autoPlayer = player

        val view = LayoutInflater.from(context).inflate(R.layout.overlay_layout, null)
        overlayView = view

        val layoutFlag = if (isAccessibilityService) {
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutFlag,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 40
            y = 250
        }

        windowManager.addView(view, params)

        val tvStatus = view.findViewById<TextView>(R.id.tvStatus)
        val tvLastAction = view.findViewById<TextView>(R.id.tvLastAction)
        val btnToggle = view.findViewById<Button>(R.id.btnToggle)
        val btnClose = view.findViewById<Button>(R.id.btnClose)

        btnToggle.setOnClickListener {
            val p = autoPlayer
            if (p?.isRunning == true) {
                p.stop()
                btnToggle.text = "START"
            } else {
                p?.start()
                btnToggle.text = "PAUSE"
            }
        }

        btnClose.setOnClickListener {
            hide()
        }

        autoPlayer?.onStatusChange = { status ->
            tvStatus.post {
                tvStatus.text = status
                if (status.startsWith("Action:")) {
                    tvLastAction.text = status
                }
            }
        }

        // Draggable
        view.setOnTouchListener(object : View.OnTouchListener {
            private var initialX = 0
            private var initialY = 0
            private var initialTouchX = 0f
            private var initialTouchY = 0f

            override fun onTouch(v: View, event: MotionEvent): Boolean {
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initialX = params.x
                        initialY = params.y
                        initialTouchX = event.rawX
                        initialTouchY = event.rawY
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        params.x = initialX + (event.rawX - initialTouchX).toInt()
                        params.y = initialY + (event.rawY - initialTouchY).toInt()
                        try {
                            windowManager.updateViewLayout(view, params)
                        } catch (e: Exception) {
                            // View detached
                        }
                        return true
                    }
                }
                return false
            }
        })
    }

    fun hide() {
        overlayView?.let {
            try {
                windowManager.removeView(it)
            } catch (e: Exception) {
                // Ignore
            }
            overlayView = null
        }
    }
}
