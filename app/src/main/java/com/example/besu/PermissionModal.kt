package com.example.besu

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.ManagedActivityResultLauncher
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack

@Composable
fun GeoPermissionModal(
    context: Context,
    primaryColor: Color,
    permissionLauncher: ManagedActivityResultLauncher<Array<String>, Map<String, @JvmSuppressWildcards Boolean>>,
    onDismiss: () -> Unit
) {
    val hasForeground = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
    
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Graphite,
        modifier = Modifier.border(1.dp, primaryColor, CutCornerShape(8.dp)),
        title = { Text("GEO-PROTOCOL // AUTHORIZATION", color = primaryColor, fontFamily = FontFamily.Monospace, fontSize = 14.sp) },
        text = {
            Column {
                Text(
                    "To switch decks automatically, ACK requires 'Always On' location access to detect boundaries while in your pocket.",
                    color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    "PRIVACY NOTICE: Your coordinates are kept strictly on-device only when using the SOVEREIGN model as processing is handled on device. Using the OPTIMIZED model enables Google Play Services support. Your location information will be transmitted to Google services if you use this method.",
                    color = NeonPalette.SWATCHES[3], fontSize = 10.sp, fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(12.dp))
                if (hasForeground && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    Text("STEP 2: Please select 'Allow all the time' in the following Android settings screen.", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                }
            }
        },
        confirmButton = {
            NeonButton("PROCEED", mainColor = primaryColor) {
                if (!hasForeground) {
                    // Step 1: Request Foreground
                    permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    // Step 2: Request Background (Requires user to manually click "Allow all the time" in settings on Android 11+)
                    permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION))
                }
                onDismiss()
            }
        },
        dismissButton = {
            NeonButton("ABORT", isActive = false, mainColor = primaryColor) { onDismiss() }
        }
    )
}
