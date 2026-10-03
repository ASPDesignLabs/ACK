// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Body text for the confirmation dialogs (delete voice, delete data, delete a safety copy). One place, so the 12 sp floor for
 * anything new (small text is a tracked problem in this app) is set once and cannot drift between dialogs.
 */
@Composable
internal fun ConfirmBodyText(text: String, bold: Boolean = false, color: Color = Color.White) {
    Text(
        text,
        color = color,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal
    )
}
