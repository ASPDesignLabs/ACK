// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.R
import com.example.besu.core.UsageSummaryText
import com.example.besu.core.UsageTally
import com.example.besu.data.UsageTallyRepository
import com.example.besu.ui.NeonButton
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.UsageSummaryState
import com.example.besu.ui.rememberText
import java.time.LocalDate

/**
 * SETTINGS > USAGE SUMMARY (the design is docs/USAGE_SUMMARY_DESIGN.md; every word is core/UsageSummaryText.kt): the switch, the numbers, SAVE USAGE SUMMARY TO A FILE and
 * FORGET USAGE SUMMARY. It counts messages and never keeps a word of one.
 *
 * Rules that must stay true (UsageSummaryWiringTest holds them):
 *  - **Turning it on asks first**, in a dialog where CANCEL is the prominent button and tapping outside cancels. Only TURN ON writes the switch. Nothing is counted before that.
 *  - **Turning it off stops counting and deletes nothing.** The counts stay until FORGET, and the screen says how many are still saved.
 *  - **FORGET asks twice**, CANCEL prominent both times, naming SAVE USAGE SUMMARY TO A FILE first; only the second DELETE PERMANENTLY calls `forgetAll`.
 *  - Plain numbers only: no chart, no animation, no sound. Text is 12 sp or larger and every button is a NeonButton.
 */
@Composable
fun UsageSummarySection(context: Context, primaryColor: Color) {
    val text = rememberText()
    val on = UsageSummaryState.on
    // Bumped after a forget, so the numbers are read again.
    var refresh by remember { mutableIntStateOf(0) }
    val summary = remember(refresh, on) { UsageTally.summarise(UsageTallyRepository.load(context), LocalDate.now()) }
    var askingToTurnOn by remember { mutableStateOf(false) }
    var forgetStep by remember { mutableIntStateOf(0) }
    val startSave = rememberUsageSummarySaveFlow(context, primaryColor)
    val cancel = stringResource(R.string.common_cancel)

    Text(
        text.get(UsageSummaryText.TITLE),
        color = primaryColor,
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(6.dp))
    ConfirmBodyText(UsageSummaryText.explanation(text), color = Color.Gray)
    Spacer(modifier = Modifier.height(10.dp))

    // The switch. Off to on asks first; on to off just stops counting.
    NeonButton(
        UsageSummaryText.switchLabel(text, on),
        Modifier.fillMaxWidth(),
        mainColor = if (on) primaryColor else Color.White
    ) {
        if (on) UsageSummaryState.set(context, false) else askingToTurnOn = true
    }
    Spacer(modifier = Modifier.height(12.dp))

    if (summary.messages == 0L) {
        ConfirmBodyText(text.get(UsageSummaryText.EMPTY))
    } else {
        ConfirmBodyText(UsageSummaryText.totalLine(text, summary.messages), bold = true)
        Spacer(modifier = Modifier.height(10.dp))
        Heading(text.get(UsageSummaryText.HEAD_KIND), primaryColor)
        summary.byKind.forEach { (kind, n) -> ConfirmBodyText(UsageSummaryText.row(text, UsageSummaryText.kindName(text, kind), n)) }
        Spacer(modifier = Modifier.height(10.dp))
        Heading(text.get(UsageSummaryText.HEAD_CHANNEL), primaryColor)
        summary.byChannel.forEach { (channel, n) -> ConfirmBodyText(UsageSummaryText.row(text, UsageSummaryText.channelName(text, channel), n)) }
        Spacer(modifier = Modifier.height(10.dp))
        Heading(UsageSummaryText.headDays(text), primaryColor)
        summary.recent.forEach { day -> ConfirmBodyText(UsageSummaryText.row(text, day.date.toString(), day.messages)) }
        Spacer(modifier = Modifier.height(10.dp))
        Heading(text.get(UsageSummaryText.HEAD_HOURS), primaryColor)
        summary.byHour.forEachIndexed { hour, n -> if (n > 0L) ConfirmBodyText(UsageSummaryText.row(text, UsageSummaryText.hourLabel(hour), n)) }
    }

    Spacer(modifier = Modifier.height(14.dp))
    NeonButton(text.get(UsageSummaryText.SAVE_BUTTON), Modifier.fillMaxWidth(), mainColor = primaryColor) { startSave() }
    if (summary.messages > 0L) {
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(text.get(UsageSummaryText.FORGET_BUTTON), Modifier.fillMaxWidth(), mainColor = Color.White) { forgetStep = 1 }
    }

    if (askingToTurnOn) {
        TightDialogSurface(
            onDismiss = { askingToTurnOn = false },
            primaryColor = primaryColor,
            title = text.get(UsageSummaryText.ON_TITLE),
            dismissLabel = cancel
        ) {
            UsageSummaryText.onQuestion(text).forEach { paragraph ->
                ConfirmBodyText(paragraph, bold = true)
                Spacer(modifier = Modifier.height(10.dp))
            }
            Spacer(modifier = Modifier.height(6.dp))
            NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { askingToTurnOn = false }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(text.get(UsageSummaryText.ON_CONFIRM), Modifier.fillMaxWidth(), mainColor = Color.White) {
                askingToTurnOn = false
                UsageSummaryState.set(context, true)
            }
        }
    }

    if (forgetStep == 1) {
        TightDialogSurface(
            onDismiss = { forgetStep = 0 },
            primaryColor = primaryColor,
            title = text.get(UsageSummaryText.FORGET_TITLE),
            dismissLabel = cancel
        ) {
            ConfirmBodyText(UsageSummaryText.forgetFirst(text, text.get(UsageSummaryText.SAVE_BUTTON)), bold = true)
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { forgetStep = 0 }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.common_continue), Modifier.fillMaxWidth(), mainColor = Color.White) { forgetStep = 2 }
        }
    }

    if (forgetStep == 2) {
        TightDialogSurface(
            onDismiss = { forgetStep = 0 },
            primaryColor = primaryColor,
            title = text.get(UsageSummaryText.FORGET_FINAL_TITLE),
            dismissLabel = cancel
        ) {
            ConfirmBodyText(UsageSummaryText.forgetFinal(text, summary.messages), bold = true)
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { forgetStep = 0 }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(text.get(UsageSummaryText.FORGET_DELETE), Modifier.fillMaxWidth(), mainColor = Color.White) {
                forgetStep = 0
                UsageTallyRepository.forgetAll(context)
                Toast.makeText(context, text.get(UsageSummaryText.FORGET_DONE), Toast.LENGTH_SHORT).show()
                refresh++
            }
        }
    }
}

@Composable
private fun Heading(label: String, color: Color) {
    Text(label, color = color, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
    Spacer(modifier = Modifier.height(4.dp))
}
