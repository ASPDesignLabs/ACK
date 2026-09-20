package com.example.besu.decks

import com.example.besu.*
import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import com.example.besu.ui.theme.*
import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
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
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun QuickActionsDeck(
    context: Context,
    deckId: String,
    primaryColor: Color
) {
    var selectedGroupIndex by remember(deckId) {
        mutableIntStateOf(0)
    }

    var config by remember(deckId) {
        mutableStateOf(
            CommandRepository.getQuickActionsConfig(
                context = context,
                deckId = deckId
            )
        )
    }

    var editingSlot by remember {
        mutableStateOf<QuickActionSlot?>(null)
    }

    var editingGroup by remember {
        mutableStateOf<QuickActionGroup?>(null)
    }

    val helpManager = LocalHelpManager.current

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    fun reportTextCommit(tag: String) {
        helpManager?.onEvent(HelpEvent.TextCommitted(tag))
    }

    val activeGroup = config.groups.find {
        it.groupIndex == selectedGroupIndex
    } ?: config.groups.first()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(
            text = "QUICK ACTIONS",
            color = primaryColor,
            fontSize = 20.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 2.sp
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "TAP: EXECUTE  //  HOLD: EDIT",
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            config.groups.forEach { group ->
                val isSelected = group.groupIndex == selectedGroupIndex

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .testTag(AckTags.QUICK_ACTION_GROUP)
                        .helpTarget(AckTags.QUICK_ACTION_GROUP, primaryColor)
                        .border(
                            width = 1.dp,
                            color = if (isSelected) {
                                primaryColor
                            } else {
                                Color.DarkGray
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .background(
                            color = if (isSelected) {
                                primaryColor.copy(alpha = 0.18f)
                            } else {
                                VoidBlack.copy(alpha = 0.45f)
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .clickable {
                            selectedGroupIndex = group.groupIndex
                            reportHelpInteraction(AckTags.QUICK_ACTION_GROUP)
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "G${group.groupIndex + 1}",
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Text(
                            text = group.boundPose.take(3),
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        QuickActionsGroupHeader(
            group = activeGroup,
            primaryColor = primaryColor,
            onEdit = {
                editingGroup = activeGroup
                reportHelpInteraction(AckTags.QUICK_ACTION_GROUP_EDIT)
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        activeGroup.slots.forEach { slot ->
            QuickActionButton(
                slot = slot,
                primaryColor = primaryColor,
                onExecute = {
                    val phrase = CommandRepository.resolveQuickAction(
                        context = context,
                        deckId = deckId,
                        groupIndex = activeGroup.groupIndex,
                        slotIndex = slot.slotIndex
                    )

                    if (phrase.isNotBlank()) {
                        context.startService(
                            Intent(context, OutputService::class.java).apply {
                                putExtra("phrase", phrase)
                                putExtra("robotic", false)
                                putExtra("source", "QUICK_ACTION")
                                // OutputService tries this recording first
                                // and falls back to synthesizing the
                                // phrase above if it can't load it, so
                                // nothing else here needs to change based
                                // on whether the slot has one.
                                if (slot.recordingId != null) {
                                    putExtra("recording_id", slot.recordingId)
                                }
                            }
                        )
                    }
                },
                onEdit = {
                    editingSlot = slot
                    reportHelpInteraction(AckTags.QUICK_ACTION_SLOT)
                }
            )

            Spacer(modifier = Modifier.height(10.dp))
        }
    }

    editingSlot?.let { slot ->
        QuickActionEditorDialog(
            context = context,
            deckId = deckId,
            groupIndex = activeGroup.groupIndex,
            slot = slot,
            primaryColor = primaryColor,
            onDismiss = {
                editingSlot = null
            },
            onSave = { label, template, localValues ->
                CommandRepository.updateQuickActionSlot(
                    context = context,
                    deckId = deckId,
                    groupIndex = activeGroup.groupIndex,
                    slotIndex = slot.slotIndex,
                    label = label,
                    template = template,
                    localValues = localValues
                )

                config = CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deckId
                )

                reportTextCommit(AckTags.QUICK_ACTION_SAVE)
                editingSlot = null
            },
            onRecordingChanged = {
                config = CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deckId
                )
            }
        )
    }

    editingGroup?.let { group ->
        QuickActionGroupEditorDialog(
            group = group,
            primaryColor = primaryColor,
            onDismiss = {
                editingGroup = null
            },
            onSave = { label, rootCategory, boundPose ->
                CommandRepository.updateQuickActionGroup(
                    context = context,
                    deckId = deckId,
                    groupIndex = group.groupIndex,
                    label = label,
                    rootCategory = rootCategory,
                    boundPose = boundPose
                )

                config = CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deckId
                )

                editingGroup = null
            }
        )
    }
}

@Composable
private fun QuickActionsGroupHeader(
    group: QuickActionGroup,
    primaryColor: Color,
    onEdit: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor,
                shape = CutCornerShape(topStart = 10.dp, bottomEnd = 10.dp)
            )
            .background(
                color = VoidBlack.copy(alpha = 0.40f),
                shape = CutCornerShape(topStart = 10.dp, bottomEnd = 10.dp)
            )
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = group.label,
                color = primaryColor,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )

            Text(
                text = "POSE: ${group.boundPose}  //  ROOT: ${group.rootCategory}",
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        NeonButton(
            text = "EDIT",
            modifier = Modifier
                .testTag(AckTags.QUICK_ACTION_GROUP_EDIT)
                .helpTarget(AckTags.QUICK_ACTION_GROUP_EDIT, primaryColor),
            mainColor = primaryColor
        ) {
            onEdit()
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun QuickActionButton(
    slot: QuickActionSlot,
    primaryColor: Color,
    onExecute: () -> Unit,
    onEdit: () -> Unit
) {
    val isConfigured = slot.template.isNotBlank()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AckTags.QUICK_ACTION_SLOT)
            .helpTarget(AckTags.QUICK_ACTION_SLOT, primaryColor)
            .border(
                width = 1.dp,
                color = if (isConfigured) primaryColor else Color.DarkGray,
                shape = CutCornerShape(topStart = 12.dp, bottomEnd = 12.dp)
            )
            .background(
                color = if (isConfigured) {
                    primaryColor.copy(alpha = 0.12f)
                } else {
                    VoidBlack.copy(alpha = 0.35f)
                },
                shape = CutCornerShape(topStart = 12.dp, bottomEnd = 12.dp)
            )
            .combinedClickable(
                onClick = onExecute,
                onLongClick = onEdit
            )
            .padding(horizontal = 18.dp, vertical = 20.dp)
    ) {
        Text(
            text = slot.label,
            color = if (isConfigured) primaryColor else Color.Gray,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(5.dp))

        Text(
            text = if (isConfigured) {
                slot.template
            } else {
                "[HOLD TO CONFIGURE]"
            },
            color = Color.Gray,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            maxLines = 2
        )
    }
}

@Composable
private fun QuickActionEditorDialog(
    context: Context,
    deckId: String,
    groupIndex: Int,
    slot: QuickActionSlot,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        label: String,
        template: String,
        localValues: List<String>
    ) -> Unit,
    onRecordingChanged: () -> Unit
) {
    var label by remember(slot.slotIndex) {
        mutableStateOf(slot.label)
    }

    var template by remember(slot.slotIndex) {
        mutableStateOf(slot.template)
    }

    val tags = remember(template) {
        TemplateEngine.getVariableTags(template)
    }

    var localValues by remember(slot.slotIndex, template) {
        mutableStateOf(
            List(tags.size) { index ->
                slot.localValues.getOrNull(index).orEmpty()
            }
        )
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "EDIT QUICK ACTION"
    ) {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = label,
                    onValueChange = {
                        label = it
                    },
                    label = {
                        Text("BUTTON LABEL")
                    },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = NeonTextFieldColors(primaryColor)
                )

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = template,
                    onValueChange = {
                        template = it
                    },
                    label = {
                        Text("PHRASE TEMPLATE")
                    },
                    shape = AckHelpShape,
                    colors = NeonTextFieldColors(primaryColor),
                    minLines = 3
                )

                if (tags.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(12.dp))

                    TightSectionLabel("LOCAL VARIABLES", color = primaryColor)

                    tags.forEachIndexed { index, tag ->
                        Spacer(modifier = Modifier.height(8.dp))

                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = localValues.getOrNull(index).orEmpty(),
                            onValueChange = { value ->
                                localValues = localValues.toMutableList().apply {
                                    this[index] = value
                                }
                            },
                            label = {
                                Text(
                                    tag?.let { "VAR:$it" } ?: "VAR ${index + 1}"
                                )
                            },
                            shape = AckHelpShape,
                            singleLine = true,
                            colors = NeonTextFieldColors(primaryColor)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                VoiceRecordingSection(
                    context = context,
                    primaryColor = primaryColor,
                    deckId = deckId,
                    groupIndex = groupIndex,
                    slotIndex = slot.slotIndex,
                    onBindingChanged = onRecordingChanged
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "SAVE",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.QUICK_ACTION_SAVE)
                            .helpTarget(AckTags.QUICK_ACTION_SAVE, primaryColor),
                        mainColor = primaryColor
                    ) {
                        onSave(
                            label,
                            template,
                            localValues
                        )
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor,
                        onClick = onDismiss
                    )
                }
    }
}

private enum class RecordingPhase { IDLE, RECORDING, PROCESSING, PREVIEW }

// Recording is its own persistence flow, independent of the dialog's SAVE
// button above -- accepting or removing a recording writes immediately
// (VoiceRecordingRepository + CommandRepository.setQuickActionSlotRecording),
// the same "commits the moment you act" pattern MatrixEditor's live-save
// template field and the Target Computer contact card editor already use.
// That way backing out of the label/template edit with CANCEL never
// undoes a recording you already accepted.
//
// Flow: IDLE (shows the existing recording, if any, plus a record button)
// -> RECORDING (live mic capture, a duration counter, stop/cancel) ->
// PROCESSING (AudioDsp.reduceNoise running off the main thread) -> PREVIEW
// (play back the processed clip, accept or discard) -> back to IDLE.
@Composable
private fun VoiceRecordingSection(
    context: Context,
    primaryColor: Color,
    deckId: String,
    groupIndex: Int,
    slotIndex: Int,
    onBindingChanged: () -> Unit
) {
    val recorder = remember(slotIndex) { VoiceRecorder() }
    val coroutineScope = rememberCoroutineScope()

    // The dialog can be dismissed (back, tap-outside, SAVE, CANCEL) while
    // a recording is still in progress -- without this, the mic and its
    // background read thread would keep running after the UI is gone.
    DisposableEffect(slotIndex) {
        onDispose {
            if (recorder.isRecording) {
                recorder.discard()
            }
        }
    }

    var refreshKey by remember { mutableIntStateOf(0) }
    val existingRecording = remember(slotIndex, refreshKey) {
        VoiceRecordingRepository.getForSlot(context, deckId, groupIndex, slotIndex)
    }

    var phase by remember(slotIndex) { mutableStateOf(RecordingPhase.IDLE) }
    var recordingDurationMs by remember(slotIndex) { mutableLongStateOf(0L) }
    var previewPcm by remember(slotIndex) { mutableStateOf<ShortArray?>(null) }
    var previewSampleRate by remember(slotIndex) { mutableIntStateOf(VoiceRecorder.SAMPLE_RATE) }
    var isPlayingPreview by remember(slotIndex) { mutableStateOf(false) }

    var micPermissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
        )
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        micPermissionGranted = granted
        if (granted && recorder.start(context)) {
            recordingDurationMs = 0L
            phase = RecordingPhase.RECORDING
        }
    }

    fun finishRecording() {
        val raw = recorder.stop()
        phase = RecordingPhase.PROCESSING
        coroutineScope.launch {
            val processed = withContext(Dispatchers.Default) {
                // Noise reduction first -- it relies on genuine quiet at
                // the very start of the clip to estimate its noise
                // profile, so trimming that away first would throw off
                // its calibration. Trimming runs on the denoised result.
                val denoised = AudioDsp.reduceNoise(raw, VoiceRecorder.SAMPLE_RATE)
                AudioDsp.trimSilence(denoised, VoiceRecorder.SAMPLE_RATE)
            }
            previewPcm = processed
            previewSampleRate = VoiceRecorder.SAMPLE_RATE
            // The live ticker's duration no longer matches once dead air's
            // been trimmed off -- reflect what the preview actually plays.
            recordingDurationMs = processed.size.toLong() * 1000L / VoiceRecorder.SAMPLE_RATE
            phase = RecordingPhase.PREVIEW
        }
    }

    // Live duration ticker while recording, and the path that notices the
    // recorder stopped itself (VoiceRecorder.MAX_DURATION_MS) rather than
    // being told to via the STOP button below.
    LaunchedEffect(phase) {
        if (phase == RecordingPhase.RECORDING) {
            while (phase == RecordingPhase.RECORDING && recorder.isRecording) {
                recordingDurationMs = recorder.currentDurationMs()
                delay(100)
            }
            if (phase == RecordingPhase.RECORDING) {
                finishRecording()
            }
        }
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        TightSectionLabel("VOICE RECORDING", color = primaryColor)
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = "WHEN SET, THIS PLAYS INSTEAD OF THE SYNTHESIZED PHRASE ABOVE.",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
        Spacer(modifier = Modifier.height(8.dp))

        when (phase) {
            RecordingPhase.IDLE -> {
                if (existingRecording != null) {
                    Text(
                        text = "RECORDED (${VoiceRecordingRepository.formatDurationMs(existingRecording.durationMs)})",
                        color = primaryColor,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (existingRecording != null) {
                        TightPanelButton(
                            text = if (isPlayingPreview) "PLAYING..." else "PLAY",
                            modifier = Modifier.weight(1f),
                            isActive = !isPlayingPreview,
                            mainColor = primaryColor
                        ) {
                            val loaded = VoiceRecordingRepository.loadPcm(context, existingRecording.id)
                            if (loaded != null && !isPlayingPreview) {
                                isPlayingPreview = true
                                coroutineScope.launch {
                                    VoiceRecordingRepository.playPreview(context, loaded.first, loaded.second)
                                    isPlayingPreview = false
                                }
                            }
                        }
                        TightPanelButton(
                            text = "REMOVE",
                            modifier = Modifier.weight(1f),
                            mainColor = RadicalRed,
                            isActive = true
                        ) {
                            VoiceRecordingRepository.delete(context, existingRecording.id)
                            CommandRepository.setQuickActionSlotRecording(
                                context = context,
                                deckId = deckId,
                                groupIndex = groupIndex,
                                slotIndex = slotIndex,
                                recordingId = null
                            )
                            refreshKey++
                            onBindingChanged()
                        }
                    }
                    TightPanelButton(
                        text = if (existingRecording != null) "RE-RECORD" else "RECORD",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        if (micPermissionGranted) {
                            if (recorder.start(context)) {
                                recordingDurationMs = 0L
                                phase = RecordingPhase.RECORDING
                            }
                        } else {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    }
                }
            }

            RecordingPhase.RECORDING -> {
                Text(
                    text = "RECORDING... ${VoiceRecordingRepository.formatDurationMs(recordingDurationMs)}",
                    color = RadicalRed,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "STOP",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        finishRecording()
                    }
                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        recorder.discard()
                        phase = RecordingPhase.IDLE
                    }
                }
            }

            RecordingPhase.PROCESSING -> {
                Text(
                    text = "REDUCING NOISE & TRIMMING SILENCE...",
                    color = Color.Gray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            RecordingPhase.PREVIEW -> {
                Text(
                    text = "PREVIEW (${VoiceRecordingRepository.formatDurationMs(recordingDurationMs)})",
                    color = primaryColor,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = if (isPlayingPreview) "PLAYING..." else "PLAY",
                        modifier = Modifier.weight(1f),
                        isActive = !isPlayingPreview,
                        mainColor = primaryColor
                    ) {
                        val pcm = previewPcm
                        if (pcm != null && !isPlayingPreview) {
                            isPlayingPreview = true
                            coroutineScope.launch {
                                VoiceRecordingRepository.playPreview(context, pcm, previewSampleRate)
                                isPlayingPreview = false
                            }
                        }
                    }
                    TightPanelButton(
                        text = "DISCARD",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        previewPcm = null
                        phase = RecordingPhase.IDLE
                    }
                    TightPanelButton(
                        text = "ACCEPT",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        val pcm = previewPcm ?: return@TightPanelButton
                        val saved = VoiceRecordingRepository.save(
                            context = context,
                            deckId = deckId,
                            groupIndex = groupIndex,
                            slotIndex = slotIndex,
                            pcm = pcm,
                            sampleRate = previewSampleRate
                        )
                        CommandRepository.setQuickActionSlotRecording(
                            context = context,
                            deckId = deckId,
                            groupIndex = groupIndex,
                            slotIndex = slotIndex,
                            recordingId = saved.id
                        )
                        previewPcm = null
                        phase = RecordingPhase.IDLE
                        refreshKey++
                        onBindingChanged()
                    }
                }
            }
        }
    }
}

@Composable
private fun QuickActionGroupEditorDialog(
    group: QuickActionGroup,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        label: String,
        rootCategory: String,
        boundPose: String
    ) -> Unit
) {
    var label by remember(group.groupIndex) {
        mutableStateOf(group.label)
    }

    var rootCategory by remember(group.groupIndex) {
        mutableStateOf(group.rootCategory)
    }

    var boundPose by remember(group.groupIndex) {
        mutableStateOf(group.boundPose)
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "EDIT GROUP"
    ) {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = label,
                    onValueChange = {
                        label = it
                    },
                    label = {
                        Text("GROUP LABEL")
                    },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = NeonTextFieldColors(primaryColor)
                )

                Spacer(modifier = Modifier.height(16.dp))

                TightSectionLabel("WATCH POSE", color = primaryColor)

                Text(
                    text = "WHICH GESTURE ON THE WATCH FIRES THIS GROUP.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(8.dp))

                CategoryButtonRow(
                    selected = boundPose,
                    primaryColor = primaryColor,
                    onSelect = { boundPose = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                TightSectionLabel("ROOT OVERRIDE SOURCE", color = primaryColor)

                Text(
                    text = "WHICH A/B/C VARIABLE BANK FILLS THIS GROUP'S {{TAGS}}.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(8.dp))

                CategoryButtonRow(
                    selected = rootCategory,
                    primaryColor = primaryColor,
                    onSelect = { rootCategory = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "SAVE",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        onSave(label, rootCategory, boundPose)
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor,
                        onClick = onDismiss
                    )
                }
    }
}

@Composable
private fun CategoryButtonRow(
    selected: String,
    primaryColor: Color,
    onSelect: (String) -> Unit
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        POSE_CATEGORIES.forEach { category ->
            val isSelected = selected == category
            val color = if (isSelected) primaryColor else Color.Gray

            Box(
                modifier = Modifier
                    .heightIn(min = 44.dp)
                    .border(1.dp, color, AckHelpShape)
                    .background(
                        if (isSelected) primaryColor.copy(alpha = 0.22f) else VoidBlack,
                        AckHelpShape
                    )
                    .clickable { onSelect(category) }
                    .padding(horizontal = 14.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = category.take(3),
                    color = color,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 10.sp
                )
            }
        }
    }
}
