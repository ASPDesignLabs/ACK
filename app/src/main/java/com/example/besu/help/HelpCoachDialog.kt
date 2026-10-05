// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.R
import com.example.besu.ui.looseSpacing
import com.example.besu.ui.helpText
import com.example.besu.ui.helpWords
import com.example.besu.ui.theme.*
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
import androidx.compose.ui.res.stringResource
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
                text = stringResource(R.string.help_coach_guidance, stepPosition(manager, module)),
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = looseSpacing(1.sp)
            )

            Text(
                text = stringResource(R.string.help_coach_abort),
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
            text = helpWords(step.title),
            color = Color.White,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black,
            letterSpacing = looseSpacing(0.8.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = helpWords(step.body),
            color = Color.White.copy(alpha = 0.84f),
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            lineHeight = 16.sp
        )

        Spacer(modifier = Modifier.height(12.dp))

        if (step.action == HelpAction.Read) {
            HelpCoachAction(
                text = stringResource(R.string.help_coach_acknowledge),
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
                        text = stringResource(R.string.help_coach_awaiting),
                        color = primaryColor,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = looseSpacing(0.7.sp)
                    )

                    Spacer(modifier = Modifier.height(3.dp))

                    Text(
                        text = helpText(helpActionInstruction(step.action)),
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
            letterSpacing = looseSpacing(1.sp)
        )
    }
}

private fun stepPosition(
    manager: HelpManager,
    module: HelpModule
): String {
    return "${manager.currentStepIndex + 1}/${module.steps.size}"
}

@Composable
private fun helpActionInstruction(action: HelpAction): String {
    return when (action) {
        is HelpAction.Interact -> stringResource(R.string.help_coach_use_control)
        is HelpAction.CommitText -> stringResource(R.string.help_coach_commit_text)
        is HelpAction.CommitFile -> stringResource(R.string.help_coach_commit_file)
        is HelpAction.OverlayCleared -> stringResource(R.string.help_coach_clear_overlay)
        is HelpAction.WatchEvent -> stringResource(R.string.help_coach_watch_event, action.eventType)
        is HelpAction.DeckSelected -> stringResource(R.string.help_coach_select_deck)
        is HelpAction.ProfileSelected -> stringResource(R.string.help_coach_select_profile)
        is HelpAction.KeyboardDismissed -> stringResource(R.string.help_coach_close_keyboard)
        HelpAction.Read -> stringResource(R.string.help_coach_read)
    }
}
