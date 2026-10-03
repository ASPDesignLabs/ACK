// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.core.StorageCatalogue
import com.example.besu.data.DataWipe
import com.example.besu.data.LogEntry
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * DELETE DATA: every storage area with what it holds and how much is stored, a DELETE button for each, and DELETE EVERYTHING.
 * What each area is, how it is backed up and what the confirmations say all come from core/StorageCatalogue.kt (tested);
 * what is deleted comes from data/DataWipe.kt. This only displays them.
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
    fun labelFor(id: String) =
        if (id == StorageCatalogue.EVERYTHING_ID) StorageCatalogue.EVERYTHING_LABEL else StorageCatalogue.area(id).label
    fun amountTextFor(id: String) = amounts[id]?.text ?: "STILL COUNTING"

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
                    status = "DELETED: ${result.deleted.joinToString(", ")}."
                    Toast.makeText(context, "DELETED: ${result.deleted.joinToString(", ")}", Toast.LENGTH_LONG).show()
                }
            } else {
                status = buildString {
                    append("COULD NOT DELETE: ${result.failed.joinToString(", ")}. ")
                    if (result.deleted.isNotEmpty()) append("DELETED: ${result.deleted.joinToString(", ")}. ")
                    if (result.failed.contains(StorageCatalogue.area(StorageCatalogue.ID_SAVED_LOCATIONS).label)) {
                        append("SAVED LOCATIONS: GOOGLE'S LOCATION SERVICE MUST CONFIRM ITS ALERTS ARE REMOVED FIRST. TRY AGAIN, OR TURN GEO-PROTOCOL OFF FIRST. ")
                    }
                    append("ACK DID NOT RESTART. CLOSE AND REOPEN IT TO SEE ALL CHANGES.")
                }
            }
        }
    }

    TightDialogSurface(
        onDismiss = { if (!busy) onDismiss() },
        primaryColor = primaryColor,
        title = "DELETE DATA",
        dismissLabel = "CLOSE"
    ) {
        Body("EACH DELETE ASKS TWICE, AND NOTHING CHANGES UNTIL YOU CONFIRM THE SECOND TIME. WHERE A BACKUP EXISTS, SAVE IT FIRST. DELETING CANNOT BE UNDONE.", color = Color.Gray)
        if (busy) {
            Spacer(modifier = Modifier.height(8.dp))
            Body("DELETING...", bold = true, color = primaryColor)
        }
        status?.let {
            Spacer(modifier = Modifier.height(8.dp))
            Body(it, bold = true, color = primaryColor)
        }

        StorageCatalogue.areas.forEach { area ->
            Spacer(modifier = Modifier.height(14.dp))
            Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
            Spacer(modifier = Modifier.height(10.dp))
            Body(area.label, bold = true)
            Spacer(modifier = Modifier.height(2.dp))
            Body(area.holds, color = Color.Gray)
            Spacer(modifier = Modifier.height(2.dp))
            Body(amountTextFor(area.id), color = primaryColor)
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton("DELETE", Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                if (!busy) firstFor = area.id
            }
        }

        Spacer(modifier = Modifier.height(14.dp))
        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
        Spacer(modifier = Modifier.height(10.dp))
        Body(StorageCatalogue.EVERYTHING_LABEL, bold = true)
        Spacer(modifier = Modifier.height(2.dp))
        Body("ALL OF THE ABOVE, AND ACK'S NOTE OF WHETHER THIS PHONE IS A NEW INSTALL.", color = Color.Gray)
        Spacer(modifier = Modifier.height(2.dp))
        Body(amountTextFor(StorageCatalogue.EVERYTHING_ID), color = primaryColor)
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton("DELETE EVERYTHING", Modifier.fillMaxWidth(), mainColor = RadicalRed) {
            if (!busy) firstFor = StorageCatalogue.EVERYTHING_ID
        }
    }

    // --- first confirmation: what, how much, how to save it first ---
    val first = firstFor
    if (first != null && secondFor == null) {
        val everything = first == StorageCatalogue.EVERYTHING_ID
        val paragraphs = if (everything) {
            StorageCatalogue.firstConfirmationEverything(amountTextFor(first))
        } else {
            StorageCatalogue.firstConfirmation(StorageCatalogue.area(first), amountTextFor(first))
        }
        TightDialogSurface(
            onDismiss = { if (!busy) firstFor = null },
            primaryColor = primaryColor,
            title = "DELETE ${labelFor(first)}",
            dismissLabel = "CANCEL"
        ) {
            paragraphs.forEachIndexed { index, text ->
                if (index > 0) Spacer(modifier = Modifier.height(10.dp))
                // The third paragraph is always the backup note: how to save it first, or that it is not backed up.
                Body(text, bold = index == 2)
            }
            Spacer(modifier = Modifier.height(16.dp))
            // Only an area EXPORT .JSON covers offers BACK UP FIRST; the others name the backup that does (in the note above).
            if (everything || StorageCatalogue.offersBackupFirst(StorageCatalogue.area(first))) {
                NeonButton("BACK UP FIRST", Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpFirst() }
                Spacer(modifier = Modifier.height(8.dp))
            }
            NeonButton("CONTINUE", Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                if (!busy) secondFor = first
            }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton("CANCEL", Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) {
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
            title = "DELETE ${labelFor(second)}",
            dismissLabel = "CANCEL"
        ) {
            Body(StorageCatalogue.CANNOT_UNDO, bold = true, color = RadicalRed)
            if (busy) {
                Spacer(modifier = Modifier.height(10.dp))
                Body("DELETING...", bold = true, color = primaryColor)
            }
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton("CANCEL", Modifier.fillMaxWidth(), mainColor = primaryColor) { cancelBoth() }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton("DELETE ${labelFor(second)}", Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                runDelete(second)
            }
        }
    }
}

@Composable
private fun Body(text: String, bold: Boolean = false, color: Color = Color.White) {
    Text(
        text,
        color = color,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal
    )
}
