// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** What the usage summary says (core/UsageSummaryText.kt), in English and in every language. */
class UsageSummaryTextTest {

    private val english = StringsXml.map(StringsXml.default)
    private val translations = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private fun words(tag: String): TextSource = if (tag == "en") EnglishText else FileText(tag)
    private val languages = listOf("en") + StringsXml.translations().keys

    /** Every `usage_*` string this feature adds, from the English file. */
    private val usageNames = english.keys.filter { it.startsWith("usage_") }

    // ---- English, exactly ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theSectionsWordsAreExactlyThisInEnglish() {
        val t = EnglishText
        assertEquals("USAGE SUMMARY", t.get(UsageSummaryText.TITLE))
        assertEquals("COUNTS HOW OFTEN AND WHEN MESSAGES ARE SENT, KEPT ON THIS PHONE FOR 90 DAYS. IT NEVER HOLDS THE WORDS OF A MESSAGE. IT IS OFF UNTIL YOU TURN IT ON.", UsageSummaryText.explanation(t))
        assertEquals("USAGE SUMMARY: ON", UsageSummaryText.switchLabel(t, true))
        assertEquals("USAGE SUMMARY: OFF", UsageSummaryText.switchLabel(t, false))
        assertEquals("MESSAGES COUNTED: 1234", UsageSummaryText.totalLine(t, 1234))
        assertEquals("THE LAST 14 DAYS", UsageSummaryText.headDays(t))
        assertEquals("YES: 12", UsageSummaryText.row(t, "YES", 12))
        assertEquals("07:00", UsageSummaryText.hourLabel(7))
        assertEquals("00:00", UsageSummaryText.hourLabel(0))
        assertEquals("23:00", UsageSummaryText.hourLabel(23))
        assertEquals("USAGE SUMMARY IS ON: ACK COUNTS HOW OFTEN AND WHEN MESSAGES ARE SENT, NEVER THE WORDS.", UsageSummaryText.terminalLine(t))
    }

    @Test
    fun theFirstTimeQuestionSaysWhatIsCounted_whatNeverIs_andWhereItStays() {
        val q = UsageSummaryText.onQuestion(EnglishText)
        assertEquals(3, q.size)
        assertEquals("IT WILL COUNT HOW MANY MESSAGES ARE SENT IN EACH HOUR OF EACH DAY, BY WHERE THEY CAME FROM AND BY KIND (YES, NO, HELP AND SO ON).", q[0])
        assertEquals("IT WILL NEVER KEEP THE WORDS OF A MESSAGE, A NAME, A PLACE OR ANY AUDIO. A MESSAGE SENT WITH /n IS NOT COUNTED AT ALL.", q[1])
        assertEquals("THE COUNTS STAY ON THIS PHONE FOR 90 DAYS AND ARE NOT IN ANY BACKUP. WHILE IT IS ON, THE TERMINAL SHOWS A LINE SAYING SO. YOU CAN SAVE IT TO A FILE OR FORGET IT AT ANY TIME.", q[2])
        assertEquals("TURN ON USAGE SUMMARY?", EnglishText.get(UsageSummaryText.ON_TITLE))
        assertEquals("TURN ON", EnglishText.get(UsageSummaryText.ON_CONFIRM))
    }

    @Test
    fun theSaveWarningIsExactlyThisInEnglish() {
        val expected = listOf(
            "MESSAGES THE FILE WOULD COUNT: 42",
            "",
            "THE FILE WILL CONTAIN:",
            "- HOW MANY MESSAGES WERE SENT IN EACH HOUR OF EACH DAY, BY WHERE THEY CAME FROM AND BY KIND",
            "NOT IN THE FILE: ANY WORDS, NAMES, PLACES OR AUDIO.",
            "IT STILL SHOWS WHEN SOMEONE COMMUNICATES, WHICH IS A DAILY PATTERN. KEEP IT LIKE A DIARY.",
            "",
            "IT IS NOT ENCRYPTED AND HAS NO PASSWORD. ANYONE WHO OPENS IT CAN READ ALL OF IT.",
            "A SCREENSHOT OR PHOTO OF THIS SCREEN IS A COPY TOO.",
            "",
            "SAVE IT WHERE YOU CONTROL WHO CAN SEE IT: THIS PHONE'S OWN STORAGE, OR YOUR OWN COMPUTER BY CABLE. AVOID GOOGLE DRIVE, ONEDRIVE AND OTHER ONLINE FOLDERS. THEIR APP WOULD UPLOAD IT.",
        ).joinToString("\n")
        assertEquals(expected, UsageSummaryText.saveDialogText(EnglishText, 42))
    }

    @Test
    fun forgettingAsksTwice_firstToSaveItToAFile_thenWhatWillBeDeleted() {
        assertEquals("THIS DELETES EVERY COUNT. IT CANNOT BE UNDONE AND IT IS NOT IN ANY BACKUP. IF YOU MIGHT WANT IT, USE SAVE USAGE SUMMARY TO A FILE FIRST.",
            UsageSummaryText.forgetFirst(EnglishText, EnglishText.get(UsageSummaryText.SAVE_BUTTON)))
        assertEquals("1234 MESSAGES COUNTED OVER UP TO 90 DAYS WILL BE DELETED. A FILE YOU SAVED EARLIER IS NOT DELETED.", UsageSummaryText.forgetFinal(EnglishText, 1234))
        assertEquals("FORGET USAGE SUMMARY?", EnglishText.get(UsageSummaryText.FORGET_TITLE))
        assertEquals("DELETE EVERY COUNT FOR GOOD?", EnglishText.get(UsageSummaryText.FORGET_FINAL_TITLE))
        assertEquals("DELETE PERMANENTLY", EnglishText.get(UsageSummaryText.FORGET_DELETE))
    }

    @Test
    fun theResultWordsSayWhatHappened_andAFailureSaysNothingWasSaved() {
        assertEquals("USAGE SUMMARY SAVED", UsageSummaryText.saveDone(EnglishText))
        assertEquals("SAVING THE USAGE SUMMARY FAILED: THE FILE COULD NOT BE OPENED. NOTHING WAS SAVED.", UsageSummaryText.saveFailed(EnglishText, "backup_fail_open"))
        assertTrue(UsageSummaryText.saveFailed(EnglishText, UsageSummaryText.SAVE_FAIL_PREPARE).contains("NOTHING WAS SAVED"))
        assertEquals("NOTHING HAS BEEN COUNTED, SO THERE IS NOTHING TO SAVE.", EnglishText.get(UsageSummaryText.SAVE_NONE))
    }

    // ---- never more than it does ---------------------------------------------------------------------------------------------------------

    @Test
    fun theWordsNeverClaimTheSummaryShowsAnEffectOrUnderstanding() {
        val all = usageNames.joinToString(" ") { EnglishText.get(it, "1", "2", "3", "4") }
        for (word in listOf("PROVEN", "EFFECTIVE", "IMPROVE", "PROGRESS", "OUTCOME", "CLINICAL", "UNDERSTOOD", "SUCCESS", "TREATMENT")) {
            assertFalse("the summary's words must not say '$word'", all.contains(word))
        }
    }

    @Test
    fun theSummaryAlwaysSaysItNeverKeepsTheWords_inEveryString_thatPromisesIt() {
        for (name in listOf("usage_explanation", "usage_terminal_line", "usage_on_never", "usage_file_warning", "usage_save_not_included")) {
            assertTrue("$name", EnglishText.get(name, "90").contains("WORDS") || EnglishText.get(name).contains("WORDS"))
        }
    }

    // ---- every language -----------------------------------------------------------------------------------------------------------------

    @Test
    fun everyLanguageHasEveryUsageString_andNoneIsEnglishOrBlank() {
        val ownNames = usageNames + listOf("area_usage_summary_label", "area_usage_summary_holds", "area_usage_summary_backup")
        // The few that read the same as English on purpose, each only in the languages that really write it that way (TranslationsTest and TrainingTextTest hold the same list).
        val sameOnPurpose = mapOf(
            "usage_row" to translations.keys, // only placeholders: the words come in as arguments
            "usage_kind_help" to setOf("af"), // HELP is the Afrikaans word too
            "usage_kind_no" to setOf("es"), // NO is Spanish for no
            "usage_kind_social" to setOf("es", "pt"), // SOCIAL is the same word in Spanish and Portuguese
        )
        for ((tag, map) in translations) for (name in ownNames) {
            val text = map[name]
            assertTrue("$tag/$name is missing", text != null)
            assertTrue("$tag/$name is blank", text!!.isNotBlank())
            if (tag !in (sameOnPurpose[name] ?: emptySet())) assertNotEquals("$tag/$name is still English", english.getValue(name), text)
        }
    }

    @Test
    fun everyKindAndEveryChannelHasANameInEveryLanguage_andTheNamesInOneListAreDifferent() {
        for (tag in languages) {
            val t = words(tag)
            val kinds = UsageKind.values().map { UsageSummaryText.kindName(t, it) }
            val channels = UsageChannel.values().map { UsageSummaryText.channelName(t, it) }
            assertEquals("$tag: two kinds share a name: $kinds", kinds.size, kinds.toSet().size)
            assertEquals("$tag: two channels share a name: $channels", channels.size, channels.toSet().size)
            for (name in UsageSummaryText.kindResources + UsageSummaryText.channelResources) assertTrue("$tag/$name", t.get(name) != name)
        }
        assertEquals("YES", UsageSummaryText.kindName(EnglishText, UsageKind.YES))
        assertEquals("ASK TO REPEAT", UsageSummaryText.kindName(EnglishText, UsageKind.REPAIR))
        assertEquals("ASK TO WAIT", UsageSummaryText.kindName(EnglishText, UsageKind.TURN_HOLDING))
        assertEquals("MATRIX DECK", UsageSummaryText.channelName(EnglishText, UsageChannel.MATRIX))
        assertEquals("TYPED AT THE TERMINAL", UsageSummaryText.channelName(EnglishText, UsageChannel.TERMINAL))
    }

    @Test
    fun theEnglishIsInCapitalsLikeTheRestOfTheApp_exceptWhereATypedCommandIsNamed() {
        // /n is a typed command and stays as typed, so the one string that names it is mixed case, in English and in every language.
        for (name in usageNames.filter { it != "usage_on_never" }) {
            val text = EnglishText.get(name, "1", "2", "3", "4")
            assertEquals(name, text.uppercase(), text)
        }
        for (name in UsageSummaryText.kindResources + UsageSummaryText.channelResources) assertEquals(name, EnglishText.get(name).uppercase(), EnglishText.get(name))
    }

    @Test
    fun theTypedCommandSlashNIsKeptExactlyInEveryLanguage_inTheSentenceThatNamesIt() {
        for (tag in languages) {
            val text = UsageSummaryText.onQuestion(words(tag))[1]
            assertTrue("$tag: /n must be there as typed: $text", Regex("""(?<![A-Za-z0-9_])/n(?![A-Za-z0-9_])""").containsMatchIn(text))
        }
    }

    @Test
    fun theRetentionDaysAreHandedInAsTheConstant_soNoTextCanDisagreeWithTheRule() {
        for (tag in languages) {
            val t = words(tag)
            assertTrue("$tag explanation", UsageSummaryText.explanation(t).contains(UsageTally.RETENTION_DAYS.toString()))
            assertTrue("$tag stays", UsageSummaryText.onQuestion(t)[2].contains(UsageTally.RETENTION_DAYS.toString()))
            assertTrue("$tag final", UsageSummaryText.forgetFinal(t, 5).contains(UsageTally.RETENTION_DAYS.toString()))
            assertTrue("$tag head days", UsageSummaryText.headDays(t).contains(UsageTally.RECENT_DAYS.toString()))
        }
    }

    @Test
    fun theSaveButtonsNameIsHandedIntoTheFirstForgetQuestion_inEveryLanguage() {
        for (tag in languages) {
            val t = words(tag)
            assertTrue("$tag", UsageSummaryText.forgetFirst(t, "SAVE-BUTTON-NAME").contains("SAVE-BUTTON-NAME"))
            assertTrue("$tag: both numbers in the last question", UsageSummaryText.forgetFinal(t, 7777).contains("7777"))
        }
    }

    @Test
    fun theTwoSafetySentencesAboutAFileAreTheExportJsonWarningsOwn_inEveryLanguage() {
        assertEquals(ExportContents.NOT_PROTECTED, UsageSummaryText.NOT_PROTECTED)
        assertEquals(ExportContents.WHERE_TO_SAVE, UsageSummaryText.WHERE_TO_SAVE)
        for (tag in languages) {
            val t = words(tag)
            val dialog = UsageSummaryText.saveDialogText(t, 3)
            assertTrue("$tag", dialog.contains(t.get(ExportContents.NOT_PROTECTED)) && dialog.contains(t.get(ExportContents.WHERE_TO_SAVE)))
            assertTrue("$tag: a screenshot is a copy too", dialog.contains(t.get(UsageSummaryText.SAVE_COPY_TOO)))
            assertTrue("$tag: the daily pattern", dialog.contains(t.get(UsageSummaryText.SAVE_PATTERN)))
        }
    }

    @Test
    fun numbersAreLatinDigits_onAPhoneSetToArabicOrHindi_inEveryLine() {
        val saved = Locale.getDefault()
        try {
            for (locale in listOf(Locale("ar", "SA"), Locale("hi", "IN"), Locale("fa", "IR"))) {
                Locale.setDefault(locale)
                for (tag in languages) {
                    val t = words(tag)
                    val line = listOf(
                        UsageSummaryText.totalLine(t, 1234567), UsageSummaryText.row(t, "X", 89), UsageSummaryText.saveCountLine(t, 456),
                        UsageSummaryText.forgetFinal(t, 321), UsageSummaryText.explanation(t), UsageSummaryText.headDays(t),
                    ).joinToString(" ")
                    val digits = line.filter { it.isDigit() }
                    assertTrue("$locale/$tag: non-Latin digits in '$line'", digits.all { it in '0'..'9' })
                }
            }
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun theDeleteDataAreaIsNamedLikeTheSection_inEveryLanguage_andItsNotesHaveNoUnfilledPlaceholder() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertEquals("$tag: the area and the section read the same", map.getValue("usage_title"), map.getValue("area_usage_summary_label"))
            assertFalse("$tag: backup note", map.getValue("area_usage_summary_backup").contains("%"))
            assertFalse("$tag: holds", map.getValue("area_usage_summary_holds").contains("%"))
        }
    }

    @Test
    fun everyUsageStringIsUsedByTheCoreWords_andNoNameIsInventedThere() {
        val core = RepoFiles.read("app/src/main/java/com/example/besu/core/UsageSummaryText.kt") + RepoFiles.read("app/src/main/java/com/example/besu/core/UsageSummaryFile.kt")
        val used = Regex(""""(usage_[a-z_]+)"""").findAll(core).map { it.groupValues[1] }.toSet() +
            UsageSummaryText.kindResources + UsageSummaryText.channelResources
        val defined = usageNames.toSet()
        assertEquals("defined but never used: ${defined - used}; used but not defined: ${used - defined}", used, defined)
    }
}
