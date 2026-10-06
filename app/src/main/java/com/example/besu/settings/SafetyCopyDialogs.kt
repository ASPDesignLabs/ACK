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
import com.example.besu.core.StorageCatalogue
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.rememberText

// The two confirmations for deleting one safety copy, like every other delete in ACK: the first says whether an export has been
// saved since the copy was made and offers one; the second says THIS CANNOT BE UNDONE with CANCEL as the prominent choice.
// What the words say is decided in core/SafetyCopyPolicy.kt (tested) and they are string resources in the chosen language; nothing happens except through a tap.

@Composable
fun SafetyCopyFirstDialog(
    primaryColor: Color,
    paragraphs: List<String>,
    offersExportFirst: Boolean,
    proceedLabel: String,
    onExportFirst: () -> Unit,
    onProceed: () -> Unit,
    onCancel: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = stringResource(R.string.safety_copy_title),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        paragraphs.forEachIndexed { index, text ->
            if (index > 0) Spacer(modifier = Modifier.height(10.dp))
            // The second paragraph is the one about whether an export has been saved since.
            ConfirmBodyText(text, bold = index == 1)
        }
        Spacer(modifier = Modifier.height(16.dp))
        if (offersExportFirst) {
            NeonButton(stringResource(R.string.safety_copy_export_first), Modifier.fillMaxWidth(), mainColor = primaryColor) { onExportFirst() }
            Spacer(modifier = Modifier.height(8.dp))
        }
        NeonButton(proceedLabel, Modifier.fillMaxWidth(), mainColor = RadicalRed) { onProceed() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) { onCancel() }
    }
}

@Composable
fun SafetyCopySecondDialog(
    primaryColor: Color,
    onDelete: () -> Unit,
    onCancel: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = stringResource(R.string.safety_copy_title),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        ConfirmBodyText(rememberText().get(StorageCatalogue.CANNOT_UNDO), bold = true, color = RadicalRed)
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.safety_copy_delete_copy), Modifier.fillMaxWidth(), mainColor = RadicalRed) { onDelete() }
    }
}
