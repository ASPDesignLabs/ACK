// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.decks

// Stubs of the three Quick Actions models MANAGE AUTOCOMPLETE reads from decks/QuickActionsModels.kt (that file is not staged), keeping only the fields it uses.
data class QuickActionSlot(val slotIndex: Int, val label: String = "ACTION ${slotIndex + 1}", val template: String = "")

data class QuickActionGroup(val groupIndex: Int, val label: String = "GROUP ${groupIndex + 1}", val slots: List<QuickActionSlot> = emptyList())

data class QuickActionsDeckConfig(val deckId: String, val groups: List<QuickActionGroup> = emptyList())
