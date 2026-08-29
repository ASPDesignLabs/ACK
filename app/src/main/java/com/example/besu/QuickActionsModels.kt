package com.example.besu

import kotlinx.serialization.Serializable

@Serializable
data class QuickActionSlot(
    val slotIndex: Int,
    val label: String = "ACTION ${slotIndex + 1}",
    val template: String = "",
    val localValues: List<String> = emptyList()
)

@Serializable
data class QuickActionGroup(
    val groupIndex: Int,
    val label: String = "GROUP ${groupIndex + 1}",

    // This lets the group's phrases use the existing A/B/C root overrides.
    //
    // It is deliberately explicit rather than inferred from the group number.
    val rootCategory: String = "IDENTITY",

    // Future watch mapping:
    // group 0 -> QUICK_ACTION_GROUP_1
    // group 1 -> QUICK_ACTION_GROUP_2
    // group 2 -> QUICK_ACTION_GROUP_3
    val slots: List<QuickActionSlot> = List(4) { slotIndex ->
        QuickActionSlot(slotIndex = slotIndex)
    }
)

@Serializable
data class QuickActionsDeckConfig(
    val deckId: String,
    val groups: List<QuickActionGroup> = List(3) { groupIndex ->
        QuickActionGroup(groupIndex = groupIndex)
    }
)
