// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.backup.BackupExporter
import com.example.besu.backup.ExportResult
import com.example.besu.core.ExportContents
import com.example.besu.ui.NeonButton
import com.example.besu.ui.TightDialogSurface

/**
 * Shown before the file picker opens for an EXPORT .JSON backup: says what the file can contain and that it is not
 * protected. The wording is in core/ExportContents.kt (tested); this only displays it. Nothing here changes by itself:
 * no checkbox, no timer, and CANCEL opens no picker. Text is 12 sp or larger; the [CANCEL] label in the header is the
 * shared dialog's own.
 */
@Composable
fun BackupWarningDialog(
    primaryColor: Color,
    onDismiss: () -> Unit,
    onChooseLocation: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "EXPORT .JSON",
        dismissLabel = "CANCEL"
    ) {
        Text(
            ExportContents.CONTAINS_HEADING,
            color = Color.White,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(6.dp))
        ExportContents.categories.forEach { category ->
            Text(
                "- ${category.label}",
                color = Color.White,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(3.dp))
        }

        Spacer(modifier = Modifier.height(12.dp))
        Text(
            ExportContents.NOT_PROTECTED,
            color = Color.White,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(12.dp))
        Text(
            ExportContents.WHERE_TO_SAVE,
            color = Color.White,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))
        NeonButton("CHOOSE WHERE TO SAVE", Modifier.fillMaxWidth(), mainColor = primaryColor) {
            onChooseLocation()
        }
    }
}

/**
 * The whole EXPORT .JSON flow in one place: the warning first, then (only after CHOOSE WHERE TO SAVE) the system file
 * picker, then BackupExporter.writeBackup and its result. Returns the function that starts it; the dialog it shows is
 * part of this composable, so the caller only has to call the function from a tap.
 *
 * Every entry point to a settings-style export goes through here so none of them can skip the warning. (The Terminal's
 * /backup confirm is the other entry point: it prints the same facts from ExportContents.terminalText() instead.)
 */
@Composable
fun rememberBackupExportFlow(
    context: Context,
    primaryColor: Color,
    // Called after an export was tried (and reported), so a screen can refresh what depends on it, such as whether a safety
    // copy has a newer export. Not called if the person cancels the picker.
    onResult: (ExportResult) -> Unit = {}
): () -> Unit {
    var showWarning by remember { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        uri?.let {
            val result = BackupExporter.writeBackup(context, it)
            BackupExporter.report(context, result)
            onResult(result)
        }
    }

    if (showWarning) {
        BackupWarningDialog(
            primaryColor = primaryColor,
            onDismiss = { showWarning = false },
            onChooseLocation = {
                showWarning = false
                launcher.launch("ack_backup_${System.currentTimeMillis()}.json")
            }
        )
    }

    return { showWarning = true }
}
