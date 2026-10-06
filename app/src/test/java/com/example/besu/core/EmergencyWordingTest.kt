// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Emergency deck reads its words from string resources, in the chosen language. The screen cannot be compiled here, so this reads it: the old English
 * literals are gone, every string it names exists and none is unused, and the things that decide what is spoken and what is saved are exactly as they were
 * (what is sent and with which overrides, the confirmation, the saved tone names and defaults, a button's saved name). On the info card, which someone else reads,
 * the card view shows the language and English; the edit form, which only the person sees, does not. The decisions are in EmergencyLabelsTest.
 */
class EmergencyWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val deck get() = noComments(RepoFiles.read("$base/decks/EmergencyDeck.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    /** The part of the deck file from [start] up to (not including) the next top-level `@Composable`. */
    private fun block(start: String): String {
        val at = deck.indexOf(start)
        assertTrue("missing $start", at >= 0)
        val end = deck.indexOf("\n@Composable", at + 1).let { if (it < 0) deck.length else it }
        return deck.substring(at, end)
    }

    @Test
    fun everyStringTheDeckNamesExists_andNoEmergencyStringIsLeftUnused() {
        val referenced = Regex("""R\.string\.(emergency_[a-z0-9_]+)""").findAll(deck).map { it.groupValues[1] }.toSet()
        val labels = noComments(RepoFiles.read("$base/core/EmergencyLabels.kt"))
        val named = Regex(""""(emergency_[a-z0-9_]+)"""").findAll(labels).map { it.groupValues[1] }.toSet() +
            EmergencyLabels.CardLabel.values().map { it.resource } + (1..3).map { "emergency_state_tone_$it" }
        val used = referenced + named
        val defined = english.keys.filter { it.startsWith("emergency_") }.toSet()
        assertEquals("named but not defined: ${used - defined}", emptySet<String>(), used - defined)
        assertTrue("defined but never used: ${defined - used}", (defined - used).isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheDeck() {
        val gone = listOf(
            "\"TAP: EXECUTE", "\"CONFIGURE OVERRIDES\"", "\"EMERGENCY INFO\"", "\"OVERRIDES: ", "\"PERSIST\"", "\"HOLD CLEAR\"", "\"SPEAKER\"", "\"BOOST\"", "\"CONFIRM\"",
            "\"READY\"", "\"HOLD TO SET\"", "\"CONFIGURE E", "\"BUTTON LABEL\"", "\"EMERGENCY PHRASE\"", "\"LOCAL VARIABLES\"", "\"CANCEL\"", "\"SAVE\"", "\"EMERGENCY OVERRIDES\"",
            "\"OVERLAY CLEARING\"", "\"PREVENT TIMED CLEAR\"", "\"REQUIRE HOLD TO CLEAR\"", "\"OUTPUT ROUTING\"", "\"FORCE DEVICE SPEAKER\"", "\"EMERGENCY VOLUME BOOST\"", "\"ALERT TONE\"",
            "\"TAP PROTECTION\"", "\"CONFIRM BEFORE SENDING\"", "\"SAVE OVERRIDES\"", "\"CONFIRM EMERGENCY\"", "\"SEND\"", "\"CLOSE\"", "\"EDIT\"", "\"EDIT EMERGENCY INFO\"",
            "NO INFO ON FILE YET", "\"NAME\"", "\"DATE OF BIRTH\"", "\"BLOOD TYPE\"", "\"COMMUNICATION\"", "\"CONDITIONS\"", "\"ALLERGIES\"", "\"MEDICATIONS\"", "\"PRIMARY CONTACT\"",
            "\"EMERGENCY CONTACT\"", "\"NOTES\"", "\"FULL NAME\"", "\"COMMUNICATION NOTE\"", "\"MEDICAL CONDITIONS\"", "\"RELATIONSHIP\"", "\"PHONE\"", "\"SECONDARY CONTACT\"",
            "\"ADDITIONAL NOTES\"", "option.name.replace", "add(config.tone.name)",
        )
        for (literal in gone) assertFalse("EmergencyDeck.kt still holds $literal", deck.contains(literal))
        assertTrue("an explicit R import is needed outside the base package", deck.contains("import com.example.besu.R"))
    }

    @Test
    fun theStatusLineMapsTheSavedToneToItsNumber_andDrawsQuietlyWhenNothingIsChanged() {
        val strip = block("private fun EmergencyStatusStrip(")
        assertTrue(strip.contains("EmergencyTone.OFF -> 0\n            EmergencyTone.TONE_1 -> 1\n            EmergencyTone.TONE_2 -> 2\n            EmergencyTone.TONE_3 -> 3"))
        assertTrue(strip.contains("EmergencyLabels.overridesLine(rememberText(), overrides)"))
        assertTrue(strip.contains("color = if (overrides.isStandard) Color.Gray else primaryColor,"))
        // Each saved switch feeds the line it names (a swapped pair would show the wrong override).
        for (pair in listOf("preventTimedClear = config.preventTimedClear", "requireHoldToClear = config.requireHoldToClear", "forceSpeaker = config.forceSpeaker",
            "boostVolume = config.boostVolume", "confirmBeforeSend = config.confirmBeforeSend")) assertTrue(pair, strip.contains(pair))
    }

    @Test
    fun theTitleIsTheDeckTypesNameThroughTheLabelTable() {
        assertTrue(deck.contains("text = labelFor(LabelKey.DECK_TYPE_EMERGENCY),"))
        // The source tag and the intent extras that make a message an emergency are logic, and stay as they were.
        assertTrue(deck.contains("putExtra(\"source\", \"EMERGENCY\")"))
        assertTrue(deck.contains("putExtra(\"emergency_mode\", true)"))
    }

    // ---- what is sent and what is saved is exactly as it was ----------------------------------------------------------------------

    @Test
    fun whatIsSentAndTheOverridesItCarriesAreUnchanged() {
        val send = block("    fun sendEmergency(phrase: String) {")
        for (extra in listOf(
            "putExtra(\"phrase\", phrase)", "putExtra(\"robotic\", false)", "putExtra(\"emergency_mode\", true)", "\"emergency_force_speaker\",\n                    config.forceSpeaker",
            "\"emergency_boost_volume\",\n                    config.boostVolume", "\"emergency_tone\",\n                    config.tone.name", "\"emergency_prevent_timed_clear\",\n                    config.preventTimedClear",
            "\"emergency_require_hold_to_clear\",\n                    config.requireHoldToClear",
        )) assertTrue("sendEmergency lost $extra", send.contains(extra))
    }

    @Test
    fun theConfirmationStillSendsExactlyWhatWasShown_andCancelSendsNothing() {
        assertTrue(deck.contains("if (config.confirmBeforeSend) {"))
        assertTrue(deck.contains("sendEmergency(pending.phrase)"))
        assertTrue(deck.contains("onClick = onCancel"))
        assertTrue(deck.contains("onClick = onSend"))
        // A tile with no phrase still sends nothing, with or without the confirmation.
        assertTrue(deck.contains("if (phrase.isBlank()) {\n                                return@EmergencyPromptButton\n                            }"))
        // The confirmation shows the button's name as the button shows it.
        assertTrue(deck.contains("slotLabel = EmergencyLabels.shownLabel(words, slot.label, slot.slotIndex),"))
    }

    @Test
    fun theSavedToneNamesAndDefaultsAreUnchanged() {
        // These are saved in the config and in a backup: a display word must never be written back.
        assertTrue(deck.contains("enum class EmergencyTone {\n    OFF,\n    TONE_1,\n    TONE_2,\n    TONE_3\n}"))
        assertTrue(deck.contains("val preventTimedClear: Boolean = true,"))
        assertTrue(deck.contains("val confirmBeforeSend: Boolean = false"))
        assertTrue(deck.contains("val communicationNote: String = \"I am non-verbal or unable to speak right now \" +"))
        assertTrue(deck.contains("val label: String = \"EMERGENCY \${slotIndex + 1}\","))
        // The tone dropdown writes the enum entry, not its label.
        assertTrue(deck.contains("tone = option"))
    }

    @Test
    fun aButtonNameIsOnlyEverRewrittenWhenThePersonChangedIt() {
        val editor = block("private fun EmergencySlotEditorDialog(")
        assertTrue(editor.contains("mutableStateOf(shownAtStart)"))
        // The field starts from the name as it is SHOWN (the default in the chosen language), computed through the same rule the button uses.
        assertTrue(editor.contains("val shownAtStart = remember(slot.slotIndex) {\n        EmergencyLabels.shownLabel(words, slot.label, slot.slotIndex)\n    }"))
        assertTrue(editor.contains("EmergencyLabels.labelToSave(label, shownAtStart, slot.label),"))
        assertFalse("the field must not start from the stored text", editor.contains("mutableStateOf(slot.label)"))
    }

    // ---- the info card: the card view is the language and English, the edit form is the person's own -----------------------------

    @Test
    fun theCardViewShowsTheLanguageAndEnglish_theEditFormDoesNot() {
        val display = block("private fun EmergencyInfoDisplay(")
        for (label in EmergencyLabels.CardLabel.values().filter { it != EmergencyLabels.CardLabel.TITLE }) {
            assertTrue("the card view does not show ${label.name} through cardLabel", display.contains("CardLabel.${label.name}"))
        }
        val form = block("private fun EmergencyInfoEditForm(")
        assertFalse("the edit form is the person's own and uses the chosen language only", form.contains("cardLabel"))
        val dialog = block("private fun EmergencyInfoDialog(")
        assertTrue(dialog.contains("EmergencyLabels.cardLabel(rememberText(), CardLabel.TITLE)"))
        assertTrue(dialog.contains("stringResource(R.string.emergency_info_edit_title)"))
        // What is on the card (the person's own words) is drawn untouched.
        for (field in listOf("card.fullName", "card.dateOfBirth", "card.bloodType", "card.communicationNote", "card.conditions", "card.allergies", "card.medications", "card.notes")) {
            assertTrue(field, display.contains(field))
        }
    }

    // ---- the safety distinctions hold in every language ---------------------------------------------------------------------------

    @Test
    fun sendAndCancelAreDifferentWordsInEveryLanguage_andTheTitleNamesTheEmergency() {
        for ((tag, map) in translations) {
            val send = map.getValue("emergency_send")
            val cancel = map.getValue("common_cancel")
            assertTrue("$tag: SEND and CANCEL must not read the same: $send / $cancel", send.isNotBlank() && cancel.isNotBlank() && send != cancel)
            assertTrue("$tag: SEND is not still English", send != english.getValue("emergency_send"))
            assertTrue("$tag: the confirmation title is its own words", map.getValue("emergency_confirm_title") != map.getValue("emergency_info_title"))
        }
        assertEquals("SEND", english.getValue("emergency_send"))
        assertEquals("CONFIRM EMERGENCY", english.getValue("emergency_confirm_title"))
    }

    @Test
    fun theThreeTonesAreThreeDifferentLabels_withTheirNumber_inEveryLanguage() {
        for (map in listOf(english) + translations.values) {
            val tones = (1..3).map { map.getValue("emergency_tone_$it") }
            assertEquals(3, tones.toSet().size)
            for ((i, t) in tones.withIndex()) assertTrue("$t has no ${i + 1}", t.contains("${i + 1}"))
            val states = (1..3).map { map.getValue("emergency_state_tone_$it") }
            assertEquals(3, states.toSet().size)
            for ((i, t) in states.withIndex()) assertTrue("$t has no ${i + 1}", t.contains("${i + 1}"))
        }
    }

    @Test
    fun theEmptyCardHintNamesTheSameEditWordTheButtonUses_inEveryLanguage() {
        for (map in listOf(english) + translations.values) {
            assertTrue(map.getValue("emergency_info_empty"), map.getValue("emergency_info_empty").contains(map.getValue("common_edit")))
        }
    }
}
