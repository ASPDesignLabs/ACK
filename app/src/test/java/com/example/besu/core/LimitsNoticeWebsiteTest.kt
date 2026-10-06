// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The first two sentences of the in-app limits statement are the website's disclaimer, word for word (the app writes in capitals, the page does not, so the
 * match ignores case). If either is edited alone, this fails, so the app and the website cannot quietly say different things about what ACK is.
 * The third sentence (keep another way to communicate) is in the app only for now; it is not checked against the page.
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
    fun theFirstTwoSentencesInTheAppAreTheWebsitesDisclaimerWordForWord() {
        val app = LimitsNotice.sentences(EnglishText).take(2).joinToString(" ")
        assertEquals(websiteDisclaimer().uppercase(), app)
    }

    @Test
    fun theWebsiteDisclaimerStillSaysWhatTheAppSays_soAWordChangedInTheAppFailsHere() {
        val page = websiteDisclaimer()
        assertTrue(page.contains("professional AAC evaluation or speech-language therapy"))
        assertTrue(page.contains("shared as-is"))
    }
}
