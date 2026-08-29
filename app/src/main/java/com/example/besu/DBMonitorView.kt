package com.example.besu

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack

@Composable
fun EnvironmentMonitorView(primaryColor: Color) {
    val context = LocalContext.current
    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasPermission = isGranted
    }

    var currentDb by remember { mutableFloatStateOf(0f) }
    val analyzer = remember { AmbientAudioAnalyzer() }

    // Manage recorder lifecycle
    DisposableEffect(hasPermission) {
        if (hasPermission) {
            analyzer.start(context)
        }
        onDispose {
            analyzer.stop()
        }
    }

    // Collect DB levels continuously
    LaunchedEffect(hasPermission) {
        if (hasPermission) {
            analyzer.collectDbLevels { level -> currentDb = level }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "ENVIRONMENTAL NOISE MONITOR",
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 2.sp,
            modifier = Modifier.align(Alignment.Start)
        )
        
        Spacer(modifier = Modifier.height(24.dp))

        if (!hasPermission) {
            NeonButton("AUTHORIZE MIC SCAN", mainColor = primaryColor) {
                permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        } else {
            // Visual Level Meter
            val maxDb = 100f // Typical noisy environment max for phone mic
            val fillRatio = (currentDb / maxDb).coerceIn(0f, 1f)
            
            // Map DB levels to warning colors (Green -> Yellow -> Red)
            val levelColor = when {
                currentDb > 80f -> Color(0xFFFF0055) // RadicalRed
                currentDb > 60f -> Color(0xFFFF9900) // DataOrange
                else -> primaryColor
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(40.dp)
                    .background(VoidBlack)
                    .border(1.dp, Color.DarkGray, CutCornerShape(4.dp))
                    .padding(4.dp)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .fillMaxWidth(fillRatio)
                        .background(levelColor, CutCornerShape(2.dp))
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            
            Text(
                text = "${currentDb.toInt()} dB",
                color = levelColor,
                fontSize = 48.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            val statusText = when {
                currentDb > 85f -> "CRITICAL: AUDIO RECOGNITION MAY FAIL"
                currentDb > 65f -> "WARNING: MODERATE INTERFERENCE"
                else -> "OPTIMAL: ENVIRONMENT CLEAR"
            }
            
            Text(
                text = statusText,
                color = levelColor,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}
