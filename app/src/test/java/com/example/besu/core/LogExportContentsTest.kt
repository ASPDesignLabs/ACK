// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What SAVE MESSAGE LOG TO A FILE says before it saves anything and after (core/LogExportContents.kt), in English and in every language.
 */
class LogExportContentsTest {

    private val everyResource = listOf(
        LogExportContents.BUTTON, "log_export_button_desc", LogExportContents.CONTAINS_HEADING, "log_export_cat_messages", "log_export_cat_names",
        LogExportContents.NOT_INCLUDED, LogExportContents.COPY_TOO, "log_export_count_line", LogExportContents.NONE_NOW, LogExportContents.DONE,
        "log_export_failed", LogExportContents.FAIL_PREPARE, LogExport.FILE_TITLE, "log_export_saved_at", "log_export_summary", LogExport.FILE_WARNING,
        LogExport.ESCAPES, LogExport.COLUMNS,
    )

    @Test
    fun theWarningDialogIsExactlyThisInEnglish() {
        val expected = listOf(
            "MESSAGES IN THE LOG NOW: 3",
            "",
            "THE FILE WILL CONTAIN:",
            "- EVERY MESSAGE STILL KEPT IN TERMINAL LOG, IN FULL, WITH ITS DATE, TIME AND WHERE IT WAS SENT FROM",
            "- WHATEVER WAS IN THOSE MESSAGES, SUCH AS NAMES, ADDRESSES OR NUMBERS, IF YOU USED THEM",
            "NOT IN THE FILE: SYSTEM LINES, COMMANDS, PEOPLE AND PLACES, VOICE AUDIO AND SETTINGS.",
            "",
            "IT IS NOT ENCRYPTED AND HAS NO PASSWORD. ANYONE WHO OPENS IT CAN READ ALL OF IT.",
            "A SCREENSHOT OR PHOTO OF THE LOG IS A COPY TOO.",
            "",
            "SAVE IT WHERE YOU CONTROL WHO CAN SEE IT: THIS PHONE'S OWN STORAGE, OR YOUR OWN COMPUTER BY CABLE. AVOID GOOGLE DRIVE, ONEDRIVE AND OTHER ONLINE FOLDERS. THEIR APP WOULD UPLOAD IT.",
        ).joinToString("\n")
        assertEquals(expected, LogExportContents.dialogText(EnglishText, "TERMINAL LOG", 3))
    }

    @Test
    fun theTwoSafetySentencesAreTheExportJsonWarningsOwn_soTheTwoWarningsNeverDisagree() {
        assertEquals(ExportContents.NOT_PROTECTED, LogExportContents.NOT_PROTECTED)
        assertEquals(ExportContents.WHERE_TO_SAVE, LogExportContents.WHERE_TO_SAVE)
        for (tag in StringsXml.translations().keys) {
            val words = FileText(tag)
            val dialog = LogExportContents.dialogText(words, "LOG", 1)
            assertTrue("$tag: not-protected sentence", dialog.contains(words.get(ExportContents.NOT_PROTECTED)))
            assertTrue("$tag: where-to-save sentence", dialog.contains(words.get(ExportContents.WHERE_TO_SAVE)))
        }
    }

    @Test
    fun itSaysWhatIsInTheFile_whatIsNot_thatItIsNotProtected_andThatAScreenshotIsACopy() {
        val d = LogExportContents.dialogText(EnglishText, "TERMINAL LOG", 5)
        for (fact in listOf("EVERY MESSAGE", "IN FULL", "DATE, TIME", "NAMES, ADDRESSES OR NUMBERS", "NOT IN THE FILE", "SYSTEM LINES", "VOICE AUDIO", "NOT ENCRYPTED", "NO PASSWORD", "SCREENSHOT OR PHOTO")) {
            assertTrue("the warning must say '$fact'", d.contains(fact))
        }
    }

    @Test
    fun theLogsNameIsHandedInSoItFollowsPlainWords_andIsShownAsItIs() {
        val plain = LogExportContents.dialogText(EnglishText, "HISTORY", 2)
        assertTrue(plain.contains("KEPT IN HISTORY,"))
        assertFalse(plain.contains("TERMINAL LOG"))
        assertEquals("SAVES THE MESSAGES IN HISTORY TO A FILE YOU CHOOSE. YOU SEE WHAT IT HOLDS BEFORE YOU PICK WHERE TO SAVE IT.", LogExportContents.buttonDescription(EnglishText, "HISTORY"))
        val odd = "50% %s \$1 \"Q\""
        assertTrue(LogExportContents.dialogText(EnglishText, odd, 1).contains(odd))
        assertTrue(LogExportContents.buttonDescription(EnglishText, odd).contains(odd))
    }

    @Test
    fun theCountIsHandedInAsText_soItIsLatinDigitsWhateverThePhoneIsSetTo() {
        val saved = Locale.getDefault()
        try {
            for (locale in listOf(Locale("ar", "SA"), Locale("hi", "IN"), Locale("fa", "IR"))) {
                Locale.setDefault(locale)
                assertEquals("MESSAGES IN THE LOG NOW: 1234567", LogExportContents.countLine(EnglishText, 1234567))
                assertEquals("MESSAGES IN THE LOG NOW: 0", LogExportContents.countLine(EnglishText, 0))
                for (tag in StringsXml.translations().keys) {
                    val line = LogExportContents.countLine(FileText(tag), 42)
                    assertTrue("$tag: '$line'", line.contains("42"))
                }
            }
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun theWordsAfterwardsSayWhatHappened_andAFailureSaysNothingWasSaved() {
        assertEquals("MESSAGE LOG SAVED", LogExportContents.doneText(EnglishText))
        assertEquals("SAVING THE MESSAGE LOG FAILED: THE FILE COULD NOT BE OPENED. NOTHING WAS SAVED.", LogExportContents.failedText(EnglishText, "backup_fail_open"))
        assertTrue(LogExportContents.failedText(EnglishText, LogExportContents.FAIL_PREPARE).contains("NOTHING WAS SAVED"))
        assertEquals("THE LOG HAS NO MESSAGES TO SAVE RIGHT NOW.", EnglishText.get(LogExportContents.NONE_NOW))
    }

    @Test
    fun theEnglishIsInCapitalsLikeTheRestOfTheApp_exceptTheFileExplanationWhichNamesEscapes() {
        for (name in everyResource - setOf(LogExport.ESCAPES)) {
            val text = EnglishText.get(name, "X", "Y", "Z")
            assertEquals("$name", text.uppercase(), text)
        }
    }

    @Test
    fun everyLanguageHasEveryWordAndNoneIsEnglishOrBlank() {
        for (tag in StringsXml.translations().keys) {
            val words = FileText(tag)
            for (name in everyResource) {
                val text = words.get(name, "X", "Y", "Z")
                assertTrue("$tag/$name is missing", text != name)
                assertTrue("$tag/$name is blank", text.isNotBlank())
                assertNotEquals("$tag/$name is still English", EnglishText.get(name, "X", "Y", "Z"), text)
            }
        }
    }

    @Test
    fun everyLanguageHoldsTheLogsNameAndTheCountInWhateverOrderItNeeds() {
        for (tag in StringsXml.translations().keys) {
            val words = FileText(tag)
            val contains = LogExportContents.contains(words, "LOG-NAME")
            assertEquals(2, contains.size)
            assertTrue("$tag: the log's name is missing from the first bullet", contains[0].contains("LOG-NAME"))
            assertTrue("$tag: the log's name is missing from the button's line", LogExportContents.buttonDescription(words, "LOG-NAME").contains("LOG-NAME"))
        }
    }

    @Test
    fun theLatinDraftsKeepTheAppsCapitalsStyle() {
        for (tag in listOf("es", "pt", "af")) {
            val words = FileText(tag)
            for (name in everyResource - setOf(LogExport.ESCAPES)) {
                val text = words.get(name, "X", "Y", "Z")
                assertEquals("$tag/$name", text.uppercase(), text)
            }
        }
    }
}
