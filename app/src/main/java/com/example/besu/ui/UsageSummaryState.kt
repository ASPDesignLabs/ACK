// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import android.content.Context
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.besu.core.UsageSummaryText
import com.example.besu.data.AssistPrefs
import com.example.besu.settings.ConfirmBodyText

/**
 * Whether the usage summary is on, as Compose state, so the screens that show it redraw at once when SETTINGS flips the switch (the Terminal's quiet line, the
 * SETTINGS section). Shaped like PlainWordsState. The switch itself is `ack_assist_prefs` > `usage_summary` (data/AssistPrefs.kt): off when nothing is stored, never
 * seeded, never in a backup. [set] writes it with commit() and only then changes what is shown.
 */
object UsageSummaryState {
    var on by mutableStateOf(false)
        private set

    /** Reads the saved choice. Safe to call more than once. */
    fun load(context: Context) {
        on = AssistPrefs.isUsageSummaryOn(context)
    }

    fun set(context: Context, value: Boolean) {
        AssistPrefs.setUsageSummary(context, value)
        on = value
    }
}

/**
 * The one quiet line the Terminal screen shows while the usage summary is on, so the person using ACK can always see that counting is happening (rules in
 * docs/USAGE_SUMMARY_DESIGN.md, section 7). 12 sp, no sound, no animation, nothing to tap. MainActivity draws it above the Terminal only: never on a deck, Emergency or
 * Type screen, where it could move a button that is about to be tapped.
 */
@Composable
fun UsageSummaryTerminalLine(modifier: Modifier = Modifier) {
    val text = rememberText()
    Box(modifier = modifier.fillMaxWidth().padding(bottom = 8.dp)) {
        ConfirmBodyText(UsageSummaryText.terminalLine(text), color = Color.Gray)
    }
}
