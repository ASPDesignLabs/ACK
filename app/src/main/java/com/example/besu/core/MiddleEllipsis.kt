// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.text.BreakIterator
import java.util.Locale

/**
 * Shortens a value that is too long to show whole by cutting its MIDDLE, so both the start and the end stay visible. Cutting the
 * end (an ordinary ellipsis) makes two values that start alike look identical, which is exactly the case for a remembered address or
 * a similar sentence. Plain Kotlin (no `android.*`).
 *
 * The result is never longer than the limit, never cuts an emoji in half, and never separates a letter from its accent: the cuts
 * fall on character (grapheme) boundaries.
 */
object MiddleEllipsis {
    private const val ELLIPSIS = "…"

    /** Below three there is no room for an end on each side of the ellipsis. */
    private const val MIN_LIMIT = 3

    fun shorten(text: String, maxChars: Int): String {
        val limit = maxChars.coerceAtLeast(MIN_LIMIT)
        if (text.length <= limit) return text

        val room = limit - ELLIPSIS.length
        val headTarget = (room + 1) / 2
        val tailTarget = room / 2

        val boundaries = BreakIterator.getCharacterInstance(Locale.ROOT)
        boundaries.setText(text)

        var headEnd = headTarget
        while (headEnd > 0 && !boundaries.isBoundary(headEnd)) headEnd--

        var tailStart = text.length - tailTarget
        while (tailStart < text.length && !boundaries.isBoundary(tailStart)) tailStart++

        return text.substring(0, headEnd) + ELLIPSIS + text.substring(tailStart)
    }
}
