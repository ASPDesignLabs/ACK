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
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.LogExport
import com.example.besu.core.LogExportContents
import com.example.besu.data.LogEntry
import com.example.besu.data.LogExporter
import com.example.besu.ui.NeonButton
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.rememberText
import java.time.ZoneId

/**
 * Shown before the file picker opens for SAVE MESSAGE LOG TO A FILE: how many messages the file would hold, what it contains and what it does not, that it is not
 * protected and that a screenshot of the log is a copy too. The wording is core/LogExportContents.kt (tested); this only displays it. Nothing happens by itself:
 * no checkbox, no timer, CANCEL opens no picker, and with no messages there is nothing to choose, only a line saying so. Text is 12 sp or larger.
 */
@Composable
fun LogExportWarningDialog(
    primaryColor: Color,
    logName: String,
    messageCount: Int,
    onDismiss: () -> Unit,
    onChooseLocation: () -> Unit
) {
    val text = rememberText()
    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = text.get(LogExportContents.BUTTON),
        dismissLabel = stringResource(R.string.common_cancel)
    ) {
        ConfirmBodyText(LogExportContents.countLine(text, messageCount), bold = true)
        Spacer(modifier = Modifier.height(12.dp))
        if (messageCount == 0) {
            ConfirmBodyText(text.get(LogExportContents.NONE_NOW))
            return@TightDialogSurface
        }
        ConfirmBodyText(text.get(LogExportContents.CONTAINS_HEADING), bold = true)
        Spacer(modifier = Modifier.height(6.dp))
        LogExportContents.contains(text, logName).forEach { bullet ->
            ConfirmBodyText("- $bullet")
            Spacer(modifier = Modifier.height(3.dp))
        }
        ConfirmBodyText(text.get(LogExportContents.NOT_INCLUDED))
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(LogExportContents.NOT_PROTECTED), bold = true)
        Spacer(modifier = Modifier.height(6.dp))
        ConfirmBodyText(text.get(LogExportContents.COPY_TOO))
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(LogExportContents.WHERE_TO_SAVE))
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(stringResource(R.string.export_choose_where), Modifier.fillMaxWidth(), mainColor = primaryColor) {
            onChooseLocation()
        }
    }
}

/**
 * The whole SAVE MESSAGE LOG flow in one place: the warning first, then (only after CHOOSE WHERE TO SAVE) the system file picker, then LogExporter.write and its
 * result. Returns the function that starts it; the dialog it shows is part of this composable, so the caller only has to call the function from a tap.
 * [logs] is the live Terminal log; it is read when the warning opens (for the count) and again when the file is written, so what is saved is what is kept then.
 */
@Composable
fun rememberLogExportFlow(
    context: Context,
    primaryColor: Color,
    logName: String,
    logs: SnapshotStateList<LogEntry>
): () -> Unit {
    var count by remember { mutableStateOf<Int?>(null) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
        uri?.let {
            val result = LogExporter.write(context, it, logs.toList())
            LogExporter.report(context, result)
        }
    }

    val shown = count
    if (shown != null) {
        LogExportWarningDialog(
            primaryColor = primaryColor,
            logName = logName,
            messageCount = shown,
            onDismiss = { count = null },
            onChooseLocation = {
                count = null
                launcher.launch(LogExport.fileName(System.currentTimeMillis(), ZoneId.systemDefault()))
            }
        )
    }

    return { count = LogExporter.messagesNow(context, logs.toList()).size }
}
