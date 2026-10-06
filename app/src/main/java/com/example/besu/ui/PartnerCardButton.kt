// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.PartnerCard
import com.example.besu.help.AckHelpShape
import com.example.besu.settings.ConfirmBodyText
import com.example.besu.ui.theme.VoidBlack

/**
 * The partner card's header icon and the question a tap opens (tracker row C3; the words and rules are core/PartnerCard.kt, tested).
 *
 * Rules that must stay true (PartnerCardWiringTest holds them):
 *  - **About 24 dp, like the save icon and HELP beside it** (the developer's choice: a 48 dp icon would make the header 24 dp taller on every screen).
 *  - **Always shown.** There is no setting to hide it (the developer's choice); it sits in the header slot next to HELP, with the backup reminder's save icon to its left.
 *  - **A tap only opens the question.** Nothing is spoken until PLAY IT is tapped; CANCEL (and the back gesture, and a tap outside) closes it and does nothing else.
 *  - **The question is where the person chooses.** Each of the seven sentences has its own ON/OFF, written in words (a switch row that is easy to hit, no haptics), and the question shows
 *    exactly what will be said; PLAY IT is not offered when every sentence is off. WRITE and EDIT open the dialog for the person's own sentences; clearing one asks a second time.
 *  - **No animation, no sound of its own.** It is a plain outline in the theme colour; the dialog's buttons are the app's usual ones.
 */
val PartnerCardIconSize = 24.dp

@Composable
fun PartnerCardIndicator(primaryColor: Color, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val description = rememberText().get(PartnerCard.ICON_DESCRIPTION)
    Box(
        modifier = modifier
            .size(PartnerCardIconSize)
            .border(1.dp, primaryColor, CutCornerShape(4.dp))
            .clickable(onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center
    ) {
        BubbleGlyph(color = primaryColor, modifier = Modifier.size(12.dp))
    }
}

// A speech bubble in outline: a box with a tail at the bottom left.
@Composable
private fun BubbleGlyph(color: Color, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val stroke = Stroke(width = 1.5.dp.toPx(), cap = StrokeCap.Square)
        val w = size.width
        val h = size.height
        val body = Path().apply {
            moveTo(0f, 0f)
            lineTo(w, 0f)
            lineTo(w, h * 0.70f)
            lineTo(w * 0.50f, h * 0.70f)
            lineTo(w * 0.20f, h)
            lineTo(w * 0.20f, h * 0.70f)
            lineTo(0f, h * 0.70f)
            close()
        }
        drawPath(body, color, style = stroke)
    }
}

/**
 * Asks before the card plays, and is where the person chooses what it says. Shows every sentence with its own ON or OFF, written in words and as a whole-row switch (no haptics, no animation), the person's
 * own two slots (WRITE when empty, EDIT when written), and says the card follows silent mode. CANCEL is the prominent button; PLAY IT is plainer and is not offered when every sentence is off, where a line
 * says so instead. [rows] are the sentences exactly as they will be said (built-in ones in the language the voice speaks); [silentModeName] is the silent-mode button's name as the person sees it.
 */
@Composable
fun PartnerCardDialog(
    primaryColor: Color,
    rows: List<PartnerCard.Row>,
    anyOn: Boolean,
    silentModeName: String,
    onToggle: (Int) -> Unit,
    onEditOwn: (Int) -> Unit,
    onCancel: () -> Unit,
    onPlay: () -> Unit
) {
    val text = rememberText()
    val cancel = stringResource(R.string.common_cancel)
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = text.get(PartnerCard.ASK_TITLE),
        dismissLabel = cancel
    ) {
        ConfirmBodyText(text.get(PartnerCard.ASK_INTRO))
        Spacer(modifier = Modifier.height(12.dp))
        rows.forEach { row ->
            SentenceRow(row, primaryColor, onToggle = { onToggle(row.slot) }, onEdit = { onEditOwn(row.slot) })
            Spacer(modifier = Modifier.height(6.dp))
        }
        Spacer(modifier = Modifier.height(6.dp))
        if (anyOn) {
            ConfirmBodyText(text.get(PartnerCard.ASK_SILENT, silentModeName))
        } else {
            ConfirmBodyText(text.get(PartnerCard.NONE_ON), bold = true)
        }
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        if (anyOn) {
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(text.get(PartnerCard.ASK_PLAY), Modifier.fillMaxWidth(), mainColor = Color.White) { onPlay() }
        }
    }
}

// One sentence: a whole-row switch showing ON or OFF in words (at least 48 dp tall), and for the person's own slots a button to write or edit it. An own slot with nothing written has no switch.
@Composable
private fun SentenceRow(row: PartnerCard.Row, primaryColor: Color, onToggle: () -> Unit, onEdit: () -> Unit) {
    val text = rememberText()
    val number = (row.slot - PartnerCard.BUILT_IN_COUNT + 1).toString()
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        if (row.written) {
            val edge = if (row.on) primaryColor else Color.Gray
            Row(
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 48.dp)
                    .border(1.dp, edge, CutCornerShape(4.dp))
                    .toggleable(value = row.on, role = Role.Switch, onValueChange = { onToggle() })
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(modifier = Modifier.widthIn(min = 40.dp)) {
                    ConfirmBodyText(stringResource(if (row.on) R.string.common_on else R.string.common_off), bold = true, color = edge)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    ConfirmBodyText(row.text, bold = row.on, color = if (row.on) Color.White else Color.Gray)
                    if (row.own) ConfirmBodyText(text.get(PartnerCard.OWN_LABEL, number), color = Color.Gray)
                }
            }
            if (row.own) {
                Spacer(modifier = Modifier.width(6.dp))
                NeonButton(text.get(PartnerCard.EDIT), mainColor = Color.White) { onEdit() }
            }
        } else {
            Column(modifier = Modifier.weight(1f)) {
                ConfirmBodyText(text.get(PartnerCard.OWN_EMPTY, number), color = Color.Gray)
            }
            Spacer(modifier = Modifier.width(6.dp))
            NeonButton(text.get(PartnerCard.WRITE), mainColor = Color.White) { onEdit() }
        }
    }
}

/**
 * Writes or changes one of the person's own sentences. A text box (nothing is saved while typing), a hint saying ACK says it exactly as written, that it is kept on this phone and is in the export
 * (which is not encrypted), and the longest it can be. CANCEL is prominent and changes nothing; SAVE is offered only when something is written (the text is tidied: one line, at most
 * [PartnerCard.MAX_OWN_LENGTH] characters); CLEAR THIS SENTENCE is offered only for a written sentence and asks a second time before it removes it. [exportName] is the export button's name as the
 * person sees it.
 */
@Composable
fun PartnerCardEditDialog(
    primaryColor: Color,
    ownNumber: Int,
    current: String,
    exportName: String,
    onSave: (String) -> Unit,
    onClear: () -> Unit,
    onCancel: () -> Unit
) {
    val text = rememberText()
    val cancel = stringResource(R.string.common_cancel)
    var draft by remember { mutableStateOf(current) }
    var asking by remember { mutableStateOf(false) }
    val number = ownNumber.toString()
    TightDialogSurface(
        onDismiss = onCancel,
        primaryColor = primaryColor,
        title = text.get(PartnerCard.OWN_LABEL, number),
        dismissLabel = cancel
    ) {
        ConfirmBodyText(text.get(PartnerCard.EDIT_HINT, exportName, PartnerCard.MAX_OWN_LENGTH.toString()))
        Spacer(modifier = Modifier.height(12.dp))
        OutlinedTextField(
            value = draft,
            onValueChange = { draft = PartnerCard.limitDraft(it) },
            placeholder = { Text(text.get(PartnerCard.EDIT_PLACEHOLDER)) },
            shape = AckHelpShape,
            modifier = Modifier.fillMaxWidth(),
            colors = TextFieldDefaults.colors(
                focusedTextColor = primaryColor,
                unfocusedTextColor = primaryColor,
                focusedContainerColor = VoidBlack,
                unfocusedContainerColor = VoidBlack,
                focusedIndicatorColor = primaryColor
            )
        )
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        if (PartnerCard.cleanOwn(draft).isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.common_save), Modifier.fillMaxWidth(), mainColor = Color.White) { onSave(draft) }
        }
        if (current.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(text.get(PartnerCard.CLEAR), Modifier.fillMaxWidth(), mainColor = Color.White) { asking = true }
        }
    }
    if (asking) {
        TightDialogSurface(
            onDismiss = { asking = false },
            primaryColor = primaryColor,
            title = text.get(PartnerCard.CLEAR_TITLE, number),
            dismissLabel = cancel
        ) {
            ConfirmBodyText(text.get(PartnerCard.CLEAR_BODY), bold = true)
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { asking = false }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(text.get(PartnerCard.CLEAR_CONFIRM), Modifier.fillMaxWidth(), mainColor = Color.White) {
                asking = false
                onClear()
            }
        }
    }
}
