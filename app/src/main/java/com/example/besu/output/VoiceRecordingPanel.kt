package com.example.besu.output

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Text
import androidx.core.content.ContextCompat
import com.example.besu.AckTags
import com.example.besu.help.HelpEvent
import com.example.besu.help.HelpOfferBanner
import com.example.besu.help.LocalHelpManager
import com.example.besu.help.helpTarget
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private enum class RecordingPanelPhase { IDLE, RECORDING, PROCESSING, PREVIEW }

// The full record -> denoise/trim -> preview -> accept flow, shared by
// every place in the app that can bind a voice recording to something
// (Quick Actions slots, Quick-Access keys, Matrix nodes). Persistence is
// entirely the caller's job via onAccept/onRemove -- this composable only
// owns the microphone/processing/preview state machine, so each owner can
// layer its own rules on top (Matrix's variable-disable confirm and
// template-changed staleness, for instance) without duplicating this.
//
// panelKey scopes the internal record/preview state to whichever slot/
// node this instance is editing -- callers pass something stable and
// unique per binding (a slot index, a node path, etc.) so switching what
// you're editing doesn't carry over a stale in-progress recording.
@Composable
fun VoiceRecordingPanel(
    context: Context,
    primaryColor: Color,
    panelKey: Any,
    existingRecording: VoiceRecording?,
    description: String = "WHEN SET, THIS PLAYS INSTEAD OF THE SYNTHESIZED PHRASE ABOVE.",
    onAccept: (pcm: ShortArray, sampleRate: Int) -> Unit,
    onRemove: () -> Unit
) {
    val recorder = remember(panelKey) { VoiceRecorder() }
    val coroutineScope = rememberCoroutineScope()
    val helpManager = LocalHelpManager.current

    var hasSeenHelpOffer by remember {
        mutableStateOf(VoiceRecordingRepository.hasSeenHelpOffer(context))
    }

    // The dialog hosting this panel can be dismissed (back, tap-outside,
    // SAVE, CANCEL) while a recording is still in progress -- without
    // this, the mic and its background read thread would keep running
    // after the UI is gone.
    DisposableEffect(panelKey) {
        onDispose {
            if (recorder.isRecording) {
                recorder.discard()
            }
        }
    }

    var phase by remember(panelKey) { mutableStateOf(RecordingPanelPhase.IDLE) }
    var recordingDurationMs by remember(panelKey) { mutableLongStateOf(0L) }
    var previewPcm by remember(panelKey) { mutableStateOf<ShortArray?>(null) }
    var previewSampleRate by remember(panelKey) { mutableIntStateOf(VoiceRecorder.SAMPLE_RATE) }
    var isPlayingPreview by remember(panelKey) { mutableStateOf(false) }

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
            phase = RecordingPanelPhase.RECORDING
        }
    }

    fun finishRecording() {
        val raw = recorder.stop()
        phase = RecordingPanelPhase.PROCESSING
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
            phase = RecordingPanelPhase.PREVIEW
        }
    }

    // Live duration ticker while recording, and the path that notices the
    // recorder stopped itself (VoiceRecorder.MAX_DURATION_MS) rather than
    // being told to via the STOP button below.
    LaunchedEffect(phase) {
        if (phase == RecordingPanelPhase.RECORDING) {
            while (phase == RecordingPanelPhase.RECORDING && recorder.isRecording) {
                recordingDurationMs = recorder.currentDurationMs()
                delay(100)
            }
            if (phase == RecordingPanelPhase.RECORDING) {
                finishRecording()
            }
        }
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        TightSectionLabel("VOICE RECORDING", color = primaryColor)
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = description,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
        Spacer(modifier = Modifier.height(8.dp))

        when (phase) {
            RecordingPanelPhase.IDLE -> {
                if (!hasSeenHelpOffer) {
                    HelpOfferBanner(
                        message = "NEW: VOICE RECORDINGS HAS A HELP WALKTHROUGH -- " +
                            "RECORDING, MATRIX NOTES, AND MANAGING WHAT YOU'VE RECORDED. " +
                            "FIND IT UNDER HELP ANYTIME.",
                        primaryColor = primaryColor,
                        onDismiss = {
                            VoiceRecordingRepository.markHelpOfferSeen(context)
                            hasSeenHelpOffer = true
                        }
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }

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
                            modifier = Modifier
                                .weight(1f)
                                .testTag(AckTags.VOICE_REC_PLAY_BTN)
                                .helpTarget(AckTags.VOICE_REC_PLAY_BTN, primaryColor),
                            isActive = !isPlayingPreview,
                            mainColor = primaryColor
                        ) {
                            helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_PLAY_BTN))
                            if (!isPlayingPreview) {
                                isPlayingPreview = true
                                // Routed through OutputService -- the same DSP/volume
                                // pipeline every other prompt plays through (raises the
                                // relevant stream's volume, honors FORCE SPEAKER), rather
                                // than a standalone AudioTrack that could end up silent.
                                context.startService(Intent(context, OutputService::class.java).apply {
                                    action = "PREVIEW_RECORDING"
                                    putExtra("recording_id", existingRecording.id)
                                })
                                coroutineScope.launch {
                                    delay(existingRecording.durationMs + 300)
                                    isPlayingPreview = false
                                }
                            }
                        }
                        TightPanelButton(
                            text = "REMOVE",
                            modifier = Modifier
                                .weight(1f)
                                .testTag(AckTags.VOICE_REC_REMOVE_BTN)
                                .helpTarget(AckTags.VOICE_REC_REMOVE_BTN, primaryColor),
                            mainColor = RadicalRed,
                            isActive = true
                        ) {
                            helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_REMOVE_BTN))
                            onRemove()
                        }
                    }
                    TightPanelButton(
                        text = if (existingRecording != null) "RE-RECORD" else "RECORD",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.VOICE_REC_RECORD_BTN)
                            .helpTarget(AckTags.VOICE_REC_RECORD_BTN, primaryColor),
                        mainColor = primaryColor
                    ) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_RECORD_BTN))
                        if (micPermissionGranted) {
                            if (recorder.start(context)) {
                                recordingDurationMs = 0L
                                phase = RecordingPanelPhase.RECORDING
                            }
                        } else {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    }
                }
            }

            RecordingPanelPhase.RECORDING -> {
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
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.VOICE_REC_STOP_BTN)
                            .helpTarget(AckTags.VOICE_REC_STOP_BTN, primaryColor),
                        mainColor = primaryColor
                    ) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_STOP_BTN))
                        finishRecording()
                    }
                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        recorder.discard()
                        phase = RecordingPanelPhase.IDLE
                    }
                }
            }

            RecordingPanelPhase.PROCESSING -> {
                Text(
                    text = "REDUCING NOISE & TRIMMING SILENCE...",
                    color = Color.Gray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            RecordingPanelPhase.PREVIEW -> {
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
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.VOICE_REC_PLAY_BTN)
                            .helpTarget(AckTags.VOICE_REC_PLAY_BTN, primaryColor),
                        isActive = !isPlayingPreview,
                        mainColor = primaryColor
                    ) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_PLAY_BTN))
                        val pcm = previewPcm
                        if (pcm != null && !isPlayingPreview) {
                            isPlayingPreview = true
                            // Not-yet-saved audio has no recording id yet -- stage it to
                            // a scratch file so OutputService can play it the same way.
                            val tempFile = VoiceRecordingRepository.writeTempPreviewFile(context, pcm, previewSampleRate)
                            context.startService(Intent(context, OutputService::class.java).apply {
                                action = "PREVIEW_RECORDING"
                                putExtra("recording_path", tempFile.absolutePath)
                            })
                            coroutineScope.launch {
                                delay(recordingDurationMs + 300)
                                isPlayingPreview = false
                            }
                        }
                    }
                    TightPanelButton(
                        text = "DISCARD",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.VOICE_REC_DISCARD_BTN)
                            .helpTarget(AckTags.VOICE_REC_DISCARD_BTN, primaryColor),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_DISCARD_BTN))
                        previewPcm = null
                        phase = RecordingPanelPhase.IDLE
                    }
                    TightPanelButton(
                        text = "ACCEPT",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.VOICE_REC_ACCEPT_BTN)
                            .helpTarget(AckTags.VOICE_REC_ACCEPT_BTN, primaryColor),
                        mainColor = primaryColor
                    ) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.VOICE_REC_ACCEPT_BTN))
                        val pcm = previewPcm ?: return@TightPanelButton
                        onAccept(pcm, previewSampleRate)
                        previewPcm = null
                        phase = RecordingPanelPhase.IDLE
                    }
                }
            }
        }
    }
}
