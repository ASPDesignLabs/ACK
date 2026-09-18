package com.example.besu.wear

import kotlinx.serialization.Serializable

// --- CONFIGURATION DATA (KEPT) ---

@Serializable
data class WatchConfig(
    val topItems: List<WatchSlot> = emptyList(),
    val pages: List<WatchPage> = emptyList()
)

@Serializable
data class WatchPage(
    val id: String,
    val title: String,
    val slots: List<WatchSlot>
)

@Serializable
data class WatchSlot(
    val label: String,
    val emoji: String,
    val path: String,
    val type: String = "COMMAND"
)

// --- DELETED: TrainingMode, MotionProfileType, TrainingRequest, MotionSample, etc. ---