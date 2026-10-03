// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import com.example.besu.core.DefaultsOffer
import com.example.besu.output.VisualPresetRepository
import com.example.besu.ui.NeonButton
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.UUID

// The one-time offer of the newer, safer defaults, for an install that already existed when they arrived. A new install
// already starts on them, and nothing here changes a setting by itself: the banner only points at the review, the review
// names exactly what would change and lets the person back up first, and each change is applied only if it was switched on
// and APPLY was tapped. It never starts HELP and never navigates anywhere.
// The decision of what to offer is core/DefaultsOffer.kt (plain Kotlin, tested); this file is only the screen.

@Composable
fun DefaultsPromptBanner(
    offer: DefaultsOffer,
    primaryColor: Color,
    onReview: () -> Unit,
    onNotNow: () -> Unit,
    modifier: Modifier = Modifier
) {
    val what = buildList {
        if (offer.unprocessedVoice) add("THE UNPROCESSED VOICE")
        if (offer.fullMessage) add("FULL MESSAGES ON SCREEN")
    }.joinToString(" AND ")
    val shape = CutCornerShape(8.dp)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.6f), shape)
            .background(primaryColor.copy(alpha = 0.08f), shape)
            .padding(12.dp)
    ) {
        Text(
            text = "NEW INSTALLS NOW START WITH $what. YOURS IS UNCHANGED, AND NOTHING CHANGES UNLESS YOU CHOOSE.",
            color = Color.LightGray,
            fontSize = 12.sp,
            lineHeight = 17.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(6.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = "[REVIEW]",
                color = primaryColor,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .clickable(onClick = onReview)
                    .padding(horizontal = 10.dp, vertical = 14.dp)
            )
            Text(
                text = "[NOT NOW]",
                color = Color.Gray,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .clickable(onClick = onNotNow)
                    .padding(horizontal = 10.dp, vertical = 14.dp)
            )
        }
    }
}

@Composable
fun DefaultsReviewDialog(
    offer: DefaultsOffer,
    primaryColor: Color,
    // The result of the last BACK UP FIRST (saved, or failed), or null if none has been tried.
    backupStatus: String?,
    onBackUpFirst: () -> Unit,
    onApply: (unprocessedVoice: Boolean, fullMessage: Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    // Every switch starts OFF: nothing is chosen for the person.
    var chooseVoice by remember { mutableStateOf(false) }
    var chooseFullMessage by remember { mutableStateOf(false) }
    val anyChosen = (offer.unprocessedVoice && chooseVoice) || (offer.fullMessage && chooseFullMessage)

    AudioDialogFrame(onDismissRequest = onDismiss, primaryColor = primaryColor, title = "NEWER DEFAULTS") {
        Column(
            modifier = Modifier
                .heightIn(max = 540.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(
                text = "New installs start with these settings. Yours stay exactly as they are unless you switch one on below and tap APPLY.",
                color = Color.White,
                fontSize = 12.sp,
                lineHeight = 17.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(14.dp))

            if (offer.unprocessedVoice) {
                DefaultsToggleRow(
                    title = "USE THE UNPROCESSED VOICE (ORGANIC)",
                    detail = "Now: CYBER, a robotic effect voice, and Emergency messages use it too. CYBER stays available to choose again.",
                    on = chooseVoice,
                    primaryColor = primaryColor
                ) { chooseVoice = !chooseVoice }
                Spacer(modifier = Modifier.height(10.dp))
            }

            if (offer.fullMessage) {
                DefaultsToggleRow(
                    title = "SHOW THE FULL MESSAGE ON SCREEN",
                    detail = "Now: a message over 5 words is cut to ALERT: plus 3 words, so the screen can show less than was spoken. " +
                        "This adds a display preset called FULL TEXT (your current colours and size, with SHOW FULL MESSAGE on) and makes " +
                        "it the active one. Your current preset is kept as it is.",
                    on = chooseFullMessage,
                    primaryColor = primaryColor
                ) { chooseFullMessage = !chooseFullMessage }
                Spacer(modifier = Modifier.height(10.dp))
            }

            Spacer(modifier = Modifier.height(4.dp))

            NeonButton("BACK UP FIRST", Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpFirst() }
            Text(
                text = backupStatus ?: "Saves a copy of your whole setup to a file you choose (the same as EXPORT .JSON). Optional.",
                color = if (backupStatus == null) Color.Gray else Color.White,
                fontSize = 11.sp,
                lineHeight = 15.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.padding(top = 6.dp)
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                NeonButton("CANCEL", Modifier.weight(1f), mainColor = Color.Gray) { onDismiss() }
                NeonButton("APPLY", Modifier.weight(1f), isActive = anyChosen, mainColor = primaryColor) {
                    if (anyChosen) {
                        onApply(offer.unprocessedVoice && chooseVoice, offer.fullMessage && chooseFullMessage)
                    }
                }
            }
        }
    }
}

@Composable
private fun DefaultsToggleRow(
    title: String,
    detail: String,
    on: Boolean,
    primaryColor: Color,
    onToggle: () -> Unit
) {
    val shape = CutCornerShape(6.dp)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, if (on) primaryColor else Color.DarkGray, shape)
            .background(if (on) primaryColor.copy(alpha = 0.12f) else Color.Transparent, shape)
            .clickable(onClick = onToggle)
            .padding(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = if (on) "[X]" else "[ ]",
                color = if (on) primaryColor else Color.Gray,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.width(10.dp))
            Text(
                text = title,
                color = if (on) primaryColor else Color.White,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f)
            )
        }
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = detail,
            color = Color.LightGray,
            fontSize = 11.sp,
            lineHeight = 15.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

/**
 * Adds a display preset called FULL TEXT, copying the look of the active one (colours, size, bold and so on) with SHOW FULL
 * MESSAGE on, and makes it the active preset. The person's own preset is not edited, so going back is just choosing it
 * again. With no preset saved yet, the copy is of the built-in default look.
 */
fun addFullTextPreset(context: Context) {
    val active = VisualPresetRepository.getActivePreset(context)
    val preset = active.copy(id = UUID.randomUUID().toString(), name = "FULL TEXT", bypassTruncation = true)
    VisualPresetRepository.savePreset(context, preset)
    VisualPresetRepository.setActivePreset(context, preset.id)
}
