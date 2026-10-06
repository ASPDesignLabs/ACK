// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The Terminal's `/info` patch notes: which string resources make up the rundown, in order, and how they are laid out and paced. Plain Kotlin (no `android.*`) so it is tested without a phone.
 *
 * **One string per bullet or heading** (`info_*`), not one string for the whole list. In English a bullet is its old hard-wrapped lines joined by a line break, so `/info` reveals exactly the lines it always did
 * ([lines]); in every other language a bullet is one line written as it reads, so a translation never has to keep the English line breaks. A note with no translation in a language (a release that has just been
 * written) is shown in English by Android's own per-string fallback, which is why `TranslationsTest` does not demand the `info_*` family in every language.
 *
 * **To add a note for a release:** add its English string to `values/strings.xml`, add its name to [ENTRIES] where it should appear, and (optionally, later) its translations. `PatchNotesTest` fails if a name
 * in [ENTRIES] has no English string or an `info_*` string is not listed here. Keep CHANGELOG.md in step, as before.
 *
 * A continuation line is indented by [CONTINUATION_INDENT] **in code**, because Android collapses runs of spaces in a resource: the strings hold no leading spaces.
 */
object PatchNotes {
    /** The indent the second and later lines of a bullet always had. */
    const val CONTINUATION_INDENT = "  "

    /** A line of this many characters or fewer is shown for [STEP_MILLIS]; a longer one for another step per this many characters, so a translated bullet (one long line) gets time to be read. 71 is the longest English line. */
    const val PACE_CHARS = 71

    /** How long the reveal waits after a line of up to [PACE_CHARS] characters (it always waited this long). */
    const val STEP_MILLIS = 2000L

    /** The string resources of the rundown, in the order they are shown. */
    val ENTRIES: List<String> = listOf(
        "info_nr_title",
        "info_nr_privacy_head",
        "info_nr_privacy_1",
        "info_nr_privacy_2",
        "info_nr_privacy_3",
        "info_nr_privacy_4",
        "info_nr_privacy_5",
        "info_nr_privacy_6",
        "info_nr_privacy_7",
        "info_nr_privacy_8",
        "info_nr_starter_head",
        "info_nr_starter_1",
        "info_nr_starter_2",
        "info_nr_starter_3",
        "info_nr_typing_head",
        "info_nr_typing_1",
        "info_nr_typing_2",
        "info_nr_typing_3",
        "info_nr_typing_4",
        "info_nr_profiles_head",
        "info_nr_profiles_1",
        "info_nr_voices_head",
        "info_nr_voices_1",
        "info_nr_voices_2",
        "info_nr_voices_3",
        "info_nr_words_head",
        "info_nr_words_1",
        "info_nr_words_2",
        "info_nr_words_3",
        "info_nr_plain_head",
        "info_nr_plain_1",
        "info_nr_plain_2",
        "info_nr_plain_3",
        "info_nr_language_head",
        "info_nr_language_1",
        "info_nr_language_terminal",
        "info_nr_language_2",
        "info_nr_fixes_head",
        "info_nr_fixes_1",
        "info_b8_title",
        "info_b8_voice_head",
        "info_b8_voice_1",
        "info_b8_voice_2",
        "info_b8_voice_3",
        "info_b8_voice_4",
        "info_b8_voice_5",
        "info_b8_voice_6",
        "info_b8_train_head",
        "info_b8_train_1",
        "info_b8_train_2",
        "info_b8_train_3",
        "info_b8_train_4",
        "info_b8_train_5",
        "info_b8_train_6",
        "info_b8_train_7",
        "info_b8_train_8",
        "info_b8_train_9",
        "info_b8_train_10",
        "info_b8_train_11",
        "info_b8_train_12",
        "info_b8_composer_head",
        "info_b8_composer_1",
        "info_b8_composer_2",
        "info_b8_composer_3",
        "info_b8_composer_4",
        "info_b8_composer_5",
        "info_b8_composer_6",
        "info_b8_composer_7",
        "info_b8_composer_8",
        "info_b8_gif_head",
        "info_b8_gif_1",
        "info_b8_target_head",
        "info_b8_target_1",
        "info_b8_target_2",
        "info_b8_privacy_head",
        "info_b8_privacy_1",
        "info_b8_privacy_2",
        "info_b8_privacy_3",
        "info_b8_tools_head",
        "info_b8_tools_1",
        "info_b8_tools_2",
        "info_b8_tools_3",
        "info_b8_tools_4",
        "info_b8_fixes_head",
        "info_b8_fixes_1",
        "info_end",
    )

    /** Every line the reveal shows, in order: each entry's lines (split at the line breaks the English holds), the second and later lines indented. */
    fun lines(text: TextSource): List<String> =
        ENTRIES.flatMap { name -> text.get(name).split("\n").mapIndexed { i, line -> if (i == 0) line else CONTINUATION_INDENT + line } }

    /** How long to wait before the next line: [STEP_MILLIS] per started [PACE_CHARS] characters, at least one step. */
    fun pauseMillis(line: String): Long = STEP_MILLIS * maxOf(1, (line.length + PACE_CHARS - 1) / PACE_CHARS)
}
