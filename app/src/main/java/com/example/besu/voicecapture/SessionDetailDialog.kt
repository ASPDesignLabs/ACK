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
import com.example.besu.output.OutputService
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import com.example.besu.ui.theme.Graphite
import java.util.Locale
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
    var session by remember { mutableStateOf<StoredSession?>(null) }
    var error by remember { mutableStateOf("") }
    var reload by remember { mutableIntStateOf(0) }
    var deleteClipIndex by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(reload) {
        try {
            session = withContext(Dispatchers.IO) { store.getSession(sessionId) }
        } catch (e: StoreException) {
            error = e.message ?: "THIS SESSION CAN'T BE READ."
        }
    }

    fun change(action: () -> Unit) {
        try { action() } catch (e: StoreException) { error = e.message ?: "THAT DID NOT WORK." }
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
                Text("SESSION", color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
                Text("[CLOSE]", color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.heightIn(min = 48.dp).clickable { onClose() }.padding(8.dp))
            }
            if (error.isNotEmpty()) Notice(error, RadicalRed, onDismiss = { error = "" })
            if (s == null) {
                Text("LOADING...", color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
            } else {
                Text(
                    (if (s.mode == "script") (s.scriptTitle ?: "SCRIPT") else "FREE SPEECH") + (if (s.label.isNotEmpty()) " // ${s.label}" else ""),
                    color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                )
                Text(
                    s.id + "  //  " + (s.sampleRate / 1000.0).toString() + " KHZ  //  " + s.source +
                        (s.noiseFloorDbfs?.let { "  //  ROOM $it DB" } ?: "") + if (!s.closed) "  //  NOT ENDED" else "",
                    color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
                )

                if (s.mode == "free") {
                    val r = s.recording
                    if (r == null) {
                        Text("NOTHING WAS RECORDED.", color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    } else {
                        Text(
                            "${clock(r.durationS)} RECORDED, ${r.pieces.size} SUGGESTED PIECE(S)  //  " +
                                when (r.state) { ClipState.DONE -> "KEPT"; ClipState.RECOVERED -> "REPAIRED, WAITING FOR YOU"; else -> "UNFINISHED" },
                            color = Color.White, fontSize = 11.sp, fontFamily = FontFamily.Monospace,
                        )
                        if (r.state == ClipState.RECOVERED) {
                            Text(
                                "THE APP CLOSED WHILE THIS WAS RECORDING. THE AUDIO WAS REPAIRED. KEEP IT TO INCLUDE IT WHEN YOU SAVE A FILE.",
                                color = RadicalRed, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                            )
                            TightPanelButton("KEEP THIS RECORDING", Modifier.fillMaxWidth(), mainColor = primaryColor) { change { store.keepRecoveredRecording(sessionId) } }
                        }
                    }
                } else {
                    val shown = s.clips.sortedBy { it.index }
                    Text("${shown.count { it.state == ClipState.DONE }} KEPT, ${shown.count { it.state != ClipState.DONE }} SET ASIDE OR WAITING", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
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
                    TightPanelButton("SAVE TO A FILE", Modifier.weight(1f), isActive = s.closed, mainColor = primaryColor) { if (s.closed) onSave(s) }
                    TightPanelButton("DELETE SESSION", Modifier.weight(1f), mainColor = RadicalRed) { onDelete() }
                }
            }
        }
    }

    deleteClipIndex?.let { index ->
        ConfirmDialog(
            title = "DELETE THIS RECORDING?",
            body = "IT WAS SET ASIDE AND IS NOT IN ANY SAVED FILE. DELETING IT REMOVES THE AUDIO FROM THIS PHONE FOR GOOD.",
            confirmLabel = "DELETE", cancelLabel = "KEEP IT", primaryColor = RadicalRed, destructive = true,
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
    Column(
        modifier = Modifier.fillMaxWidth().border(1.dp, if (held) RadicalRed else Color.DarkGray).padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            "CARD ${clip.card}, TRY ${clip.attempt}  //  " + String.format(Locale.ROOT, "%.1f", clip.durationS) + " S  //  " +
                when (clip.state) { ClipState.DONE -> "KEPT"; ClipState.REDONE -> "SET ASIDE"; ClipState.RECOVERED -> "REPAIRED: LISTEN AND DECIDE"; else -> "UNFINISHED" },
            color = if (held) RadicalRed else primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        Text(clip.text.take(90) + if (clip.text.length > 90) "..." else "", color = Color.White, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        if (clip.flags.any { it !in ClipFlags.PERSON }) {
            Text("NOTES: " + clip.flags.filter { it !in ClipFlags.PERSON }.joinToString(", ").uppercase(), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
            if (hasAudio) TightPanelButton("PLAY", Modifier.weight(1f), mainColor = primaryColor, onClick = onPlay)
            when (clip.state) {
                ClipState.RECOVERED -> {
                    TightPanelButton("KEEP", Modifier.weight(1f), mainColor = primaryColor, onClick = onKeep)
                    TightPanelButton("SET ASIDE", Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onAside)
                }
                ClipState.REDONE -> TightPanelButton("DELETE", Modifier.weight(1f), mainColor = RadicalRed, onClick = onDelete)
                else -> {}
            }
        }
        if (clip.state == ClipState.DONE) {
            Text("MARK THIS CLIP (A MARK KEEPS IT OUT OF TRAINING UNTIL YOU REVIEW IT ON THE COMPUTER):", color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            for (rowOfMarks in ClipFlags.PERSON.chunked(3)) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.fillMaxWidth()) {
                    for (flag in rowOfMarks) {
                        TightPanelButton(flag.uppercase(), Modifier.weight(1f), isActive = flag in clip.flags, mainColor = primaryColor) { onToggle(flag) }
                    }
                    repeat(3 - rowOfMarks.size) { Spacer(modifier = Modifier.weight(1f)) }
                }
            }
        }
    }
}
