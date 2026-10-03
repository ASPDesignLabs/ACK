// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The profile-change warning touches files that cannot be compiled or run without the Android SDK (MainActivity, SettingsView,
 * InstallState, TransferManager, CommandRepository, the dialog). The decisions are in plain Kotlin and tested elsewhere; this reads
 * those files and holds them to the rules: where the warning is wired, where it deliberately is not, and that Quick Actions
 * positions can never become profile-dependent.
 */
class ProfileWarningWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    private fun bodyOf(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        assertTrue("fun $name( not found", at >= 0)
        val open = text.indexOf('{', text.indexOf(')', at))
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == '{') depth++
            if (text[i] == '}') { depth--; if (depth == 0) return text.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces in $name")
    }

    // ---- the switch's storage ---------------------------------------------------------------------------------------------

    @Test
    fun theSwitchLivesInItsOwnFile_withTheNamesTheCoreSays_andFallsBackToOff() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.FILE, Regex("""const val PREFS = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertEquals(AssistSettings.KEY_WARN_PROFILE_CHANGE, Regex("""const val KEY_WARN_PROFILE_CHANGE = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertEquals(AssistSettings.KEY_WARN_OFFER_DISMISSED, Regex("""const val KEY_WARN_OFFER_DISMISSED = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertTrue(
            "reading the switch must fall back to AssistSettings.WARN_FALLBACK (off), so an existing install is unchanged",
            RepoFiles.declarationOf(prefs, "isProfileChangeWarningOn").contains("AssistSettings.WARN_FALLBACK")
        )
    }

    @Test
    fun aNewInstallIsSeededWithTheWarningOn_onlyWhereNothingIsStored() {
        val prefs = source("data/AssistPrefs.kt")
        val body = bodyOf(prefs, "seedFreshInstallDefaults")
        assertTrue(body.contains("AssistSettings.WARN_FRESH_INSTALL"))
        assertTrue("the seed must write nothing that is already there", body.contains("contains(KEY_WARN_PROFILE_CHANGE)"))
    }

    @Test
    fun theSeedRunsForAFreshInstallAndAfterASettingsWipe_butNeverOnItsOwnForAnExistingInstall() {
        val state = source("data/InstallState.kt")
        assertTrue(bodyOf(state, "seedFreshInstallDefaults").contains("AssistPrefs.seedFreshInstallDefaults(context)"))
        // seedFreshInstallDefaults is called only from the fresh branch of ensureRecorded and from seedDefaultsAfterWipe
        val callers = Regex("""(?<!AssistPrefs\.)seedFreshInstallDefaults\(context\)""").findAll(state).count()
        assertEquals("exactly two calls: ensureRecorded (fresh branch) and seedDefaultsAfterWipe", 2, callers)
    }

    @Test
    fun theFileIsOwnedByInstallStateAndClearedWithSettings() {
        val list = Regex("OWNED_PREFS_FILES\\s*=\\s*listOf\\(([^)]*)\\)").find(source("data/InstallState.kt"))?.groupValues?.get(1)
            ?: error("OWNED_PREFS_FILES not found")
        assertTrue(list.contains("\"${AssistSettings.FILE}\""))
        assertTrue(AssistSettings.FILE in StorageCatalogue.area(StorageCatalogue.ID_SETTINGS).prefsFilesCleared)
    }

    @Test
    fun theSwitchIsInTheBackup_asANullableField_describedByTheExportWarning_andNotInTheFingerprint() {
        assertTrue(Regex("""val warnBeforeProfileChange: Boolean\? = null""").containsMatchIn(source("backup/AckBackup.kt")))
        assertTrue("warnBeforeProfileChange" in ExportContents.mappedFields)
        assertTrue("warnBeforeProfileChange" in BackupFingerprint.IGNORED_FIELDS)
        val transfer = source("backup/TransferManager.kt")
        assertTrue(bodyOf(transfer, "buildBackup").contains("warnBeforeProfileChange = AssistPrefs.profileChangeWarningStored(context)"))
        val apply = bodyOf(transfer, "applyBackupToStorage")
        assertTrue(
            "a backup that says nothing (null) must leave the device's own choice alone",
            Regex("""if \(backup\.warnBeforeProfileChange != null\) \{\s*AssistPrefs\.setProfileChangeWarning\(context, backup\.warnBeforeProfileChange\)""").containsMatchIn(apply)
        )
    }

    // ---- where the warning is, and where it deliberately is not ---------------------------------------------------------------

    @Test
    fun theProfileMenu_asksFirst_andAppliesOnlyThroughOneFunction() {
        val main = source("MainActivity.kt")
        val request = bodyOf(main, "requestProfileChange")
        assertTrue(request.contains("ProfileSwapDiff.changes("))
        assertTrue(request.contains("ProfileSwapDiff.shouldWarn("))
        assertTrue(request.contains("AssistPrefs.isProfileChangeWarningOn(context)"))
        val apply = bodyOf(main, "applyProfileChange")
        assertTrue(apply.contains("CommandRepository.setActiveProfile("))
        assertTrue(apply.contains("WatchSync.sendProfileConfig("))
        assertTrue(apply.contains("HelpEvent.ProfileWasSelected(AckTags.PROFILE_SELECTOR)"))
        assertTrue("the menu row must call requestProfileChange", main.contains("requestProfileChange(profile)"))
        assertEquals("setActiveProfile is called once in MainActivity, from applyProfileChange", 1, Regex("""CommandRepository\.setActiveProfile\(""").findAll(main).count())
    }

    @Test
    fun theWidgetAndARestoreAreNotAskedToWarn_becauseTheyHaveNoScreenOrAreAlreadyConfirmed() {
        val service = source("output/OutputService.kt")
        assertFalse(service.contains("ProfileSwapDiff"))
        assertFalse(service.contains("AssistPrefs"))
        val widget = source("settings/ProfileWidget.kt")
        assertFalse(widget.contains("ProfileSwapDiff"))
        // restore applies the file's active profile directly, as before
        assertTrue(source("backup/TransferManager.kt").contains("CommandRepository.setActiveProfile(context, backup.activeProfile)"))
    }

    @Test
    fun theSlotsAreComparedByTheirResolvedPhrases_usingTheRepositorysOwnResolveFunction() {
        val body = bodyOf(source("data/CommandRepository.kt"), "profileSwapSlots")
        assertEquals("one resolve per side", 2, Regex("""getResolvedPhrase\(""").findAll(body).count())
        assertFalse("must not re-implement the fall-back by reading preferences", body.contains("getSharedPreferences"))
        assertFalse(body.contains("consumeSingleUse = true"))
    }

    // ---- Quick Actions positions stay fixed -------------------------------------------------------------------------------------

    @Test
    fun theDecksWithoutProfiles_neverGainAProfileParameter() {
        val repository = source("data/CommandRepository.kt")
        for (fn in listOf("quickActionsKey", "emojiDeckKey", "emergencyKey")) {
            val signature = Regex("""fun $fn\(([^)]*)\)""").find(repository)?.groupValues?.get(1)
                ?: error("$fn not found in CommandRepository.kt")
            assertFalse("$fn must not take a profile: its buttons would move when the profile changes ($signature)", signature.contains("profile", ignoreCase = true))
            assertEquals("$fn takes only the deck id", "deckId: String", signature.trim())
        }
    }

    // ---- the dialog and the settings --------------------------------------------------------------------------------------------

    @Test
    fun theDialog_isQuiet_hasStayBeforeChange_andACheckboxThatFlipsTheSameSetting() {
        val dialog = source("ui/ProfileChangeDialog.kt")
        assertTrue(dialog.contains("TightDialogSurface("))
        assertTrue(dialog.contains("ProfileSwapText.heading("))
        assertTrue(dialog.contains("ProfileSwapText.lines("))
        assertTrue("STAY must come before CHANGE PROFILE, and be the prominent one", dialog.indexOf("ProfileWarningText.STAY") < dialog.indexOf("ProfileWarningText.CHANGE"))
        assertTrue(dialog.contains("onDontShowAgainChanged"))
        for (banned in listOf("performHapticFeedback", "HapticFeedback", "ToneGenerator", "MediaPlayer", "SoundPool", "OutputService", "TextToSpeech", "animate", "TightPanelButton")) {
            assertFalse("the dialog must not use $banned", dialog.contains(banned))
        }
        val sizes = Regex("""fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp""").findAll(dialog).map { it.groupValues[1].toDouble() }.toList()
        assertTrue(sizes.isNotEmpty())
        for (s in sizes) assertTrue("text of $s sp; the floor for new text is 12", s >= 12.0)
        assertFalse("the dialog must never start HELP", dialog.contains("helpManager") || dialog.contains("HelpManager"))
    }

    @Test
    fun theCheckboxWritesTheSameSettingAsSettings_throughOneFunction() {
        val main = source("MainActivity.kt")
        assertTrue(main.contains("AssistPrefs.setProfileChangeWarning(context, !checked)"))
        val settings = source("settings/SettingsView.kt")
        assertTrue(settings.contains("ProfileWarningText.switchLabel("))
        assertTrue(settings.contains("ProfileWarningText.SWITCH_EXPLANATION"))
        assertTrue(settings.contains("AssistPrefs.setProfileChangeWarning("))
    }

    @Test
    fun theOffer_isShownOnlyInSettings_andNeverStartsHelpOrNavigates() {
        val settings = source("settings/SettingsView.kt")
        assertTrue(settings.contains("AssistSettings.shouldOfferWarning("))
        assertTrue(settings.contains("ProfileWarningText.OFFER_TEXT"))
        assertTrue(settings.contains("AssistPrefs.dismissProfileWarningOffer(context)"))
        // the offer must not change the setting except by the TURN ON tap
        val at = settings.indexOf("ProfileWarningText.OFFER_TURN_ON")
        assertTrue(at >= 0)
    }
}
