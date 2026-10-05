// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.data.*
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf


/**
 * A module family (a chip in the HELP menu). Its words are string resources named `help_cat_<constant name in lower case>_title`, `_chip` and `_subtitle`, read through
 * core/HelpMenuText.kt, so adding a constant needs those three strings in every language (HelpMenuTextTest fails otherwise). A name may hold a label placeholder, which `helpText()` fills in (core/PlainLabels.kt).
 */
enum class HelpCategory {
    BASICS_NAVIGATION,
    BASICS_DECKS,
    BASICS_SETTINGS,
    BASICS_PERSONALIZATION,
    BASICS_MANUAL_OVERRIDE,
    USING_DECKS,
    CONTEXTUAL_SYSTEMS,
    FIELD_OPS,
    VOICE_RECORDINGS
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
