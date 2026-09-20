package com.example.besu.settings

import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import android.content.Context
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
import kotlinx.coroutines.launch

// PROTOCOL -> "MANAGE RECORDINGS": every voice recording across every
// Quick Actions deck, one place to browse/play/delete them regardless of
// which deck or group they're bound to. Recording itself only ever happens
// from a Quick Actions slot's own EDIT screen (QuickActionsDeck.kt) --
// this dialog is management only, no record button here.
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
                "NO RECORDINGS YET. RECORD ONE FROM A QUICK ACTIONS PROMPT'S EDIT SCREEN (HOLD A SLOT TO EDIT IT).",
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
                            val loaded = VoiceRecordingRepository.loadPcm(context, recording.id)
                            if (loaded != null && isPlayingId == null) {
                                isPlayingId = recording.id
                                coroutineScope.launch {
                                    VoiceRecordingRepository.playPreview(context, loaded.first, loaded.second)
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
                "This removes the recording. The prompt it's bound to stays and falls back to synthesized speech. This cannot be undone.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("DELETE", Modifier.weight(1f), mainColor = RadicalRed) {
                    if (target != null) {
                        VoiceRecordingRepository.delete(context, target.id)
                        CommandRepository.setQuickActionSlotRecording(
                            context = context,
                            deckId = target.deckId,
                            groupIndex = target.groupIndex,
                            slotIndex = target.slotIndex,
                            recordingId = null
                        )
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
    // reads over a handful of decks/slots, and it means a rename of the
    // deck or the slot's own label since the recording was made still
    // shows up correctly here instead of a stale snapshot.
    val deckName = remember(recording.deckId) {
        CommandRepository.getDeckName(context, recording.deckId)
    }
    val slotLabel = remember(recording.deckId, recording.groupIndex, recording.slotIndex) {
        val config = CommandRepository.getQuickActionsConfig(context, recording.deckId)
        val group = config.groups.find { it.groupIndex == recording.groupIndex }
        group?.slots?.find { it.slotIndex == recording.slotIndex }?.label
            ?: "SLOT ${recording.slotIndex + 1}"
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.4f), AckHelpShape)
            .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
            .padding(10.dp)
    ) {
        Text(
            text = "$deckName / G${recording.groupIndex + 1} / $slotLabel",
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
