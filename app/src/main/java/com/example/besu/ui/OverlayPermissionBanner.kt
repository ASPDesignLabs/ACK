// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.besu.ui.theme.ErrorRed
import com.example.besu.ui.theme.Graphite

private const val TAG = "ACK_OVERLAY"

// 12 sp is the floor for a message that reports a safety fault; small text is itself a tracked problem.
private const val BANNER_TEXT_SP = 14

private fun Context.findComponentActivity(): ComponentActivity? {
    var c: Context? = this
    while (c is ContextWrapper) {
        if (c is ComponentActivity) return c
        c = c.baseContext
    }
    return null
}

/**
 * Whether Android's "Display over other apps" permission is on, kept current: it is read again every time the app comes back
 * to the front, so the answer is right after the person has been to Settings and returned, without restarting ACK.
 * (Same way of watching the lifecycle as voicecapture/CaptureSessionScreen.kt, which is known to build here.)
 */
@Composable
fun rememberCanDrawOverlays(): State<Boolean> {
    val context = LocalContext.current
    val canDraw = remember { mutableStateOf(Settings.canDrawOverlays(context)) }
    DisposableEffect(context) {
        val owner = context.findComponentActivity()
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                canDraw.value = Settings.canDrawOverlays(context)
            }
        }
        owner?.lifecycle?.addObserver(observer)
        onDispose { owner?.lifecycle?.removeObserver(observer) }
    }
    return canDraw
}

/**
 * Shown above the header on every main screen while "Display over other apps" is off. With it off, a message is spoken but
 * never shown on screen, and nothing else says so. It is not dismissible: it reports a safety fault, not a tip, and it clears
 * itself the moment the permission is on.
 */
@Composable
fun OverlayPermissionBanner(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val canDraw by rememberCanDrawOverlays()
    if (canDraw) return

    Row(
        modifier = modifier
            .fillMaxWidth()
            .border(2.dp, ErrorRed, CutCornerShape(8.dp))
            .background(Graphite, CutCornerShape(8.dp))
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "DISPLAY PERMISSION IS OFF. MESSAGES ARE SPOKEN BUT NOT SHOWN ON SCREEN.",
            color = ErrorRed,
            fontSize = BANNER_TEXT_SP.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.weight(1f)
        )
        NeonButton("ALLOW", mainColor = ErrorRed) { openOverlaySettings(context) }
    }
}

// The page for this app's own "Display over other apps" switch. Some phone makers do not offer that page, so fall back to
// the app's general settings page, where the person can find it.
private fun openOverlaySettings(context: Context) {
    val packageUri = Uri.parse("package:" + context.packageName)
    try {
        context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, packageUri))
    } catch (e: Exception) {
        Log.e(TAG, "overlay permission page not available; opening app settings instead", e)
        try {
            context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, packageUri))
        } catch (e2: Exception) {
            Log.e(TAG, "app settings page not available either", e2)
        }
    }
}
