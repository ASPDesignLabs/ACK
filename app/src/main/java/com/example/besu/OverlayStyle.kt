package com.example.besu

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.besu.ui.theme.Graphite

/**
 * The "tight" overlay-window language shared across variable/group/text editors,
 * matching the Training Ground / Deck Trainer panels: a bordered [AckHelpShape]
 * surface (no Material elevation) with a hand-laid-out header, instead of a stock
 * Material3 AlertDialog.
 */

private val MIN_TOUCH_TARGET = 44.dp

@Composable
fun TightDialogSurface(
    onDismiss: () -> Unit,
    primaryColor: Color,
    title: String,
    subtitle: String? = null,
    dismissLabel: String = "CLOSE",
    surfaceModifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Surface(
                modifier = surfaceModifier
                    .fillMaxWidth()
                    .widthIn(max = 560.dp)
                    .border(width = 1.dp, color = primaryColor, shape = AckHelpShape),
                color = Graphite,
                shape = AckHelpShape
            ) {
                Column(
                    modifier = Modifier
                        .padding(16.dp)
                        .heightIn(max = 640.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = title.uppercase(),
                                color = primaryColor,
                                fontSize = 13.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Black,
                                letterSpacing = 1.sp
                            )

                            if (subtitle != null) {
                                Spacer(modifier = Modifier.height(1.dp))

                                Text(
                                    text = subtitle,
                                    color = Color.Gray,
                                    fontSize = 9.sp,
                                    fontFamily = FontFamily.Monospace,
                                    letterSpacing = 1.sp
                                )
                            }
                        }

                        Text(
                            text = "[$dismissLabel]",
                            color = Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .heightIn(min = MIN_TOUCH_TARGET)
                                .clickable(onClick = onDismiss)
                                .padding(horizontal = 4.dp),
                            textAlign = androidx.compose.ui.text.style.TextAlign.End
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    content()
                }
            }
        }
    }
}

@Composable
fun TightPanelButton(
    text: String,
    modifier: Modifier = Modifier,
    isActive: Boolean = true,
    mainColor: Color,
    onClick: () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    val contentColor = if (isActive) mainColor else mainColor.copy(alpha = 0.5f)
    val fillAlpha = if (isActive) 0.12f else 0f

    Box(
        modifier = modifier
            .heightIn(min = MIN_TOUCH_TARGET)
            .border(width = 1.dp, color = contentColor, shape = AckHelpShape)
            .background(color = mainColor.copy(alpha = fillAlpha), shape = AckHelpShape)
            .clickable {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                onClick()
            }
            .padding(horizontal = 12.dp, vertical = 11.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text.uppercase(),
            color = contentColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )
    }
}

@Composable
fun TightSectionLabel(text: String, color: Color = Color.Gray) {
    Text(
        text = text.uppercase(),
        color = color,
        fontSize = 10.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold,
        letterSpacing = 1.sp
    )
}
