// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.runtime.Composable
import com.example.besu.core.LabelKey
import com.example.besu.data.DeckType

/**
 * The word for a deck's type (MATRIX, QUICK ACTIONS, EMERGENCY, EMOJI, GIF): the label table's word, so the chosen language and PLAIN WORDS apply. A deck's type is stored as the enum's name and
 * never changes; only the word drawn for it does. The `when` has no `else`, so a new deck type fails the build here until it has a label.
 */
@Composable
fun deckTypeLabel(type: DeckType): String = labelFor(
    when (type) {
        DeckType.MATRIX -> LabelKey.DECK_TYPE_MATRIX
        DeckType.QUICK_ACTIONS -> LabelKey.DECK_TYPE_QUICK
        DeckType.EMERGENCY -> LabelKey.DECK_TYPE_EMERGENCY
        DeckType.EMOJI -> LabelKey.DECK_TYPE_EMOJI
        DeckType.GIF -> LabelKey.DECK_TYPE_GIF
    }
)
