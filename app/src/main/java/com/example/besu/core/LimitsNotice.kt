// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The limits statement (tracker row C4): ACK is not a substitute for professional AAC evaluation or therapy, one person built it and shares it as it is, and a
 * person relying on it should keep another way to communicate. It is shown in two places: a permanent ABOUT section in SETTINGS, and a one-time banner on the
 * Terminal and Settings screens. Plain Kotlin (no `android.*`) so what is said and where it may appear are tested without a phone. The words are string resources
 * (`about_*` in strings.xml, in the chosen language) supplied through a [TextSource].
 *
 * Rules that must stay true:
 *  - **The three sentences are the website's disclaimer, word for word** (index.html), so the app and the website say the same. LimitsNoticeWebsiteTest holds it.
 *  - **It is only a notice.** It never blocks speech, never asks a question, never starts HELP and never navigates. Dismissing the banner only remembers that it
 *    was seen (data/AssistPrefs.kt); the ABOUT section stays.
 *  - **The banner never appears on a deck, Emergency or Type screen**, where it could move a button that is about to be tapped ([BANNER_SCREENS]).
 *  - It makes no claim about what ACK does for anyone. The evaluation found no evidence yet that it helps; nothing here may suggest otherwise.
 */
object LimitsNotice {
    // Resource names, not words.
    const val ABOUT_TITLE = "about_title"
    const val GOT_IT = "about_got_it"
    private const val WHERE = "about_banner_where"

    /** The statement, one sentence per resource, in the order they are read. Joined with a space in code: Android trims a space at the end of a string. */
    val SENTENCES: List<String> = listOf(
        "about_limits_not_a_substitute",
        "about_limits_built_by_one",
        "about_limits_keep_another_way",
    )

    /**
     * The screens (MainActivity's view modes) where the one-time banner may appear: the same two as the backup reminder's banner, and never a deck.
     * MainActivity asks [shouldShowBanner] with its current view mode.
     */
    val BANNER_SCREENS: Set<String> = setOf("TERMINAL", "SETTINGS")

    /** Show the banner only on one of [BANNER_SCREENS] and only until it has been dismissed once (anywhere, ever). */
    fun shouldShowBanner(seen: Boolean, viewMode: String): Boolean = !seen && viewMode in BANNER_SCREENS

    /** The three sentences, for a screen that draws each on its own line. */
    fun sentences(text: TextSource): List<String> = SENTENCES.map { text.get(it) }

    /** The whole statement as one text (a screen reader, a test). */
    fun statement(text: TextSource): String = sentences(text).joinToString(" ")

    /**
     * The banner's last line, telling the person where to read it again. [settingsName] is the SETTINGS button's name as the screen shows it (it follows PLAIN
     * WORDS, so it is handed in, never typed here) and the section's own title is read from the same source, so the sentence points at things that exist.
     */
    fun whereToReadAgain(text: TextSource, settingsName: String): String = text.get(WHERE, settingsName, text.get(ABOUT_TITLE))
}
