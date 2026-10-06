// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * When a chip's value is too long to show whole, keep BOTH ends and cut the middle, so two values that start alike (two long
 * addresses, two similar sentences) can still be told apart by how they end.
 */
class MiddleEllipsisTest {

    private val dots = "…"

    @Test
    fun aValueThatFits_isUnchanged() {
        assertEquals("Mum", MiddleEllipsis.shorten("Mum", 10))
        assertEquals("", MiddleEllipsis.shorten("", 10))
    }

    @Test
    fun aValueExactlyAtTheLimit_isUnchanged() {
        assertEquals("0123456789", MiddleEllipsis.shorten("0123456789", 10))
    }

    @Test
    fun aValueOneOverTheLimit_keepsBothEndsAndFitsTheLimit() {
        val text = "0123456789A"
        val out = MiddleEllipsis.shorten(text, 10)
        assertTrue(out.length <= 10)
        assertTrue(out.contains(dots))
        assertTrue(out.startsWith("0123"))
        assertTrue(out.endsWith("89A".takeLast(3)))
    }

    @Test
    fun theEndIsKept_soTwoValuesThatStartAlikeCanBeToldApart() {
        val a = "12 Long Street, Some Town, Some County, AB1 2CD"
        val b = "12 Long Street, Some Town, Some County, XY9 8ZW"
        assertNotEquals(MiddleEllipsis.shorten(a, 24), MiddleEllipsis.shorten(b, 24))
        assertTrue(MiddleEllipsis.shorten(a, 24).endsWith("AB1 2CD"))
        assertTrue(MiddleEllipsis.shorten(b, 24).endsWith("XY9 8ZW"))
    }

    @Test
    fun theResultNeverExceedsTheLimit_atAnyLength() {
        for (max in 3..40) for (len in 0..120) {
            val out = MiddleEllipsis.shorten("x".repeat(len), max)
            assertTrue("len=$len max=$max -> ${out.length}", out.length <= maxOf(max, 3))
        }
    }

    @Test
    fun anEmojiIsNeverSplit() {
        val text = "😀".repeat(70) // 140 chars
        for (max in 5..30) {
            val out = MiddleEllipsis.shorten(text, max)
            assertFalse("lone surrogate at max=$max", hasLoneSurrogate(out))
            assertTrue(out.length <= max)
        }
    }

    @Test
    fun aLetterIsNeverSeparatedFromItsAccent() {
        val unit = "é" // e + combining acute
        val text = unit.repeat(60)
        for (max in 5..30) {
            val out = MiddleEllipsis.shorten(text, max)
            val kept = out.replace(dots, "")
            assertEquals("max=$max: only whole letter+accent pairs are kept", kept, unit.repeat(kept.length / 2))
        }
    }

    @Test
    fun aVeryLowLimit_isRaisedToThree_soThereIsAlwaysAnEndOnEachSide() {
        val out = MiddleEllipsis.shorten("abcdefghij", 0)
        assertEquals(3, out.length)
        assertEquals("a${dots}j", out)
    }

    @Test
    fun spacesAreNotTrimmed() {
        val out = MiddleEllipsis.shorten("   padded value   ", 9)
        assertTrue(out.startsWith("   "))
        assertTrue(out.endsWith("   "))
    }

    private fun hasLoneSurrogate(s: String): Boolean {
        var i = 0
        while (i < s.length) {
            val c = s[i]
            if (c.isHighSurrogate()) {
                if (i + 1 >= s.length || !s[i + 1].isLowSurrogate()) return true
                i += 2
                continue
            }
            if (c.isLowSurrogate()) return true
            i++
        }
        return false
    }
}
