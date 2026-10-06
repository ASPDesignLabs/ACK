// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.AckTags
import com.example.besu.R
import com.example.besu.core.InterfaceLanguage
import com.example.besu.help.AckHelpShape
import com.example.besu.ui.NeonButton
import com.example.besu.ui.TightDialogSurface

/**
 * SETTINGS > LANGUAGE: the language of ACK's own words (rules in core/InterfaceLanguage.kt). The heading is the word for language in every language ACK
 * has, fixed text, so a person who cannot read the current language can still find it. Each language is named in its own script, never translated.
 *
 * Choosing one does not change anything yet: it opens a confirmation (CANCEL is the prominent button, and tapping outside cancels) that says ACK will
 * restart once and that nothing is deleted. Only the confirming button calls [onConfirmed], which saves the choice and restarts (the caller owns that).
 * Text is 12 sp or larger, every choice is at least 48 dp tall, and nothing animates or vibrates.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun InterfaceLanguageSection(
    current: InterfaceLanguage,
    primaryColor: Color,
    onConfirmed: (InterfaceLanguage) -> Unit
) {
    var pending by remember { mutableStateOf<InterfaceLanguage?>(null) }

    Text(
        stringResource(R.string.interface_language_all),
        color = primaryColor,
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(6.dp))
    Text(
        stringResource(R.string.interface_language_explanation),
        color = Color.Gray,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(10.dp))

    FlowRow(
        modifier = Modifier.fillMaxWidth().testTag(AckTags.INTERFACE_LANGUAGE),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        InterfaceLanguage.values().forEach { language ->
            val selected = language == current
            val name = if (language == InterfaceLanguage.DEVICE) stringResource(R.string.interface_language_device) else language.nativeName
            Box(
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .border(if (selected) 2.dp else 1.dp, if (selected) primaryColor else Color.Gray, AckHelpShape)
                    .selectable(selected = selected, role = Role.RadioButton, onClick = { if (!selected) pending = language })
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    if (selected) "✓ $name" else name,
                    color = if (selected) primaryColor else Color.White,
                    fontSize = 12.sp,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }

    val choice = pending
    if (choice != null) {
        val name = if (choice == InterfaceLanguage.DEVICE) stringResource(R.string.interface_language_device) else choice.nativeName
        val cancel = stringResource(R.string.common_cancel)
        TightDialogSurface(
            onDismiss = { pending = null },
            primaryColor = primaryColor,
            title = stringResource(R.string.interface_language_confirm_title),
            dismissLabel = cancel
        ) {
            ConfirmBodyText(stringResource(R.string.interface_language_confirm_body, name), bold = true)
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { pending = null }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(stringResource(R.string.interface_language_confirm), Modifier.fillMaxWidth(), mainColor = Color.White) {
                pending = null
                onConfirmed(choice)
            }
        }
    }
}
