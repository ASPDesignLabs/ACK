// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui
import androidx.compose.ui.graphics.Color
val RadicalRed = Color(0xFFFF0055)

// Stubs of the app's own shared pieces that DesignSystem.kt owns (that file is Android-bound and is not staged). Written from the real signatures.
@androidx.compose.runtime.Composable
fun NeonButton(
    text: String,
    modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier,
    isActive: Boolean = true,
    mainColor: Color = Color.Cyan,
    onClick: () -> Unit
) {}

@androidx.compose.runtime.Composable
fun labelFor(key: com.example.besu.core.LabelKey): String = key.name

@androidx.compose.runtime.Composable
fun stringFormatLabel(key: com.example.besu.core.LabelKey, vararg args: Any): String = key.name

@androidx.compose.runtime.Composable
fun poseLabel(stored: String): String = stored

/** HELP text with its label placeholders filled in (the real one is in ui/PlainWords.kt, which is not staged). */
@androidx.compose.runtime.Composable
fun helpText(text: String): String = text

/** A HELP walkthrough's own words, a resource name read in the chosen language and filled in (the real one is in ui/PlainWords.kt, which is not staged). */
@androidx.compose.runtime.Composable
fun helpWords(nameOrText: String): String = nameOrText

/** The label for a Matrix slot's stored name (the real one is in ui/PlainWords.kt, which is not staged). */
@androidx.compose.runtime.Composable
fun slotLabel(stored: String): String = stored
