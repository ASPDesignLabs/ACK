// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The printable page (docs/PARTNER_CARD.md) says exactly what ACK says, in every language. If one is edited alone, this fails. */
class PartnerCardPrintableTest {

    private val page = RepoFiles.read("docs/PARTNER_CARD.md")
    private val quoted: List<String> = page.lines().filter { it.startsWith("> ") }.map { it.removePrefix("> ").trimEnd() }
    private val sets: Map<String, List<String>> =
        (listOf("en") + StringsXml.translations().keys).associateWith { tag ->
            val map = if (tag == "en") StringsXml.map(StringsXml.default) else StringsXml.map(StringsXml.translations().getValue(tag))
            PartnerCard.SENTENCES.map { map.getValue(it) }
        }

    @Test
    fun thePageHoldsEveryLanguagesFiveSentencesExactly_inOrder() {
        assertEquals("six languages of five sentences, and nothing else quoted", 30, quoted.size)
        for ((tag, sentences) in sets) {
            val at = quoted.indexOf(sentences.first())
            assertTrue("$tag: its first sentence is on the page", at >= 0)
            assertEquals("$tag: the five sentences are on the page together, in order, and exactly as ACK says them", sentences, quoted.subList(at, at + 5))
        }
    }

    @Test
    fun thePageSaysItIsADraftAndNamesTheButtonAsTheAppDoes() {
        assertTrue(page.contains("DRAFT"))
        assertTrue("it says what the speech-bubble icon asks", page.contains(StringsXml.map(StringsXml.default).getValue(PartnerCard.ASK_TITLE)))
        assertTrue("it names HELP as the header button reads", page.contains("**HELP**"))
        assertTrue("it names PLAY IT as the button reads", page.contains("**PLAY IT**"))
    }
}
