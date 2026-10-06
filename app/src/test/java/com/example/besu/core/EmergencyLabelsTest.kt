// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.core.EmergencyLabels.CardLabel
import com.example.besu.core.EmergencyLabels.Overrides
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EmergencyLabelsTest {

    private val languages = listOf("es", "pt", "af", "hi", "ar")
    private fun overrides(
        persist: Boolean = false, hold: Boolean = false, speaker: Boolean = false, boost: Boolean = false, tone: Int = 0, confirm: Boolean = false,
    ) = Overrides(persist, hold, speaker, boost, tone, confirm)

    // ---- the line that lists the overrides in force ---------------------------------------------------------------------------------------

    @Test
    fun noOverridesSaysStandard_andIsDrawnQuietly() {
        assertEquals("OVERRIDES: STANDARD", EmergencyLabels.overridesLine(EnglishText, overrides()))
        assertTrue(overrides().isStandard)
    }

    @Test
    fun eachOverrideThatIsOnIsListedInAFixedOrder_withTheOldWords() {
        assertEquals("OVERRIDES: PERSIST", EmergencyLabels.overridesLine(EnglishText, overrides(persist = true)))
        assertEquals("OVERRIDES: HOLD CLEAR", EmergencyLabels.overridesLine(EnglishText, overrides(hold = true)))
        assertEquals("OVERRIDES: SPEAKER", EmergencyLabels.overridesLine(EnglishText, overrides(speaker = true)))
        assertEquals("OVERRIDES: BOOST", EmergencyLabels.overridesLine(EnglishText, overrides(boost = true)))
        assertEquals("OVERRIDES: TONE_1", EmergencyLabels.overridesLine(EnglishText, overrides(tone = 1)))
        assertEquals("OVERRIDES: TONE_2", EmergencyLabels.overridesLine(EnglishText, overrides(tone = 2)))
        assertEquals("OVERRIDES: TONE_3", EmergencyLabels.overridesLine(EnglishText, overrides(tone = 3)))
        assertEquals("OVERRIDES: CONFIRM", EmergencyLabels.overridesLine(EnglishText, overrides(confirm = true)))
        assertEquals(
            "OVERRIDES: PERSIST // HOLD CLEAR // SPEAKER // BOOST // TONE_2 // CONFIRM",
            EmergencyLabels.overridesLine(EnglishText, overrides(true, true, true, true, 2, true)),
        )
        for (o in listOf(overrides(persist = true), overrides(tone = 3), overrides(confirm = true))) assertFalse(o.isStandard)
    }

    @Test
    fun aToneOutsideOneToThreeIsNotListed() {
        assertEquals("OVERRIDES: STANDARD", EmergencyLabels.overridesLine(EnglishText, overrides(tone = 0)))
        assertEquals("OVERRIDES: STANDARD", EmergencyLabels.overridesLine(EnglishText, overrides(tone = 4)))
        assertEquals("OVERRIDES: STANDARD", EmergencyLabels.overridesLine(EnglishText, overrides(tone = -1)))
        assertTrue(overrides(tone = 4).isStandard)
    }

    @Test
    fun theLineIsInEveryLanguage_andKeepsTheSeparatorBetweenWhatIsOn() {
        for (tag in languages) {
            val text = FileText(tag)
            val standard = EmergencyLabels.overridesLine(text, overrides())
            assertTrue("$tag: $standard", standard.isNotBlank() && standard != EmergencyLabels.overridesLine(EnglishText, overrides()))
            val all = EmergencyLabels.overridesLine(text, overrides(true, true, true, true, 3, true))
            assertEquals("$tag: six on, five separators", 5, Regex(Regex.escape(EmergencyLabels.SEPARATOR)).findAll(all).count())
        }
    }

    // ---- the hint ---------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theHintKeepsItsDoubleSpacedSeparator() {
        assertEquals("TAP: EXECUTE  //  HOLD: CONFIGURE", EmergencyLabels.hint(EnglishText))
        for (tag in languages) assertTrue(tag, EmergencyLabels.hint(FileText(tag)).contains("  //  "))
    }

    // ---- a button's name: shown in the language, never rewritten when saved ---------------------------------------------------------

    @Test
    fun aButtonStillNamedByItsDefaultIsShownInTheChosenLanguage() {
        for (index in 0..3) {
            assertEquals("EMERGENCY ${index + 1}", EmergencyLabels.shownLabel(EnglishText, EmergencyLabels.storedDefaultLabel(index), index))
        }
        assertEquals("EMERGENCIA 3", EmergencyLabels.shownLabel(FileText("es"), "EMERGENCY 3", 2))
        assertEquals("EMERGÊNCIA 1", EmergencyLabels.shownLabel(FileText("pt"), "EMERGENCY 1", 0))
        assertEquals("NOODGEVAL 4", EmergencyLabels.shownLabel(FileText("af"), "EMERGENCY 4", 3))
    }

    @Test
    fun aNameThePersonTypedIsShownExactlyAsTyped_inEveryLanguage() {
        for (text in listOf<TextSource>(EnglishText) + languages.map { FileText(it) }) {
            assertEquals("MUM", EmergencyLabels.shownLabel(text, "MUM", 0))
            assertEquals("emergency 1", EmergencyLabels.shownLabel(text, "emergency 1", 0))
            // The default of ANOTHER button is just text on this one: it is not translated.
            assertEquals("EMERGENCY 2", EmergencyLabels.shownLabel(text, "EMERGENCY 2", 0))
            assertEquals("", EmergencyLabels.shownLabel(text, "", 0))
        }
    }

    @Test
    fun savingFromTheEditorKeepsWhatWasStoredUnlessTheNameWasChanged() {
        // Untouched: the stored default stays the stored default (not the translated words).
        assertEquals("EMERGENCY 1", EmergencyLabels.labelToSave(typed = "EMERGENCIA 1", shownAtStart = "EMERGENCIA 1", storedAtStart = "EMERGENCY 1"))
        // Untouched custom name.
        assertEquals("MUM", EmergencyLabels.labelToSave("MUM", "MUM", "MUM"))
        // Changed: exactly what was typed, even if it is the default's translated words or empty.
        assertEquals("DOCTOR", EmergencyLabels.labelToSave("DOCTOR", "EMERGENCIA 1", "EMERGENCY 1"))
        assertEquals("", EmergencyLabels.labelToSave("", "EMERGENCIA 1", "EMERGENCY 1"))
        assertEquals("EMERGENCIA 2", EmergencyLabels.labelToSave("EMERGENCIA 2", "EMERGENCIA 1", "EMERGENCY 1"))
    }

    @Test
    fun theStoredDefaultIsTheOneEmergencyPromptSlotIsCreatedWith() {
        val source = RepoFiles.read("app/src/main/java/com/example/besu/decks/EmergencyDeck.kt")
        assertTrue(source.contains("val label: String = \"EMERGENCY \${slotIndex + 1}\""))
        for (i in 0..3) assertEquals("EMERGENCY ${i + 1}", EmergencyLabels.storedDefaultLabel(i))
    }

    // ---- the info card, read by someone else ---------------------------------------------------------------------------------------

    @Test
    fun inEnglishEachCardLabelIsOneLabel() {
        for (label in CardLabel.values()) assertEquals(label.english, EmergencyLabels.cardLabel(EnglishText, label))
    }

    @Test
    fun inEveryOtherLanguageEachCardLabelIsTheLanguageThenEnglish() {
        for (tag in languages) {
            val text = FileText(tag)
            for (label in CardLabel.values()) {
                val shown = EmergencyLabels.cardLabel(text, label)
                val local = text.get(label.resource)
                assertEquals("$tag/$label", "$local // ${label.english}", shown)
                assertTrue("$tag/$label ends with the English a responder can read", shown.endsWith(" // ${label.english}"))
                assertTrue("$tag/$label has a real local word", local.isNotBlank() && !local.equals(label.english, ignoreCase = true))
            }
        }
    }

    @Test
    fun aLabelThatIsTheSameInBothLanguagesIsShownOnce() {
        val same = object : TextSource {
            override fun get(name: String, vararg args: Any): String = CardLabel.values().first { it.resource == name }.english.lowercase()
            override fun count(name: String, quantity: Int): String = name
        }
        for (label in CardLabel.values()) assertEquals(label.english, EmergencyLabels.cardLabel(same, label))
    }

    @Test
    fun theFixedEnglishHalfIsTheEnglishStringsFile_soTheTwoCannotDrift() {
        val english = StringsXml.map(StringsXml.default)
        for (label in CardLabel.values()) assertEquals(label.name, english.getValue(label.resource), label.english)
    }
}
