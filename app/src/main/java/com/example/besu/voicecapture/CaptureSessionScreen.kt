// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import com.example.besu.ui.looseSpacing
import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.ActivityInfo
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.besu.AckTags
import com.example.besu.R
import com.example.besu.capture.CaptureConstants
import com.example.besu.capture.CaptureNotice
import com.example.besu.capture.Card
import com.example.besu.capture.CardSplitter
import com.example.besu.capture.ClipFlags
import com.example.besu.capture.DiskGuard
import com.example.besu.capture.NoiseCheck
import com.example.besu.capture.NoiseVerdict
import com.example.besu.capture.StoreException
import com.example.besu.capture.TrainingScript
import com.example.besu.core.CaptureText
import com.example.besu.help.HelpEvent
import com.example.besu.help.LocalHelpManager
import com.example.besu.help.helpTarget
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import com.example.besu.ui.rememberText
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private enum class Phase { SETUP, CHECKING, CHECKED, CAPTURING, FINISHING, FINISHED }

// What the screen shows, copied from the runner about ten times a second. A data class, so an unchanged copy does not recompose.
private data class CaptureSnapshot(
    val state: RunState = RunState.PAUSED,
    val notice: CaptureNotice? = null,
    val currentCard: Int = -1,
    val attempt: Int = 1,
    val levelDb: Int = -120,
    val inSpeech: Boolean = false,
    val kept: Int = 0,
    val cardsLeft: Int = 0,
    val lastKeptCard: Int = 0,
    val lastKeptSeconds: Double = 0.0,
    val marks: Set<String> = emptySet(),
    val canRedo: Boolean = false,
    val hasLast: Boolean = false,
    val seconds: Double = 0.0,
    val paused: Boolean = false,
    val stopped: Boolean = false,
)

private fun Context.findActivity(): Activity? {
    var c: Context? = this
    while (c is ContextWrapper) {
        if (c is Activity) return c
        c = c.baseContext
    }
    return null
}

// A recording session, from setup to the finished summary. While it is on screen the phone stays awake and does not rotate (a
// rotation would rebuild the screen in the middle of a card), and if the app goes to the background the recording pauses itself.
// There is deliberately no sound and no vibration anywhere in here: the microphone is open, and a buzz or a beep would end up in
// the next card's audio. The buttons are plain boxes for the same reason (the app's usual buttons give haptic feedback).
@Composable
internal fun CaptureSessionScreen(context: Context, primaryColor: Color, scriptId: String?, free: Boolean, onDone: () -> Unit) {
    val store = remember { TrainingCapture.store(context) }
    val helpManager = LocalHelpManager.current
    val words = rememberText()
    val mic = remember { TrainingMicrophone() }

    var phase by remember { mutableStateOf(Phase.SETUP) }
    var script by remember { mutableStateOf<TrainingScript?>(null) }
    var cards by remember { mutableStateOf<List<Card>>(emptyList()) }
    var doneTexts by remember { mutableStateOf<Set<String>>(emptySet()) }
    var includeDone by remember { mutableStateOf(false) }
    var pace by remember { mutableDoubleStateOf(CaptureConstants.DEFAULT_PACE_WPS) }
    var paceIsMeasured by remember { mutableStateOf(false) }
    var loadError by remember { mutableStateOf<CaptureNotice?>(null) }
    var label by remember { mutableStateOf(TrainingCapture.lastLabel(context)) }
    var topic by remember { mutableStateOf("") }
    var endWait by remember { mutableIntStateOf(TrainingCapture.endWaitHops(context)) }
    var micError by remember { mutableStateOf<CaptureNotice?>(null) }
    var noise by remember { mutableStateOf<NoiseCheckRunner?>(null) }
    var noiseSeconds by remember { mutableDoubleStateOf(0.0) }
    var noiseResult by remember { mutableStateOf<NoiseCheck?>(null) }
    var runner by remember { mutableStateOf<ScriptSessionRunner?>(null) }
    var freeRunner by remember { mutableStateOf<FreeSessionRunner?>(null) }
    var snap by remember { mutableStateOf(CaptureSnapshot()) }
    var confirmEnd by remember { mutableStateOf(false) }
    var summary by remember { mutableStateOf<CaptureText.SessionSummary?>(null) }

    // Load the script and work out the cards, off the main thread (a long text takes a moment).
    LaunchedEffect(scriptId) {
        if (scriptId == null) return@LaunchedEffect
        try {
            val loaded = withContext(Dispatchers.IO) {
                val sc = store.getScript(scriptId) ?: return@withContext null
                val measured = TrainingCapture.measuredPace(store)
                val p = measured ?: CaptureConstants.DEFAULT_PACE_WPS
                Triple(sc, CardSplitter.splitCards(sc.text, p, sc.lines), Triple(p, measured != null, store.doneCardTexts(sc.id)))
            }
            if (loaded == null) { loadError = CaptureNotice.ScriptGone; return@LaunchedEffect }
            script = loaded.first
            cards = loaded.second
            pace = loaded.third.first
            paceIsMeasured = loaded.third.second
            doneTexts = loaded.third.third
        } catch (e: StoreException) {
            loadError = CaptureNotice.ScriptUnreadable(e.message)
        }
    }

    val pending = remember(cards, doneTexts, includeDone) { cards.indices.filter { includeDone || cards[it].text !in doneTexts } }

    // Keep the screen on and the orientation fixed while this screen is up; pause when the app is no longer in front.
    DisposableEffect(Unit) {
        val activity = context.findActivity()
        val oldOrientation = activity?.requestedOrientation
        activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LOCKED
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val owner = activity as? ComponentActivity
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                runner?.pause()
                freeRunner?.pause()
            }
        }
        owner?.lifecycle?.addObserver(observer)
        onDispose {
            owner?.lifecycle?.removeObserver(observer)
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (oldOrientation != null) activity?.requestedOrientation = oldOrientation
            noise?.cancel()
            runner?.close()                                       // ends the session; everything kept stays kept
            freeRunner?.let { r -> Thread { try { r.stop() } catch (_: Exception) { } }.start() }   // scanning a long recording is not for the main thread
            mic.close()
        }
    }

    fun beginQuietCheck() {
        micError = null
        noiseResult = null
        val free2 = TrainingCapture.usableBytes(context)
        if (!DiskGuard.canStart(free2)) {
            micError = CaptureNotice.NotEnoughRoomToStart(DiskGuard.room(free2, 48_000), DiskGuard.MIN_FREE_TO_START_BYTES / (1024 * 1024))
            return
        }
        val error = mic.open(context)
        if (error != null) { micError = error; return }
        val r = NoiseCheckRunner(mic)
        noise = r
        noiseSeconds = 0.0
        r.start()
        phase = Phase.CHECKING
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) beginQuietCheck() else micError = CaptureNotice.MicDenied
    }

    fun startCapture() {
        val floor = noiseResult?.floorDbfs()
        TrainingCapture.setLastLabel(context, label)
        TrainingCapture.setEndWaitHops(context, endWait)
        try {
            if (free) {
                val r = FreeSessionRunner(context, mic, label.trim(), topic.trim(), floor)
                freeRunner = r
                r.start()
            } else {
                val sc = script ?: return
                val r = ScriptSessionRunner(context, mic, sc, cards, pending, label.trim(), floor, endWait, pace)
                runner = r
                r.start()
            }
            phase = Phase.CAPTURING
        } catch (e: StoreException) {
            micError = CaptureNotice.CouldNotStart(e.message)
        }
    }

    fun finishScript(r: ScriptSessionRunner) {
        mic.close()
        summary = CaptureText.SessionSummary.Script(r.kept, r.cardsLeft)
        phase = Phase.FINISHED
    }

    // The quiet check: wait for the two seconds, then show what was heard.
    LaunchedEffect(phase, noise) {
        val r = noise
        if (phase != Phase.CHECKING || r == null) return@LaunchedEffect
        while (phase == Phase.CHECKING) {
            noiseSeconds = r.seconds
            if (r.done) {
                noiseResult = r.result()
                phase = Phase.CHECKED
            }
            delay(50)
        }
    }

    // Recording: copy what the runner knows into the snapshot, ten times a second.
    LaunchedEffect(phase, runner, freeRunner) {
        if (phase != Phase.CAPTURING) return@LaunchedEffect
        while (phase == Phase.CAPTURING) {
            val r = runner
            val f = freeRunner
            val failure = mic.failure
            if (r != null) {
                if (failure != null && r.state == RunState.LISTENING) r.pause()
                val last = r.lastKept
                snap = CaptureSnapshot(
                    state = r.state, notice = failure ?: r.notice, currentCard = r.currentCard, attempt = r.attempt, levelDb = r.level.toInt(),
                    inSpeech = r.inSpeech, kept = r.kept, cardsLeft = r.cardsLeft, lastKeptCard = last?.card ?: 0, lastKeptSeconds = last?.durationS ?: 0.0,
                    marks = r.marks(), canRedo = r.canRedo, hasLast = last != null,
                )
                if (r.state == RunState.FINISHED) finishScript(r)
            } else if (f != null) {
                if (failure != null && !f.isPaused && !f.isStopped) f.pause()
                snap = CaptureSnapshot(notice = failure ?: f.notice, levelDb = f.level.toInt(), inSpeech = f.isSpeech, seconds = f.seconds, paused = f.isPaused, stopped = f.isStopped)
                if (f.isStopped) {
                    phase = Phase.FINISHING
                }
            }
            delay(100)
        }
    }

    // A free recording is stopped by the person or by itself; either way it is scanned for suggested pieces off the main thread.
    LaunchedEffect(phase) {
        val f = freeRunner
        if (phase != Phase.FINISHING || f == null) return@LaunchedEffect
        val result = withContext(Dispatchers.IO) { try { f.stop() } catch (e: Exception) { null } }
        mic.close()
        summary = if (result == null) CaptureText.SessionSummary.NothingRecorded else CaptureText.SessionSummary.Free(result.durationS, result.pieces.size)
        phase = Phase.FINISHED
    }

    BackHandler(enabled = phase == Phase.CAPTURING) { confirmEnd = true }

    when (phase) {
        Phase.SETUP, Phase.CHECKING, Phase.CHECKED -> SetupView(
            primaryColor = primaryColor, free = free, script = script, cardsCount = cards.size, pendingCount = pending.size,
            allDone = !free && cards.isNotEmpty() && pending.isEmpty(), includeDone = includeDone, onIncludeDone = { includeDone = it },
            pace = pace, paceIsMeasured = paceIsMeasured, loadError = loadError,
            label = label, onLabel = { label = it.take(120) }, topic = topic, onTopic = { topic = it.take(200) },
            endWait = endWait, onEndWait = { endWait = it }, micError = micError,
            phase = phase, noiseSeconds = noiseSeconds, noise = noiseResult,
            onCheck = {
                helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_QUIET_CHECK_BTN))
                if (TrainingCapture.hasMicPermission(context)) beginQuietCheck() else permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            },
            onStart = {
                helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_START_BTN))
                startCapture()
            },
            onBack = onDone,
        )
        Phase.CAPTURING -> if (free) FreeCaptureView(primaryColor, snap, freeRunner, onEnd = { freeRunner?.let { phase = Phase.FINISHING; Unit } })
        else ScriptCaptureView(primaryColor, snap, runner, cards, onEnd = { confirmEnd = true })
        Phase.FINISHING -> CenterMessage(stringResource(R.string.capture_finishing), primaryColor)
        Phase.FINISHED -> Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.capture_session_ended), color = primaryColor, fontSize = 16.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            summary?.let { Text(CaptureText.summary(words, it), color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace) }
            Text(
                CaptureText.finishedNote(words),
                color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
            )
            TightPanelButton(stringResource(R.string.common_done), Modifier.fillMaxWidth(), mainColor = primaryColor) { onDone() }
        }
    }

    if (confirmEnd) {
        ConfirmDialog(
            title = stringResource(R.string.capture_end_title),
            body = stringResource(R.string.capture_end_body),
            confirmLabel = stringResource(R.string.capture_end_session), cancelLabel = stringResource(R.string.capture_continue_recording), primaryColor = primaryColor,
            onConfirm = {
                confirmEnd = false
                val r = runner
                if (r != null) { r.end(); finishScript(r) }
            },
            onCancel = { confirmEnd = false },
        )
    }
}

@Composable
private fun CenterMessage(text: String, color: Color) {
    Box(modifier = Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(text, color = color, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
    }
}

// A plain box button: the same look as the app's, but with no haptic feedback, so pressing it cannot buzz into the microphone.
@Composable
private fun CaptureButton(text: String, modifier: Modifier = Modifier, color: Color, active: Boolean = true, compact: Boolean = false, onClick: () -> Unit) {
    val c = if (active) color else color.copy(alpha = 0.4f)
    Box(
        modifier = modifier.heightIn(min = if (compact) 48.dp else 56.dp).border(1.dp, c, CutCornerShape(8.dp)).background(color.copy(alpha = if (active) 0.12f else 0f), CutCornerShape(8.dp))
            .clickable(onClick = onClick).padding(horizontal = if (compact) 2.dp else 12.dp, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text.uppercase(), color = c, fontSize = if (compact) 9.sp else 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(if (compact) 0.sp else 1.sp), textAlign = TextAlign.Center, maxLines = 2,
        )
    }
}

@Composable
private fun LevelMeter(levelDb: Int, color: Color) {
    val fraction = ((levelDb + 90) / 90f).coerceIn(0f, 1f)
    Box(modifier = Modifier.fillMaxWidth().height(14.dp).background(Color.DarkGray)) {
        Box(modifier = Modifier.fillMaxWidth(fraction).fillMaxHeight().background(color))
    }
}

@Composable
private fun SetupView(
    primaryColor: Color,
    free: Boolean,
    script: TrainingScript?,
    cardsCount: Int,
    pendingCount: Int,
    allDone: Boolean,
    includeDone: Boolean,
    onIncludeDone: (Boolean) -> Unit,
    pace: Double,
    paceIsMeasured: Boolean,
    loadError: CaptureNotice?,
    label: String,
    onLabel: (String) -> Unit,
    topic: String,
    onTopic: (String) -> Unit,
    endWait: Int,
    onEndWait: (Int) -> Unit,
    micError: CaptureNotice?,
    phase: Phase,
    noiseSeconds: Double,
    noise: NoiseCheck?,
    onCheck: () -> Unit,
    onStart: () -> Unit,
    onBack: () -> Unit,
) {
    val words = rememberText()
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(if (free) R.string.capture_free_speech else R.string.capture_record_script_title), color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = looseSpacing(2.sp))
            Text(
                stringResource(R.string.capture_back), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                modifier = Modifier.heightIn(min = 48.dp).clickable(enabled = phase != Phase.CHECKING) { onBack() }.padding(horizontal = 8.dp, vertical = 12.dp),
            )
        }
        loadError?.let { Notice(CaptureText.notice(words, it), RadicalRed, onDismiss = null) }
        micError?.let { Notice(CaptureText.notice(words, it), RadicalRed, onDismiss = null) }

        if (!free && script != null) {
            Text(script.title, color = Color.White, fontSize = 13.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            Text(
                CaptureText.setupCardsLine(words, cardsCount, pendingCount, includeDone),
                color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
            )
            Text(
                CaptureText.paceLine(words, pace, paceIsMeasured),
                color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
            )
            if (cardsCount > 0 && (pendingCount < cardsCount || allDone)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    TightPanelButton(CaptureText.includeDoneLabel(words, includeDone, allDone), Modifier.weight(1f), mainColor = primaryColor) { onIncludeDone(!includeDone) }
                }
            }
        }

        TightSectionLabel(stringResource(R.string.capture_name_session), color = primaryColor)
        Text(stringResource(R.string.capture_name_hint), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
        SimpleField(label, primaryColor, onLabel)
        if (free) {
            TightSectionLabel(stringResource(R.string.capture_topic), color = primaryColor)
            SimpleField(topic, primaryColor, onTopic)
        } else {
            TightSectionLabel(stringResource(R.string.capture_wait_title), color = primaryColor)
            Text(
                CaptureText.waitNote(words, endWait),
                color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
            )
            Slider(
                value = endWait / 100f, onValueChange = { onEndWait(Math.round(it * 20f) * 5) },
                valueRange = TrainingCapture.END_WAIT_MIN_HOPS / 100f..TrainingCapture.END_WAIT_MAX_HOPS / 100f,
                colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray),
            )
        }

        TightSectionLabel(stringResource(R.string.capture_before_title), color = primaryColor)
        Text(
            stringResource(R.string.capture_before_text),
            color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
        )
        if (free) {
            // Free speech keeps everything the microphone hears, so anyone nearby is recorded too (wording: capture_free_notice_setup, through CaptureText.freeNoticeSetup).
            // Text only, in this screen's own palette and at 12 sp: this screen makes no sound or vibration, so no dialog, toast or
            // standard button here. Script recording does not show it.
            Text(
                CaptureText.freeNoticeSetup(words),
                color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
            )
        }

        when (phase) {
            Phase.SETUP -> TightPanelButton(
                CaptureText.startQuietLabel(words),
                Modifier.fillMaxWidth().testTag(AckTags.TRAIN_QUIET_CHECK_BTN).helpTarget(AckTags.TRAIN_QUIET_CHECK_BTN, primaryColor),
                isActive = free || pendingCount > 0 || includeDone, mainColor = primaryColor, onClick = onCheck,
            )
            Phase.CHECKING -> {
                Text(stringResource(R.string.capture_stay_quiet), color = primaryColor, fontSize = 22.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
                Box(modifier = Modifier.fillMaxWidth().height(14.dp).background(Color.DarkGray)) {
                    Box(modifier = Modifier.fillMaxWidth((noiseSeconds / CaptureConstants.NOISE_CHECK_S).toFloat().coerceIn(0f, 1f)).fillMaxHeight().background(primaryColor))
                }
            }
            else -> {
                val verdict = noise?.verdict()
                val bad = verdict == NoiseVerdict.NO_SIGNAL || verdict == NoiseVerdict.INTERRUPTED
                Text(noise?.let { CaptureText.noiseVerdict(words, it.verdict(), it.floorDbfs()) } ?: "", color = if (verdict == NoiseVerdict.GOOD) primaryColor else RadicalRed, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    TightPanelButton(stringResource(R.string.capture_check_again), Modifier.weight(1f), isActive = bad, mainColor = primaryColor, onClick = onCheck)
                    TightPanelButton(
                        stringResource(R.string.capture_start_recording), Modifier.weight(1f).testTag(AckTags.TRAIN_START_BTN).helpTarget(AckTags.TRAIN_START_BTN, primaryColor),
                        isActive = !bad, mainColor = primaryColor,
                    ) { if (!bad) onStart() }
                }
            }
        }
        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun SimpleField(value: String, primaryColor: Color, onValueChange: (String) -> Unit) {
    BasicTextField(
        value = value, onValueChange = onValueChange, singleLine = true,
        textStyle = TextStyle(color = Color.White, fontSize = 13.sp, fontFamily = FontFamily.Monospace),
        cursorBrush = SolidColor(primaryColor),
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).background(VoidBlack).border(1.dp, primaryColor.copy(alpha = 0.75f)).padding(10.dp),
    )
}

@Composable
private fun ScriptCaptureView(primaryColor: Color, snap: CaptureSnapshot, runner: ScriptSessionRunner?, cards: List<Card>, onEnd: () -> Unit) {
    val helpManager = LocalHelpManager.current
    val words = rememberText()
    val card = cards.getOrNull(snap.currentCard)
    val next = cards.getOrNull(snap.currentCard + 1)
    val listening = snap.state == RunState.LISTENING
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                CaptureText.cardHeading(words, snap.currentCard + 1, cards.size, snap.attempt),
                color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
            )
            Text(CaptureText.keptLeft(words, snap.kept, snap.cardsLeft), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        }
        LevelMeter(snap.levelDb, if (snap.inSpeech) primaryColor else Color.Gray)
        Text(
            CaptureText.scriptStatus(words, paused = snap.state == RunState.PAUSED, inSpeech = snap.inSpeech),
            color = if (snap.state == RunState.PAUSED) RadicalRed else primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        snap.notice?.let { Notice(CaptureText.notice(words, it), RadicalRed, onDismiss = null) }

        Box(
            modifier = Modifier.fillMaxWidth().weight(1f).border(1.dp, primaryColor, CutCornerShape(12.dp)).background(Graphite, CutCornerShape(12.dp)).padding(16.dp)
                .testTag(AckTags.TRAIN_CARD_TEXT).helpTarget(AckTags.TRAIN_CARD_TEXT, primaryColor),
        ) {
            Text(
                card?.text ?: "", color = Color.White, fontSize = 26.sp, lineHeight = 36.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                modifier = Modifier.verticalScroll(rememberScrollState()),
            )
        }
        if (next != null) {
            Text(CaptureText.nextLine(words, next.text), color = Color.DarkGray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, maxLines = 2)
        }
        if (snap.hasLast) {
            Text(
                CaptureText.lastSaved(words, snap.lastKeptCard, snap.lastKeptSeconds),
                color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.fillMaxWidth()) {
                for (flag in ClipFlags.PERSON) {
                    CaptureButton(CaptureText.markWord(words, flag), Modifier.weight(1f), color = primaryColor, active = flag in snap.marks, compact = true) { runner?.toggleMark(flag) }
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            CaptureButton(stringResource(R.string.capture_redo_last), Modifier.weight(1f).testTag(AckTags.TRAIN_REDO_BTN).helpTarget(AckTags.TRAIN_REDO_BTN, primaryColor), color = primaryColor, active = snap.canRedo) {
                helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_REDO_BTN))
                runner?.redoLast()
            }
            if (listening) {
                CaptureButton(stringResource(R.string.capture_pause), Modifier.weight(1f).testTag(AckTags.TRAIN_PAUSE_BTN).helpTarget(AckTags.TRAIN_PAUSE_BTN, primaryColor), color = primaryColor) {
                    helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_PAUSE_BTN))
                    runner?.pause()
                }
            } else {
                CaptureButton(stringResource(R.string.capture_resume), Modifier.weight(1f).testTag(AckTags.TRAIN_PAUSE_BTN).helpTarget(AckTags.TRAIN_PAUSE_BTN, primaryColor), color = primaryColor) {
                    helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_PAUSE_BTN))
                    runner?.resume()
                }
            }
        }
        CaptureButton(stringResource(R.string.capture_end_session), Modifier.fillMaxWidth().testTag(AckTags.TRAIN_END_BTN).helpTarget(AckTags.TRAIN_END_BTN, primaryColor), color = RadicalRed, onClick = onEnd)
    }
}

@Composable
private fun FreeCaptureView(primaryColor: Color, snap: CaptureSnapshot, runner: FreeSessionRunner?, onEnd: () -> Unit) {
    val words = rememberText()
    Column(modifier = Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.capture_free_speech), color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Text(clock(snap.seconds), color = Color.White, fontSize = 56.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
        LevelMeter(snap.levelDb, if (snap.inSpeech) primaryColor else Color.Gray)
        Text(
            CaptureText.freeStatus(words, paused = snap.paused, inSpeech = snap.inSpeech),
            color = if (snap.paused) RadicalRed else primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        snap.notice?.let { Notice(CaptureText.notice(words, it), RadicalRed, onDismiss = null) }
        Text(
            CaptureText.freeNote(words),
            color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
        )
        Spacer(modifier = Modifier.weight(1f))
        if (snap.paused) {
            CaptureButton(stringResource(R.string.capture_resume), Modifier.fillMaxWidth(), color = primaryColor) { runner?.resume() }
        } else {
            CaptureButton(stringResource(R.string.capture_pause), Modifier.fillMaxWidth(), color = primaryColor) { runner?.pause() }
        }
        CaptureButton(stringResource(R.string.capture_stop_keep), Modifier.fillMaxWidth().testTag(AckTags.TRAIN_END_BTN).helpTarget(AckTags.TRAIN_END_BTN, primaryColor), color = RadicalRed, onClick = onEnd)
    }
}
