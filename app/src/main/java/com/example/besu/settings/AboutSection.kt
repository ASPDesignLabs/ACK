// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.core.LimitsNotice
import com.example.besu.ui.rememberText

/**
 * SETTINGS > ABOUT ACK: the limits statement, always there to read again (rules in core/LimitsNotice.kt). It only shows words: nothing in it is a switch, a
 * button or a link, and nothing changes by looking at it. It is the permanent home of the statement; the one-time banner (ui/LimitsNoticeBanner.kt) only points here.
 * Text is 12 sp or larger and the heading matches the other new sections.
 */
@Composable
fun AboutSection(primaryColor: Color) {
    val text = rememberText()
    Text(
        text.get(LimitsNotice.ABOUT_TITLE),
        color = primaryColor,
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(6.dp))
    LimitsNotice.sentences(text).forEach { sentence ->
        ConfirmBodyText(sentence)
        Spacer(modifier = Modifier.height(4.dp))
    }
}
