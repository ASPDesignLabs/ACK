// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.core.CustomVoiceRemoval
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface

// The two confirmations DELETE CUSTOM VOICE needs before anything is removed. Nothing happens in either dialog except
// through a tap; no timer, no checkbox. Text is 12 sp or larger and the buttons are NeonButton (12 sp), so the header's
// [CANCEL] is the only 10 sp text, and it is the shared dialog's own.

/**
 * First confirmation: what will be removed, that the only copy may be on this phone, which voices will switch (if any),
 * and a way to save a voice backup first. [backupStatus] is the result of that backup if one was just tried, so the person
 * can see it worked before they continue.
 */
@Composable
fun DeleteVoiceFirstDialog(
    primaryColor: Color,
    impact: CustomVoiceRemoval.Impact,
    backupStatus: String?,
    onExportBackupFirst: () -> Unit,
    onContinue: () -> Unit,
    onCancel: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = "DELETE CUSTOM VOICE",
        dismissLabel = "CANCEL"
    ) {
        BodyText("THIS REMOVES YOUR TRAINED VOICE FROM THIS PHONE: THE VOICE MODEL, ITS SETTINGS FILE, AND THE TEMPORARY FILE MADE FROM IT.")
        Spacer(modifier = Modifier.height(10.dp))
        BodyText("THE ONLY COPY MAY BE ON THIS PHONE. IF YOU MIGHT WANT IT AGAIN, SAVE A VOICE BACKUP FIRST.", bold = true)

        if (impact.anyAffected) {
            Spacer(modifier = Modifier.height(10.dp))
            BodyText("THESE VOICES USE IT AND WILL SWITCH TO A NORMAL VOICE:")
            impact.affectedLabels.forEach { label ->
                Spacer(modifier = Modifier.height(3.dp))
                BodyText("- $label")
            }
            if (impact.activeProfileChanges) {
                Spacer(modifier = Modifier.height(6.dp))
                BodyText("YOUR ACTIVE VOICE WILL BECOME ${CustomVoiceRemoval.FALLBACK_PROFILE_ID}.")
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        BodyText("THIS DOES NOT DELETE A BACKUP YOU SAVED ELSEWHERE.", color = Color.Gray)

        if (backupStatus != null) {
            Spacer(modifier = Modifier.height(10.dp))
            BodyText(backupStatus, bold = true, color = primaryColor)
        }

        Spacer(modifier = Modifier.height(16.dp))
        NeonButton("EXPORT VOICE BACKUP FIRST", Modifier.fillMaxWidth(), mainColor = primaryColor) { onExportBackupFirst() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton("CONTINUE", Modifier.fillMaxWidth(), mainColor = RadicalRed) { onContinue() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton("CANCEL", Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) { onCancel() }
    }
}

/** Second confirmation. CANCEL is the prominent button; the destructive one is red and below it. */
@Composable
fun DeleteVoiceSecondDialog(
    primaryColor: Color,
    onDelete: () -> Unit,
    onCancel: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = "DELETE CUSTOM VOICE",
        dismissLabel = "CANCEL"
    ) {
        BodyText("THIS CANNOT BE UNDONE.", bold = true, color = RadicalRed)
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton("CANCEL", Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton("DELETE VOICE", Modifier.fillMaxWidth(), mainColor = RadicalRed) { onDelete() }
    }
}

@Composable
private fun BodyText(text: String, bold: Boolean = false, color: Color = Color.White) {
    Text(
        text,
        color = color,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal
    )
}
