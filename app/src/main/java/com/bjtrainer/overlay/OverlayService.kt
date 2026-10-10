package com.bjtrainer.overlay

import android.app.Service
import android.content.Intent
import android.os.IBinder
import com.bjtrainer.service.BjAccessibilityService

class OverlayService : Service() {

    private var overlayManager: OverlayManager? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        overlayManager = OverlayManager(this, isAccessibilityService = false)
        overlayManager?.show(BjAccessibilityService.instance?.autoPlayer)
    }

    override fun onDestroy() {
        super.onDestroy()
        overlayManager?.hide()
        overlayManager = null
    }
}
