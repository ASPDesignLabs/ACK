// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import com.example.besu.ui.looseSpacing
import com.example.besu.core.CaptureText
import com.example.besu.core.LabelKey
import com.example.besu.ui.labelFor
import com.example.besu.ui.rememberText
import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.besu.AckTags
import com.example.besu.R
import com.example.besu.capture.CaptureConstants
import com.example.besu.capture.CaptureSession
import com.example.besu.capture.CaptureTime
import com.example.besu.capture.CardSplitter
import com.example.besu.capture.ClipState
import com.example.besu.capture.PackagePlanner
import com.example.besu.capture.PackageVerifier
import com.example.besu.capture.PackageWriteException
import com.example.besu.capture.PackageWriter
import com.example.besu.capture.RecoveryReport
import com.example.besu.capture.StoredSession
import com.example.besu.capture.TrainingScript
import com.example.besu.help.HelpEvent
import com.example.besu.help.HelpOfferBanner
import com.example.besu.help.LocalHelpManager
import com.example.besu.help.helpTarget
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private sealed interface CaptureScreen {
    data object Home : CaptureScreen
    data class Editor(val scriptId: String?) : CaptureScreen
    data class ScriptSetup(val scriptId: String) : CaptureScreen
    data object FreeSetup : CaptureScreen
}

private data class ScriptSummary(val script: TrainingScript, val cards: Int, val done: Int)
private data class SessionSummary(val session: StoredSession, val bytes: Long)

internal fun megabytes(bytes: Long): String = CaptureText.megabytes(bytes)

internal fun clock(seconds: Double): String = CaptureText.clock(seconds)

// "RECORD TRAINING DATA": the phone-side half of building a voice model. Scripts to read, a hands-free recorder that cuts and keeps
// one clip per card, free speech, and saving what was recorded to a file for the computer. Everything stays on the phone until the
// person saves a package and moves it themselves; there is no network code and no share sheet here, by design (see CLAUDE.md,
// DATA SOVEREIGNTY). The logic is in com.example.besu.capture; this is the screen around it.
@Composable
fun TrainingCaptureHome(context: Context, primaryColor: Color, onClose: () -> Unit) {
    val store = remember { TrainingCapture.store(context) }
    val scope = rememberCoroutineScope()
    val helpManager = LocalHelpManager.current
    val words = rememberText()

    var screen by remember { mutableStateOf<CaptureScreen>(CaptureScreen.Home) }
    var refresh by remember { mutableIntStateOf(0) }
    var scripts by remember { mutableStateOf<List<ScriptSummary>>(emptyList()) }
    var sessions by remember { mutableStateOf<List<SessionSummary>>(emptyList()) }
    var damaged by remember { mutableStateOf<List<CaptureText.Damaged>>(emptyList()) }
    var recovery by remember { mutableStateOf<RecoveryReport?>(null) }
    var loaded by remember { mutableStateOf(false) }
    var hasSeenHelpOffer by remember { mutableStateOf(TrainingCapture.hasSeenHelpOffer(context)) }
    var detailFor by remember { mutableStateOf<String?>(null) }
    var deleteStep by remember { mutableStateOf(0) }
    var deleteId by remember { mutableStateOf<String?>(null) }

    // Anything left unfinished by the app closing unexpectedly is repaired once, when this screen opens.
    LaunchedEffect(Unit) {
        val report = withContext(Dispatchers.IO) { store.recoverOpenSessions(CaptureTime.utc(System.currentTimeMillis())) }
        if (report.sessionsClosed > 0 || report.problems.isNotEmpty()) recovery = report
        refresh++
    }

    LaunchedEffect(refresh) {
        val result = withContext(Dispatchers.IO) {
            val pace = TrainingCapture.measuredPace(store) ?: CaptureConstants.DEFAULT_PACE_WPS
            val scriptListing = store.listScripts()
            val sessionListing = store.listSessions()
            val summaries = scriptListing.items.map { s ->
                val cards = CardSplitter.splitCards(s.text, pace, s.lines)
                val doneTexts = store.doneCardTexts(s.id)
                ScriptSummary(s, cards.size, cards.count { it.text in doneTexts })
            }
            val sess = sessionListing.items.map { SessionSummary(it, store.sessionBytes(it.id)) }
            Triple(
                summaries, sess,
                scriptListing.damaged.map { CaptureText.Damaged(CaptureText.DamagedKind.SCRIPT, it) } + sessionListing.damaged.map { CaptureText.Damaged(CaptureText.DamagedKind.SESSION, it) },
            )
        }
        scripts = result.first
        sessions = result.second
        damaged = result.third
        loaded = true
    }

    // -- saving packages ------------------------------------------------------------------------------------------------
    var groups by remember { mutableStateOf<List<List<CaptureSession>>>(emptyList()) }
    var groupIndex by remember { mutableIntStateOf(0) }
    var saveStamp by remember { mutableLongStateOf(0L) }
    var nextFileName by remember { mutableStateOf<String?>(null) }
    var saveProgress by remember { mutableStateOf<Pair<Long, Long>?>(null) }
    var saveNotice by remember { mutableStateOf<CaptureText.SaveNotice?>(null) }

    val createDocument = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri: Uri? ->
        if (uri == null) {
            groups = emptyList()
            Toast.makeText(context, context.getString(R.string.capture_save_cancelled), Toast.LENGTH_SHORT).show()
        } else {
            val group = groups.getOrNull(groupIndex)
            if (group != null) {
                saveProgress = 0L to 1L
                scope.launch {
                    val error = withContext(Dispatchers.IO) {
                        writePackage(context, uri, group) { done, total -> saveProgress = done to maxOf(total, 1L) }
                    }
                    saveProgress = null
                    if (error != null) {
                        saveNotice = error
                        groups = emptyList()
                    } else if (groupIndex + 1 < groups.size) {
                        groupIndex += 1
                        nextFileName = CaptureTime.packageFileName(saveStamp, groupIndex + 1)
                    } else {
                        Toast.makeText(context, context.getString(R.string.capture_saved_checked), Toast.LENGTH_LONG).show()
                        groups = emptyList()
                    }
                }
            }
        }
    }

    // The next file of a package set is asked for here, outside the picker's own result handler.
    LaunchedEffect(nextFileName) {
        nextFileName?.let {
            nextFileName = null
            createDocument.launch(it)
        }
    }

    fun startSaving(chosen: List<StoredSession>) {
        scope.launch {
            val plan = withContext(Dispatchers.IO) {
                val list = chosen.filter { it.closed }.mapNotNull { store.toCaptureSession(it) }
                list to PackagePlanner.plan(list)
            }
            when {
                plan.first.isEmpty() -> saveNotice = CaptureText.SaveNotice.NothingToSave
                plan.second.tooBig.isNotEmpty() -> saveNotice = CaptureText.SaveNotice.TooBig(plan.second.tooBig)
                else -> {
                    saveNotice = null
                    groups = plan.second.packages
                    groupIndex = 0
                    saveStamp = System.currentTimeMillis()
                    createDocument.launch(CaptureTime.packageFileName(saveStamp, 1))
                }
            }
        }
    }

    // -- screens --------------------------------------------------------------------------------------------------------
    when (val current = screen) {
        is CaptureScreen.Editor -> {
            ScriptEditorScreen(context, primaryColor, current.scriptId) { changed ->
                if (changed) refresh++
                screen = CaptureScreen.Home
            }
            return
        }
        is CaptureScreen.ScriptSetup -> {
            CaptureSessionScreen(context, primaryColor, scriptId = current.scriptId, free = false) {
                refresh++
                screen = CaptureScreen.Home
            }
            return
        }
        CaptureScreen.FreeSetup -> {
            CaptureSessionScreen(context, primaryColor, scriptId = null, free = true) {
                refresh++
                screen = CaptureScreen.Home
            }
            return
        }
        CaptureScreen.Home -> {}
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(labelFor(LabelKey.RECORD_TRAINING), color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = looseSpacing(2.sp))
            Text(
                stringResource(R.string.capture_close), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                modifier = Modifier.heightIn(min = 48.dp).clickable { onClose() }.padding(horizontal = 8.dp, vertical = 12.dp),
            )
        }
        Text(
            stringResource(R.string.capture_intro),
            color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
        )

        if (!hasSeenHelpOffer) {
            // The names of the header's HELP button and of this screen follow the chosen language and PLAIN WORDS, so the sentence points at things that exist.
            HelpOfferBanner(
                message = CaptureText.helpOffer(words, stringResource(R.string.help_button), labelFor(LabelKey.RECORD_TRAINING)),
                primaryColor = primaryColor,
                onDismiss = {
                    TrainingCapture.markHelpOfferSeen(context)
                    hasSeenHelpOffer = true
                },
            )
        }

        val used = sessions.sumOf { it.bytes }
        val free = TrainingCapture.usableBytes(context)
        Text(
            CaptureText.phoneLine(words, sessions.size, megabytes(used), megabytes(free)),
            color = if (free < com.example.besu.capture.DiskGuard.MIN_FREE_TO_START_BYTES) RadicalRed else primaryColor,
            fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )

        recovery?.let { r ->
            Notice(
                CaptureText.recoveryNotice(words, r.sessionsClosed, r.clipsRecovered, r.problems),
                RadicalRed,
                onDismiss = { recovery = null },
            )
        }
        if (damaged.isNotEmpty()) {
            Notice(CaptureText.damagedNotice(words, damaged), RadicalRed, onDismiss = null)
        }
        saveNotice?.let { notice -> Notice(CaptureText.saveNotice(words, notice), RadicalRed, onDismiss = { saveNotice = null }) }

        // -- scripts --
        TightSectionLabel(stringResource(R.string.capture_scripts), color = primaryColor)
        if (loaded && scripts.isEmpty()) {
            Text(stringResource(R.string.capture_no_scripts), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        }
        for (summary in scripts) {
            Column(
                modifier = Modifier.fillMaxWidth().border(1.dp, Color.DarkGray).background(Graphite).padding(10.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(summary.script.title, color = Color.White, fontSize = 13.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                Text(
                    CaptureText.scriptCardsLine(words, summary.cards, summary.done),
                    color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TightPanelButton(stringResource(R.string.capture_record), Modifier.weight(1f).testTag(AckTags.TRAIN_SCRIPT_RECORD_BTN).helpTarget(AckTags.TRAIN_SCRIPT_RECORD_BTN, primaryColor), isActive = summary.cards > 0, mainColor = primaryColor) {
                        helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_SCRIPT_RECORD_BTN))
                        if (summary.cards > 0) screen = CaptureScreen.ScriptSetup(summary.script.id)
                    }
                    TightPanelButton(stringResource(R.string.common_edit), Modifier.weight(1f), mainColor = primaryColor) { screen = CaptureScreen.Editor(summary.script.id) }
                }
            }
        }
        TightPanelButton(
            stringResource(R.string.capture_new_script),
            Modifier.fillMaxWidth().testTag(AckTags.TRAIN_NEW_SCRIPT_BTN).helpTarget(AckTags.TRAIN_NEW_SCRIPT_BTN, primaryColor),
            mainColor = primaryColor,
        ) {
            helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_NEW_SCRIPT_BTN))
            screen = CaptureScreen.Editor(null)
        }

        // -- free speech --
        TightSectionLabel(stringResource(R.string.capture_free_speech), color = primaryColor)
        Text(
            CaptureText.freeIntro(words, CaptureConstants.MAX_FREE_SESSION_S / 60),
            color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace,
        )
        // Anyone nearby is recorded too (wording: capture_free_notice_home). Text only, 12 sp.
        Text(
            stringResource(R.string.capture_free_notice_home),
            color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        TightPanelButton(
            stringResource(R.string.capture_record_free),
            Modifier.fillMaxWidth().testTag(AckTags.TRAIN_FREE_BTN).helpTarget(AckTags.TRAIN_FREE_BTN, primaryColor),
            mainColor = primaryColor,
        ) {
            helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_FREE_BTN))
            screen = CaptureScreen.FreeSetup
        }

        // -- sessions --
        TightSectionLabel(stringResource(R.string.capture_sessions), color = primaryColor)
        if (loaded && sessions.isEmpty()) {
            Text(stringResource(R.string.capture_no_sessions), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        }
        for (item in sessions) {
            val s = item.session
            val kept = s.clips.count { it.state == ClipState.DONE }
            val held = s.clips.count { it.state == ClipState.RECOVERED } + if (s.recording?.state == ClipState.RECOVERED) 1 else 0
            Column(
                modifier = Modifier.fillMaxWidth().border(1.dp, if (held > 0) RadicalRed else Color.DarkGray).background(Graphite)
                    .clickable { detailFor = s.id }.padding(10.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    CaptureText.sessionTitle(words, s.mode, s.scriptTitle, s.label),
                    color = Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                )
                Text(
                    CaptureText.sessionLine(words, s.started, s.mode, kept, s.recording?.durationS, item.bytes, s.closed),
                    color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
                )
                if (held > 0) Text(CaptureText.heldLine(words, held), color = RadicalRed, fontSize = 9.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            }
        }
        if (sessions.any { it.session.closed }) {
            TightPanelButton(
                stringResource(R.string.capture_save_all),
                Modifier.fillMaxWidth().testTag(AckTags.TRAIN_SAVE_ALL_BTN).helpTarget(AckTags.TRAIN_SAVE_ALL_BTN, primaryColor),
                mainColor = primaryColor,
            ) {
                helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_SAVE_ALL_BTN))
                startSaving(sessions.map { it.session })
            }
            Text(
                stringResource(R.string.capture_save_note),
                color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
            )
        }
        Spacer(modifier = Modifier.height(24.dp))
    }

    // -- dialogs --------------------------------------------------------------------------------------------------------
    saveProgress?.let { (done, total) ->
        Dialog(onDismissRequest = {}) {
            Column(modifier = Modifier.fillMaxWidth().background(Graphite).border(1.dp, primaryColor).padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    CaptureText.savingLine(words, groupIndex + 1, maxOf(groups.size, 1)),
                    color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                )
                LinearProgressIndicator(progress = { (done.toFloat() / total).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth(), color = primaryColor, trackColor = Color.DarkGray)
                Text(CaptureText.savingBytes(words, done, total), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
            }
        }
    }

    detailFor?.let { id ->
        SessionDetailDialog(
            context = context, primaryColor = primaryColor, sessionId = id,
            onSave = { s -> detailFor = null; startSaving(listOf(s)) },
            onDelete = { detailFor = null; deleteId = id; deleteStep = 1 },
            onClose = { detailFor = null; refresh++ },
        )
    }

    deleteId?.let { id ->
        val target = sessions.firstOrNull { it.session.id == id }
        if (deleteStep == 1) {
            ConfirmDialog(
                title = stringResource(R.string.capture_delete_session_title),
                body = CaptureText.deleteSessionBody(words, target?.bytes),
                confirmLabel = stringResource(R.string.common_continue), cancelLabel = stringResource(R.string.capture_keep_it), primaryColor = primaryColor,
                onConfirm = { deleteStep = 2 }, onCancel = { deleteId = null; deleteStep = 0 },
            )
        } else if (deleteStep == 2) {
            ConfirmDialog(
                title = stringResource(R.string.capture_really_delete),
                body = stringResource(R.string.capture_last_chance),
                confirmLabel = stringResource(R.string.capture_delete_forever), cancelLabel = stringResource(R.string.capture_keep_it), primaryColor = RadicalRed, destructive = true,
                onConfirm = {
                    scope.launch(Dispatchers.IO) { store.deleteSession(id) }.invokeOnCompletion { refresh++ }
                    deleteId = null; deleteStep = 0
                },
                onCancel = { deleteId = null; deleteStep = 0 },
            )
        }
    }
}

// Writes one package to the file the person chose, then reads it back and checks every file against its checksum. If anything is
// wrong the half-made file is deleted, so a bad package is never left lying around looking like a good one. Returns null on success, otherwise why not (the screen words it).
private fun writePackage(context: Context, uri: Uri, sessions: List<CaptureSession>, onProgress: (Long, Long) -> Unit): CaptureText.SaveNotice? {
    val resolver = context.contentResolver
    fun discard() { try { DocumentsContract.deleteDocument(resolver, uri) } catch (_: Exception) { } }
    return try {
        val out = resolver.openOutputStream(uri, "w") ?: run {
            Log.e(TrainingCapture.LOG_TAG, "save: the file could not be opened for writing")
            return CaptureText.SaveNotice.CouldNotOpen
        }
        out.use { PackageWriter.write(sessions, it, CaptureTime.utc(System.currentTimeMillis()), TrainingCapture.appVersion(context), onProgress) }
        val verified = resolver.openInputStream(uri)?.use { PackageVerifier.verify(it) }
        when {
            verified == null -> { Log.e(TrainingCapture.LOG_TAG, "save: the saved file could not be read back"); discard(); CaptureText.SaveNotice.CouldNotReadBack }
            !verified.ok -> { Log.e(TrainingCapture.LOG_TAG, "save: the saved file failed its check: ${verified.problems.take(5)}"); discard(); CaptureText.SaveNotice.FailedCheck(verified.problems.first()) }
            else -> { Log.i(TrainingCapture.LOG_TAG, "save: wrote and verified ${verified.sessions} sessions, ${verified.audioFiles} recordings, ${verified.bytes} bytes"); null }
        }
    } catch (e: PackageWriteException) {
        Log.e(TrainingCapture.LOG_TAG, "save: the package could not be made: ${e.problems.take(5)}")
        discard()
        CaptureText.SaveNotice.CouldNotMake(e.problems.firstOrNull() ?: e.message)
    } catch (e: Exception) {
        Log.e(TrainingCapture.LOG_TAG, "save failed", e)
        discard()
        CaptureText.SaveNotice.Failed(e.message ?: e.javaClass.simpleName)
    }
}

@Composable
internal fun Notice(text: String, color: Color, onDismiss: (() -> Unit)?) {
    Row(
        modifier = Modifier.fillMaxWidth().border(1.dp, color).background(VoidBlack).padding(10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, color = color, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        if (onDismiss != null) {
            Text(stringResource(R.string.capture_ok), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.heightIn(min = 48.dp).clickable { onDismiss() }.padding(8.dp))
        }
    }
}

@Composable
internal fun ConfirmDialog(
    title: String,
    body: String,
    confirmLabel: String,
    cancelLabel: String,
    primaryColor: Color,
    destructive: Boolean = false,
    onConfirm: () -> Unit,
    onCancel: () -> Unit,
) {
    Dialog(onDismissRequest = onCancel) {
        Column(modifier = Modifier.fillMaxWidth().background(Graphite).border(1.dp, primaryColor).padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black)
            Text(body, color = Color.White, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                // The safe choice is first and gets the same weight as the risky one.
                TightPanelButton(cancelLabel, Modifier.weight(1f), mainColor = Color.White, onClick = onCancel)
                TightPanelButton(confirmLabel, Modifier.weight(1f), mainColor = if (destructive) RadicalRed else primaryColor, onClick = onConfirm)
            }
        }
    }
}
