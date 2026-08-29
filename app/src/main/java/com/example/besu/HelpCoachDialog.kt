package com.example.besu

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
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
import com.example.besu.ui.theme.VoidBlack

@Composable
fun HelpCoachPanel(
    manager: HelpManager,
    primaryColor: Color,
    modifier: Modifier = Modifier
) {
    val module = manager.activeModule ?: return
    val step = manager.currentStep ?: return

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
                text = "GUIDANCE // ${stepPosition(manager, module)}",
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )

            Text(
                text = "[ABORT]",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable {
                        manager.abort()
                    }
                    .padding(4.dp)
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        HelpProgressBar(
            completedSteps = manager.currentStepIndex,
            totalSteps = module.steps.size,
            primaryColor = primaryColor
        )

        Spacer(modifier = Modifier.height(12.dp))

        Text(
            text = step.title,
            color = Color.White,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black,
            letterSpacing = 0.8.sp
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = step.body,
            color = Color.White.copy(alpha = 0.84f),
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            lineHeight = 16.sp
        )

        Spacer(modifier = Modifier.height(12.dp))

        if (step.action == HelpAction.Read) {
            HelpCoachAction(
                text = "ACKNOWLEDGE // CONTINUE",
                color = primaryColor,
                onClick = {
                    manager.advanceReadStep()
                }
            )
        } else {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        color = VoidBlack,
                        shape = AckHelpShape
                    )
                    .border(
                        width = 1.dp,
                        color = primaryColor.copy(alpha = 0.4f),
                        shape = AckHelpShape
                    )
                    .padding(10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .width(8.dp)
                        .height(8.dp)
                        .background(primaryColor, AckHelpShape)
                )

                Spacer(modifier = Modifier.width(8.dp))

                Column {
                    Text(
                        text = "AWAITING LIVE INPUT",
                        color = primaryColor,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.7.sp
                    )

                    Spacer(modifier = Modifier.height(3.dp))

                    Text(
                        text = helpActionInstruction(step.action),
                        color = Color.Gray,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
    }
}

@Composable
private fun HelpProgressBar(
    completedSteps: Int,
    totalSteps: Int,
    primaryColor: Color
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        repeat(totalSteps) { index ->
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(3.dp)
                    .background(
                        color = if (index <= completedSteps) {
                            primaryColor
                        } else {
                            Color.DarkGray
                        }
                    )
            )
        }
    }
}

@Composable
private fun HelpCoachAction(
    text: String,
    color: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = color,
                shape = AckHelpShape
            )
            .background(
                color = color.copy(alpha = 0.12f),
                shape = AckHelpShape
            )
            .clickable(onClick = onClick)
            .padding(vertical = 11.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )
    }
}

private fun stepPosition(
    manager: HelpManager,
    module: HelpModule
): String {
    return "${manager.currentStepIndex + 1}/${module.steps.size}"
}

private fun helpActionInstruction(action: HelpAction): String {
    return when (action) {
        is HelpAction.Interact -> "USE THE HIGHLIGHTED CONTROL TO PROCEED."
        is HelpAction.CommitText -> "COMMIT TEXT INPUT TO PROCEED."
        is HelpAction.CommitFile -> "COMMIT A FILE TO PROCEED."
        is HelpAction.OverlayCleared -> "CLEAR THE ACTIVE OVERLAY TO PROCEED."
        is HelpAction.WatchEvent -> "WAITING FOR WATCH EVENT: ${action.eventType}"
        is HelpAction.DeckSelected -> "SELECT A MATRIX DECK TO PROCEED."
        is HelpAction.ProfileSelected -> "SELECT A PROFILE TO PROCEED."
        is HelpAction.KeyboardDismissed -> {
            "TYPE IF NEEDED, THEN CLOSE THE KEYBOARD TO PROCEED."
        }

        HelpAction.Read -> "READ AND CONTINUE."
    }
}
