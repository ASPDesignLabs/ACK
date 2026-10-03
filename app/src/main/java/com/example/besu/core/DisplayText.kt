// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

// A message of more than this many words is cut when full text is off (the legacy rule).
private const val LEGACY_WORD_LIMIT = 5

// ...to the first this many words, after an ALERT: line.
private const val LEGACY_WORDS_SHOWN = 3

/**
 * What the full-screen display shows for a message. Plain Kotlin (no `android.*`) so it is tested without a phone; the
 * Android side (output/VisualPromptLogic.kt) is a thin wrapper that passes the active preset's bypassTruncation as [fullText].
 *
 * The rules, in order:
 *  1. a visual override (a shorthand set on a Matrix node) wins, uppercased;
 *  2. then a target name, uppercased;
 *  3. then, if [fullText] is on, the whole phrase, uppercased;
 *  4. otherwise the legacy rule: a phrase of more than 5 words becomes "ALERT:" and a line break, then its first 3 words
 *     and "...". A phrase of 5 words or fewer is shown as it is, uppercased.
 *
 * Rule 4 is kept only so an install made before full text became the default behaves as it did. With it, the screen can show
 * less than was spoken. Capitalisation (everything uppercased) is deliberately unchanged here.
 */
fun resolveDisplayText(
    rawPhrase: String,
    targetName: String?,
    matrixVisualOverride: String?,
    fullText: Boolean
): String {
    // RULE 1: Specific shorthand visual override (e.g. Work/Custom mapping)
    if (!matrixVisualOverride.isNullOrBlank()) {
        return matrixVisualOverride.uppercase()
    }

    // RULE 2: Target Ping overrides phrase
    if (!targetName.isNullOrBlank()) {
        return targetName.uppercase()
    }

    // RULE 3: Full text. Show it all; the display shrinks it to fit.
    if (fullText) {
        return rawPhrase.uppercase()
    }

    // RULE 4: Legacy heuristic (cut if more than LEGACY_WORD_LIMIT words)
    val words = rawPhrase.trim().split("\\s+".toRegex())
    return if (words.size <= LEGACY_WORD_LIMIT) {
        rawPhrase.uppercase()
    } else {
        "ALERT:\n${words.take(LEGACY_WORDS_SHOWN).joinToString(" ").uppercase()}..."
    }
}
