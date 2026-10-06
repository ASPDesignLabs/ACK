// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.besu.core.LimitsNotice
import com.example.besu.settings.ConfirmBodyText
import com.example.besu.ui.theme.Graphite

/**
 * The limits statement's one-time banner (rules in core/LimitsNotice.kt). Shown above the header on the Terminal and Settings screens only (MainActivity decides
 * where, through LimitsNotice.shouldShowBanner), so it can never move a button that is about to be tapped on a deck or the Emergency screen.
 *
 * It is a notice and nothing more: no question, no timer, no sound of its own, no animation, and it never blocks or changes speech. GOT IT only calls [onDismiss],
 * which remembers the banner was seen; it does not start HELP and does not navigate. Text is 12 sp (the floor for anything new) and the button is the app's
 * NeonButton. [settingsName] is the SETTINGS button's name as the screen shows it (it follows PLAIN WORDS), handed in so this file reads no labels.
 */
@Composable
fun LimitsNoticeBanner(
    primaryColor: Color,
    settingsName: String,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    val text = rememberText()
    Column(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor, CutCornerShape(8.dp))
            .background(Graphite, CutCornerShape(8.dp))
            .padding(12.dp)
    ) {
        LimitsNotice.sentences(text).forEach { sentence ->
            ConfirmBodyText(sentence, bold = true)
            Spacer(modifier = Modifier.height(4.dp))
        }
        Spacer(modifier = Modifier.height(4.dp))
        ConfirmBodyText(LimitsNotice.whereToReadAgain(text, settingsName), color = Color.Gray)
        Spacer(modifier = Modifier.height(10.dp))
        NeonButton(text.get(LimitsNotice.GOT_IT), mainColor = primaryColor) { onDismiss() }
    }
}
