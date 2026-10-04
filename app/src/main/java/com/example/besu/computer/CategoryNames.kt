// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.computer

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.example.besu.R
import com.example.besu.core.ComputerLabels
import com.example.besu.ui.rememberText

/**
 * A category's name as the screens show it: the default in the chosen language while it still has its saved default name, otherwise exactly what is saved
 * (rule and tests in core/ComputerLabels.kt). Display only: ids, saved names and `[COMPUTER:id]` tokens are never changed by it.
 */
@Composable
fun categoryName(category: ComputerCategory): String =
    ComputerLabels.shownCategoryLabel(rememberText(), category.id, category.label)

/** A place card's day as shown (its short name in the chosen language); the saved key ("MON") never changes (core/ComputerLabels.kt). */
@Composable
internal fun dayName(day: String): String = ComputerLabels.dayLabel(rememberText(), day)

/** The words for a display mode ("TREE" or "DROPDOWN"); the mode itself is a logic value and stays as it is. */
@Composable
internal fun displayModeLabel(mode: String): String =
    stringResource(if (mode == "TREE") R.string.people_mode_tree else R.string.people_mode_dropdown)
