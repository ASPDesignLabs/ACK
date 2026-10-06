// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.besu.capture.ClipFlags
import com.example.besu.capture.ClipState
import com.example.besu.capture.StoreException
import com.example.besu.capture.StoredClip
import com.example.besu.capture.StoredSession
import com.example.besu.R
import com.example.besu.core.CaptureText
import com.example.besu.output.OutputService
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import com.example.besu.ui.rememberText
import com.example.besu.ui.theme.Graphite
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

// One recording session, opened: listen to any clip (through the app's normal audio output), mark clips, decide about repaired
// recordings, save the session to a file or delete it. Free-speech recordings are long, so they are described rather than played.
@Composable
internal fun SessionDetailDialog(
    context: Context,
    primaryColor: Color,
    sessionId: String,
    onSave: (StoredSession) -> Unit,
    onDelete: () -> Unit,
    onClose: () -> Unit,
) {
    val store = remember { TrainingCapture.store(context) }
    val words = rememberText()
    var session by remember { mutableStateOf<StoredSession?>(null) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    var deleteClipIndex by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(reload) {
        try {
            session = withContext(Dispatchers.IO) { store.getSession(sessionId) }
        } catch (e: StoreException) {
            error = e.message ?: words.get("capture_session_unreadable")
        }
    }

    fun change(action: () -> Unit) {
        try { action() } catch (e: StoreException) { error = e.message ?: words.get("capture_action_failed") }
        reload++
    }

    fun play(clip: StoredClip) {
        val file = store.clipFile(sessionId, clip.index)
        context.startService(Intent(context, OutputService::class.java).apply {
            action = "PREVIEW_RECORDING"
            putExtra("recording_path", file.absolutePath)
        })
    }

    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(
            modifier = Modifier.fillMaxWidth(0.96f).background(Graphite).border(1.dp, primaryColor).padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            val s = session
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.capture_session), color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
                Text(stringResource(R.string.manual_close), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.heightIn(min = 48.dp).clickable { onClose() }.padding(8.dp))
            }
            if (error.isNotEmpty()) Notice(error, RadicalRed, onDismiss = { error = "" })
            if (s == null) {
                Text(stringResource(R.string.capture_loading), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
            } else {
                Text(
                    CaptureText.sessionTitle(words, s.mode, s.scriptTitle, s.label),
                    color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                )
                Text(
                    CaptureText.detailsLine(words, s.id, s.sampleRate, s.source, s.noiseFloorDbfs, s.closed),
                    color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
                )

                if (s.mode == "free") {
                    val r = s.recording
                    if (r == null) {
                        Text(stringResource(R.string.capture_nothing_recorded), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    } else {
                        Text(
                            CaptureText.recordingLine(words, r.durationS, r.pieces.size, r.state),
                            color = Color.White, fontSize = 11.sp, fontFamily = FontFamily.Monospace,
                        )
                        if (r.state == ClipState.RECOVERED) {
                            Text(
                                stringResource(R.string.capture_recovered_note),
                                color = RadicalRed, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                            )
                            TightPanelButton(stringResource(R.string.capture_keep_recording), Modifier.fillMaxWidth(), mainColor = primaryColor) { change { store.keepRecoveredRecording(sessionId) } }
                        }
                    }
                } else {
                    val shown = s.clips.sortedBy { it.index }
                    Text(CaptureText.keptAside(words, shown.count { it.state == ClipState.DONE }, shown.count { it.state != ClipState.DONE }), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    LazyColumn(modifier = Modifier.fillMaxWidth().heightIn(max = 360.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(shown, key = { it.index }) { c ->
                            ClipRow(c, primaryColor, store.clipFile(sessionId, c.index).isFile,
                                onPlay = { play(c) },
                                onToggle = { flag ->
                                    val set = c.flags.filter { it in ClipFlags.PERSON }.toMutableSet()
                                    if (!set.add(flag)) set.remove(flag)
                                    change { store.setPersonFlags(sessionId, c.index, set) }
                                },
                                onKeep = { change { store.keepRecovered(sessionId, c.index) } },
                                onAside = { change { store.setRecoveredAside(sessionId, c.index) } },
                                onDelete = { deleteClipIndex = c.index },
                            )
                        }
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    TightPanelButton(stringResource(R.string.capture_save_file), Modifier.weight(1f), isActive = s.closed, mainColor = primaryColor) { if (s.closed) onSave(s) }
                    TightPanelButton(stringResource(R.string.capture_delete_session), Modifier.weight(1f), mainColor = RadicalRed) { onDelete() }
                }
            }
        }
    }

    deleteClipIndex?.let { index ->
        ConfirmDialog(
            title = stringResource(R.string.capture_delete_clip_title),
            body = stringResource(R.string.capture_delete_clip_body),
            confirmLabel = stringResource(R.string.common_delete), cancelLabel = stringResource(R.string.capture_keep_it), primaryColor = RadicalRed, destructive = true,
            onConfirm = { deleteClipIndex = null; change { store.deleteClip(sessionId, index) } },
            onCancel = { deleteClipIndex = null },
        )
    }
}

@Composable
private fun ClipRow(
    clip: StoredClip,
    primaryColor: Color,
    hasAudio: Boolean,
    onPlay: () -> Unit,
    onToggle: (String) -> Unit,
    onKeep: () -> Unit,
    onAside: () -> Unit,
    onDelete: () -> Unit,
) {
    val held = clip.state == ClipState.RECOVERED
    val words = rememberText()
    Column(
        modifier = Modifier.fillMaxWidth().border(1.dp, if (held) RadicalRed else Color.DarkGray).padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            CaptureText.clipLine(words, clip.card, clip.attempt, clip.durationS, clip.state),
            color = if (held) RadicalRed else primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        Text(clip.text.take(90) + if (clip.text.length > 90) "..." else "", color = Color.White, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        if (clip.flags.any { it !in ClipFlags.PERSON }) {
            Text(CaptureText.notesLine(words, clip.flags), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
            if (hasAudio) TightPanelButton(stringResource(R.string.capture_play), Modifier.weight(1f), mainColor = primaryColor, onClick = onPlay)
            when (clip.state) {
                ClipState.RECOVERED -> {
                    TightPanelButton(stringResource(R.string.capture_keep), Modifier.weight(1f), mainColor = primaryColor, onClick = onKeep)
                    TightPanelButton(stringResource(R.string.capture_set_aside), Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onAside)
                }
                ClipState.REDONE -> TightPanelButton(stringResource(R.string.common_delete), Modifier.weight(1f), mainColor = RadicalRed, onClick = onDelete)
                else -> {}
            }
        }
        if (clip.state == ClipState.DONE) {
            Text(stringResource(R.string.capture_mark_hint), color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            for (rowOfMarks in ClipFlags.PERSON.chunked(3)) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.fillMaxWidth()) {
                    for (flag in rowOfMarks) {
                        TightPanelButton(CaptureText.markWord(words, flag), Modifier.weight(1f), isActive = flag in clip.flags, mainColor = primaryColor) { onToggle(flag) }
                    }
                    repeat(3 - rowOfMarks.size) { Spacer(modifier = Modifier.weight(1f)) }
                }
            }
        }
    }
}
