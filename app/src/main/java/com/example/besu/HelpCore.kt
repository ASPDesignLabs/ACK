package com.example.besu

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf


enum class HelpCategory(
    val title: String,
    val subtitle: String
) {
    BASICS_NAVIGATION(
        title = "BASICS // NAVIGATION",
        subtitle = "DECKS, PROFILES, CONTEXT, AND PROMPTS"
    ),
    BASICS_DECKS(
        title = "BASICS // DECK MANAGEMENT",
        subtitle = "CREATE, ORGANIZE, RECOLOR, AND REMOVE DECKS"
    ),
    BASICS_SETTINGS(
        title = "BASICS // SETTINGS",
        subtitle = "PROTOCOL, WATCH, SENSORS, SHORTCUTS, AND DATA"
    ),
    BASICS_PERSONALIZATION(
        title = "BASICS // PERSONALIZATION",
        subtitle = "AUDIO ARCHITECT AND OUTPUT CUSTOMIZATION"
    ),
    BASICS_MANUAL_OVERRIDE(
        title = "BASICS // MANUAL OVERRIDE",
        subtitle = "MEMORY BANKS AND DIRECT TEXT INPUT"
    ),
    USING_DECKS(
        title = "USING DECKS",
        subtitle = "DECK-SPECIFIC WORKFLOWS AND CONTROLS"
    ),
    CONTEXTUAL_SYSTEMS(
        title = "CONTEXTUAL SYSTEMS",
        subtitle = "TARGET COMPUTER, GEO-PROTOCOL, AND LOGS"
    ),
    FIELD_OPS(
        title = "FIELD OPS // GESTURE TRAINING",
        subtitle = "ARM, POSE, MODIFY, AND FIRE FROM THE WATCH"
    )
}

enum class HelpDestination(
    val viewMode: String
) {
    TERMINAL("TERMINAL"),
    MATRIX("MATRIX"),
    SETTINGS("SETTINGS"),
    TYPE("TYPE"),
    AUDIO("AUDIO"),
    TARGETS("TARGETS"),
    GEO("GEO")
}

enum class HelpCoachPlacement {
    TOP,
    BOTTOM
}

sealed interface HelpAction {


    data object Read : HelpAction

    data class Interact(
        val targetTag: String
    ) : HelpAction

    data class CommitText(
        val targetTag: String
    ) : HelpAction

    data class CommitFile(
        val targetTag: String
    ) : HelpAction

    data class OverlayCleared(
        val targetTag: String
    ) : HelpAction

    data class WatchEvent(
        val eventType: String
    ) : HelpAction

    data class DeckSelected(
        val targetTag: String
    ) : HelpAction

    data class ProfileSelected(
        val targetTag: String
    ) : HelpAction

    data class KeyboardDismissed(
        val targetTag: String
    ) : HelpAction
}

sealed interface HelpEvent {




    data class Interacted(
        val targetTag: String
    ) : HelpEvent

    data class TextCommitted(
        val targetTag: String
    ) : HelpEvent

    data class FileCommitted(
        val targetTag: String
    ) : HelpEvent

    data class OverlayWasCleared(
        val targetTag: String
    ) : HelpEvent

    data class WatchInput(
        val eventType: String
    ) : HelpEvent

    data class DeckWasSelected(
        val targetTag: String
    ) : HelpEvent

    data class ProfileWasSelected(
        val targetTag: String
    ) : HelpEvent

    data class KeyboardWasDismissed(
        val targetTag: String
    ) : HelpEvent
}

data class HelpStep(
    val id: String,
    val title: String,
    val body: String,
    val action: HelpAction = HelpAction.Read,
    val targetTag: String? = null,
    val destination: HelpDestination? = null,
    val coachPlacement: HelpCoachPlacement = HelpCoachPlacement.BOTTOM
)

data class HelpModule(
    val id: String,
    val category: HelpCategory,
    val title: String,
    val summary: String,
    val steps: List<HelpStep>,
    val destination: HelpDestination? = null,
    val requiresMatrixDeck: Boolean = false
)

data class HelpContext(
    val viewMode: String,
    val deckId: String,
    val deckType: DeckType,
    val profile: String
)



val LocalHelpManager = staticCompositionLocalOf<HelpManager?> {
    null
}
