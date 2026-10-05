// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** HELP text is fixed, so a step names a label with `{{KEY:Original}}`: the Original is shown as it always was, and PLAIN WORDS swaps in the plain label. */
class HelpPlaceholdersTest {

    private val plainOf = { key: LabelKey, plain: Boolean -> if (plain) "PLAIN(${key.name})" else "STD(${key.name})" }

    @Test
    fun standardModeShowsTheOriginalWordingExactly_soNothingChangesForAnyoneNotUsingPlainWords() {
        val text = "Build statements from {{TARGET_COMPUTER:Target Computer}} entries."
        assertEquals("Build statements from Target Computer entries.", HelpPlaceholders.substitute(text, plain = false, resolve = plainOf))
    }

    @Test
    fun plainModeShowsThePlainLabel() {
        val text = "Build statements from {{TARGET_COMPUTER:Target Computer}} entries."
        assertEquals("Build statements from PLAIN(TARGET_COMPUTER) entries.", HelpPlaceholders.substitute(text, plain = true, resolve = plainOf))
    }

    @Test
    fun aPlaceholderWithNoOriginalShowsTheStandardLabelInStandardMode() {
        assertEquals("Open STD(DECK).", HelpPlaceholders.substitute("Open {{DECK}}.", plain = false, resolve = plainOf))
        assertEquals("Open PLAIN(DECK).", HelpPlaceholders.substitute("Open {{DECK}}.", plain = true, resolve = plainOf))
    }

    @Test
    fun severalPlaceholdersInOneStepAreAllReplaced() {
        val text = "{{DECK:Deck}} and {{POSE:pose}} and {{DECK:Deck}}"
        assertEquals("Deck and pose and Deck", HelpPlaceholders.substitute(text, false, plainOf))
        assertEquals("PLAIN(DECK) and PLAIN(POSE) and PLAIN(DECK)", HelpPlaceholders.substitute(text, true, plainOf))
    }

    @Test
    fun anUnknownKeyNeverShowsBraces_itFallsBackToItsOriginalOrTheKeyName() {
        assertEquals("keep this", HelpPlaceholders.substitute("{{NOT_A_KEY:keep this}}", false, plainOf))
        assertEquals("keep this", HelpPlaceholders.substitute("{{NOT_A_KEY:keep this}}", true, plainOf))
        assertEquals("NOT_A_KEY", HelpPlaceholders.substitute("{{NOT_A_KEY}}", false, plainOf))
    }

    @Test
    fun aResolverThatFindsNothingFallsBackToTheOriginal_neverToBlank() {
        val nothing = { _: LabelKey, _: Boolean -> null }
        assertEquals("Deck", HelpPlaceholders.substitute("{{DECK:Deck}}", true, nothing))
        assertEquals("Deck", HelpPlaceholders.substitute("{{DECK:Deck}}", false, nothing))
    }

    @Test
    fun textWithNoPlaceholderIsReturnedUnchanged_includingBracesThatAreNotOne() {
        val text = "Use {VAR:A} or [COMPUTER:HOME] or {{not a placeholder}} or {{ }} here."
        assertEquals(text, HelpPlaceholders.substitute(text, true, plainOf))
        assertEquals(text, HelpPlaceholders.substitute(text, false, plainOf))
    }

    @Test
    fun theTemplateTokensTheAppUsesAreNeverTouched() {
        val text = "Insert {VAR:A} then [COMPUTER:SELF]."
        assertEquals(text, HelpPlaceholders.substitute(text, true, plainOf))
    }

    @Test
    fun anOriginalMayContainAColonOrBrackets_butNotBraces() {
        assertEquals("a: b (c)", HelpPlaceholders.substitute("{{DECK:a: b (c)}}", false, plainOf))
    }

    @Test
    fun keysInReportsEveryKeyUsed_forTheDriftTest() {
        assertEquals(listOf("DECK", "POSE", "NOT_A_KEY"), HelpPlaceholders.keysIn("{{DECK:Deck}} {{POSE}} {{NOT_A_KEY:x}}"))
        assertTrue(HelpPlaceholders.keysIn("no placeholders {VAR:A}").isEmpty())
    }

    // ---- the real HELP text --------------------------------------------------------------------------------------------------------

    @Test
    fun everyOriginalInTheHelpTextIsTheStandardLabelOfItsKey_ignoringCase_soTheRightKeyIsNamed() {
        val strings = StringsXml.map(StringsXml.default)
        val dir = RepoFiles.file("app/src/main/java/com/example/besu/help")
        var checked = 0
        for (file in dir.listFiles()!!.filter { it.extension == "kt" }) {
            for (m in Regex("""\{\{([A-Z0-9_]+):([^{}]*)\}\}""").findAll(file.readText())) {
                val key = LabelKey.fromName(m.groupValues[1]) ?: continue
                val standard = strings.getValue(key.resourceName(false))
                assertTrue(
                    "${file.name}: {{${key.name}:${m.groupValues[2]}}} does not read like the standard label \"$standard\"",
                    m.groupValues[2].equals(standard, ignoreCase = true),
                )
                checked++
            }
        }
        // A walkthrough family that has moved to resources keeps its placeholders in the English strings file, so the same rule is applied there.
        for ((name, text) in strings.filter { it.key.startsWith("helpmod_") }) {
            for (m in Regex("""\{\{([A-Z0-9_]+):([^{}]*)\}\}""").findAll(text)) {
                val key = LabelKey.fromName(m.groupValues[1]) ?: continue
                val standard = strings.getValue(key.resourceName(false))
                assertTrue("$name: {{${key.name}:${m.groupValues[2]}}} does not read like the standard label \"$standard\"", m.groupValues[2].equals(standard, ignoreCase = true))
                checked++
            }
        }
        assertTrue("expected to check many placeholders, checked $checked", checked > 100)
    }

    @Test
    fun everyPlaceholderInTheHelpModulesNamesARealLabel_andItsOriginalIsNotLeftBlankInStandardMode() {
        val dir = RepoFiles.file("app/src/main/java/com/example/besu/help")
        val used = dir.listFiles()!!.filter { it.extension == "kt" }.flatMap { file ->
            Regex("""\{\{([A-Z0-9_]+)(?::[^{}]*)?\}\}""").findAll(file.readText()).map { file.name to it.groupValues[1] }.toList()
        }
        for ((file, key) in used) assertTrue("$file uses {{$key}}, which is not a LabelKey", LabelKey.fromName(key) != null)
        assertFalse("the scan found no placeholder at all; is the HELP text really using them?", used.isEmpty())
    }
}
