// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.besu.R
import com.example.besu.core.PartnerCard
import com.example.besu.settings.ConfirmBodyText

/**
 * The partner card's header icon and the question a tap opens (tracker row C3; the words and rules are core/PartnerCard.kt, tested).
 *
 * Rules that must stay true (PartnerCardWiringTest holds them):
 *  - **About 24 dp, like the save icon and HELP beside it** (the developer's choice: a 48 dp icon would make the header 24 dp taller on every screen).
 *  - **Always shown.** There is no setting to hide it (the developer's choice); it sits in the header slot next to HELP, with the backup reminder's save icon to its left.
 *  - **A tap only opens the question.** Nothing is spoken until PLAY IT is tapped; CANCEL (and the back gesture, and a tap outside) closes it and does nothing else.
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
 * Asks before the card plays: shows exactly the words it will say, in the language the voice will say them, and says it follows silent mode. CANCEL is the prominent button.
 * [lines] are the card's sentences as they will be spoken; [silentModeName] is the silent-mode button's name as the person sees it (it follows PLAIN WORDS).
 */
@Composable
fun PartnerCardDialog(
    primaryColor: Color,
    lines: List<String>,
    silentModeName: String,
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
        lines.forEach { line ->
            ConfirmBodyText(line, bold = true)
            Spacer(modifier = Modifier.height(4.dp))
        }
        Spacer(modifier = Modifier.height(12.dp))
        ConfirmBodyText(text.get(PartnerCard.ASK_SILENT, silentModeName))
        Spacer(modifier = Modifier.height(16.dp))
        NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }
        Spacer(modifier = Modifier.height(8.dp))
        NeonButton(text.get(PartnerCard.ASK_PLAY), Modifier.fillMaxWidth(), mainColor = Color.White) { onPlay() }
    }
}
