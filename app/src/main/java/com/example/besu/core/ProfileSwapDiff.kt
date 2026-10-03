// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What one Matrix slot says under the profile you are on and under the one you are about to change to. Both phrases are the
 * RESOLVED ones (after the fall-back to the DEFAULT profile, and with variables and targets filled in), as the repository's own
 * resolve function returns them: comparing stored keys would call "no phrase of its own, so it falls back" a difference when it is not.
 */
data class SlotPhrases(val path: String, val name: String, val current: String, val target: String)

/** A slot that would say something different, with the phrases exactly as they are (not trimmed). */
data class SlotChange(val path: String, val name: String, val oldPhrase: String, val newPhrase: String)

/**
 * Decides whether changing profile would change what a gesture says, so ACK can warn first. Plain Kotlin (no `android.*`).
 *
 * A person learns which gesture says what by repetition. Each profile can hold a different phrase for the same slot, so a profile
 * change can quietly change what a practised gesture says. This only DECIDES; showing the warning is the screen's job, and the
 * Quick Actions, Emoji, GIF and Emergency decks have no profiles at all, so none of this applies to them.
 */
object ProfileSwapDiff {

    /**
     * The slots whose phrase differs, in the order given. Two phrases that differ only by white space at either end count as the same
     * (they are spoken the same); any other difference, including capitals and punctuation, counts.
     */
    fun changes(slots: List<SlotPhrases>): List<SlotChange> =
        slots.filter { it.current.trim() != it.target.trim() }
            .map { SlotChange(it.path, it.name, it.current, it.target) }

    /** Never interrupt for nothing: no warning if the switch is off or if nothing would change. */
    fun shouldWarn(warningOn: Boolean, changes: List<SlotChange>): Boolean = warningOn && changes.isNotEmpty()
}

/** The words the warning dialog shows. Plain Kotlin so they are tested. */
object ProfileSwapText {
    /** How many changes are listed before "AND N MORE". */
    const val MAX_LISTED = 4

    private const val MAX_PHRASE_CHARS = 48

    fun heading(count: Int, targetProfile: String): String =
        "$count ${if (count == 1) "GESTURE" else "GESTURES"} WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO $targetProfile:"

    /** "GESTURE NAME: old phrase, becomes: new phrase" for the first few, then how many more. */
    fun lines(changes: List<SlotChange>): List<String> {
        val listed = changes.take(MAX_LISTED).map { "${it.name}: ${phrase(it.oldPhrase)}, becomes: ${phrase(it.newPhrase)}" }
        val more = changes.size - MAX_LISTED
        return if (more > 0) listed + "AND $more MORE" else listed
    }

    // A very long phrase is shortened in the middle (so its end shows); a blank one is said to be blank, not shown as nothing.
    private fun phrase(text: String): String = if (text.isBlank()) "(BLANK)" else MiddleEllipsis.shorten(text.trim(), MAX_PHRASE_CHARS)
}

/** The words for the WARN BEFORE PROFILE CHANGES switch in SETTINGS, the dialog's buttons, and the one-time offer. */
object ProfileWarningText {
    fun switchLabel(on: Boolean): String = "WARN BEFORE PROFILE CHANGES: ${if (on) "ON" else "OFF"}"

    const val SWITCH_EXPLANATION =
        "WHEN CHANGING PROFILE WOULD MAKE A MATRIX GESTURE SAY SOMETHING DIFFERENT, ACK SHOWS WHAT WOULD CHANGE AND ASKS FIRST. " +
            "THIS IS ABOUT THE MATRIX DECK ONLY: QUICK ACTIONS, EMERGENCY, EMOJI AND GIF DECKS HAVE NO PROFILES, SO THEIR BUTTONS NEVER MOVE. " +
            "IT ONLY APPLIES TO THE PROFILE MENU IN THE APP. THE HOME-SCREEN WIDGET AND THE WATCH CHANGE PROFILE WITHOUT ASKING."

    const val DIALOG_TITLE = "CHANGE PROFILE?"
    const val STAY = "STAY"
    const val CHANGE = "CHANGE PROFILE"
    const val DONT_SHOW_AGAIN = "DO NOT SHOW THIS WARNING AGAIN"
    const val DONT_SHOW_AGAIN_NOTE = "YOU CAN TURN IT BACK ON IN SETTINGS."

    // For an install that already existed: said once, dismissible, and nothing changes unless it is tapped.
    const val OFFER_TEXT =
        "NEW: ACK CAN WARN YOU BEFORE A PROFILE CHANGE MAKES A GESTURE SAY SOMETHING DIFFERENT. IT IS OFF FOR YOU, AND NOTHING CHANGES UNLESS YOU TURN IT ON."
    const val OFFER_TURN_ON = "TURN ON"
    const val OFFER_NOT_NOW = "NOT NOW"
}
