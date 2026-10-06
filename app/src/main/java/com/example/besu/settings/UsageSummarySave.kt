// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.UsageSummaryFile
import com.example.besu.core.UsageSummaryText
import com.example.besu.data.UsageSummaryExporter
import com.example.besu.data.UsageTallyRepository
import com.example.besu.ui.NeonButton
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.rememberText
import java.time.ZoneId

/**
 * Shown before the file picker opens for SAVE USAGE SUMMARY TO A FILE: how many counted messages the file would cover, what it contains and what it does not, that it still
 * shows a daily pattern, that it is not protected and that a screenshot is a copy too. The wording is core/UsageSummaryText.kt (tested); this only displays it. Nothing
 * happens by itself: no checkbox, no timer, CANCEL opens no picker, and with nothing counted there is nothing to choose, only a line saying so. Text is 12 sp or larger.
 */
@Composable
fun UsageSummarySaveDialog(
    primaryColor: Color,
    messageCount: Long,
    onDismiss: () -> Unit,
    onChooseLocation: () -> Unit
) {
    val text = rememberText()
    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = text.get(UsageSummaryText.SAVE_BUTTON),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        ConfirmBodyText(UsageSummaryText.saveCountLine(text, messageCount), bold = true)
        Spacer(modifier = Modifier.height(12.dp))
        if (messageCount == 0L) {
            ConfirmBodyText(text.get(UsageSummaryText.SAVE_NONE))
            return@TightDialogSurface
        }
        ConfirmBodyText(text.get(UsageSummaryText.SAVE_CONTAINS_HEADING), bold = true)
        Spacer(modifier = Modifier.height(6.dp))
        ConfirmBodyText("- ${UsageSummaryText.saveContains(text)}")
        Spacer(modifier = Modifier.height(3.dp))
        ConfirmBodyText(text.get(UsageSummaryText.SAVE_NOT_INCLUDED))
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(UsageSummaryText.SAVE_PATTERN), bold = true)
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(UsageSummaryText.NOT_PROTECTED), bold = true)
        Spacer(modifier = Modifier.height(6.dp))
        ConfirmBodyText(text.get(UsageSummaryText.SAVE_COPY_TOO))
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(UsageSummaryText.WHERE_TO_SAVE))
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(stringResource(R.string.export_choose_where), Modifier.fillMaxWidth(), mainColor = primaryColor) {
            onChooseLocation()
        }
    }
}

/**
 * The whole SAVE USAGE SUMMARY flow in one place: the warning first, then (only after CHOOSE WHERE TO SAVE) the system file picker, then UsageSummaryExporter.write and its
 * result. Returns the function that starts it; the dialog it shows is part of this composable, so the caller only has to call the function from a tap.
 */
@Composable
fun rememberUsageSummarySaveFlow(context: Context, primaryColor: Color): () -> Unit {
    var count by remember { mutableStateOf<Long?>(null) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
        uri?.let {
            val result = UsageSummaryExporter.write(context, it)
            UsageSummaryExporter.report(context, result)
        }
    }

    val shown = count
    if (shown != null) {
        UsageSummarySaveDialog(
            primaryColor = primaryColor,
            messageCount = shown,
            onDismiss = { count = null },
            onChooseLocation = {
                count = null
                launcher.launch(UsageSummaryFile.fileName(System.currentTimeMillis(), ZoneId.systemDefault()))
            }
        )
    }

    return { count = UsageTallyRepository.messageCount(context) }
}
