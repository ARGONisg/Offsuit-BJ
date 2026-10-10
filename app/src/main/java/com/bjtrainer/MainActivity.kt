package com.bjtrainer

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.bjtrainer.service.BjAccessibilityService

class MainActivity : AppCompatActivity() {

    private lateinit var btnAccessibility: Button
    private lateinit var btnOverlay: Button
    private lateinit var btnStartOverlay: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        btnAccessibility = findViewById(R.id.btnAccessibility)
        btnOverlay = findViewById(R.id.btnOverlay)
        btnStartOverlay = findViewById(R.id.btnStartOverlay)

        btnAccessibility.setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        }

        btnOverlay.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                try {
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName")
                    )
                    startActivity(intent)
                } catch (e: ActivityNotFoundException) {
                    val fallbackIntent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
                    startActivity(fallbackIntent)
                }
            }
        }

        btnStartOverlay.setOnClickListener {
            val service = BjAccessibilityService.instance
            if (service != null) {
                // Accessibility is granted! The accessibility service can show overlays
                // natively using TYPE_ACCESSIBILITY_OVERLAY without needing SYSTEM_ALERT_WINDOW.
                service.showOverlay()
                Toast.makeText(this, "Overlay Started! Switch to Blackjack game.", Toast.LENGTH_SHORT).show()
                moveTaskToBack(true)
            } else {
                Toast.makeText(this, "Please enable Accessibility Service first!", Toast.LENGTH_LONG).show()
                val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                startActivity(intent)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateUiStatus()
    }

    private fun updateUiStatus() {
        val isAccessibilityActive = BjAccessibilityService.instance != null
        if (isAccessibilityActive) {
            btnAccessibility.text = "✓ Accessibility: GRANTED"
            btnOverlay.text = "Overlay Permission (Optional - Handled by Accessibility)"
        } else {
            btnAccessibility.text = "Enable Accessibility Service"
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (Settings.canDrawOverlays(this)) {
                btnOverlay.text = "✓ Overlay Permission: GRANTED"
            }
        }
    }
}
