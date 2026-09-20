package com.example.besu.settings

import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// PROTOCOL -> "MANAGE RECORDINGS": every voice recording in the app --
// Quick Actions slots, Quick-Access keys, and Matrix nodes -- one place to
// browse/play/delete them regardless of what they're bound to. Recording
// itself only ever happens from each feature's own edit UI (a Quick
// Actions slot's EDIT dialog, a Quick-Access key's REC button in
// PROTOCOL, or a Matrix node's editor) -- this dialog is management only,
// no record button here.
@Composable
fun ManageRecordingsDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val recordings = remember(refreshKey) {
        VoiceRecordingRepository.getAll(context).sortedByDescending { it.createdAt }
    }
    var isPlayingId by remember { mutableStateOf<String?>(null) }
    var confirmingDeleteId by remember { mutableStateOf<String?>(null) }
    val coroutineScope = rememberCoroutineScope()

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "MANAGE RECORDINGS",
        subtitle = "${recordings.size} RECORDING${if (recordings.size == 1) "" else "S"}"
    ) {
        if (recordings.isEmpty()) {
            Text(
                "NO RECORDINGS YET. RECORD ONE FROM A QUICK ACTIONS SLOT'S EDIT SCREEN, A QUICK-ACCESS KEY'S REC BUTTON, OR A MATRIX NODE'S EDITOR.",
                color = Color.DarkGray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        } else {
            Column(
                modifier = Modifier
                    .heightIn(max = 420.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                recordings.forEach { recording ->
                    RecordingRow(
                        context = context,
                        primaryColor = primaryColor,
                        recording = recording,
                        isPlaying = isPlayingId == recording.id,
                        onPlay = {
                            if (isPlayingId == null) {
                                isPlayingId = recording.id
                                // Routed through OutputService -- the same DSP/volume
                                // pipeline every other prompt plays through, rather than
                                // a standalone AudioTrack that could end up silent.
                                context.startService(Intent(context, OutputService::class.java).apply {
                                    action = "PREVIEW_RECORDING"
                                    putExtra("recording_id", recording.id)
                                })
                                coroutineScope.launch {
                                    delay(recording.durationMs + 300)
                                    isPlayingId = null
                                }
                            }
                        },
                        onDeleteRequested = { confirmingDeleteId = recording.id }
                    )
                }
            }
        }
    }

    val deletingId = confirmingDeleteId
    if (deletingId != null) {
        val target = recordings.find { it.id == deletingId }
        TightDialogSurface(
            onDismiss = { confirmingDeleteId = null },
            primaryColor = RadicalRed,
            title = "DELETE RECORDING",
            dismissLabel = "CANCEL"
        ) {
            Text(
                "This removes the recording. Whatever it's bound to stays and falls back to synthesized speech (or, for a Matrix entry, its normal variable-resolved text). This cannot be undone.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("DELETE", Modifier.weight(1f), mainColor = RadicalRed) {
                    if (target != null) {
                        VoiceRecordingRepository.delete(context, target.id)
                        // Only a Quick Actions slot stores a pointer back to
                        // the recording (QuickActionSlot.recordingId) --
                        // Quick-Access keys and Matrix nodes look theirs up
                        // live by index/path, nothing else to clear.
                        if (target.owner == RecordingOwner.QUICK_ACTION &&
                            target.deckId != null && target.groupIndex != null && target.slotIndex != null
                        ) {
                            CommandRepository.setQuickActionSlotRecording(
                                context = context,
                                deckId = target.deckId,
                                groupIndex = target.groupIndex,
                                slotIndex = target.slotIndex,
                                recordingId = null
                            )
                        }
                    }
                    confirmingDeleteId = null
                    refreshKey++
                }
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    confirmingDeleteId = null
                }
            }
        }
    }
}

@Composable
private fun RecordingRow(
    context: Context,
    primaryColor: Color,
    recording: VoiceRecording,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onDeleteRequested: () -> Unit
) {
    // Resolved fresh each time this dialog opens -- cheap SharedPreferences
    // reads, and it means a rename of the deck/key/node label since the
    // recording was made still shows up correctly here instead of a stale
    // snapshot.
    val boundToLabel = remember(recording.id) {
        when (recording.owner) {
            RecordingOwner.QUICK_ACTION -> {
                val deckId = recording.deckId ?: "DEFAULT"
                val deckName = CommandRepository.getDeckName(context, deckId)
                val config = CommandRepository.getQuickActionsConfig(context, deckId)
                val group = config.groups.find { it.groupIndex == recording.groupIndex }
                val slotLabel = group?.slots?.find { it.slotIndex == recording.slotIndex }?.label
                    ?: "SLOT ${(recording.slotIndex ?: 0) + 1}"
                "$deckName / G${(recording.groupIndex ?: 0) + 1} / $slotLabel"
            }
            RecordingOwner.QUICK_ACCESS_KEY -> {
                val keyLabel = CommandRepository.getHeaderShortcuts(context)
                    .getOrNull(recording.slotIndex ?: -1)
                    ?.label
                    ?: "M${(recording.slotIndex ?: 0) + 1}"
                "QUICK-ACCESS KEY / $keyLabel"
            }
            RecordingOwner.MATRIX_NODE -> {
                val deckId = recording.deckId ?: "DEFAULT"
                val deckName = CommandRepository.getDeckName(context, deckId)
                val nodeLabel = recording.path?.let { CommandRepository.findMatrixNode(context, it)?.label }
                    ?: "UNKNOWN NODE"
                "$deckName / ${recording.profile ?: "DEFAULT"} / $nodeLabel"
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.4f), AckHelpShape)
            .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
            .padding(10.dp)
    ) {
        Text(
            text = boundToLabel,
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = VoiceRecordingRepository.formatDurationMs(recording.durationMs),
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
        if (recording.owner == RecordingOwner.MATRIX_NODE && !recording.enabled) {
            Text(
                text = "DISABLED -- entry text changed since this was recorded",
                color = RadicalRed,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton(
                text = if (isPlaying) "PLAYING..." else "PLAY",
                modifier = Modifier.weight(1f),
                isActive = !isPlaying,
                mainColor = primaryColor,
                onClick = onPlay
            )
            TightPanelButton(
                text = "DELETE",
                modifier = Modifier.weight(1f),
                mainColor = RadicalRed,
                onClick = onDeleteRequested
            )
        }
    }
}
