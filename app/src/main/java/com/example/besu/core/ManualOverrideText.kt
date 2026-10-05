// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the legacy Manual Override screen (TYPE behind Terminal's `/m`, with its MEMORY BANKS popup) and the BUILDER deck's tactical guide say that is decided, not just drawn.
 * Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`manual_*`, in the chosen language) read through a [TextSource].
 *
 * **Deleting a saved phrase asks in two parts, and both are always said.** The question names the phrase exactly as it was saved (the person's own words, never changed); the warning says it
 * cannot be undone and suggests a backup first. They are two strings joined by one space here, so a test can check that every language says both, and a resource's trailing space never has to be relied on.
 */
object ManualOverrideText {
    /** The memory banks popup's message when nothing is saved yet. [encodeWord] is the ENCODE button's own word, so the sentence names the button the screen shows. */
    fun emptyBanks(text: TextSource, encodeWord: String): String = text.get("manual_banks_empty", encodeWord)

    /** The question and the warning of the delete confirmation, joined by one space. [phrase] is shown exactly as saved. */
    fun deleteQuestion(text: TextSource, phrase: String): String =
        listOf(text.get("manual_delete_question", phrase), text.get("manual_delete_warning")).joinToString(" ")

    /**
     * The tactical guide's title and body for a pose. [poseWord] is the POSE label (it follows PLAIN WORDS). The pose names are saved logic (`IDENTITY`, `DEFEND`, `CONNECT`) and never change;
     * any other name reads UNKNOWN / No data available, as it always did.
     */
    fun guide(text: TextSource, poseWord: String, category: String): Pair<String, String> = when (category) {
        "IDENTITY" -> text.get("manual_guide_identity_title", poseWord) to text.get("manual_guide_identity_body")
        "DEFEND" -> text.get("manual_guide_defend_title", poseWord) to text.get("manual_guide_defend_body")
        "CONNECT" -> text.get("manual_guide_connect_title", poseWord) to text.get("manual_guide_connect_body")
        else -> text.get("manual_guide_unknown_title") to text.get("manual_guide_unknown_body")
    }

    /** The line above the guide's body: "// TACTICAL GUIDE: POSE: ARM RAISED UP". */
    fun guideHeader(text: TextSource, title: String): String = text.get("manual_guide_header", title)
}
