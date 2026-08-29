package com.example.besu.wear

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText
import androidx.wear.compose.material.TimeTextDefaults
import androidx.compose.ui.unit.TextUnit
import androidx.compose.foundation.layout.padding

// UI CONSTANTS
private const val DECK_INDICATOR_FONT_SP = 12
private const val CLOCK_FONT_SP = 11

// --- HUD TYPE TUNING ---
// Increase these independently to tune readability on-device.
val DeckIndicatorFontSize: TextUnit = 13.sp
val ClockFontSize: TextUnit = 13.sp

// --- CYBERPUNK PALETTE ---
val CyberCyan = Color(0xFF00F3FF)
val CyberPink = Color(0xFFFF0055)
val CyberGreen = Color(0xFF00FF41) // <--- NEON GREEN FOR CONTEXT
val CyberAmber = Color(0xFFFF9900)
val CyberBg = Color(0xFF050505)
val CyberDark = Color(0xFF121212)
val CyberIce = Color(0xFFAADDFF)





@Composable
fun CryoMenuOverlay(minutes: Int, onIncrement: () -> Unit, onDecrement: () -> Unit, onConfirm: () -> Unit) {
    Box(
        modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.95f)),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("CRYO SETUP", color = CyberIce, fontFamily = FontFamily.Monospace, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                UiButton("-") { onDecrement() }
                Spacer(modifier = Modifier.width(16.dp))
                Text("${minutes}m", color = CyberIce, fontFamily = FontFamily.Monospace, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.width(16.dp))
                UiButton("+") { onIncrement() }
            }
            Spacer(modifier = Modifier.height(20.dp))
            Box(
                modifier = Modifier
                    .clip(CutCornerShape(12.dp))
                    .background(CyberIce.copy(alpha=0.2f))
                    .border(1.dp, CyberIce, CutCornerShape(12.dp))
                    .pointerInput(Unit) { detectTapGestures(onTap = { onConfirm() }) }
                    .padding(horizontal = 32.dp, vertical = 10.dp)
            ) {
                Text("INITIATE", color = CyberIce, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            }
        }
    }
}

@Composable
fun UiButton(text: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(CyberDark)
            .border(1.dp, CyberIce.copy(alpha=0.5f), CircleShape)
            .pointerInput(Unit) { detectTapGestures(onTap = { onClick() }) },
        contentAlignment = Alignment.Center
    ) { Text(text, color = CyberIce, fontSize = 24.sp) }
}

@Composable
fun CryoHud(label: String, subLabel: String, remainingSeconds: Long?) {
    val isInfinite = remainingSeconds == null
    val timeString = if (!isInfinite)
        "%02d:%02d".format(remainingSeconds!! / 60, remainingSeconds % 60)
    else "∞"

    val infiniteTransition = rememberInfiniteTransition()
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f, targetValue = 0.8f,
        animationSpec = infiniteRepeatable(animation = tween(2000, easing = FastOutSlowInEasing), repeatMode = RepeatMode.Reverse)
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.85f)),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            drawCircle(brush = Brush.radialGradient(colors = listOf(CyberIce.copy(alpha=0.15f), Color.Transparent)), radius = size.width * 0.8f)
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = CyberIce.copy(alpha = pulseAlpha), fontFamily = FontFamily.Monospace, fontSize = 10.sp, letterSpacing = 4.sp)
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = timeString,
                color = if (!isInfinite) CyberIce else CyberIce.copy(alpha = 0.7f),
                fontFamily = FontFamily.Monospace,
                fontSize = if (isInfinite) 56.sp else 42.sp,
                fontWeight = FontWeight.Light
            )

            Spacer(modifier = Modifier.height(12.dp))
            Text(subLabel, color = CyberIce.copy(alpha = 0.5f), fontSize = 8.sp, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
fun AckWatchHud(
    status: String, 
    pose: String, 
    twist: Int,
    primaryColor: Color = CyberCyan,
    deckName: String = "",
    profileName: String = "DEFAULT" // <--- NEW PARAMETER
) {
    // Dynamic Status Color: Uses Deck Color for neutral states
    val statusColor = when (status) {
        "CRYO" -> primaryColor.copy(alpha = 0.65f)
        "IDLE" -> Color.Gray
        "INIT", "TX", "PTT_READY" -> primaryColor
        "ARMED" -> CyberCyan
        "LOCKED", "POSE_LOCKED" -> CyberAmber
        else -> Color.White
    }

    val isMotionArmed = status == "ARMED" || status == "POSE_LOCKED"

    val shouldAnimateScanlines = status == "ARMED" ||
            status == "POSE_LOCKED"

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(CyberBg),
        contentAlignment = Alignment.Center,
    ) {
        //  if (isMotionArmed) {
        //      ScanlineEffect(primaryColor)
        //  }

        TacticalReticle(statusColor)

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(horizontal = 16.dp)
        ) {

            // 1. DECK INDICATOR
            val deckIndicator = if (
                deckName.isNotEmpty() &&
                deckName != "DEFAULT"
            ) {
                "DECK: ${deckName.uppercase()}"
            } else {
                "AUGMENTED COMM"
            }

            Text(
                text = deckIndicator,
                color = primaryColor.copy(
                    alpha = if (deckName.isNotEmpty() && deckName != "DEFAULT") {
                        0.9f
                    } else {
                        0.55f
                    },
                ),
                fontSize = DeckIndicatorFontSize,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.6.sp,
            )

            // 2. CONTEXT/PROFILE INDICATOR (NEON GREEN)
            if (profileName != "DEFAULT") {
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    "CTX: $profileName",
                    color = CyberGreen,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(4.dp))
            } else {
                Spacer(modifier = Modifier.height(8.dp))
            }

            // 3. MAIN STATUS BOX
            Box(
                modifier = Modifier.border(1.dp, statusColor, CutCornerShape(8.dp))
                    .background(statusColor.copy(alpha = 0.1f))
                    .padding(horizontal = 12.dp, vertical = 4.dp)
            ) {
                Text(
                    status,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = statusColor,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 2.sp
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "POSE: $pose",
                fontSize = 12.sp,
                color = Color.White,
                fontFamily = FontFamily.Monospace,
            )

            if (twist > 0) {
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    repeat(twist) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .background(
                                    primaryColor,
                                    CutCornerShape(2.dp),
                                ),
                        )
                    }
                }
            }
        }

        TimeText(
            timeTextStyle = TimeTextDefaults.timeTextStyle(
                color = primaryColor.copy(alpha = 0.72f),
                fontSize = ClockFontSize,
            ).copy(
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
            ),
        )

        if (status == "CRYO") {
            CryoStatusIndicator(
                primaryColor = primaryColor,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 18.dp),
            )
        }
    }
}

@Composable
fun TacticalReticle(color: Color) {
    Canvas(modifier = Modifier.fillMaxSize()) {
        val w = size.width; val h = size.height; val stroke = Stroke(width = 3f)
        val path = Path().apply {
            moveTo(w * 0.2f, h * 0.15f); lineTo(w * 0.15f, h * 0.15f); lineTo(w * 0.15f, h * 0.2f)
            moveTo(w * 0.8f, h * 0.15f); lineTo(w * 0.85f, h * 0.15f); lineTo(w * 0.85f, h * 0.2f)
            moveTo(w * 0.2f, h * 0.85f); lineTo(w * 0.15f, h * 0.85f); lineTo(w * 0.15f, h * 0.8f)
            moveTo(w * 0.8f, h * 0.85f); lineTo(w * 0.85f, h * 0.85f); lineTo(w * 0.85f, h * 0.8f)
        }
        drawPath(path, color, style = stroke)
        drawCircle(color.copy(alpha=0.3f), radius = 2f, center = Offset(w*0.5f, h*0.85f))
    }
}

@Composable
fun ScanlineEffect(color: Color = CyberCyan) {
    val infiniteTransition = rememberInfiniteTransition()
    val offsetY by infiniteTransition.animateFloat(initialValue = 0f, targetValue = 1000f, animationSpec = infiniteRepeatable(tween(2000, easing = LinearEasing), RepeatMode.Restart))
    Canvas(modifier = Modifier.fillMaxSize().alpha(0.15f)) {
        val lineSpacing = 6.dp.toPx()
        val totalLines = (size.height / lineSpacing).toInt()
        for (i in 0..totalLines) {
            val y = (i * lineSpacing + offsetY) % size.height
            drawLine(color, Offset(0f, y), Offset(size.width, y), 1f)
        }
    }
}

@Composable
fun CryoStatusIndicator(
    primaryColor: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = "◈ CRYO",
            color = primaryColor.copy(alpha = 0.78f),
            fontFamily = FontFamily.Monospace,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.5.sp,
        )

        Spacer(modifier = Modifier.height(3.dp))

        Text(
            text = "TAP TO ARM",
            color = Color.White.copy(alpha = 0.48f),
            fontFamily = FontFamily.Monospace,
            fontSize = 8.sp,
            letterSpacing = 0.8.sp,
        )
    }
}
