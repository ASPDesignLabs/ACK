// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.CustomVoiceRemoval
import com.example.besu.core.LabelKey
import com.example.besu.core.StorageCatalogue
import com.example.besu.ui.labelFor
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.rememberText

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
        title = labelFor(LabelKey.DELETE_CUSTOM_VOICE),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        ConfirmBodyText(stringResource(R.string.delete_voice_removes))
        Spacer(modifier = Modifier.height(10.dp))
        ConfirmBodyText(stringResource(R.string.delete_voice_only_copy), bold = true)

        if (impact.anyAffected) {
            Spacer(modifier = Modifier.height(10.dp))
            ConfirmBodyText(stringResource(R.string.delete_voice_these_voices))
            impact.affectedLabels.forEach { label ->
                Spacer(modifier = Modifier.height(3.dp))
                ConfirmBodyText("- $label")
            }
            if (impact.activeProfileChanges) {
                Spacer(modifier = Modifier.height(6.dp))
                ConfirmBodyText(stringResource(R.string.delete_voice_active_becomes, CustomVoiceRemoval.FALLBACK_PROFILE_ID))
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        ConfirmBodyText(stringResource(R.string.delete_voice_not_backup), color = Color.Gray)

        if (backupStatus != null) {
            Spacer(modifier = Modifier.height(10.dp))
            ConfirmBodyText(backupStatus, bold = true, color = primaryColor)
        }

        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(stringResource(R.string.delete_voice_export_first), Modifier.fillMaxWidth(), mainColor = primaryColor) { onExportBackupFirst() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.common_continue), Modifier.fillMaxWidth(), mainColor = RadicalRed) { onContinue() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) { onCancel() }
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
        title = labelFor(LabelKey.DELETE_CUSTOM_VOICE),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        ConfirmBodyText(rememberText().get(StorageCatalogue.CANNOT_UNDO), bold = true, color = RadicalRed)
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.delete_voice_delete), Modifier.fillMaxWidth(), mainColor = RadicalRed) { onDelete() }
    }
}
