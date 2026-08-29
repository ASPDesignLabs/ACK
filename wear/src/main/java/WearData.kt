package com.example.besu.wear

import kotlinx.serialization.Serializable

// --- 1. LEGACY HARDCODED COMMANDS ---
data class WearCommand(
    val label: String,
    val emoji: String,
    val path: String,
    val subCommands: List<WearCommand> = emptyList()
)

object WearVocabulary {
    val motionSet = listOf(
        WearCommand("Name", "😀", "/gesture/name", listOf(WearCommand("Ask", "❓", "/gesture/ask_name"))),
        WearCommand("No", "🚫", "/gesture/no", listOf(WearCommand("Hate", "😠", "/gesture/hate"))),
        WearCommand("Hello", "👋", "/gesture/wave", listOf(WearCommand("Bye", "👋", "/gesture/goodbye"))),
        WearCommand("Stop", "✋", "/gesture/stop", listOf(WearCommand("Wait", "⏳", "/gesture/wait"))),
        WearCommand("Good", "👍", "/gesture/thumbsup", listOf(WearCommand("Bad", "👎", "/gesture/thumbsdown"))),
        WearCommand("Nice", "🤝", "/gesture/nice", listOf(WearCommand("Same", "✨", "/gesture/same")))
    )
}

// --- 2. CONFIGURATION (UI PAGES) ---

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