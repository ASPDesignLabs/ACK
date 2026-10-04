// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The person-chosen switches kept in `ack_assist_prefs` (data/AssistPrefs.kt): what each is when nothing is stored, what a new install
 * is given, and who is offered it. Plain Kotlin (no `android.*`) so the decisions are tested without a phone. Today it holds one switch,
 * WARN BEFORE PROFILE CHANGES; later switches belong here too.
 *
 * Every switch falls back, when nothing is stored, to its safest and least surprising value, and is never turned on or off for an
 * existing person without a tap: a new install is SEEDED with a default, an existing install is OFFERED it once.
 */
object AssistSettings {
    /** The preference file (a test keeps it equal to AssistPrefs's own literal, which the storage scan needs). */
    const val FILE = "ack_assist_prefs"

    const val KEY_WARN_PROFILE_CHANGE = "warn_profile_change"
    const val KEY_WARN_OFFER_DISMISSED = "warn_profile_change_offer_dismissed"

    const val KEY_SPEECH_LANGUAGE = "speech_language"
    const val KEY_PLAIN_WORDS = "plain_words"
    const val KEY_PLAIN_WORDS_OFFER_DISMISSED = "plain_words_offer_dismissed"
    const val KEY_WORD_SUGGESTIONS = "word_suggestions"
    const val KEY_WORD_OFFER_DISMISSED = "word_suggestions_offer_dismissed"

    /** What the warning is when nothing is stored: off, so an install that already existed behaves exactly as before. */
    const val WARN_FALLBACK = false

    /** What a brand-new install (and a phone after DELETE DATA > SETTINGS) is given. */
    const val WARN_FRESH_INSTALL = true

    /**
     * The keys the seed writes, which InstallClassifier ignores so an interrupted seed still reads as fresh. The "offer dismissed"
     * note is not one: only a tap ever writes it.
     */
    val SEED_KEYS: Set<String> = setOf(KEY_WARN_PROFILE_CHANGE, KEY_SPEECH_LANGUAGE)

    /**
     * The one-time offer in SETTINGS: only where no value is stored (the person never chose, and a new install was already seeded) and
     * it was not dismissed. Anyone with a value stored, whether seeded or chosen, is never offered.
     */
    fun shouldOfferWarning(switchStored: Boolean, offerDismissed: Boolean): Boolean = !switchStored && !offerDismissed

    /**
     * What WORD SUGGESTIONS is when nothing is stored, and what a new install is given: off. Unlike the profile warning it is **never seeded**:
     * it learns from what the person types, so it starts only when they turn it on. (A test keeps both keys out of [SEED_KEYS].)
     */
    const val WORD_SUGGESTIONS_FALLBACK = false

    /** The one-time offer: while the switch is off and the offer was never answered. Turning the switch on from SETTINGS counts as an answer. */
    fun shouldOfferWordSuggestions(switchOn: Boolean, offerDismissed: Boolean): Boolean = !switchOn && !offerDismissed

    /**
     * What PLAIN WORDS is when nothing is stored, and what every install is given: off. The developer's decision: it is **never seeded** (a new install
     * included), and one dismissible offer says what it changes and starts with the switch off. (A test keeps both keys out of [SEED_KEYS].)
     */
    const val PLAIN_WORDS_FALLBACK = false

    /** The one-time offer in SETTINGS: while the switch is off and the offer was never answered. Choosing the switch by hand counts as an answer. */
    fun shouldOfferPlainWords(switchOn: Boolean, offerDismissed: Boolean): Boolean = !switchOn && !offerDismissed
}
