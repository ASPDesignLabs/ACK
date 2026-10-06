// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.ui.unit.TextUnit
import com.example.besu.core.ActiveScript

/**
 * The app's wide letter spacing is a style for capital Latin letters. In a script whose letters join (Arabic) spacing added between them pulls the word
 * apart and stops the joined forms from forming, so there it is dropped: every `letterSpacing = N.sp` goes through this. A test fails on one that does not.
 */
fun looseSpacing(spacing: TextUnit): TextUnit = if (ActiveScript.joinsLetters) TextUnit.Unspecified else spacing
