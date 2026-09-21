package com.example.besu.settings

import com.example.besu.AckTags
import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// PROTOCOL -> "MANAGE RECORDINGS": every voice recording in the app --
// Quick Actions slots, Quick-Access keys, and Matrix nodes -- browsed as a
// drill-down tree (same ASCII-connector style as the Target Computer
// editor), grouped by how each owner is actually scoped: Quick Actions as
// Deck > Group > Slot, Quick-Access keys as a flat list (no deck/group
// concept), Matrix as Deck > Profile > Pose > Slot. A leaf shows the text
// that would actually reach the overlay, play time, file size on disk,
// and offers PLAY, RE-RECORD, and DELETE right there.

private sealed class RecTreeNode {
    abstract val id: String
    abstract val label: String
}

private data class RecBranch(
    override val id: String,
    override val label: String,
    val children: List<RecTreeNode>
) : RecTreeNode()

private data class RecLeaf(
    override val id: String,
    override val label: String,
    val recording: VoiceRecording
) : RecTreeNode()

private data class RecTreeVisualRow(
    val node: RecTreeNode,
    val depth: Int,
    val isLastChild: Boolean,
    val ancestorContinues: List<Boolean>
)

private fun flattenVisibleRecordingTree(
    nodes: List<RecTreeNode>,
    expandedIds: Set<String>,
    depth: Int = 0,
    ancestorContinues: List<Boolean> = emptyList()
): List<RecTreeVisualRow> {
    val rows = mutableListOf<RecTreeVisualRow>()
    nodes.forEachIndexed { index, node ->
        val isLast = index == nodes.lastIndex
        rows.add(RecTreeVisualRow(node, depth, isLast, ancestorContinues))
        if (node is RecBranch && node.id in expandedIds) {
            rows.addAll(
                flattenVisibleRecordingTree(node.children, expandedIds, depth + 1, ancestorContinues + !isLast)
            )
        }
    }
    return rows
}

private fun recConnectorPrefix(row: RecTreeVisualRow): String {
    val sb = StringBuilder()
    for (i in 0 until row.depth) {
        sb.append(if (row.ancestorContinues.getOrElse(i) { false }) "│  " else "   ")
    }
    sb.append(if (row.isLastChild) "└─ " else "├─ ")
    return sb.toString()
}

// Deck > Group > Slot (Quick Actions), a flat list (Quick-Access keys --
// no deck/group concept), and Deck > Profile > Pose > Slot (Matrix,
// matching exactly how the node's own phrase text is scoped). Only
// branches that actually lead to a recording are built -- this is a
// browser for what exists, not the full theoretical deck/profile/pose
// space.
private fun buildRecordingTree(context: Context, recordings: List<VoiceRecording>): List<RecTreeNode> {
    val kinds = mutableListOf<RecTreeNode>()

    val quickActionRecs = recordings.filter { it.owner == RecordingOwner.QUICK_ACTION }
    if (quickActionRecs.isNotEmpty()) {
        val qaDeckBranches = quickActionRecs.groupBy { it.deckId ?: "DEFAULT" }.map { (deckId, deckRecs) ->
            val deckName = CommandRepository.getDeckName(context, deckId)
            val config = CommandRepository.getQuickActionsConfig(context, deckId)
            val qaGroupBranches = deckRecs.groupBy { it.groupIndex ?: 0 }.map { (groupIndex, groupRecs) ->
                val group = config.groups.find { it.groupIndex == groupIndex }
                val groupLabel = group?.label ?: "G${groupIndex + 1}"
                val slotLeaves = groupRecs.map { rec ->
                    val slotLabel = group?.slots?.find { it.slotIndex == rec.slotIndex }?.label
                        ?: "SLOT ${(rec.slotIndex ?: 0) + 1}"
                    RecLeaf(id = "leaf_${rec.id}", label = slotLabel, recording = rec)
                }.sortedBy { it.label }
                RecBranch(id = "qa_${deckId}_g$groupIndex", label = groupLabel, children = slotLeaves)
            }.sortedBy { it.label }
            RecBranch(id = "qa_deck_$deckId", label = deckName, children = qaGroupBranches)
        }.sortedBy { it.label }
        kinds.add(RecBranch(id = "kind_qa", label = "QUICK ACTIONS (${quickActionRecs.size})", children = qaDeckBranches))
    }

    val keyRecs = recordings.filter { it.owner == RecordingOwner.QUICK_ACCESS_KEY }
    if (keyRecs.isNotEmpty()) {
        val shortcuts = CommandRepository.getHeaderShortcuts(context)
        val keyLeaves = keyRecs.map { rec ->
            val index = rec.slotIndex ?: 0
            val keyLabel = shortcuts.getOrNull(index)?.label ?: "M${index + 1}"
            RecLeaf(id = "leaf_${rec.id}", label = keyLabel, recording = rec)
        }.sortedBy { it.label }
        kinds.add(RecBranch(id = "kind_qk", label = "QUICK-ACCESS KEYS (${keyRecs.size})", children = keyLeaves))
    }

    val matrixRecs = recordings.filter { it.owner == RecordingOwner.MATRIX_NODE }
    if (matrixRecs.isNotEmpty()) {
        val matrixDeckBranches = matrixRecs.groupBy { it.deckId ?: "DEFAULT" }.map { (deckId, deckRecs) ->
            val deckName = CommandRepository.getDeckName(context, deckId)
            val profileBranches = deckRecs.groupBy { it.profile ?: "DEFAULT" }.map { (profile, profileRecs) ->
                val poseBranches = profileRecs.groupBy { rec ->
                    rec.path?.let { CommandRepository.findMatrixNode(context, it)?.category } ?: "UNKNOWN"
                }.map { (pose, poseRecs) ->
                    val nodeLeaves = poseRecs.map { rec ->
                        val nodeLabel = rec.path?.let { CommandRepository.findMatrixNode(context, it)?.label }
                            ?: "UNKNOWN NODE"
                        RecLeaf(id = "leaf_${rec.id}", label = nodeLabel, recording = rec)
                    }.sortedBy { it.label }
                    RecBranch(id = "mtx_${deckId}_${profile}_$pose", label = pose, children = nodeLeaves)
                }.sortedBy { it.label }
                RecBranch(id = "mtx_${deckId}_$profile", label = profile, children = poseBranches)
            }.sortedBy { it.label }
            RecBranch(id = "mtx_deck_$deckId", label = deckName, children = profileBranches)
        }.sortedBy { it.label }
        kinds.add(RecBranch(id = "kind_mtx", label = "MATRIX (${matrixRecs.size})", children = matrixDeckBranches))
    }

    return kinds
}

// The text that would actually reach the overlay/log if this recording's
// owner were triggered right now -- a Matrix node prefers its visual
// override (see CommandRepository.getVisualOverride), matching exactly
// what MatrixCategory's row and dispatch already show/send.
private fun resolveOverlayText(context: Context, recording: VoiceRecording): String {
    return when (recording.owner) {
        RecordingOwner.QUICK_ACTION -> {
            val deckId = recording.deckId ?: "DEFAULT"
            val groupIndex = recording.groupIndex ?: 0
            val slotIndex = recording.slotIndex ?: 0
            CommandRepository.resolveQuickAction(context, deckId, groupIndex, slotIndex).ifBlank { "(EMPTY PROMPT)" }
        }
        RecordingOwner.QUICK_ACCESS_KEY -> {
            val index = recording.slotIndex ?: 0
            CommandRepository.getHeaderShortcuts(context).getOrNull(index)?.phrase
                ?.ifBlank { "(EMPTY PROMPT)" } ?: "(EMPTY PROMPT)"
        }
        RecordingOwner.MATRIX_NODE -> {
            val path = recording.path
            if (path == null) {
                "(UNKNOWN NODE)"
            } else {
                val deckId = recording.deckId ?: "DEFAULT"
                val profile = recording.profile ?: "DEFAULT"
                CommandRepository.getVisualOverride(context, path, deckId, profile).ifBlank {
                    CommandRepository.getResolvedPhrase(context, path, deckId, profile).ifBlank { "(EMPTY PROMPT)" }
                }
            }
        }
    }
}

private fun deleteRecordingTarget(context: Context, target: VoiceRecording) {
    VoiceRecordingRepository.delete(context, target.id)
    // Only a Quick Actions slot stores a pointer back to the recording
    // (QuickActionSlot.recordingId) -- Quick-Access keys and Matrix nodes
    // look theirs up live by index/path, nothing else to clear.
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

private fun saveReRecording(context: Context, target: VoiceRecording, pcm: ShortArray, sampleRate: Int) {
    when (target.owner) {
        RecordingOwner.QUICK_ACTION -> {
            val deckId = target.deckId ?: return
            val groupIndex = target.groupIndex ?: return
            val slotIndex = target.slotIndex ?: return
            val saved = VoiceRecordingRepository.saveForQuickAction(context, deckId, groupIndex, slotIndex, pcm, sampleRate)
            CommandRepository.setQuickActionSlotRecording(context, deckId, groupIndex, slotIndex, saved.id)
        }
        RecordingOwner.QUICK_ACCESS_KEY -> {
            val slotIndex = target.slotIndex ?: return
            VoiceRecordingRepository.saveForQuickAccessKey(context, slotIndex, pcm, sampleRate)
        }
        RecordingOwner.MATRIX_NODE -> {
            val deckId = target.deckId ?: return
            val profile = target.profile ?: return
            val path = target.path ?: return
            val snapshot = CommandRepository.getPhrase(context, path, deckId, profile)
            VoiceRecordingRepository.saveForMatrixNode(context, deckId, profile, path, pcm, sampleRate, snapshot)
        }
    }
}

@Composable
fun ManageRecordingsDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val recordings = remember(refreshKey) { VoiceRecordingRepository.getAll(context) }
    val tree = remember(refreshKey) { buildRecordingTree(context, recordings) }

    var expandedIds by remember { mutableStateOf<Set<String>>(emptySet()) }
    var isPlayingId by remember { mutableStateOf<String?>(null) }
    var confirmingDeleteId by remember { mutableStateOf<String?>(null) }
    var reRecordTargetId by remember { mutableStateOf<String?>(null) }
    var showOverlayOnPreview by remember {
        mutableStateOf(VoiceRecordingRepository.getShowOverlayOnPreview(context))
    }
    val coroutineScope = rememberCoroutineScope()
    val helpManager = LocalHelpManager.current

    var hasSeenHelpOffer by remember {
        mutableStateOf(VoiceRecordingRepository.hasSeenHelpOffer(context))
    }

    fun playRecording(recording: VoiceRecording) {
        if (isPlayingId != null) return
        isPlayingId = recording.id
        // Routed through OutputService -- the same DSP/volume pipeline
        // every other prompt plays through, rather than a standalone
        // AudioTrack that could end up silent.
        context.startService(Intent(context, OutputService::class.java).apply {
            action = "PREVIEW_RECORDING"
            putExtra("recording_id", recording.id)
            // The overlay toggle sends this recording's own stored text to
            // the overlay -- a second, visual way to confirm this is the
            // prompt being looked for, especially one personalized enough
            // that the audio alone doesn't immediately place it. Preview
            // stays a non-logged, non-dispatch action either way.
            if (showOverlayOnPreview) {
                putExtra("preview_visual_text", resolveOverlayText(context, recording))
            }
        })
        coroutineScope.launch {
            delay(recording.durationMs + 300)
            isPlayingId = null
        }
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "MANAGE RECORDINGS",
        subtitle = "${recordings.size} RECORDING${if (recordings.size == 1) "" else "S"}",
        headerActions = {
            Text(
                text = if (showOverlayOnPreview) "[OVERLAY: ON]" else "[OVERLAY: OFF]",
                color = if (showOverlayOnPreview) primaryColor else Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .heightIn(min = 44.dp)
                    .testTag(AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE)
                    .helpTarget(AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE, primaryColor)
                    .clickable {
                        showOverlayOnPreview = !showOverlayOnPreview
                        VoiceRecordingRepository.setShowOverlayOnPreview(context, showOverlayOnPreview)
                        helpManager?.onEvent(
                            HelpEvent.Interacted(AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE)
                        )
                    }
                    .padding(horizontal = 4.dp)
            )
        }
    ) {
        if (!hasSeenHelpOffer) {
            HelpOfferBanner(
                message = "NEW: VOICE RECORDINGS HAS A HELP WALKTHROUGH -- RECORDING, " +
                    "MATRIX NOTES, AND MANAGING WHAT YOU'VE RECORDED. FIND IT UNDER HELP " +
                    "ANYTIME.",
                primaryColor = primaryColor,
                onDismiss = {
                    VoiceRecordingRepository.markHelpOfferSeen(context)
                    hasSeenHelpOffer = true
                }
            )
            Spacer(modifier = Modifier.height(10.dp))
        }

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
                    .heightIn(max = 460.dp)
                    .testTag(AckTags.VOICE_REC_MANAGE_TREE)
                    .helpTarget(AckTags.VOICE_REC_MANAGE_TREE, primaryColor)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                flattenVisibleRecordingTree(tree, expandedIds).forEach { row ->
                    when (val node = row.node) {
                        is RecBranch -> {
                            val isExpanded = node.id in expandedIds
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        expandedIds = if (isExpanded) expandedIds - node.id else expandedIds + node.id
                                    }
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = recConnectorPrefix(row) + (if (isExpanded) "▾ " else "▸ ") + node.label,
                                    color = if (isExpanded) primaryColor else Color.LightGray,
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = if (row.depth == 0) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                        }
                        is RecLeaf -> {
                            RecTreeLeafCard(
                                context = context,
                                row = row,
                                leaf = node,
                                primaryColor = primaryColor,
                                isPlaying = isPlayingId == node.recording.id,
                                onPlay = { playRecording(node.recording) },
                                onReRecord = { reRecordTargetId = node.recording.id },
                                onDeleteRequested = { confirmingDeleteId = node.recording.id }
                            )
                        }
                    }
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
                        deleteRecordingTarget(context, target)
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

    val reRecordId = reRecordTargetId
    val reRecordTarget = if (reRecordId != null) recordings.find { it.id == reRecordId } else null
    if (reRecordTarget != null) {
        TightDialogSurface(
            onDismiss = { reRecordTargetId = null },
            primaryColor = primaryColor,
            title = "RE-RECORD"
        ) {
            VoiceRecordingPanel(
                context = context,
                primaryColor = primaryColor,
                panelKey = "manage_rerecord_${reRecordTarget.id}",
                existingRecording = reRecordTarget,
                onAccept = { pcm, sampleRate ->
                    saveReRecording(context, reRecordTarget, pcm, sampleRate)
                    reRecordTargetId = null
                    refreshKey++
                },
                onRemove = {
                    deleteRecordingTarget(context, reRecordTarget)
                    reRecordTargetId = null
                    refreshKey++
                }
            )
        }
    }
}

@Composable
private fun RecTreeLeafCard(
    context: Context,
    row: RecTreeVisualRow,
    leaf: RecLeaf,
    primaryColor: Color,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onReRecord: () -> Unit,
    onDeleteRequested: () -> Unit
) {
    val recording = leaf.recording

    val overlayText = remember(recording.id) { resolveOverlayText(context, recording) }
    val fileSize = remember(recording.id) {
        VoiceRecordingRepository.formatFileSize(VoiceRecordingRepository.getAudioFileSizeBytes(context, recording.id))
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = recConnectorPrefix(row) + leaf.label,
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = (row.depth * 14).dp, top = 2.dp)
                .testTag(AckTags.VOICE_REC_MANAGE_LEAF)
                .helpTarget(AckTags.VOICE_REC_MANAGE_LEAF, primaryColor)
                .border(1.dp, primaryColor.copy(alpha = 0.4f), AckHelpShape)
                .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
                .padding(10.dp)
        ) {
            Text(
                text = "\"$overlayText\"",
                color = Color.White,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = "${VoiceRecordingRepository.formatDurationMs(recording.durationMs)} / $fileSize",
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

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TightPanelButton(
                    text = if (isPlaying) "PLAYING..." else "PLAY",
                    modifier = Modifier.weight(1f),
                    isActive = !isPlaying,
                    mainColor = primaryColor,
                    onClick = onPlay
                )
                TightPanelButton(
                    text = "RE-RECORD",
                    modifier = Modifier.weight(1f),
                    mainColor = primaryColor,
                    onClick = onReRecord
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
}
