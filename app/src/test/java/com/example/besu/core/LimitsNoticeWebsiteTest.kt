// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The three sentences of the in-app limits statement are the website's disclaimer, word for word (the app writes in capitals, the page does not, so the
 * match ignores case). If either side is edited alone, this fails, so the app and the website cannot quietly say different things about what ACK is.
 */
class LimitsNoticeWebsiteTest {

    /** The text of the page's `<p class="disclaimer">`, with its tags removed and its line breaks and runs of spaces collapsed to one space. */
    private fun websiteDisclaimer(): String {
        val page = RepoFiles.read("index.html")
        val matches = Regex("""<p class="disclaimer"[^>]*>(.*?)</p>""", RegexOption.DOT_MATCHES_ALL).findAll(page).toList()
        val limits = matches.map { it.groupValues[1] }.filter { it.contains("Not a substitute", ignoreCase = true) }
        assertEquals("exactly one disclaimer paragraph on the page carries the limits sentence", 1, limits.size)
        return limits.single().replace(Regex("<[^>]+>"), "").replace(Regex("\\s+"), " ").trim()
    }

    @Test
    fun theThreeSentencesInTheAppAreTheWebsitesDisclaimerWordForWord() {
        val app = LimitsNotice.sentences(EnglishText).joinToString(" ")
        assertEquals(websiteDisclaimer().uppercase(), app)
    }

    @Test
    fun theWebsiteDisclaimerStillSaysWhatTheAppSays_soAWordChangedInTheAppFailsHere() {
        val page = websiteDisclaimer()
        assertTrue(page.contains("professional AAC evaluation or speech-language therapy"))
        assertTrue(page.contains("shared as-is"))
        assertTrue(page.contains("Keep another way to communicate available at all times."))
    }
}
