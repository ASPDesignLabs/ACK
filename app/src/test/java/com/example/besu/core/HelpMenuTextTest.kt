// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The words HELP's menu shows around a module family and on each card, in English exactly as they always were and in every language. The walkthroughs' own text is not here
 * (it is still English); this is the chrome.
 */
class HelpMenuTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val helpCore get() = RepoFiles.read("app/src/main/java/com/example/besu/help/HelpCore.kt")

    /** What HelpPlaceholders makes of a name in standard mode: the label's standard wording in the language whose strings are [map]. */
    private fun standardWording(map: Map<String, String>, text: String): String =
        HelpPlaceholders.substitute(text, plain = false) { key, plain -> map[key.resourceName(plain)] }

    private fun categoryNames(): List<String> {
        val body = helpCore.substringAfter("enum class HelpCategory {").substringBefore("}")
        return body.lines().map { it.trim().trimEnd(',') }.filter { Regex("[A-Z][A-Z_]+").matches(it) }
    }

    private fun destinationModes(): List<String> =
        Regex("""^\s*[A-Z]+\("([A-Z]+)"\)""", RegexOption.MULTILINE).findAll(helpCore.substringAfter("enum class HelpDestination(").substringBefore("enum class HelpCoachPlacement")).map { it.groupValues[1] }.toList()

    // ---- English is exactly what the screens always said ---------------------------------------------------------------------------------

    private data class Family(val name: String, val title: String, val chip: String, val subtitle: String)

    private val oldEnglish = listOf(
        Family("BASICS_NAVIGATION", "BASICS // NAVIGATION", "NAVIGATION", "DECKS, PROFILES, CONTEXT, AND PROMPTS"),
        Family("BASICS_DECKS", "BASICS // DECK MANAGEMENT", "DECK MANAGEMENT", "CREATE, ORGANIZE, RECOLOR, AND REMOVE DECKS"),
        Family("BASICS_SETTINGS", "BASICS // SETTINGS", "SETTINGS", "PROTOCOL, WATCH, SENSORS, SHORTCUTS, AND DATA"),
        Family("BASICS_PERSONALIZATION", "BASICS // PERSONALIZATION", "PERSONALIZATION", "AUDIO ARCHITECT AND OUTPUT CUSTOMIZATION"),
        Family("BASICS_MANUAL_OVERRIDE", "BASICS // MANUAL OVERRIDE", "MANUAL OVERRIDE", "MEMORY BANKS AND DIRECT TEXT INPUT"),
        Family("USING_DECKS", "USING DECKS", "USING DECKS", "DECK-SPECIFIC WORKFLOWS AND CONTROLS"),
        Family("CONTEXTUAL_SYSTEMS", "CONTEXTUAL SYSTEMS", "CONTEXTUAL SYSTEMS", "TARGET COMPUTER, GEO-PROTOCOL, AND LOGS"),
        Family("FIELD_OPS", "FIELD OPS // GESTURE TRAINING", "GESTURE TRAINING", "ARM, POSE, MODIFY, AND FIRE FROM THE WATCH"),
        Family("VOICE_RECORDINGS", "VOICE RECORDINGS", "VOICE RECORDINGS", "RECORD, ATTACH, AND MANAGE YOUR OWN VOICE PROMPTS"),
    )

    @Test
    fun theEnglishFamilyNamesAreExactlyWhatTheEnumUsedToHold_onceTheirPlaceholdersAreFilled() {
        assertEquals("every family the enum has is checked here", oldEnglish.map { it.name }, categoryNames())
        for (f in oldEnglish) {
            assertEquals("${f.name} title", f.title, standardWording(english, HelpMenuText.categoryTitle(t, f.name)))
            assertEquals("${f.name} chip", f.chip, standardWording(english, HelpMenuText.categoryChip(t, f.name)))
            assertEquals("${f.name} subtitle", f.subtitle, standardWording(english, HelpMenuText.categorySubtitle(t, f.name)))
            // The chip used to be cut out of the title after its "// "; it is still exactly that in English.
            assertEquals("${f.name}: the chip is what follows the section", f.title.substringAfter("// ").trim(), f.chip)
        }
    }

    @Test
    fun aFamilyNameHoldsLabelPlaceholdersUnfilled_soPlainWordsCanSwapThem() {
        // The raw text keeps {{DECKS}} (and the others), which helpText() fills with the standard or the everyday word; a filled-in word here would never follow PLAIN WORDS.
        assertEquals("USING {{DECKS}}", HelpMenuText.categoryTitle(t, "USING_DECKS"))
        assertEquals("BASICS // {{DECK}} MANAGEMENT", HelpMenuText.categoryTitle(t, "BASICS_DECKS"))
        assertEquals("{{DECK}} MANAGEMENT", HelpMenuText.categoryChip(t, "BASICS_DECKS"))
        assertEquals("{{TARGET_COMPUTER}}, {{GEO_PROTOCOL}}, AND LOGS", HelpMenuText.categorySubtitle(t, "CONTEXTUAL_SYSTEMS"))
        val plain = HelpPlaceholders.substitute(HelpMenuText.categoryTitle(t, "USING_DECKS"), plain = true) { key, isPlain -> english[key.resourceName(isPlain)] }
        assertNotEquals("the everyday word replaces DECKS", "USING DECKS", plain)
        assertTrue(plain.startsWith("USING "))
    }

    @Test
    fun theStepsLineIsExactlyWhatTheCardAlwaysSaid_exceptThatOneStepIsNotCalledOneSteps() {
        assertEquals("5 STEPS // MATRIX", HelpMenuText.stepsLine(t, 5, "MATRIX"))
        assertEquals("12 STEPS // TERMINAL", HelpMenuText.stepsLine(t, 12, "TERMINAL"))
        assertEquals("3 STEPS // SETTINGS", HelpMenuText.stepsLine(t, 3, "SETTINGS"))
        assertEquals("2 STEPS // TYPE", HelpMenuText.stepsLine(t, 2, "TYPE"))
        assertEquals("4 STEPS // AUDIO", HelpMenuText.stepsLine(t, 4, "AUDIO"))
        assertEquals("6 STEPS // TARGETS", HelpMenuText.stepsLine(t, 6, "TARGETS"))
        assertEquals("7 STEPS // GEO", HelpMenuText.stepsLine(t, 7, "GEO"))
        assertEquals("8 STEPS // CURRENT VIEW", HelpMenuText.stepsLine(t, 8, null))
        // The one deliberate change: the two chooser entries have a single placeholder step, and used to read "1 STEPS".
        assertEquals("1 STEP // CURRENT VIEW", HelpMenuText.stepsLine(t, 1, null))
    }

    // ---- every screen a walkthrough goes to has words, in every language ----------------------------------------------------------------

    @Test
    fun everyDestinationHasWords_andTheMapHoldsNothingElse() {
        val modes = destinationModes()
        assertEquals("the seven destinations HelpCore.kt declares", listOf("TERMINAL", "MATRIX", "SETTINGS", "TYPE", "AUDIO", "TARGETS", "GEO"), modes)
        assertEquals(modes.toSet(), HelpMenuText.viewNameResources.keys)
        for ((mode, resource) in HelpMenuText.viewNameResources) {
            assertEquals("resource name for $mode", "help_view_${mode.lowercase()}", resource)
            for ((tag, map) in listOf("en" to english) + translations.toList()) assertTrue("$tag/$resource is missing", map.containsKey(resource))
        }
    }

    @Test
    fun aViewIsNamedInTheLanguage_aMissingOneIsCurrentView_andAnUnknownOneReadsAsItself() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            for ((mode, resource) in HelpMenuText.viewNameResources) assertEquals("$tag: $mode", map.getValue(resource), HelpMenuText.viewName(f, mode))
            assertEquals("$tag: current view", map.getValue("help_menu_current_view"), HelpMenuText.viewName(f, null))
            assertNotEquals("$tag: still English", "CURRENT VIEW", HelpMenuText.viewName(f, null))
        }
        assertEquals("SOMEWHERE_NEW", HelpMenuText.viewName(t, "SOMEWHERE_NEW"))
        // Two different screens are never named the same on a card.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val names = HelpMenuText.viewNameResources.values.map { map.getValue(it) } + map.getValue("help_menu_current_view")
            assertEquals("$tag: two views share a name: $names", names.size, names.map { it.uppercase() }.toSet().size)
        }
    }

    @Test
    fun theStepsLineHoldsTheCountAndTheViewInEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val line = HelpMenuText.stepsLine(f, 7, "SETTINGS")
            assertTrue("$tag: the count", line.contains("7"))
            assertTrue("$tag: the view", line.contains(map.getValue("help_view_settings")))
            assertFalse("$tag: a resource name was shown instead of words: $line", line.contains("help_"))
            assertTrue("$tag: the line is still count // view", line.contains(" // "))
        }
    }

    // ---- every family has its three texts in every language ------------------------------------------------------------------------------

    @Test
    fun everyFamilyHasTitleChipAndSubtitleInEveryLanguage_andNoFamilyStringIsLeftOver() {
        val names = categoryNames()
        val wanted = names.flatMap { n -> listOf("title", "chip", "subtitle").map { HelpMenuText.categoryKey(n, it) } }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = wanted.filter { it !in map }
            assertEquals("$tag: missing $missing", emptyList<String>(), missing)
            val leftOver = map.keys.filter { it.startsWith("help_cat_") && it !in wanted }
            assertEquals("$tag: a family string with no family: $leftOver", emptyList<String>(), leftOver)
        }
    }

    @Test
    fun aChipIsTheEndOfItsTitle_orTheWholeTitleWhenThereIsNoSection_inEveryLanguage() {
        val sectioned = oldEnglish.filter { it.title.contains("// ") }.map { it.name }.toSet()
        assertEquals(6, sectioned.size)
        for ((tag, map) in translations) {
            for (name in categoryNames()) {
                val title = standardWording(map, map.getValue(HelpMenuText.categoryKey(name, "title")))
                val chip = standardWording(map, map.getValue(HelpMenuText.categoryKey(name, "chip")))
                if (name in sectioned) {
                    assertTrue("$tag/$name: a sectioned title reads SECTION // NAME: $title", title.contains(" // "))
                    assertTrue("$tag/$name: the chip ($chip) is the end of the title ($title)", title.endsWith(chip))
                    assertNotEquals("$tag/$name: the chip is not the whole title", title, chip)
                } else {
                    assertEquals("$tag/$name: no section, so the chip is the title", title, chip)
                    assertFalse("$tag/$name: no section, so no separator", title.contains("//"))
                }
            }
        }
    }

    @Test
    fun noTwoChipsReadTheSame_andNoTwoSubtitlesDo_inAnyLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (part in listOf("chip", "subtitle")) {
                val said = categoryNames().map { standardWording(map, map.getValue(HelpMenuText.categoryKey(it, part))).uppercase() }
                assertEquals("$tag: two families share a $part: $said", said.size, said.toSet().size)
            }
        }
    }

    @Test
    fun theLabelPlaceholdersAreTheSameInEveryLanguage_andAllNameARealLabel() {
        val all = Regex("""\{\{([A-Z0-9_]+)(?::([^{}]*))?\}\}""")
        for ((name, text) in english.filter { it.key.startsWith("help_") }) {
            val inEnglish = HelpPlaceholders.keysIn(text)
            for (key in inEnglish) assertTrue("$name: {{$key}} is not a LabelKey", LabelKey.fromName(key) != null)
            assertTrue("$name: the placeholder names its label and carries no original (the standard wording of the language is the original)", all.findAll(text).all { it.groups[2] == null })
            for ((tag, map) in translations) {
                assertEquals("$tag/$name: the same placeholders as English", inEnglish.sorted(), HelpPlaceholders.keysIn(map.getValue(name)).sorted())
                assertFalse("$tag/$name: braces left over after the labels are filled in", standardWording(map, map.getValue(name)).contains("{{"))
            }
        }
    }

    @Test
    fun aFamilyNameWithAPlaceholderHasNoArticleBeforeIt_soAnEverydayWordOfAnotherGenderStillReads() {
        // The Latin-script drafts avoid "UN {{DECK}}" and "EL {{DECK}}": the everyday word may be masculine or feminine. A test cannot judge grammar, only this convention.
        val articles = mapOf(
            "es" to listOf("EL", "LA", "LOS", "LAS", "UN", "UNA", "DEL"),
            "pt" to listOf("O", "A", "OS", "AS", "UM", "UMA", "DO", "DA"),
        )
        for ((tag, list) in articles) for ((name, text) in translations.getValue(tag).filter { it.key.startsWith("help_cat_") }) {
            for (article in list) assertFalse("$tag/$name: article $article before a placeholder: $text", Regex("""\b$article \{\{""").containsMatchIn(text))
        }
    }
}
