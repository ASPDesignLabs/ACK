// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.AckTags
import com.example.besu.R
import com.example.besu.core.LabelKey
import com.example.besu.core.SendFlag
import com.example.besu.core.SendFlags
import com.example.besu.help.AckHelpShape
import com.example.besu.settings.ConfirmBodyText
import com.example.besu.ui.theme.VoidBlack

/**
 * The buttons and switches that PLAIN WORDS adds to the Terminal screen for what used to need a typed command (docs/PLAIN_LANGUAGE.md, section B).
 * Every typed command keeps working; these only call the same code. All text here is 12 sp or larger and every tap target is at least 48 dp tall.
 * Nothing here vibrates or animates: a vibration is audible to an open microphone, and a screen that moves is harder to read.
 */

/**
 * The four send switches. They stay on until they are turned off (the developer's choice), kept in memory only: they survive sending, leaving this
 * screen and coming back, but not closing ACK, and they are turned off when PLAIN WORDS is turned off (see core/SendFlags.kt for why a switch must
 * never act while it cannot be seen). They are not saved to the phone, so there is nothing for DELETE DATA or a backup to carry.
 */
object TerminalSendSwitches {
    var flags by mutableStateOf(SendFlags())
        private set

    fun set(flag: SendFlag, on: Boolean) {
        flags = flags.with(flag, on)
    }

    fun reset() {
        flags = SendFlags()
    }
}

@Composable
private fun sendFlagName(flag: SendFlag): String = stringResource(
    when (flag) {
        SendFlag.QUIET -> R.string.plain_ctl_send_quietly
        SendFlag.SKIP_LOG -> R.string.plain_ctl_send_no_history
        SendFlag.STICKY -> R.string.plain_ctl_send_keep
        SendFlag.EMERGENCY -> R.string.plain_ctl_send_emergency
    }
)

/** One switch: the words on the left, ON or OFF written out on the right (colour alone is never the only sign), and a screen-reader switch role. */
@Composable
private fun SendSwitchRow(flag: SendFlag, on: Boolean, primaryColor: Color) {
    val accent = if (flag == SendFlag.EMERGENCY) RadicalRed else primaryColor
    val name = sendFlagName(flag)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .background(if (on) accent.copy(alpha = 0.18f) else Color.Transparent, AckHelpShape)
            .border(if (on) 2.dp else 1.dp, if (on) accent else Color.Gray, AckHelpShape)
            .toggleable(value = on, role = Role.Switch, onValueChange = { TerminalSendSwitches.set(flag, it) })
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            name,
            color = if (on) accent else Color.White,
            fontFamily = FontFamily.Monospace,
            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f)
        )
        Text(
            stringResource(if (on) R.string.plain_ctl_on else R.string.plain_ctl_off),
            color = if (on) VoidBlack else Color.Gray,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 12.sp,
            modifier = Modifier
                .padding(start = 8.dp)
                .background(if (on) accent else Color.Transparent, AckHelpShape)
                .padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

/** A plain-mode action button: bordered, 12 sp text, at least 48 dp tall, no vibration. Shared by the Terminal, the Type tab and SETTINGS. */
@Composable
internal fun PlainActionButton(text: String, color: Color, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier
            .heightIn(min = 48.dp)
            .border(1.dp, color, AckHelpShape)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(text, color = color, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 12.sp)
    }
}

/**
 * SEND OPTIONS: one steady row that opens to the four switches and the two insert buttons (for `/v` and `/t`). Closed, the row still says which
 * switches are on, so a switch that is on is never hidden. [onInsertVariable] and [onBrowseTargets] do what typing `/v` and `/t` does.
 */
@Composable
fun SendOptionsPanel(primaryColor: Color, onInsertVariable: () -> Unit, onBrowseTargets: () -> Unit) {
    var open by remember { mutableStateOf(false) }
    val flags = TerminalSendSwitches.flags
    val onNames = flags.onFlags().map { sendFlagName(it) }
    val anyOn = onNames.isNotEmpty()
    val headerText = if (anyOn) {
        stringResource(R.string.plain_ctl_send_options_on, onNames.joinToString(", "))
    } else {
        stringResource(R.string.plain_ctl_send_options)
    }
    val headerColor = if (flags.emergency) RadicalRed else primaryColor

    Column(modifier = Modifier.fillMaxWidth().testTag(AckTags.TERMINAL_SEND_OPTIONS)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .background(if (anyOn) headerColor.copy(alpha = 0.18f) else Color.Transparent, AckHelpShape)
                .border(if (anyOn) 2.dp else 1.dp, if (anyOn) headerColor else Color.Gray, AckHelpShape)
                .clickable(role = Role.Button) { open = !open }
                .padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                headerText,
                color = if (anyOn) headerColor else Color.White,
                fontFamily = FontFamily.Monospace,
                fontWeight = if (anyOn) FontWeight.Bold else FontWeight.Normal,
                fontSize = 12.sp,
                modifier = Modifier.weight(1f)
            )
            Text(
                if (open) "▾" else "▸",
                color = headerColor,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                modifier = Modifier.padding(start = 8.dp)
            )
        }

        if (open) {
            // Tall enough for all of it on a large phone; scrolls instead of pushing the typing box off a small one.
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 260.dp)
                    .verticalScroll(rememberScrollState())
                    .padding(top = 6.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                SendFlag.values().forEach { flag -> SendSwitchRow(flag, flags.isOn(flag), primaryColor) }
                Text(
                    stringResource(R.string.plain_ctl_options_hint),
                    color = Color.Gray,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )
                PlainActionButton(labelFor(LabelKey.INSERT_VARIABLE), primaryColor, Modifier.fillMaxWidth(), onInsertVariable)
                PlainActionButton(labelFor(LabelKey.BROWSE_TARGETS), primaryColor, Modifier.fillMaxWidth(), onBrowseTargets)
            }
        }
    }
}

/** WHAT'S NEW (`/info`) and CLEAR HISTORY (`/cls`), across the top of the Terminal screen, away from the keyboard. */
@Composable
fun TerminalToolsRow(primaryColor: Color, onWhatsNew: () -> Unit, onClearHistory: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        PlainActionButton(
            stringResource(R.string.plain_ctl_whats_new), primaryColor,
            Modifier.weight(1f).testTag(AckTags.TERMINAL_WHATS_NEW), onWhatsNew
        )
        PlainActionButton(
            stringResource(R.string.plain_ctl_clear_history), RadicalRed,
            Modifier.weight(1f).testTag(AckTags.TERMINAL_CLEAR_HISTORY), onClearHistory
        )
    }
}

/**
 * The confirmation for CLEAR HISTORY: the same two steps as typing `/cls` and then `/cls CONFIRM` (a tap, then a second tap here). CANCEL is the
 * prominent button; the one that deletes is red and below it, and tapping outside does not delete.
 */
@Composable
fun ClearHistoryDialog(primaryColor: Color, onConfirm: () -> Unit, onCancel: () -> Unit) {
    val cancel = stringResource(R.string.plain_ctl_cancel)
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = stringResource(R.string.plain_ctl_clear_history),
        dismissLabel = cancel
    ) {
        ConfirmBodyText(stringResource(R.string.plain_ctl_clear_history_body), bold = true, color = RadicalRed)
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.plain_ctl_clear_history), Modifier.fillMaxWidth(), mainColor = RadicalRed) { onConfirm() }
    }
}
