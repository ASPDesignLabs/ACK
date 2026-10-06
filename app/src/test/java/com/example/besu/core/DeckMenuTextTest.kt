// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the deck menu in MainActivity's header says that is decided, in English exactly as it always was and in every language: the SYSTEM DEFAULT row, a deck's row, the MANAGE hint, the locked notice for the
 * permanent Matrix deck, the edit panel's title and the two questions that delete a deck. The deck's name is the person's own and is shown exactly as saved; the words for DECK and for a deck's type come in as arguments.
 */
class DeckMenuTextTest {

    private val t = EnglishText
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val english get() = StringsXml.map(StringsXml.default)
    private fun count(text: String, part: String) = Regex(Regex.escape(part)).findAll(text).count()
    private val words = DeckMenuText.BackupWords(exportJson = "EXPORT .JSON", gifExportEntry = "EXPORT DECK (.ZIP)", gifBackupMenu = "BACKUP", gifLabel = "GIF")
    private val marked = DeckMenuText.BackupWords(exportJson = "XJX", gifExportEntry = "EEE", gifBackupMenu = "MMM", gifLabel = "GGG")
    private val awkwardNames = listOf("Work", "100% %s %d", "price \$5 \$1", "she said \"no\"", "line one\nline two", "[BRACKETS] // SLASHES")

    // ---- English is exactly what the menu always said -------------------------------------------------------------------------------

    @Test
    fun theEnglishWordsAreExactlyWhatTheMenuAlwaysSaid() {
        assertEquals("SYSTEM DEFAULT // MATRIX", DeckMenuText.systemDefaultRow(t, "MATRIX"))
        assertEquals("OURS // QUICK ACTIONS", DeckMenuText.deckRow("OURS", "QUICK ACTIONS"))
        assertEquals("SELECT A DECK TO RENAME, RECOLOR, OR DELETE", DeckMenuText.manageHint(t, "DECK"))
        assertEquals("SYSTEM MATRIX DECK LOCKED", DeckMenuText.lockedTitle(t, "MATRIX", "DECK"))
        assertEquals("THE PERMANENT MATRIX DECK CANNOT BE EDITED OR DELETED.", DeckMenuText.lockedBody(t, "MATRIX", "DECK"))
        assertEquals("[LOCKED]", DeckMenuText.rowTag(t, locked = true))
        assertEquals("[EDIT]", DeckMenuText.rowTag(t, locked = false))
        assertEquals("EDIT: QUICK ACTIONS", DeckMenuText.editTitle(t, "QUICK ACTIONS"))
        assertEquals("CONFIRM DECK DELETION", DeckMenuText.deleteTitle(t, "DECK"))
        assertEquals("MARK Work FOR DELETION?", DeckMenuText.deleteQuestion(t, "Work"))
        val plain = DeckMenuText.finalConfirmation(t, "Work", "DECK", isGifDeck = false, words = words)
        assertEquals("DELETE Work PERMANENTLY?", plain.question)
        assertEquals("THIS REMOVES THE DECK AND ITS LOCAL CONFIGURATION.", plain.removes)
        assertNull(plain.gifWarning)
        assertEquals("THIS CANNOT BE UNDONE. BACK UP FIRST WITH EXPORT .JSON.", plain.backupAdvice)
        val gif = DeckMenuText.finalConfirmation(t, "Work", "DECK", isGifDeck = true, words = words)
        assertEquals("GIF FILES BELONGING TO THIS DECK WILL ALSO BE REMOVED.", gif.gifWarning)
        assertEquals("THIS CANNOT BE UNDONE. TO KEEP THE GIF FILES, FIRST USE BACKUP, THEN EXPORT DECK (.ZIP), ON THE GIF SCREEN.", gif.backupAdvice)
        // With PLAIN WORDS the export label is the everyday one.
        assertEquals("THIS CANNOT BE UNDONE. BACK UP FIRST WITH SAVE A BACKUP.", DeckMenuText.finalConfirmation(t, "Work", "PAGE", false, DeckMenuText.BackupWords("SAVE A BACKUP", "x", "y", "z")).backupAdvice)
        // The same sentences with the everyday word for DECK (PLAIN WORDS).
        assertEquals("SELECT A PAGE TO RENAME, RECOLOR, OR DELETE", DeckMenuText.manageHint(t, "PAGE"))
        assertEquals("SYSTEM GESTURE PHRASES PAGE LOCKED", DeckMenuText.lockedTitle(t, "GESTURE PHRASES", "PAGE"))
    }

    @Test
    fun theSimpleWordsAreHeldExactly() {
        val expected = mapOf(
            "deckmenu_manage" to "MANAGE", "deckmenu_exit_manage" to "EXIT MANAGE", "deckmenu_ui_color" to "UI COLOR", "deckmenu_continue" to "[CONTINUE]", "deckmenu_cancel" to "[CANCEL]",
            "deckmenu_final_title" to "FINAL CONFIRMATION", "deckmenu_delete_permanently" to "[DELETE PERMANENTLY]", "manual_close" to "[CLOSE]",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theRowsHoldTheirWordsOnce_andADecksNameIsShownExactlyAsSaved_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val system = DeckMenuText.systemDefaultRow(f, "MMM")
            assertEquals("$tag: the Matrix word once in '$system'", 1, count(system, "MMM"))
            assertTrue("$tag: it keeps the app's // between the two parts: $system", system.contains(" // "))
            assertNotEquals("$tag: still English", "SYSTEM DEFAULT // MMM", system)
            for (name in awkwardNames) {
                assertEquals("$tag", "$name // TTT", DeckMenuText.deckRow(name, "TTT"))
                assertEquals("$tag: the type word once in the edit title", 1, count(DeckMenuText.editTitle(f, "TTT"), "TTT"))
            }
            assertNotEquals("$tag: still English", "EDIT: TTT", DeckMenuText.editTitle(f, "TTT"))
        }
    }

    @Test
    fun theManageHintAndTheLockedNoticeHoldTheirWordsOnce_inAnyOrder_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val hint = DeckMenuText.manageHint(f, "DDD")
            assertEquals("$tag: the DECK word once in '$hint'", 1, count(hint, "DDD"))
            assertNotEquals("$tag: still English", "SELECT A DDD TO RENAME, RECOLOR, OR DELETE", hint)
            for ((which, line) in listOf("title" to DeckMenuText.lockedTitle(f, "MMM", "DDD"), "body" to DeckMenuText.lockedBody(f, "MMM", "DDD"))) {
                assertEquals("$tag/$which: the Matrix word once in '$line'", 1, count(line, "MMM"))
                assertEquals("$tag/$which: the DECK word once in '$line'", 1, count(line, "DDD"))
                assertFalse("$tag/$which: a placeholder leaked: $line", line.contains("%"))
            }
            assertNotEquals("$tag: the title and the body are two sentences", DeckMenuText.lockedTitle(f, "MMM", "DDD"), DeckMenuText.lockedBody(f, "MMM", "DDD"))
            assertNotEquals("$tag: still English", "THE PERMANENT MMM DDD CANNOT BE EDITED OR DELETED.", DeckMenuText.lockedBody(f, "MMM", "DDD"))
        }
    }

    @Test
    fun theLockedAndEditTagsDifferAndAreBracketed_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val locked = DeckMenuText.rowTag(f, locked = true)
            val edit = DeckMenuText.rowTag(f, locked = false)
            assertNotEquals("$tag: LOCKED and EDIT read the same", locked, edit)
            for (line in listOf(locked, edit)) assertTrue("$tag: bracketed: $line", line.startsWith("[") && line.endsWith("]"))
            assertNotEquals("$tag: still English", "[LOCKED]", locked)
        }
    }

    @Test
    fun theFirstQuestionMarksTheDeckAndNamesItExactlyAsSaved_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            for (name in awkwardNames) {
                val question = DeckMenuText.deleteQuestion(f, name)
                assertEquals("$tag: '$name' once in '$question'", 1, count(question, name))
                assertFalse("$tag: a placeholder leaked for '$name'", question.replace(name, "").contains("%"))
                assertTrue("$tag: it is a question: $question", question.trimEnd().endsWith("?") || question.trimEnd().endsWith("؟"))
            }
            val title = DeckMenuText.deleteTitle(f, "DDD")
            assertEquals("$tag: the DECK word once in '$title'", 1, count(title, "DDD"))
            assertNotEquals("$tag: still English", "CONFIRM DDD DELETION", title)
        }
    }

    @Test
    fun theFinalQuestionNamesTheDeckAndWhatIsLost_andTheGifSentenceIsSaidForAGifDeckOnly_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            for (name in awkwardNames) {
                val plain = DeckMenuText.finalConfirmation(f, name, "DDD", isGifDeck = false, words = marked)
                val gif = DeckMenuText.finalConfirmation(f, name, "DDD", isGifDeck = true, words = marked)
                assertEquals("$tag: '$name' once in '${plain.question}'", 1, count(plain.question, name))
                assertFalse("$tag: a placeholder leaked", plain.question.replace(name, "").contains("%"))
                assertTrue("$tag: a question: ${plain.question}", plain.question.trimEnd().endsWith("?") || plain.question.trimEnd().endsWith("؟"))
                assertNull("$tag: no GIF sentence for another deck", plain.gifWarning)
                assertNotNull("$tag: the GIF sentence for a GIF deck", gif.gifWarning)
                assertEquals("$tag: the same question and the same loss either way", plain.question, gif.question)
                assertEquals("$tag", plain.removes, gif.removes)
            }
            val gif = DeckMenuText.finalConfirmation(f, "N", "DDD", isGifDeck = true, words = marked)
            assertEquals("$tag: the DECK word once in '${gif.removes}'", 1, count(gif.removes, "DDD"))
            assertEquals("$tag: the DECK word once in '${gif.gifWarning}'", 1, count(gif.gifWarning!!, "DDD"))
            // "GIF files" names the file kind: Latin in es, pt and af, the label's own script in hi and ar (as the GIF deck's own sentences do).
            val kind = mapOf("hi" to "जीआईएफ", "ar" to "جيف").getOrDefault(tag, "GIF")
            assertTrue("$tag: the GIF sentence names the file kind '$kind': ${gif.gifWarning}", gif.gifWarning!!.contains(kind))
            assertNotEquals("$tag: the two questions are different", DeckMenuText.deleteQuestion(f, "N"), gif.question)
            assertNotEquals("$tag: the loss sentence is not English", "THIS REMOVES THE DDD AND ITS LOCAL CONFIGURATION.", gif.removes)
            assertNotEquals("$tag: the GIF sentence is not English", "GIF FILES BELONGING TO THIS DDD WILL ALSO BE REMOVED.", gif.gifWarning)
            assertNotEquals("$tag: the two sentences differ", gif.removes, gif.gifWarning)
        }
    }

    @Test
    fun theFinalDialogAlwaysSaysItCannotBeUndoneAndWhatToBackUpFirst_aGifDeckBeingPointedAtItsOwnBackupMenu_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val cannotUndo = map.getValue("storage_cannot_undo")
            val plain = DeckMenuText.finalConfirmation(f, "N", "DDD", isGifDeck = false, words = marked).backupAdvice
            val gif = DeckMenuText.finalConfirmation(f, "N", "DDD", isGifDeck = true, words = marked).backupAdvice
            for ((which, advice) in listOf("deck" to plain, "gif" to gif)) {
                assertTrue("$tag/$which: it says it cannot be undone first: $advice", advice.startsWith(cannotUndo + " "))
                assertFalse("$tag/$which: a placeholder leaked: $advice", advice.contains("%"))
                assertFalse("$tag/$which: no double space where the sentences join: $advice", advice.contains("  "))
                assertTrue("$tag/$which: more than the warning: $advice", advice.length > cannotUndo.length + 8)
            }
            // A deck's configuration is in EXPORT .JSON, so that is the advice; a GIF deck's files are not, so it is the GIF screen's BACKUP menu and never EXPORT .JSON.
            assertEquals("$tag: the export label once", 1, count(plain, "XJX"))
            for (gifWord in listOf("EEE", "MMM", "GGG")) assertEquals("$tag: no GIF word in the other advice ($gifWord)", 0, count(plain, gifWord))
            for (gifWord in listOf("EEE", "MMM", "GGG")) assertEquals("$tag: the GIF word once ($gifWord) in '$gif'", 1, count(gif, gifWord))
            assertEquals("$tag: not EXPORT .JSON for a GIF deck", 0, count(gif, "XJX"))
            assertNotEquals("$tag: the two pieces of advice differ", plain, gif)
            assertNotEquals("$tag: still English", "THIS CANNOT BE UNDONE. BACK UP FIRST WITH XJX.", plain)
            assertNotEquals("$tag: still English", "THIS CANNOT BE UNDONE. TO KEEP THE GIF FILES, FIRST USE MMM, THEN EEE, ON THE GGG SCREEN.", gif)
            assertNotEquals("$tag: the cannot-undo sentence is not English", "THIS CANNOT BE UNDONE.", cannotUndo)
            // The GIF advice names the order: the BACKUP menu is opened before its export entry.
            assertTrue("$tag: BACKUP is named before the export entry in '$gif'", gif.indexOf("MMM") < gif.indexOf("EEE") || tag == "ar")
        }
    }

    @Test
    fun theWordsOfTheDeletionDialogsThatAnswerDifferentQuestionsDifferInEveryLanguage_andEveryButtonIsBracketed() {
        val pairs = listOf(
            "deckmenu_continue" to "deckmenu_cancel", "deckmenu_continue" to "deckmenu_delete_permanently", "deckmenu_cancel" to "deckmenu_delete_permanently",
            "deckmenu_manage" to "deckmenu_exit_manage", "deckmenu_final_title" to "deckmenu_delete_title", "deckmenu_locked_tag" to "deckmenu_edit_tag", "deckmenu_ui_color" to "deckmenu_manage",
        )
        for ((tag, map) in translations) {
            for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
            for (name in listOf("deckmenu_continue", "deckmenu_cancel", "deckmenu_delete_permanently", "manual_close", "deckmenu_locked_tag", "deckmenu_edit_tag")) {
                assertTrue("$tag/$name: in brackets", map.getValue(name).startsWith("[") && map.getValue(name).endsWith("]"))
            }
            // The destructive button is not the plain word for deleting: it says permanently (or, in the languages that do, for good).
            assertNotEquals("$tag: [DELETE PERMANENTLY] is not just DELETE", "[" + map.getValue("common_delete") + "]", map.getValue("deckmenu_delete_permanently"))
        }
    }

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        val expected = mapOf(
            "deckmenu_system_default" to "%1\$s", "deckmenu_manage_hint" to "%1\$s", "deckmenu_locked_title" to "%1\$s %2\$s", "deckmenu_locked_body" to "%1\$s %2\$s", "deckmenu_edit_title" to "%1\$s",
            "deckmenu_delete_title" to "%1\$s", "deckmenu_delete_question" to "%1\$s", "deckmenu_final_question" to "%1\$s", "deckmenu_final_removes" to "%1\$s", "deckmenu_final_gif" to "%1\$s", "deckmenu_final_backup" to "%1\$s", "deckmenu_final_backup_gif" to "%1\$s %2\$s %3\$s",
            "deckmenu_manage" to "", "deckmenu_exit_manage" to "", "deckmenu_locked_tag" to "", "deckmenu_edit_tag" to "", "deckmenu_ui_color" to "", "deckmenu_continue" to "", "deckmenu_cancel" to "",
            "deckmenu_final_title" to "", "deckmenu_delete_permanently" to "", "manual_close" to "",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for ((name, args) in expected) {
                val found = Regex("""%\d\$[sd]""").findAll(map.getValue(name)).map { it.value }.toList()
                assertEquals("$tag/$name: each argument once", args.split(" ").filter { it.isNotEmpty() }.toSet(), found.toSet())
                assertEquals("$tag/$name: no argument twice", found.size, found.toSet().size)
            }
        }
    }
}
