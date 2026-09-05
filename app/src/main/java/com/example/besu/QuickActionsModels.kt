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

    // Which watch pose fires this group -- distinct from rootCategory above.
    // CommandRepository.resolveSignalToPhrase() routes an incoming gesture to
    // whichever group has boundPose == the pose that was just locked, and the
    // fired twist index (0-3) selects the slot within it. Normalized to a
    // permutation of IDENTITY/DEFEND/CONNECT across the deck's three groups --
    // see normalizeQuickActionsConfig.
    val boundPose: String = defaultBoundPose(groupIndex),

    val slots: List<QuickActionSlot> = List(4) { slotIndex ->
        QuickActionSlot(slotIndex = slotIndex)
    }
)

fun defaultBoundPose(groupIndex: Int): String =
    POSE_CATEGORIES.getOrElse(groupIndex) { POSE_CATEGORIES[0] }

val POSE_CATEGORIES = listOf("IDENTITY", "DEFEND", "CONNECT")

@Serializable
data class QuickActionsDeckConfig(
    val deckId: String,
    val groups: List<QuickActionGroup> = List(3) { groupIndex ->
        QuickActionGroup(groupIndex = groupIndex)
    }
)
