// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import com.example.besu.R
import com.example.besu.backup.BackupReminder
import com.example.besu.core.BackupReminderText
import com.example.besu.settings.ConfirmBodyText
import com.example.besu.ui.theme.Graphite

// The backup reminder's three faces. All are quiet: no sound, no vibration beyond the app's normal tap feedback, no animation, and
// nothing changes without a tap. Each reads BackupReminder.due itself and shows nothing when it is null. The words come from
// core/BackupReminderText.kt. NOT NOW snoozes it for 24 hours (BackupReminder.snooze); BACK UP NOW starts the same flow as the
// EXPORT .JSON button, so its warning shows first.

/**
 * Shown above the header on the Terminal and Settings screens only (MainActivity decides where): never on a deck, Emergency or
 * Type screen, so it can never move a button that is about to be tapped. Text is 12 sp and the buttons are NeonButton (12 sp).
 */
@Composable
fun BackupReminderBanner(
    primaryColor: Color,
    onBackUpNow: () -> Unit,
    onNotNow: () -> Unit,
    modifier: Modifier = Modifier
) {
    val due = BackupReminder.due ?: return
    val text = rememberText()
    Column(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor, CutCornerShape(8.dp))
            .background(Graphite, CutCornerShape(8.dp))
            .padding(12.dp)
    ) {
        ConfirmBodyText(BackupReminderText.message(text, due.daysSince, due.neverBackedUp), bold = true)
        Spacer(modifier = Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NeonButton(text.get(BackupReminderText.BACK_UP_NOW), mainColor = primaryColor) { onBackUpNow() }
            NeonButton(text.get(BackupReminderText.NOT_NOW), isActive = false, mainColor = primaryColor) { onNotNow() }
        }
    }
}

/** Width the header keeps free for [BackupSaveIndicator] at all times. */
val BackupIndicatorSlot = 24.dp

/**
 * A small save (floppy disk) icon for the header, left of HELP and under PROTOCOL, shown only while a backup is due. Its slot is
 * always laid out at the same size and only the icon inside it comes and goes, so it can never push anything aside when it
 * appears or disappears. Drawn in the app's own cut-corner outline style, in the theme colour. Tapping it opens
 * [BackupReminderDialog]. No animation.
 */
@Composable
fun BackupSaveIndicator(primaryColor: Color, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val due = BackupReminder.due
    val iconDescription = rememberText().get(BackupReminderText.ICON_DESCRIPTION)
    Box(modifier = modifier.size(BackupIndicatorSlot), contentAlignment = Alignment.Center) {
        if (due != null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .border(1.dp, primaryColor, CutCornerShape(4.dp))
                    .clickable(onClick = onClick)
                    .semantics { contentDescription = iconDescription },
                contentAlignment = Alignment.Center
            ) {
                SaveGlyph(color = primaryColor, modifier = Modifier.size(12.dp))
            }
        }
    }
}

// A floppy disk in outline: a body with its top-right corner cut, the shutter along the top and the label across the bottom.
@Composable
private fun SaveGlyph(color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val stroke = Stroke(width = 1.5.dp.toPx(), cap = StrokeCap.Square)
        val w = size.width
        val h = size.height
        val body = Path().apply {
            moveTo(0f, 0f)
            lineTo(w * 0.72f, 0f)
            lineTo(w, h * 0.28f)
            lineTo(w, h)
            lineTo(0f, h)
            close()
        }
        drawPath(body, color, style = stroke)
        drawRect(color, topLeft = Offset(w * 0.22f, 0f), size = Size(w * 0.42f, h * 0.30f), style = stroke)
        drawRect(color, topLeft = Offset(w * 0.18f, h * 0.55f), size = Size(w * 0.64f, h * 0.45f), style = stroke)
    }
}

/** What the header's save icon opens: the same reminder as the banner, on any screen, without moving anything. */
@Composable
fun BackupReminderDialog(
    primaryColor: Color,
    onBackUpNow: () -> Unit,
    onNotNow: () -> Unit,
    onClose: () -> Unit
) {
    val due = BackupReminder.due
    val text = rememberText()
    // It was snoozed, switched off or answered elsewhere while this was open: close it rather than show nothing.
    LaunchedEffect(due == null) { if (due == null) onClose() }
    if (due == null) return
    TightDialogSurface(
        onDismiss = onClose,
        primaryColor = primaryColor,
        title = text.get(BackupReminderText.DIALOG_TITLE),
        dismissLabel = stringResource(R.string.common_close)
    ) {
        ConfirmBodyText(BackupReminderText.message(text, due.daysSince, due.neverBackedUp), bold = true)
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(text.get(BackupReminderText.BACK_UP_NOW), Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpNow() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(text.get(BackupReminderText.NOT_NOW), Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) { onNotNow() }
    }
}
