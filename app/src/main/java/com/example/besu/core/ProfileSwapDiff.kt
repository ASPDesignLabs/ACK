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

/**
 * The words the warning dialog shows, read through a [TextSource] so they are in the chosen language. Plain Kotlin so they are tested in every language.
 * A gesture's name and a profile's name are shown as given (the caller passes a gesture's name already worded like the Matrix screen words it); the phrases are the person's own.
 */
object ProfileSwapText {
    /** How many changes are listed before "AND N MORE". */
    const val MAX_LISTED = 4

    private const val MAX_PHRASE_CHARS = 48

    /** "2 GESTURES WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK:", with the gesture count in the language's plural form. */
    fun heading(text: TextSource, count: Int, targetProfile: String): String = text.count("profile_swap_heading", count, targetProfile)

    /**
     * "GESTURE NAME: old phrase, becomes: new phrase" for the first few, then how many more. [names] are the gestures' display names in the same order as [changes]
     * (a name that is missing falls back to the stored one), so the dialog can name a gesture the way the Matrix screen does.
     */
    fun lines(text: TextSource, changes: List<SlotChange>, names: List<String> = emptyList()): List<String> {
        val listed = changes.take(MAX_LISTED).mapIndexed { i, change ->
            text.get("profile_swap_line", names.getOrNull(i) ?: change.name, phrase(text, change.oldPhrase), phrase(text, change.newPhrase))
        }
        val more = changes.size - MAX_LISTED
        return if (more > 0) listed + text.get("profile_swap_more", more) else listed
    }

    // A very long phrase is shortened in the middle (so its end shows); a blank one is said to be blank, not shown as nothing.
    private fun phrase(text: TextSource, phrase: String): String = if (phrase.isBlank()) text.get("profile_swap_blank") else MiddleEllipsis.shorten(phrase.trim(), MAX_PHRASE_CHARS)
}

/** The words for the WARN BEFORE PROFILE CHANGES switch in SETTINGS: its label (ON or OFF said in words) and its three-sentence explanation. The dialog's and the offer's words are plain strings the screens read. */
object ProfileWarningText {
    fun switchLabel(text: TextSource, on: Boolean): String = text.get("profile_warn_switch", text.get(if (on) "common_on" else "common_off"))

    private val explanation = listOf("profile_warn_explain_1", "profile_warn_explain_2", "profile_warn_explain_3")

    /** The three sentences, joined with one space in code (a string resource's own trailing space is trimmed by Android). */
    fun switchExplanation(text: TextSource): String = explanation.joinToString(" ") { text.get(it) }
}
