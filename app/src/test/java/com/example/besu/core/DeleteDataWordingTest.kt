// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The DELETE DATA wording (the areas, their two confirmations, the safety-copy dialogs and DELETE CUSTOM VOICE) reads its words from string resources, in
 * the chosen language. What is said after a delete is decided in core/StorageCatalogue.kt and tested here with the real English text; the screens cannot be
 * compiled here, so they are read: the old English literals are gone, every string they name exists and none is left unused, a toast reads its text through
 * the context, and a result is carried by area **id** so no decision depends on a translated word. The sentences that keep a delete safe are checked in every
 * language: they are present, they keep their placeholders, and the button names that are still English on their own screens are not translated away.
 */
class DeleteDataWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val english get() = StringsXml.map(StringsXml.default)
    private val englishPlurals get() = StringsXml.plurals(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val prefixes = listOf("area_", "storage_", "delete_data_", "safety_copy_", "delete_voice_")
    private fun isThisScreensName(name: String) = prefixes.any { name.startsWith(it) } || name == "common_continue"

    private fun allSources(): List<String> =
        RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" }.map { noComments(it.readText(Charsets.UTF_8)) }.toList()

    // ---- every string exists, none is unused -----------------------------------------------------------------------------------------

    @Test
    fun everyStringTheDeleteScreensNameExists_andNoneIsLeftUnused() {
        val referenced = allSources().flatMap {
            Regex("""R\.string\.((?:area|storage|delete_data|safety_copy|delete_voice)_[a-z0-9_]+|common_continue)""").findAll(it).map { m -> m.groupValues[1] }.toList()
        }.toSet()
        // The decisions name theirs as plain strings (resource names read through a TextSource); an area's three are built from its id.
        val named = listOf("core/StorageCatalogue.kt", "core/SafetyCopyPolicy.kt").flatMap {
            Regex(""""((?:area|storage|delete_data|safety_copy|delete_voice)_[a-z0-9_]+|common_continue)"""").findAll(noComments(source(it))).map { m -> m.groupValues[1] }.toList()
        }.toSet() + StorageCatalogue.areas.flatMap { listOf(it.labelResource, it.holdsResource, it.backupResource) }
        val used = referenced + named
        val defined = english.keys.filter { isThisScreensName(it) }.toSet() + englishPlurals.keys.filter { isThisScreensName(it) }
        assertEquals("named but not defined: ${used - defined}", emptySet<String>(), used - defined)
        assertTrue("defined but never used: ${defined - used}", (defined - used).isEmpty())
    }

    // ---- the old English literals are gone -------------------------------------------------------------------------------------------

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheDeleteScreens() {
        val gone = mapOf(
            "settings/ManageDataDialog.kt" to listOf(
                "THIS CANNOT BE UNDONE", "\"DELETE DATA\"", "\"CLOSE\"", "\"CANCEL\"", "\"CONTINUE\"", "\"BACK UP FIRST\"", "\"DELETING...\"", "\"DELETE EVERYTHING\"", "\"DELETE\"",
                "\"DELETE \${", "EACH DELETE ASKS TWICE", "STILL COUNTING", "\"DELETED: ", "COULD NOT DELETE", "GOOGLE'S LOCATION SERVICE", "ACK DID NOT RESTART",
                "ALL OF THE ABOVE", "area.label", "area.holds",
            ),
            "settings/SafetyCopyDialogs.kt" to listOf("THIS CANNOT BE UNDONE", "\"DELETE SAFETY COPY\"", "\"CANCEL\"", "\"EXPORT FIRST\"", "\"DELETE COPY\""),
            "settings/DeleteVoiceDialogs.kt" to listOf(
                "\"CANCEL\"", "\"CONTINUE\"", "\"DELETE VOICE\"", "\"EXPORT VOICE BACKUP FIRST\"", "THIS REMOVES YOUR TRAINED VOICE", "THE ONLY COPY MAY BE",
                "THESE VOICES USE IT", "YOUR ACTIVE VOICE WILL BECOME", "THIS DOES NOT DELETE A BACKUP", "THIS CANNOT BE UNDONE",
            ),
            "settings/AudioView.kt" to listOf(
                "\"VOICE BACKUP SAVED.\"", "VOICE BACKUP FAILED. NOTHING WAS DELETED", "\"VOICE BACKUP EXPORTED\"", "\"EXPORT FAILED\"", "\"CUSTOM VOICE DELETED\"",
                "VOICE REMOVED, BUT SOME FILES", "\"COULD NOT DELETE THE VOICE\"",
            ),
            "settings/SettingsView.kt" to listOf(
                "\"DELETE DATA\"", "\"SAFETY COPY DELETED\"", "COULD NOT DELETE THE SAFETY COPY", "\"DATA DELETED -- RESTARTING\"",
            ),
            "data/DataWipe.kt" to listOf("DATA DELETED:", "DATA DELETE INCOMPLETE", "area.label"),
            "core/StorageCatalogue.kt" to listOf(
                "THIS DELETES", "STORED NOW", "NOTHING STORED", "UNDER 1 KB", "THIS CANNOT BE UNDONE", "A PAIRED WATCH", "ACK WILL RESTART", "THIS DOES NOT DELETE FILES",
                "MESSAGES AND DECKS", "EMERGENCY INFO CARD", "AFTERWARDS", "IT IS IN EXPORT .JSON", "\"SAFETY COPIES\"", "\"TERMINAL LOG\"",
            ),
            "core/SafetyCopyPolicy.kt" to listOf("DELETE ANYWAY", "\"CONTINUE\"", "ACK MADE A PRIVATE SAFETY COPY", "YOU HAVE SAVED AN EXPORT", "\"d MMM yyyy\", Locale.ENGLISH"),
        )
        for ((file, literals) in gone) {
            val text = noComments(source(file))
            for (literal in literals) assertFalse("$file still holds $literal", text.contains(literal))
        }
    }

    // ---- what is said after a delete (areas by id, English text read through the real strings) ----------------------------------------

    private val deletedIds = listOf(StorageCatalogue.ID_SETTINGS)
    private val failedIds = listOf(StorageCatalogue.ID_TERMINAL_LOG, StorageCatalogue.ID_SAVED_LOCATIONS)

    @Test
    fun aDeleteThatDidNotAllGoThroughSaysWhichAreasFailed_whichWereDeleted_andThatAckDidNotRestart() {
        assertEquals(
            "COULD NOT DELETE: TERMINAL LOG, SAVED LOCATIONS. DELETED: SETTINGS. " +
                "SAVED LOCATIONS: GOOGLE'S LOCATION SERVICE MUST CONFIRM ITS ALERTS ARE REMOVED FIRST. TRY AGAIN, OR TURN GEO-PROTOCOL OFF FIRST. " +
                "ACK DID NOT RESTART. CLOSE AND REOPEN IT TO SEE ALL CHANGES.",
            StorageCatalogue.failureStatus(EnglishText, deletedIds, failedIds),
        )
    }

    @Test
    fun theGoogleNoteAppearsOnlyWhenSavedLocationsFailed() {
        val withoutIt = StorageCatalogue.failureStatus(EnglishText, deletedIds, listOf(StorageCatalogue.ID_TERMINAL_LOG))
        assertEquals("COULD NOT DELETE: TERMINAL LOG. DELETED: SETTINGS. ACK DID NOT RESTART. CLOSE AND REOPEN IT TO SEE ALL CHANGES.", withoutIt)
        assertFalse(withoutIt.contains("GOOGLE"))
        // Nothing was deleted: the DELETED sentence is left out rather than shown empty.
        val none = StorageCatalogue.failureStatus(EnglishText, emptyList(), listOf(StorageCatalogue.ID_TERMINAL_LOG))
        assertFalse(none.contains("DELETED:"))
    }

    @Test
    fun theSuccessAndLogLinesHaveTheirOldWords() {
        val two = listOf(StorageCatalogue.ID_TERMINAL_LOG, StorageCatalogue.ID_SAFETY_COPIES)
        assertEquals("DELETED: TERMINAL LOG, SAFETY COPIES.", StorageCatalogue.successStatus(EnglishText, two))
        assertEquals("DELETED: TERMINAL LOG, SAFETY COPIES", StorageCatalogue.successToast(EnglishText, two))
        assertEquals("DATA DELETED: TERMINAL LOG, SAFETY COPIES", StorageCatalogue.logLine(EnglishText, two, emptyList()))
        assertEquals("DATA DELETE INCOMPLETE. COULD NOT DELETE: SETTINGS", StorageCatalogue.logLine(EnglishText, emptyList(), listOf(StorageCatalogue.ID_SETTINGS)))
        assertEquals(
            "DATA DELETE INCOMPLETE. COULD NOT DELETE: SETTINGS. DELETED: TERMINAL LOG, SAFETY COPIES",
            StorageCatalogue.logLine(EnglishText, two, listOf(StorageCatalogue.ID_SETTINGS)),
        )
    }

    @Test
    fun theFirstConfirmationsParagraphsAreInTheOrderTheScreenRelies_theThirdIsTheBackupNote() {
        // ManageDataDialog bolds paragraph index 2 because it is always the backup note: how to save it first, or that it is not backed up.
        for (area in StorageCatalogue.areas) {
            val paragraphs = StorageCatalogue.firstConfirmation(EnglishText, area, "3 ITEMS, 12 KB")
            assertEquals(area.id, "THIS DELETES: ${StorageCatalogue.holds(EnglishText, area)}", paragraphs[0])
            assertEquals(area.id, "STORED NOW: 3 ITEMS, 12 KB.", paragraphs[1])
            assertEquals(area.id, StorageCatalogue.backupNote(EnglishText, area), paragraphs[2])
            assertEquals(area.id, EnglishText.get(StorageCatalogue.NOT_ELSEWHERE), paragraphs.last())
        }
        val everything = StorageCatalogue.firstConfirmationEverything(EnglishText, "X")
        assertTrue(everything[0].contains("ALL OF THE ${StorageCatalogue.areas.size} AREAS"))
        assertTrue(everything[2].startsWith("EXPORT .JSON DOES NOT COVER: "))
    }

    @Test
    fun aBackupNoteNamesTheExportButtonsThroughTheLabelTable_notAsALiteral() {
        // "EXPORT .JSON", "AUDIO ARCHITECT", "EXPORT VOICE BACKUP", "SAVE ALL TO A FILE" and "RECORD TRAINING DATA" are the names of buttons and screens that are
        // translated; the notes take them as arguments so a note and the button it points to cannot read differently in any language.
        for (name in english.keys.filter { it.startsWith("area_") && it.endsWith("_backup") } + "storage_everything_not_covered") {
            val text = english.getValue(name)
            assertFalse("$name holds the literal EXPORT .JSON", text.contains("EXPORT .JSON"))
            assertFalse("$name holds the literal AUDIO ARCHITECT", text.contains("AUDIO ARCHITECT"))
            assertFalse("$name holds the literal EXPORT VOICE BACKUP", text.contains("EXPORT VOICE BACKUP"))
            assertFalse("$name holds the literal SAVE ALL TO A FILE", text.contains("SAVE ALL TO A FILE"))
            assertFalse("$name holds the literal RECORD TRAINING DATA", text.contains("RECORD TRAINING DATA"))
        }
        assertFalse("the training-data area's holds line types the screen's name", english.getValue("area_training_data_holds").contains("RECORD TRAINING DATA"))
        assertEquals(listOf("%1\$s", "%4\$s", "%5\$s", "%1\$s"), StringsXml.placeholders(english.getValue("area_training_data_backup")))
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("area_training_data_holds")))
        assertEquals(listOf("%1\$s", "%3\$s", "%2\$s"), StringsXml.placeholders(english.getValue("area_trained_voice_backup")))
        assertEquals("IT IS NOT IN EXPORT .JSON. SAVE IT FIRST WITH EXPORT VOICE BACKUP (AUDIO ARCHITECT).",
            StorageCatalogue.backupNote(EnglishText, StorageCatalogue.area(StorageCatalogue.ID_TRAINED_VOICE)))
    }

    // ---- results are carried by id, never by a translated word ----------------------------------------------------------------------

    @Test
    fun aResultCarriesAreaIds_andNoDecisionComparesALabel() {
        val wipe = noComments(source("data/DataWipe.kt"))
        assertTrue(wipe.contains("(if (ok) deleted else failed).add(area.id)"))
        assertTrue(wipe.contains("val deletedIds = deleted.toSet()"))
        assertTrue(wipe.contains("StorageCatalogue.logLine(ResourceText(context), result.deleted, result.failed)"))
        val dialog = noComments(source("settings/ManageDataDialog.kt"))
        assertTrue(dialog.contains("StorageCatalogue.failureStatus(words, result.deleted, result.failed)"))
        assertFalse("a label is compared", dialog.contains("failed.contains("))
    }

    @Test
    fun theSecondConfirmationOfEveryDeleteSaysItCannotBeUndone_throughTheSharedSentence() {
        val sentence = "rememberText().get(StorageCatalogue.CANNOT_UNDO)"
        assertTrue(noComments(source("settings/ManageDataDialog.kt")).contains("words.get(StorageCatalogue.CANNOT_UNDO), bold = true, color = RadicalRed"))
        assertTrue(noComments(source("settings/SafetyCopyDialogs.kt")).contains(sentence))
        assertTrue(noComments(source("settings/DeleteVoiceDialogs.kt")).contains(sentence))
    }

    @Test
    fun backUpFirstIsOfferedOnlyWhereTheAreaCanBeBackedUpByExportJson_orForEverything() {
        val dialog = noComments(source("settings/ManageDataDialog.kt"))
        assertTrue(dialog.contains("if (everything || StorageCatalogue.offersBackupFirst(StorageCatalogue.area(first))) {"))
        assertTrue(dialog.contains("NeonButton(stringResource(R.string.delete_data_back_up_first)"))
    }

    // ---- toasts and non-composable code read through the context ---------------------------------------------------------------------

    @Test
    fun theToastsReadTheirTextThroughTheContext_becauseTheyAreNotInAComposableLambda() {
        val settings = noComments(source("settings/SettingsView.kt"))
        assertTrue(settings.contains("context.getString(if (gone) R.string.safety_copy_deleted else R.string.safety_copy_not_deleted)"))
        assertTrue(settings.contains("context.getString(R.string.delete_data_done_restarting)"))
        val audio = noComments(source("settings/AudioView.kt"))
        assertTrue(audio.contains("context.getString(if (success) R.string.delete_voice_backup_saved else R.string.delete_voice_backup_failed)"))
        assertTrue(audio.contains("context.getString(if (success) R.string.delete_voice_backup_toast_ok else R.string.delete_voice_backup_toast_failed)"))
        // Which message goes with which outcome: all three, in this order (an outcome must never be told as another).
        assertTrue(
            Regex("""when \{\s*allGone -> R\.string\.delete_voice_deleted\s*!stillUsable -> R\.string\.delete_voice_partly\s*else -> R\.string\.delete_voice_failed\s*\}""")
                .containsMatchIn(audio)
        )
        for (file in listOf(settings, audio)) assertFalse(Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(file))
        assertTrue("AudioView needs the explicit R import", audio.contains("import com.example.besu.R"))
    }

    @Test
    fun deletingTheVoiceStillSaysTheOnlyCopyMayBeOnThisPhone_andOffersABackupFirst() {
        val dialogs = noComments(source("settings/DeleteVoiceDialogs.kt"))
        for (name in listOf("delete_voice_only_copy", "delete_voice_export_first", "delete_voice_not_backup", "delete_voice_delete")) {
            assertTrue(name, dialogs.contains("R.string.$name"))
        }
        assertTrue(dialogs.contains("StorageCatalogue.CANNOT_UNDO"))
        // The profile that MY VOICE falls back to is a name shown as a name, not a word.
        assertTrue(dialogs.contains("stringResource(R.string.delete_voice_active_becomes, CustomVoiceRemoval.FALLBACK_PROFILE_ID)"))
    }

    @Test
    fun theLanguageTheDateIsWrittenInIsTheOneTheWordsAreIn() {
        // ResourceText says its language is the one ACK chose at startup, and ActiveScript keeps that tag (set once, with the script).
        assertTrue(noComments(source("data/ResourceText.kt")).contains("override val languageTag: String get() = ActiveScript.tag"))
        try {
            ActiveScript.use("es")
            assertEquals("es", ActiveScript.tag)
            ActiveScript.use("ar")
            assertEquals("ar", ActiveScript.tag)
            assertTrue(ActiveScript.joinsLetters)
        } finally {
            ActiveScript.use("en")
        }
        assertEquals("en", ActiveScript.tag)
        assertFalse(ActiveScript.joinsLetters)
    }

    // ---- the safety sentences hold in every language ------------------------------------------------------------------------------------

    @Test
    fun theSentencesThatKeepADeleteSafeAreInEveryLanguage_andKeepTheirPlaceholders() {
        val mustExist = listOf(
            "storage_cannot_undo", "storage_not_elsewhere", "storage_restart_note", "storage_watch_note", "delete_data_intro", "delete_voice_only_copy",
            "delete_voice_not_backup", "delete_voice_removes", "safety_copy_no_newer_export", "safety_copy_row", "area_after_defaults", "area_after_starters",
            "delete_data_not_restarted", "delete_voice_backup_failed",
        )
        for ((tag, map) in translations) {
            for (name in mustExist) {
                val text = map.getValue(name)
                assertTrue("$tag/$name is not a real sentence: $text", text.length >= 12)
                assertTrue("$tag/$name is still English", text != english.getValue(name))
            }
            // "the confirmation says which area" and "the count of areas" and "the profile it becomes" cannot lose their placeholder.
            assertTrue("$tag: delete_data_confirm_title", map.getValue("delete_data_confirm_title").contains("%1\$s"))
            assertTrue("$tag: storage_everything_deletes", map.getValue("storage_everything_deletes").contains("%1\$d"))
            assertTrue("$tag: delete_voice_active_becomes", map.getValue("delete_voice_active_becomes").contains("%1\$s"))
            assertTrue("$tag: safety_copy_row date and size", map.getValue("safety_copy_row").let { it.contains("%1\$s") && it.contains("%2\$s") })
            assertTrue("$tag: safety_copy_first date and size", map.getValue("safety_copy_first").let { it.contains("%1\$s") && it.contains("%2\$s") })
            assertTrue("$tag: delete_data_google_note names the area", map.getValue("delete_data_google_note").contains("%1\$s"))
        }
    }

    @Test
    fun anAreaThatEXPORTJSONCoversNamesItsButton_andOneItDoesNotCoverDoesNot_inEveryLanguage() {
        for (map in listOf(english) + translations.values) {
            for (area in StorageCatalogue.areas) {
                val note = map.getValue(area.backupResource)
                val mentionsExport = note.contains("%1\$s")
                val expected = area.id != StorageCatalogue.ID_TERMINAL_LOG && area.id != StorageCatalogue.ID_USAGE_SUMMARY && area.id != StorageCatalogue.ID_SAFETY_COPIES && area.id != StorageCatalogue.ID_TEMPORARY_FILES
                assertEquals("${area.id}: $note", expected, mentionsExport)
            }
        }
    }

    @Test
    fun theButtonNamesStillEnglishOnTheirOwnScreensAreNotTranslatedAwayInTheNotes() {
        // EXPORT DECK (.ZIP) (GIF decks) is still a literal English button on its own screen until that menu is migrated; a note that translated it would send
        // the person looking for a button that does not exist. When it moves, change this list and the note together. (EXPORT VOICE BACKUP moved with the AUDIO
        // ARCHITECT screen and SAVE ALL TO A FILE / RECORD TRAINING DATA with the capture screens: those notes take the buttons' names as arguments.)
        val stillEnglish = mapOf(
            "area_gif_library_backup" to listOf("EXPORT DECK (.ZIP)"),
        )
        for ((tag, map) in translations) for ((name, names) in stillEnglish) for (button in names) {
            assertTrue("$tag/$name must keep \"$button\" exactly", map.getValue(name).contains(button))
        }
    }

    @Test
    fun theTrainingDataNotesNameTheCaptureButtonsAsTheScreenWritesThem_inEveryLanguage() {
        // The note points at SAVE ALL TO A FILE on the RECORD TRAINING DATA screen; read in each language with that language's own file, it must hold exactly the words
        // the button and the screen carry there (a note that said another word would send the person looking for a button that does not exist).
        val area = StorageCatalogue.area(StorageCatalogue.ID_TRAINING_DATA)
        for (tag in listOf("en") + translations.keys) {
            val text = if (tag == "en") EnglishText else FileText(tag)
            val note = StorageCatalogue.backupNote(text, area)
            val holds = StorageCatalogue.holds(text, area)
            val map = if (tag == "en") english else translations.getValue(tag)
            assertTrue("$tag: $note", note.contains(map.getValue("capture_save_all") + " (" + map.getValue("label_record_training") + ")"))
            assertTrue("$tag: $holds", holds.contains(map.getValue("label_record_training")))
            assertFalse("$tag: no unfilled placeholder in $note", note.contains("%"))
            assertFalse("$tag: no unfilled placeholder in $holds", holds.contains("%"))
        }
    }

    @Test
    fun theTwoAreaNamesThatAreAlsoScreenNamesReadTheSameInEveryLanguage() {
        // TERMINAL LOG and SAFETY COPIES are in the label table (LabelKey) and in DELETE DATA. DELETE DATA keeps its own string (it does not follow PLAIN WORDS),
        // but the standard words must never drift apart from the screens' own.
        for (map in listOf(english) + translations.values) {
            assertEquals(map.getValue("label_terminal_log"), map.getValue("area_terminal_log_label"))
            assertEquals(map.getValue("label_safety_copies"), map.getValue("area_safety_copies_label"))
        }
    }

    @Test
    fun everyConfirmationTitleNamesTheAreaItDeletes_soAnotherLanguageCannotShowTheWrongOne() {
        // The title is "DELETE <area>" in the chosen language, built from the area's own name; EVERYTHING has its own name.
        assertEquals("DELETE TERMINAL LOG", EnglishText.get("delete_data_confirm_title", StorageCatalogue.labelOf(EnglishText, StorageCatalogue.ID_TERMINAL_LOG)))
        assertEquals("DELETE EVERYTHING", EnglishText.get("delete_data_confirm_title", StorageCatalogue.labelOf(EnglishText, StorageCatalogue.EVERYTHING_ID)))
        assertEquals("DELETE EVERYTHING", english.getValue("delete_data_delete_everything"))
    }
}
