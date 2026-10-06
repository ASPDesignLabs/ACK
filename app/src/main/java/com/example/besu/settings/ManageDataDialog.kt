// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.StorageCatalogue
import com.example.besu.data.DataWipe
import com.example.besu.data.LogEntry
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface
import com.example.besu.ui.rememberText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * DELETE DATA: every storage area with what it holds and how much is stored, a DELETE button for each, and DELETE EVERYTHING.
 * What each area is, how it is backed up and what the confirmations say all come from core/StorageCatalogue.kt (tested) and are string resources in the chosen
 * language; what is deleted comes from data/DataWipe.kt, which reports areas by id. This only displays them.
 *
 * Every delete asks twice, with CANCEL as the safe choice. Nothing is deleted or changed by opening this screen, and nothing
 * happens on a timer. Text is 12 sp or larger and the buttons are NeonButton (12 sp); the header's [CLOSE]/[CANCEL] is the
 * shared dialog's own 10 sp label. While a delete is running the dialogs ignore dismissing, so it cannot be abandoned half-way.
 */
@Composable
fun ManageDataDialog(
    context: Context,
    primaryColor: Color,
    logs: SnapshotStateList<LogEntry>,
    /** Starts the EXPORT .JSON flow (its warning comes first). The confirmation stays open underneath. */
    onBackUpFirst: () -> Unit,
    /** Called after a successful delete. [needsRestart]: the caller shows the toast and does the delayed restart. */
    onWiped: (needsRestart: Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    val words = rememberText()
    var refresh by remember { mutableIntStateOf(0) }
    var amounts by remember { mutableStateOf<Map<String, DataWipe.Amount>>(emptyMap()) }
    LaunchedEffect(refresh) {
        amounts = withContext(Dispatchers.IO) {
            StorageCatalogue.areas.associate { it.id to DataWipe.measure(context, it) } +
                (StorageCatalogue.EVERYTHING_ID to DataWipe.measureEverything(context))
        }
    }

    var firstFor by remember { mutableStateOf<String?>(null) }
    var secondFor by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun areasFor(id: String) =
        if (id == StorageCatalogue.EVERYTHING_ID) StorageCatalogue.areas else listOf(StorageCatalogue.area(id))
    fun amountTextFor(id: String) = amounts[id]?.text(words) ?: words.get(StorageCatalogue.COUNTING)

    fun runDelete(id: String) {
        if (busy) return
        busy = true
        status = null
        scope.launch {
            val selected = areasFor(id)
            val result = withContext(Dispatchers.IO) {
                DataWipe.wipe(context, selected, id == StorageCatalogue.EVERYTHING_ID, logs)
            }
            DataWipe.logResult(context, result)
            busy = false
            firstFor = null
            secondFor = null
            refresh++
            if (result.allOk) {
                if (StorageCatalogue.needsRestart(selected)) {
                    onWiped(true)
                } else {
                    status = StorageCatalogue.successStatus(words, result.deleted)
                    Toast.makeText(context, StorageCatalogue.successToast(words, result.deleted), Toast.LENGTH_LONG).show()
                }
            } else {
                status = StorageCatalogue.failureStatus(words, result.deleted, result.failed)
            }
        }
    }

    TightDialogSurface(
        onDismiss = { if (!busy) onDismiss() },
        primaryColor = primaryColor,
        title = stringResource(R.string.delete_data_title),
        dismissLabel = stringResource(R.string.common_close)
    ) {
        ConfirmBodyText(stringResource(R.string.delete_data_intro), color = Color.Gray)
        if (busy) {
            Spacer(modifier = Modifier.height(8.dp))
            ConfirmBodyText(stringResource(R.string.delete_data_deleting), bold = true, color = primaryColor)
        }
        status?.let {
            Spacer(modifier = Modifier.height(8.dp))
            ConfirmBodyText(it, bold = true, color = primaryColor)
        }

        StorageCatalogue.areas.forEach { area ->
            Spacer(modifier = Modifier.height(14.dp))
            Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
            Spacer(modifier = Modifier.height(10.dp))
            ConfirmBodyText(StorageCatalogue.label(words, area), bold = true)
            Spacer(modifier = Modifier.height(2.dp))
            ConfirmBodyText(StorageCatalogue.holds(words, area), color = Color.Gray)
            Spacer(modifier = Modifier.height(2.dp))
            ConfirmBodyText(amountTextFor(area.id), color = primaryColor)
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.common_delete), Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                if (!busy) firstFor = area.id
            }
        }

        Spacer(modifier = Modifier.height(14.dp))
        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
        Spacer(modifier = Modifier.height(10.dp))
        ConfirmBodyText(words.get(StorageCatalogue.EVERYTHING_LABEL), bold = true)
        Spacer(modifier = Modifier.height(2.dp))
        ConfirmBodyText(words.get(StorageCatalogue.EVERYTHING_HOLDS), color = Color.Gray)
        Spacer(modifier = Modifier.height(2.dp))
        ConfirmBodyText(amountTextFor(StorageCatalogue.EVERYTHING_ID), color = primaryColor)
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(stringResource(R.string.delete_data_delete_everything), Modifier.fillMaxWidth(), mainColor = RadicalRed) {
            if (!busy) firstFor = StorageCatalogue.EVERYTHING_ID
        }
    }

    // --- first confirmation: what, how much, how to save it first ---
    val first = firstFor
    if (first != null && secondFor == null) {
        val everything = first == StorageCatalogue.EVERYTHING_ID
        val paragraphs = if (everything) {
            StorageCatalogue.firstConfirmationEverything(words, amountTextFor(first))
        } else {
            StorageCatalogue.firstConfirmation(words, StorageCatalogue.area(first), amountTextFor(first))
        }
        TightDialogSurface(
            onDismiss = { if (!busy) firstFor = null },
            primaryColor = primaryColor,
            title = stringResource(R.string.delete_data_confirm_title, StorageCatalogue.labelOf(words, first)),
            dismissLabel = stringResource(R.string.common_cancel)
        ) {
            paragraphs.forEachIndexed { index, text ->
                if (index > 0) Spacer(modifier = Modifier.height(10.dp))
                // The third paragraph is always the backup note: how to save it first, or that it is not backed up.
                ConfirmBodyText(text, bold = index == 2)
            }
            Spacer(modifier = Modifier.height(16.dp))
            // Only an area EXPORT .JSON covers offers BACK UP FIRST; the others name the backup that does (in the note above).
            if (everything || StorageCatalogue.offersBackupFirst(StorageCatalogue.area(first))) {
                NeonButton(stringResource(R.string.delete_data_back_up_first), Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpFirst() }
                Spacer(modifier = Modifier.height(8.dp))
            }
            NeonButton(stringResource(R.string.common_continue), Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                if (!busy) secondFor = first
            }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) {
                if (!busy) firstFor = null
            }
        }
    }

    // --- second confirmation: CANCEL is the prominent choice ---
    val second = secondFor
    if (second != null) {
        // Cancelling here abandons the delete altogether (it does not fall back into the first confirmation).
        val cancelBoth: () -> Unit = { if (!busy) { secondFor = null; firstFor = null } }
        TightDialogSurface(
            onDismiss = { cancelBoth() },
            primaryColor = primaryColor,
            title = stringResource(R.string.delete_data_confirm_title, StorageCatalogue.labelOf(words, second)),
            dismissLabel = stringResource(R.string.common_cancel)
        ) {
            ConfirmBodyText(words.get(StorageCatalogue.CANNOT_UNDO), bold = true, color = RadicalRed)
            if (busy) {
                Spacer(modifier = Modifier.height(10.dp))
                ConfirmBodyText(stringResource(R.string.delete_data_deleting), bold = true, color = primaryColor)
            }
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(stringResource(R.string.common_cancel), Modifier.fillMaxWidth(), mainColor = primaryColor) { cancelBoth() }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.delete_data_confirm_title, StorageCatalogue.labelOf(words, second)), Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                runDelete(second)
            }
        }
    }
}
