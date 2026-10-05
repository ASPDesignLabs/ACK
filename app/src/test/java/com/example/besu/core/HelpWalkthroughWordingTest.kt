// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The HELP walkthroughs' own words move to string resources one family (one file in help/) at a time. This reads the families that have moved: each holds only resource names that
 * follow the naming rule, every name exists in English and in every language, English is word for word what the walkthrough always said, a translation uses the bare label placeholder and
 * names the same labels as English, and the three places that draw or speak a step read it through the walkthrough text. A family that has not moved is listed here with its reason, so a
 * new family file cannot be forgotten and a moved one cannot be left on the list. HelpWalkthroughTextTest holds the decisions.
 */
class HelpWalkthroughWordingTest {
    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val everyLanguage get() = listOf("en" to english) + translations.toList()

    /** The families that have moved to resources (a file in help/). */
    private val moved = listOf("GeoProtocolHelp.kt", "LogsHelp.kt")

    /** The families that still hold their own English, each to be moved in its own commit. */
    private val notYetMoved = listOf(
        "BasicsNavigationHelp.kt", "DeckManagementHelp.kt", "EmergencyDeckHelp.kt", "EmojiDeckHelp.kt", "FieldOpsHelp.kt", "GifDeckHelp.kt", "MatrixDeckHelp.kt",
        "PersonalizationHelp.kt", "QuickActionsDeckHelp.kt", "RecordTrainingDataHelp.kt", "SettingsManagementHelp.kt", "StatementComposerHelp.kt", "TargetComputerHelp.kt", "VoiceRecordingsHelp.kt",
        // The registry itself holds one inline module (MANUAL OVERRIDE), so it is a family too.
        "HelpRegistry.kt",
    )

    private class Step(val id: String, val title: String?, val body: String?)
    private class Mod(val id: String, val title: String?, val summary: String?, val steps: List<Step>)

    /** Modules and steps of a family file: each `HelpModule(` / `HelpStep(` with its `id`, and the `title`, `summary` and `body` that follow it before the next one. */
    private fun parse(text: String): List<Mod> {
        val marks = Regex("""Help(Module|Step)\(""").findAll(text).toList()
        val mods = mutableListOf<Mod>()
        var steps = mutableListOf<Step>()
        var current: Triple<String, String?, String?>? = null
        fun flush() { current?.let { mods.add(Mod(it.first, it.second, it.third, steps)) }; steps = mutableListOf() }
        for ((i, m) in marks.withIndex()) {
            val region = text.substring(m.range.last, if (i + 1 < marks.size) marks[i + 1].range.first else text.length)
            val id = Regex("""\bid = "([^"]+)"""").find(region)?.groupValues?.get(1) ?: continue
            val title = Regex("""\btitle = "([^"]*)"""").find(region)?.groupValues?.get(1)
            if (m.groupValues[1] == "Module") {
                flush()
                current = Triple(id, title, Regex("""\bsummary = "([^"]*)"""").find(region)?.groupValues?.get(1))
            } else {
                steps.add(Step(id, title, Regex("""\bbody = "([^"]*)"""").find(region)?.groupValues?.get(1)))
            }
        }
        flush()
        return mods
    }

    private fun namesIn(path: String): List<String> = parse(file(path)).flatMap { m ->
        listOfNotNull(m.title, m.summary) + m.steps.flatMap { listOfNotNull(it.title, it.body) }
    }

    // ---- the files ------------------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyFamilyFileIsEitherMovedOrListedAsNotYetMoved_neverBoth_neverNeither() {
        val onDisk = RepoFiles.file("$base/help").listFiles()!!.map { it.name }.filter { it.endsWith("Help.kt") || it == "HelpRegistry.kt" }.toSet()
        assertEquals("a family file that is on neither list (or listed but gone)", onDisk, (moved + notYetMoved).toSet())
        assertEquals("a file on both lists", emptyList<String>(), moved.filter { it in notYetMoved })
        for (f in notYetMoved) assertFalse("$f holds a resource name but is listed as not yet moved", file("help/$f").contains("\"helpmod_"))
        for (f in moved) assertTrue("$f is listed as moved but holds no resource name", file("help/$f").contains("\"helpmod_"))
    }

    @Test
    fun aFamilyThatMovedHoldsOnlyResourceNames_followingTheNamingRule() {
        for (f in moved) {
            val mods = parse(file("help/$f"))
            assertTrue("$f: no module found", mods.isNotEmpty())
            for (m in mods) {
                assertEquals("$f/${m.id}: module title", HelpWalkthroughText.moduleTitle(m.id), m.title)
                assertEquals("$f/${m.id}: module summary", HelpWalkthroughText.moduleSummary(m.id), m.summary)
                assertTrue("$f/${m.id}: no steps", m.steps.isNotEmpty())
                for (s in m.steps) {
                    assertEquals("$f/${m.id}/${s.id}: step title", HelpWalkthroughText.stepTitle(m.id, s.id), s.title)
                    assertEquals("$f/${m.id}/${s.id}: step body", HelpWalkthroughText.stepBody(m.id, s.id), s.body)
                }
            }
            // Nothing else in the file is a string with words in it that the person would see: the old title/body/summary parameters are the only text a step holds.
            assertFalse("$f: a title, body or summary is still written out", Regex("""\b(title|body|summary) = "(?!helpmod_)""").containsMatchIn(file("help/$f")))
        }
    }

    @Test
    fun noWalkthroughNameIsDefinedTwiceInAnyLanguage() {
        for (path in listOf("values") + StringsXml.translations().keys.map { "values-$it" }) {
            val names = Regex("""<string name="(helpmod_[a-z0-9_]+)"""").findAll(RepoFiles.read("app/src/main/res/$path/strings.xml")).map { it.groupValues[1] }.toList()
            assertEquals("$path: a walkthrough name is defined twice", emptyList<String>(), names.groupingBy { it }.eachCount().filter { it.value > 1 }.keys.toList())
        }
    }

    @Test
    fun everyNameUsedExistsInEnglishAndInEveryLanguage_andNoWalkthroughStringIsLeftUnused() {
        val used = moved.flatMap { namesIn("help/$it") }.toSet()
        val defined = english.keys.filter { it.startsWith(HelpWalkthroughText.PREFIX) }.toSet()
        assertEquals("a name used that English does not define, or defined and never used", used, defined)
        for ((tag, map) in translations) for (name in used) assertTrue("$tag is missing $name", map[name]?.isNotBlank() == true)
        for ((tag, map) in translations) {
            val extra = map.keys.filter { it.startsWith(HelpWalkthroughText.PREFIX) }.toSet() - defined
            assertEquals("$tag defines a walkthrough string English does not", emptySet<String>(), extra)
        }
    }

    // ---- English is exactly what it always said -----------------------------------------------------------------------------------------------

    /** The English of every moved family, as the walkthrough said it before it moved (help_walkthrough_english.tsv: name, a tab, the text with \\n, \\t and \\\\ escaped). */
    private val pins: Map<String, String> get() = RepoFiles.read("app/src/test/resources/help_walkthrough_english.tsv").split("\n").filter { it.isNotEmpty() }.associate { line ->
        val (name, text) = line.split("\t", limit = 2)
        name to Regex("""\\(.)""").replace(text) { m -> when (m.groupValues[1]) { "n" -> "\n"; "t" -> "\t"; else -> m.groupValues[1] } }
    }

    @Test
    fun theEnglishOfEveryMovedFamilyIsWordForWordWhatItAlwaysSaid() {
        val pinned = pins
        val defined = english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }
        assertEquals("a string with no pin, or a pin with no string", pinned.keys, defined.keys)
        for ((name, text) in pinned) assertEquals(name, text, english.getValue(name))
    }

    // ---- the labels a step names ------------------------------------------------------------------------------------------------------------------

    private fun filled(map: Map<String, String>, text: String, plain: Boolean): String =
        HelpPlaceholders.substitute(text, plain) { key, usePlain -> map[key.resourceName(usePlain)] }

    @Test
    fun theEnglishOriginalsReadLikeTheStandardLabel_andATranslationUsesTheBarePlaceholderNamingTheSameLabels() {
        var checked = 0
        for ((name, text) in english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            val keys = HelpPlaceholders.keysIn(text)
            for (m in Regex("""\{\{([A-Z0-9_]+)(?::([^{}]*))?\}\}""").findAll(text)) {
                val key = LabelKey.fromName(m.groupValues[1])
                assertTrue("$name: {{${m.groupValues[1]}}} is not a LabelKey", key != null)
                val original = m.groups[2]?.value
                if (original != null) assertTrue("$name: the original \"$original\" does not read like the standard label", original.equals(english.getValue(key!!.resourceName(false)), ignoreCase = true))
                checked++
            }
            for ((tag, map) in translations) {
                val t = map.getValue(name)
                assertFalse("$tag/$name: a translation carries no English original", Regex("""\{\{[A-Z0-9_]+:""").containsMatchIn(t))
                assertEquals("$tag/$name: the same labels as English", keys.sorted(), HelpPlaceholders.keysIn(t).sorted())
                for (plain in listOf(false, true)) assertFalse("$tag/$name: braces left after the labels are filled in (plain=$plain)", filled(map, t, plain).contains("{{"))
            }
            for (plain in listOf(false, true)) assertFalse("en/$name: braces left (plain=$plain)", filled(english, text, plain).contains("{{"))
        }
        assertTrue("expected to check some placeholders, checked $checked", checked > 0)
    }

    @Test
    fun aLatinScriptDraftHasNoArticleBeforeAPlaceholder_soAnEverydayWordOfAnotherGenderStillReads() {
        val articles = mapOf(
            "es" to listOf("EL", "LA", "LOS", "LAS", "UN", "UNA", "DEL", "AL"),
            "pt" to listOf("O", "A", "OS", "AS", "UM", "UMA", "DO", "DA", "NO", "NA", "AO"),
        )
        for ((tag, list) in articles) for ((name, text) in translations.getValue(tag).filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            for (article in list) assertFalse("$tag/$name: article $article before a placeholder: $text", Regex("""(?<![\p{L}])$article \{\{""").containsMatchIn(text))
        }
    }

    /** A title that is exactly a label's or a control's own word in every language, so the walkthrough and the screen agree. */
    private val isExactly = mapOf(
        "helpmod_geo_protocol_title" to "label_geo_protocol",
        "helpmod_geo_protocol_intro_title" to "label_geo_protocol",
        "helpmod_geo_protocol_map_data_title" to "geo_map_data",
    )

    /** A text that names a label in plain words (English has no placeholder there), so every language holds that label's own standard word, and it does not follow PLAIN WORDS (a known gap). */
    private val namesLabelLiterally = mapOf(
        "helpmod_logs_intro_title" to listOf("label_terminal"),
        "helpmod_logs_intro_body" to listOf("label_terminal"),
    )

    @Test
    fun aTitleThatNamesALabelOrAControlIsThatLabelsOrControlsOwnWordInEveryLanguage() {
        for ((tag, map) in everyLanguage) for ((name, source) in isExactly) assertEquals("$tag/$name", map.getValue(source), map.getValue(name))
        assertTrue("every entry names a walkthrough string that exists", (isExactly.keys + namesLabelLiterally.keys).all { it in english })
    }

    @Test
    fun aTextThatNamesALabelInPlainWordsHoldsThatLabelsOwnWordInEveryLanguage() {
        for ((tag, map) in everyLanguage) for ((name, sources) in namesLabelLiterally) for (source in sources) {
            val word = map.getValue(source)
            assertTrue("$tag/$name does not hold \"$word\" ($source): ${map.getValue(name)}", map.getValue(name).contains(word, ignoreCase = true))
        }
    }

    @Test
    fun theMapStepStillNamesTheFileKindAndTheFormat_andTakesNoArgumentInEveryLanguage() {
        for ((tag, map) in everyLanguage) {
            val body = map.getValue("helpmod_geo_protocol_map_data_body")
            assertTrue("$tag: Mapsforge is a name: $body", body.contains("Mapsforge", ignoreCase = true))
            assertTrue("$tag: the .map file kind is named: $body", body.contains(".map", ignoreCase = true))
            for ((name, text) in map.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) assertFalse("$tag/$name takes an argument nothing passes: $text", text.contains("%"))
        }
    }

    @Test
    fun noWalkthroughStringStartsOrEndsWithASpace_whichAndroidWouldTrim() {
        for ((tag, map) in everyLanguage) for ((name, text) in map.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) assertEquals("$tag/$name", text.trim(), text)
    }

    // ---- where a step is drawn and spoken -------------------------------------------------------------------------------------------------------

    @Test
    fun theCoachAndTheMenuDrawAWalkthroughsWordsThroughHelpWords() {
        val coach = file("help/HelpCoachDialog.kt")
        val menu = file("help/HelpMenuDialog.kt")
        assertTrue(coach.contains("text = helpWords(step.title)") && coach.contains("text = helpWords(step.body)"))
        assertTrue(menu.contains("text = helpWords(module.title)") && menu.contains("text = helpWords(module.summary)"))
        assertTrue(coach.contains("import com.example.besu.ui.helpWords") && menu.contains("import com.example.besu.ui.helpWords"))
        val words = RepoFiles.read("$base/ui/PlainWords.kt")
        val helpWords = words.substring(words.indexOf("fun helpWords("))
        assertTrue("helpWords reads the name through the walkthrough text and then fills the placeholders", helpWords.contains("helpText(remember(nameOrText, words) { HelpWalkthroughText.read(words, nameOrText) })"))
        assertTrue("helpWords makes the text source once", helpWords.contains("val words = rememberText()"))
    }

    @Test
    fun theSpokenGuideSpeaksTheTranslatedStepOnlyWhenTheRuleSaysSo_andOtherwiseTheEnglishStep() {
        val main = RepoFiles.read("$base/MainActivity.kt").lines().joinToString("\n") { it.substringBefore("//") }
        val from = main.indexOf("val speakTranslated")
        assertTrue("the speaking rule was not found", from >= 0)
        val block = main.substring(from, main.indexOf("val spokenText = buildString", from))
        assertTrue(block.contains("HelpWalkthroughText.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)"))
        assertTrue("the English step is read from an English context", block.contains("val spokenContext = if (speakTranslated) context else EnglishResources.context(context)"))
        assertTrue(block.contains("val spokenWords = ResourceText(spokenContext)"))
        assertTrue("the words are read through the walkthrough text, from the spoken text source", block.contains("HelpWalkthroughText.read(spokenWords, nameOrText)"))
        assertTrue("the labels placeholders fill in from the same context, so an English step never gets a Spanish label", block.contains("LabelText.resolveOrNull(spokenContext, key, plain)"))
        assertTrue(block.contains("PlainWordsState.on"))
        assertFalse("nothing else reads the step's words", Regex("""append\(step\.(title|body)\)""").containsMatchIn(main))
        val edge = RepoFiles.read("$base/data/ResourceText.kt")
        assertTrue(edge.contains("object EnglishResources") && edge.contains("setLocale(Locale.ENGLISH)"))
        assertTrue("it never throws", edge.substring(edge.indexOf("object EnglishResources")).contains("catch (e: Exception)"))
    }

    @Test
    fun theOtherSpokenPlacesAreNotChanged_thePhraseGoesToTheServiceAsBefore() {
        val main = RepoFiles.read("$base/MainActivity.kt").lines().joinToString("\n") { it.substringBefore("//") }
        val at = main.indexOf("val spokenText = buildString")
        val tail = main.substring(at, at + 700)
        assertTrue(tail.contains("""putExtra("phrase", spokenText)""") && tail.contains("""putExtra("robotic", true)""") && tail.contains("""putExtra("source", "HELP/${'$'}{module.id}")"""))
    }
}
