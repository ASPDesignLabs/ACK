// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import com.example.besu.ui.looseSpacing
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.res.stringResource
import com.example.besu.AckTags
import com.example.besu.R
import com.example.besu.core.CaptureText
import com.example.besu.ui.rememberText
import com.example.besu.capture.CaptureConstants
import com.example.besu.capture.Card
import com.example.besu.capture.CardSplitter
import com.example.besu.capture.StoreException
import com.example.besu.capture.TrainingScript
import com.example.besu.capture.TrainingStore
import com.example.besu.help.HelpEvent
import com.example.besu.help.LocalHelpManager
import com.example.besu.help.helpTarget
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightPanelButton
import com.example.besu.ui.TightSectionLabel
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private val LANGUAGE_CODE = Regex("^[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?$")

// Where a text to read is typed or pasted. Saving an edit to an existing script asks first; leaving with unsaved changes asks first;
// deleting takes two steps. A brand-new script saves directly, since there is nothing yet to lose. The cards the text will become are
// shown as it is edited, so the person sees what they will be asked to read before they start.
@Composable
internal fun ScriptEditorScreen(context: Context, primaryColor: Color, scriptId: String?, onDone: (changed: Boolean) -> Unit) {
    val store: TrainingStore = remember { TrainingCapture.store(context) }
    val helpManager = LocalHelpManager.current
    val words = rememberText()
    val loadError = remember(scriptId) { mutableStateOf<String?>(null) }
    val existing: TrainingScript? = remember(scriptId) {
        if (scriptId == null) null else try { store.getScript(scriptId) } catch (e: StoreException) { loadError.value = e.message; null }
    }

    var title by remember { mutableStateOf(existing?.title ?: "") }
    var text by remember { mutableStateOf(existing?.text ?: "") }
    var lines by remember { mutableStateOf(existing?.lines ?: "join") }
    var language by remember { mutableStateOf(existing?.language ?: TrainingCapture.defaultLanguage()) }
    var message by remember { mutableStateOf(loadError.value ?: "") }
    var confirmSave by remember { mutableStateOf(false) }
    var confirmLeave by remember { mutableStateOf(false) }
    var deleteStep by remember { mutableIntStateOf(0) }

    val dirty = if (existing == null) title.isNotBlank() || text.isNotBlank()
    else title != existing.title || text != existing.text || lines != existing.lines || language != existing.language

    val pace = remember { TrainingCapture.measuredPace(store) ?: CaptureConstants.DEFAULT_PACE_WPS }
    var cards by remember { mutableStateOf<List<Card>>(emptyList()) }
    LaunchedEffect(text, lines) {
        delay(350)                                                  // wait for a pause in typing before working the cards out
        cards = withContext(Dispatchers.Default) { CardSplitter.splitCards(text, pace, lines) }
    }

    fun save() {
        if (!LANGUAGE_CODE.matches(language)) { message = CaptureText.languageCodeBad(words, "EN-US"); return }
        try {
            val base = existing ?: store.newScript(title, text, lines, language, System.currentTimeMillis())
            store.saveScript(base.copy(title = title, text = text, lines = lines, language = language), System.currentTimeMillis())
            onDone(true)
        } catch (e: StoreException) {
            message = e.message ?: words.get("capture_script_save_failed")
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(if (existing == null) R.string.capture_editor_new else R.string.capture_editor_edit), color = primaryColor, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = looseSpacing(2.sp))
            Text(
                stringResource(R.string.capture_back), color = Color.Gray, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                modifier = Modifier.heightIn(min = 48.dp).clickable { if (dirty) confirmLeave = true else onDone(false) }.padding(horizontal = 8.dp, vertical = 12.dp),
            )
        }

        if (message.isNotEmpty()) Notice(message, RadicalRed, onDismiss = { message = "" })

        TightSectionLabel(stringResource(R.string.capture_title), color = primaryColor)
        EditorField(title, primaryColor, singleLine = true, modifier = Modifier.testTag(AckTags.TRAIN_SCRIPT_TITLE).helpTarget(AckTags.TRAIN_SCRIPT_TITLE, primaryColor)) {
            title = it.take(TrainingStore.MAX_TITLE_CHARS)
        }

        TightSectionLabel(stringResource(R.string.capture_text_to_read), color = primaryColor)
        Text(
            stringResource(R.string.capture_text_hint),
            color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
        )
        EditorField(
            text, primaryColor, singleLine = false, minHeight = 200.dp,
            modifier = Modifier.testTag(AckTags.TRAIN_SCRIPT_TEXT).helpTarget(AckTags.TRAIN_SCRIPT_TEXT, primaryColor),
        ) { text = it.take(TrainingStore.MAX_SCRIPT_CHARS) }
        Text(CaptureText.charsLine(words, text.length, TrainingStore.MAX_SCRIPT_CHARS), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)

        TightSectionLabel(stringResource(R.string.capture_line_breaks), color = primaryColor)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton(stringResource(R.string.capture_join_lines), Modifier.weight(1f), isActive = lines == "join", mainColor = primaryColor) { lines = "join" }
            TightPanelButton(stringResource(R.string.capture_one_per_line), Modifier.weight(1f), isActive = lines == "keep", mainColor = primaryColor) { lines = "keep" }
        }
        Text(
            CaptureText.lineBreakNote(words, lines),
            color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace,
        )

        TightSectionLabel(stringResource(R.string.capture_language_code), color = primaryColor)
        EditorField(language, primaryColor, singleLine = true) { language = it.take(12) }

        TightSectionLabel(stringResource(R.string.capture_cards), color = primaryColor)
        val minutes = cards.sumOf { it.estS } / 60.0
        Text(
            if (text.isBlank()) stringResource(R.string.capture_nothing_to_read)
            else CaptureText.cardsSummary(words, cards.size, minutes, pace, measured = TrainingCapture.measuredPace(store) != null),
            color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
        )
        val symbolCards = cards.count { "digits" in it.warnings || "symbols" in it.warnings }
        if (symbolCards > 0) {
            Text(
                CaptureText.symbolCards(words, symbolCards),
                color = RadicalRed, fontSize = 9.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
            )
        }
        for ((i, card) in cards.take(3).withIndex()) {
            Text("${i + 1}. ${card.text}", color = Color.White, fontSize = 10.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.border(1.dp, Color.DarkGray).background(Graphite).padding(8.dp).fillMaxWidth())
        }
        if (cards.size > 3) Text(CaptureText.andMore(words, cards.size - 3), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            TightPanelButton(
                stringResource(R.string.common_save), Modifier.weight(1f).testTag(AckTags.TRAIN_SCRIPT_SAVE_BTN).helpTarget(AckTags.TRAIN_SCRIPT_SAVE_BTN, primaryColor),
                isActive = dirty, mainColor = primaryColor,
            ) {
                helpManager?.onEvent(HelpEvent.Interacted(AckTags.TRAIN_SCRIPT_SAVE_BTN))
                if (!dirty) return@TightPanelButton
                if (existing == null) save() else confirmSave = true
            }
            TightPanelButton(stringResource(R.string.common_cancel), Modifier.weight(1f), isActive = false, mainColor = primaryColor) { if (dirty) confirmLeave = true else onDone(false) }
        }
        if (existing != null) {
            TightPanelButton(stringResource(R.string.capture_delete_script), Modifier.fillMaxWidth(), mainColor = RadicalRed) { deleteStep = 1 }
            Text(stringResource(R.string.capture_delete_script_note), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
        }
        Spacer(modifier = Modifier.height(24.dp))
    }

    if (confirmSave) {
        ConfirmDialog(
            title = stringResource(R.string.capture_save_changes_title),
            body = CaptureText.saveChangesBody(words, existing?.title),
            confirmLabel = stringResource(R.string.common_save), cancelLabel = stringResource(R.string.capture_keep_editing), primaryColor = primaryColor,
            onConfirm = { confirmSave = false; save() }, onCancel = { confirmSave = false },
        )
    }
    if (confirmLeave) {
        ConfirmDialog(
            title = stringResource(R.string.capture_leave_title),
            body = stringResource(R.string.capture_leave_body),
            confirmLabel = stringResource(R.string.capture_leave), cancelLabel = stringResource(R.string.capture_keep_editing), primaryColor = RadicalRed, destructive = true,
            onConfirm = { confirmLeave = false; onDone(false) }, onCancel = { confirmLeave = false },
        )
    }
    if (deleteStep == 1) {
        ConfirmDialog(
            title = stringResource(R.string.capture_delete_script_title),
            body = stringResource(R.string.capture_delete_script_body),
            confirmLabel = stringResource(R.string.common_continue), cancelLabel = stringResource(R.string.capture_keep_it), primaryColor = primaryColor,
            onConfirm = { deleteStep = 2 }, onCancel = { deleteStep = 0 },
        )
    }
    if (deleteStep == 2 && existing != null) {
        ConfirmDialog(
            title = stringResource(R.string.capture_really_delete),
            body = stringResource(R.string.capture_last_chance),
            confirmLabel = stringResource(R.string.capture_delete_forever), cancelLabel = stringResource(R.string.capture_keep_it), primaryColor = RadicalRed, destructive = true,
            onConfirm = { deleteStep = 0; store.deleteScript(existing.id); onDone(true) }, onCancel = { deleteStep = 0 },
        )
    }
}

@Composable
private fun EditorField(
    value: String,
    primaryColor: Color,
    singleLine: Boolean,
    modifier: Modifier = Modifier,
    minHeight: androidx.compose.ui.unit.Dp = 0.dp,
    onValueChange: (String) -> Unit,
) {
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = singleLine,
        textStyle = TextStyle(color = Color.White, fontSize = 14.sp, fontFamily = FontFamily.Monospace),
        cursorBrush = SolidColor(primaryColor),
        modifier = modifier.fillMaxWidth().heightIn(min = maxOf(minHeight, 48.dp)).background(VoidBlack).border(1.dp, primaryColor.copy(alpha = 0.75f)).padding(10.dp),
    )
}
