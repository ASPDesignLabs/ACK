// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The five translations (Spanish, Portuguese, Hindi, Arabic, Afrikaans) are drafts written without a native speaker, so the tests cannot say they are
 * right. They say they are complete, safe to use and honest about being drafts: the same strings as English and nothing else, the same format
 * placeholders, every standard and everyday name present and different, no two buttons sharing an everyday name, the house style of capitals where the
 * script has capitals, Android's escaping, and a draft notice at the top of every file.
 */
class TranslationsTest {

    private val english = StringsXml.read(StringsXml.default)
    private val englishText: Map<String, String> = english.associate { it.name to it.text }
    private val translatableNames: Set<String> = english.filter { it.translatable }.map { it.name }.toSet()
    private val files: Map<String, File> = StringsXml.translations()
    private val texts: Map<String, Map<String, String>> = files.mapValues { StringsXml.map(it.value) }

    private val latin = setOf("es", "pt", "af")

    // ---- which languages ---------------------------------------------------------------------------------------------------------

    @Test
    fun theTranslatedLanguagesAreExactlyTheFiveTheSettingOffers() {
        assertEquals(InterfaceLanguagePolicy.translatedTags, files.keys)
    }

    // ---- complete, and nothing else ----------------------------------------------------------------------------------------------

    @Test
    fun everyTranslationHasEveryTranslatableStringAndNothingElse() {
        for ((tag, map) in texts) {
            val missing = translatableNames - map.keys
            val extra = map.keys - translatableNames
            assertTrue("$tag is missing: $missing", missing.isEmpty())
            assertTrue("$tag has strings English does not (or that are not translatable): $extra", extra.isEmpty())
        }
    }

    @Test
    fun theFormatPlaceholdersMatchEnglishInEveryString() {
        for ((tag, map) in texts) for ((name, text) in map) {
            assertEquals("$tag/$name", StringsXml.placeholders(englishText.getValue(name)).sorted(), StringsXml.placeholders(text).sorted())
        }
    }

    @Test
    fun noTranslationIsBlank() {
        for ((tag, map) in texts) for ((name, text) in map) assertTrue("$tag/$name is blank", text.isNotBlank())
    }

    // ---- not just English again ---------------------------------------------------------------------------------------------------

    /** Texts that are the same as English on purpose: acronyms and loan words every one of these languages uses as they are. */
    private val sameAsEnglishAllowed = setOf(
        "label_deck_type_emoji", "label_deck_type_emoji_plain",
        "label_deck_type_gif", "label_deck_type_gif_plain",
        "label_bitcrush", "label_pose", "label_variable_tag", "label_add_var", "label_terminal",
        "label_deck_type_emergency_plain", "label_deck_type_emergency",
        "label_nav_type", "label_nav_type_plain",
        "label_data_port_plain", // "MY DATA" is how Afrikaans says it too
        "label_pose_connect_plain", "label_variable", // real words in Spanish and Portuguese that are spelled as in English (SOCIAL, VARIABLE)
    )

    @Test
    fun aTextEqualToTheEnglishOneIsOnTheShortListOfAcronymsAndLoanWords() {
        val unexpected = texts.flatMap { (tag, map) ->
            map.filter { (name, text) -> text == englishText.getValue(name) && text.any { it.isLetter() } }.keys
                .filter { it !in sameAsEnglishAllowed }.map { "$tag/$it" }
        }
        assertTrue("still English: $unexpected", unexpected.isEmpty())
    }

    // ---- the label table holds in every language ---------------------------------------------------------------------------------------

    private fun standard(tag: String, key: LabelKey) = texts.getValue(tag).getValue(key.resourceName(plain = false))
    private fun plain(tag: String, key: LabelKey) = texts.getValue(tag).getValue(key.resourceName(plain = true))

    private val alreadyPlain = setOf(LabelKey.NAV_TYPE, LabelKey.DECK_TYPE_EMERGENCY, LabelKey.DECK_TYPE_EMOJI)

    @Test
    fun aPlainNameDiffersFromTheStandardOne_exceptTheThreeThatAreAlreadyPlain() {
        for (tag in texts.keys) {
            val same = LabelKey.values().filter { standard(tag, it).equals(plain(tag, it), ignoreCase = true) }.toSet()
            assertEquals("$tag: plain equal to standard", alreadyPlain, same)
        }
    }

    /** The four places where one thing is named from two screens, exactly as in English (PlainLabelsTest). */
    private val samePlaceNames: Set<Set<LabelKey>> = setOf(
        setOf(LabelKey.NAV_LOGS, LabelKey.TERMINAL_LOG),
        setOf(LabelKey.NAV_TARGETS, LabelKey.TARGET_COMPUTER),
        setOf(LabelKey.NAV_ZONES, LabelKey.GEO_PROTOCOL),
        setOf(LabelKey.NAV_AUDIO, LabelKey.AUDIO_ARCHITECT),
    )

    @Test
    fun twoDifferentButtonsNeverShareAnEverydayName_exceptTheFourSamePlaceNames() {
        for (tag in texts.keys) {
            val shared = LabelKey.values().groupBy { plain(tag, it).uppercase() }.values.filter { it.size > 1 }.map { it.toSet() }.toSet()
            assertEquals("$tag: everyday names shared between different buttons", samePlaceNames, shared)
        }
    }

    // ---- house style and scripts ---------------------------------------------------------------------------------------------------

    @Test
    fun theLatinLanguagesKeepTheAppsAllCapitalsStyle_exceptTheScreenReaderNamesAndStoredSlotNames() {
        for (tag in latin) for ((name, text) in texts.getValue(tag)) {
            if (name == "accessibility_service_description") continue
            // The standard names of the tabs are read by a screen reader (mixed case) and the standard slot names are stored data's names (mixed case).
            if (name.startsWith("label_nav_") && !name.endsWith("_plain")) continue
            if (name.startsWith("label_twist_") && !name.endsWith("_plain") && !name.startsWith("label_twist_sens")) continue
            val words = text.replace(Regex("""%(?:\d+\$)?[sdf]"""), "")
            assertEquals("$tag/$name", words.uppercase(), words)
        }
    }

    @Test
    fun hindiAndArabicTextIsInItsOwnScript_exceptTheShortListOfPlainSymbolsAndAcronyms() {
        val devanagari = Regex("[\\u0900-\\u097F]")
        val arabic = Regex("[\\u0600-\\u06FF]")
        val latinOnlyAllowed = setOf("label_add_var_plain_never")
        for ((tag, script) in listOf("hi" to devanagari, "ar" to arabic)) for ((name, text) in texts.getValue(tag)) {
            if (name in latinOnlyAllowed) continue
            assertTrue("$tag/$name has no ${if (tag == "hi") "Devanagari" else "Arabic"} letters: $text", script.containsMatchIn(text))
        }
    }

    // ---- escaping and the draft notice ---------------------------------------------------------------------------------------------------

    @Test
    fun everyApostropheAndQuoteIsEscapedTheWayAndroidNeedsIt() {
        for ((tag, file) in files) {
            val raw = file.readText(Charsets.UTF_8)
            for (m in Regex("""<string name="([^"]+)"[^>]*>(.*?)</string>""", RegexOption.DOT_MATCHES_ALL).findAll(raw)) {
                val body = m.groupValues[2]
                assertFalse("$tag/${m.groupValues[1]} has an unescaped apostrophe", Regex("""(?<!\\)'""").containsMatchIn(body))
                assertFalse("$tag/${m.groupValues[1]} has an unescaped quote", Regex("""(?<!\\)"""").containsMatchIn(body))
            }
        }
    }

    @Test
    fun everyFileStartsWithTheDraftNotice_soNobodyMistakesItForReviewedText() {
        for ((tag, file) in files) {
            val head = file.readText(Charsets.UTF_8).take(900)
            assertTrue("$tag: no DRAFT TRANSLATION notice", head.contains("DRAFT TRANSLATION"))
            assertTrue("$tag: the notice must say it was not reviewed", head.contains("NOT yet reviewed by a native speaker"))
            assertTrue("$tag: the notice must point to the translation guide", head.contains("docs/TRANSLATIONS.md"))
        }
    }

    @Test
    fun theInterfaceLanguageExplanationSaysEveryLanguageButEnglishIsADraft_inEveryLanguage() {
        // The words differ by language; what must hold in all of them is that the sentence is there and is not the English one.
        for ((tag, map) in texts) {
            val text = map.getValue("interface_language_explanation")
            assertTrue("$tag: too short to carry the draft warning", text.length > 120)
            assertTrue(tag, text != englishText.getValue("interface_language_explanation"))
        }
    }
}
