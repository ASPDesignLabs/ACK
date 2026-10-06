// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Statement Composer (the TYPE tab) and MY STATEMENTS read their words from string resources. The file cannot be compiled here, so this reads it:
 * the old English literals are gone, the places that cannot use a composable (the two toasts) read the resource through the context, the logic around the
 * words is as it was, and a person's own folder and statement names are still shown as they typed them. That every string it names exists and is used is
 * checked in MatrixDeckScreenStringsTest (which covers the composer_ prefix too).
 */
class ComposerStringsTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val composer get() = noComments(RepoFiles.read("$base/composer/StatementComposerView.kt"))
    private val english get() = StringsXml.map(StringsXml.default)

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheComposer() {
        val gone = listOf(
            "\"COPIED\"", "\"[EXIT FULL SCREEN]\"", "\"[FULL SCREEN]\"", "\"COMPOSE A STATEMENT...\"", "\"NOTHING TO PREVIEW YET.\"", "\"[HIDE TARGET BROWSER]\"",
            "\"[HIDE VARIABLES]\"", "\"SAVE\"", "\"COPY\"", "\"SPEAK\"", "\"SAVE STATEMENT\"", "\"LABEL\"", "\"FOLDER\"", "\"[+ NEW FOLDER]\"", "\"STATEMENT SAVED\"",
            "\"CANCEL\"", "\"NEW FOLDER\"", "\"CREATE\"", "\"CLOSE\"", "NOTHING SAVED YET", "VARIABLES\")", "\"(NOT SET)\"", "\"DELETE ALL?\"", "\"DELETE?\"",
            "\"[YES]\"", "\"[NO]\"", "\"[+ SUB]\"", "\"[DELETE]\"", "\"[COPY]\"", "\"[SPEAK]\"", "E.G. ",
        )
        for (literal in gone) assertFalse("the composer still draws $literal", composer.contains(literal))
    }

    @Test
    fun theTwoToastsReadTheirTextThroughTheContext_becauseTheyAreNotInAComposableLambda() {
        assertTrue(composer.contains("Toast.makeText(context, context.getString(R.string.composer_copied), Toast.LENGTH_SHORT).show()"))
        assertTrue(composer.contains("Toast.makeText(context, context.getString(R.string.composer_saved_toast), Toast.LENGTH_SHORT).show()"))
        assertFalse("a toast cannot call a composable", Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(composer))
    }

    @Test
    fun theLogicAroundTheWordsIsAsItWas() {
        // The clipboard's own label, the source tags the history shows, and the default grouping are not words on the screen.
        assertTrue(composer.contains("ClipData.newPlainText(\"ACK STATEMENT\", resolved)"))
        assertTrue(composer.contains("\"COMPOSER/SPEAK\""))
        assertTrue(composer.contains("\"COMPOSER/BANK\""))
        assertTrue(composer.contains("mutableStateOf(\"IDENTITY\")"))
        assertTrue(composer.contains("listOf(\"A\", \"B\", \"C\")"))
        // What a person typed as a folder or statement name is shown as typed, in capitals as before.
        assertTrue(composer.contains("node.label.uppercase()"))
    }

    @Test
    fun theVariablePickerTitleNamesThePoseThroughTheHeadingHelper_andKeepsALayerTheyNamed() {
        assertTrue(composer.contains("stringResource(R.string.composer_variables_title, poseHeading(category))"))
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("composer_variables_title")))
        val plain = noComments(RepoFiles.read("$base/ui/PlainWords.kt"))
        val heading = plain.substring(plain.indexOf("fun poseHeading("), plain.indexOf("fun helpText("))
        assertTrue(heading.contains("PlainLabels.poseLabelKey(stored) ?: return stored.uppercase()"))
        assertTrue(heading.contains("return labelFor(key)"))
    }

    @Test
    fun theSharedWordsAreSharedNotCopied() {
        for (name in listOf("common_save", "common_copy", "common_speak", "common_delete", "common_yes", "common_no", "common_create", "common_cancel", "common_close")) {
            assertTrue("$name is missing", english.containsKey(name))
        }
        // The yes/no and delete/copy/speak links are bracketed text, built around the shared word.
        assertTrue(composer.contains("\"[\${stringResource(R.string.common_yes)}]\""))
        assertTrue(composer.contains("\"[\${stringResource(R.string.common_delete)}]\""))
    }

    @Test
    fun theNothingSavedSentenceIsOneStringWithBothHalves() {
        val text = english.getValue("composer_nothing_saved")
        assertTrue(text.contains("TAP SAVE, OR ADD A FOLDER"))
        assertEquals(text, text.uppercase())
    }
}
