package com.example.besu

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite

// Live watch telemetry, unpaced -- for free-form gesture practice. Distinct from
// HelpCoachPanel: no steps, nothing to complete, the watch's normal timing is left
// alone (see BackgroundSensorService.TrainingMode.LIVE).
@Composable
fun TrainingGroundPanel(
    stateLabel: String,
    poseLabel: String,
    twistLevel: Int,
    primaryColor: Color,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor,
                shape = AckHelpShape
            )
            .background(
                color = Graphite.copy(alpha = 0.97f),
                shape = AckHelpShape
            )
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "TRAINING GROUND // LIVE",
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )

            Text(
                text = "[EXIT]",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable(onClick = onClose)
                    .padding(4.dp)
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = "GESTURE FREELY. TELEMETRY ONLY -- NO COMMANDS FIRE.",
            color = Color.White.copy(alpha = 0.7f),
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            lineHeight = 14.sp
        )

        Spacer(modifier = Modifier.height(14.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            TelemetryReadout(label = "STATE", value = stateLabel, primaryColor = primaryColor)
            TelemetryReadout(label = "POSE", value = fullPoseName(poseLabel), primaryColor = primaryColor)
            TelemetryReadout(label = "MOD", value = twistLevel.toString(), primaryColor = primaryColor)
        }
    }
}

// Training Ground has room to spell poses out in full, unlike the compact header
// readout -- these are the same wire codes BackgroundSensorService.Pose.wireLabel()
// sends (ID/DEF/CON/---), just expanded for display here.
private fun fullPoseName(poseLabel: String): String = when (poseLabel) {
    "ID" -> "IDENTITY"
    "DEF" -> "DEFEND"
    "CON" -> "CONNECT"
    "---" -> "NONE"
    else -> poseLabel
}

@Composable
private fun TelemetryReadout(
    label: String,
    value: String,
    primaryColor: Color
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = label,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 1.sp
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = value,
            color = primaryColor,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black
        )
    }
}
