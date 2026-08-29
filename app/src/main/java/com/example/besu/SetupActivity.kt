package com.example.besu

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.example.besu.MainActivity

class SetupActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)

        updatePermissionStatus()

        findViewById<Button>(R.id.btnGrantOverlay).setOnClickListener {
            requestOverlayPermission()
        }

        findViewById<Button>(R.id.btnComplete).setOnClickListener {
            completeSetup()
        }
    }

    override fun onResume() {
        super.onResume()
        updatePermissionStatus()
    }

    private fun updatePermissionStatus() {
        val overlayGranted = checkOverlayPermission()

        findViewById<TextView>(R.id.tvOverlayStatus).text =
            if (overlayGranted) "✓ Overlay permission granted"
            else "✗ Overlay permission needed"

        findViewById<Button>(R.id.btnGrantOverlay).isEnabled = !overlayGranted
        findViewById<Button>(R.id.btnComplete).isEnabled = overlayGranted
    }

    private fun checkOverlayPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else {
            true
        }
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        }
    }

    private fun completeSetup() {
        // 1. Mark setup as complete
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        prefs.edit().putBoolean("setup_complete", true).apply()

        // 2. Initialize default gesture prefs if needed
        val gesturePref = getSharedPreferences("gestures", Context.MODE_PRIVATE)
        if (!gesturePref.contains("triple_tap")) {
            gesturePref.edit().apply {
                putString("triple_tap", "😊")
                putString("device_triple_tap", "👍")
                apply()
            }
        }

        // 3. IMPORTANT: Start Main Activity BEFORE finishing
        // This prevents the "DeadObjectException" by ensuring there is a valid window to go to.
        val intent = Intent(this, MainActivity::class.java)
        // Clear flags ensure we don't have back-stack weirdness
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)

        // 4. Close this activity
        finish()
    }
}