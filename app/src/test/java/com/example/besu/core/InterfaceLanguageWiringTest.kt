// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * INTERFACE LANGUAGE touches files that cannot be compiled or run without the Android SDK (AssistPrefs, InterfaceLocale, MainActivity, SettingsView, the
 * section screen, TransferManager). The rules are in plain Kotlin and tested in InterfaceLanguageTest; this reads those files and holds them to the
 * promises: an existing install stays English, a new one follows the phone, a choice asks first and restarts once, ACK always opens, nothing competes
 * with the in-app choice, and the setting is backed up, checked and described.
 */
class InterfaceLanguageWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }
    private val strings get() = StringsXml.map(StringsXml.default)

    // ---- the saved choice --------------------------------------------------------------------------------------------------------

    @Test
    fun theKeyMatchesTheCore_andReadingFallsBackToEnglishSoAnExistingInstallIsUnchanged() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_INTERFACE_LANGUAGE, Regex("""const val KEY_INTERFACE_LANGUAGE = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        val read = RepoFiles.declarationOf(prefs, "interfaceLanguage")
        assertTrue(read.contains("InterfaceLanguagePolicy.FALLBACK"))
        assertFalse("reading must not write", read.contains("edit()"))
    }

    @Test
    fun aNewInstallIsSeededWithThePhonesLanguage_onlyWhereNothingIsStored_andTheKeyIsASeedKey() {
        val prefs = source("data/AssistPrefs.kt")
        val start = prefs.indexOf("fun seedFreshInstallDefaults(")
        val body = prefs.substring(start, prefs.indexOf("fun isWordSuggestionsOn(", start))
        assertTrue(body.contains("InterfaceLanguagePolicy.FRESH_INSTALL"))
        assertTrue("the seed must write nothing that is already there", body.contains("contains(KEY_INTERFACE_LANGUAGE)"))
        assertTrue(AssistSettings.KEY_INTERFACE_LANGUAGE in AssistSettings.SEED_KEYS)
    }

    @Test
    fun theChoiceIsWrittenWithCommit_soItIsOnDiskBeforeACKRestarts() {
        assertTrue(RepoFiles.declarationOf(source("data/AssistPrefs.kt"), "setInterfaceLanguage").contains(".commit()"))
    }

    // ---- applying it ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theMainScreenAppliesItBeforeAnythingReadsAString() {
        val main = noComments(source("MainActivity.kt"))
        val at = main.indexOf("override fun attachBaseContext(newBase: Context)")
        assertTrue(at >= 0)
        assertTrue(main.substring(at, at + 200).contains("super.attachBaseContext(InterfaceLocale.wrap(newBase))"))
    }

    @Test
    fun followingThePhoneLeavesTheContextAlone_aNamedLanguageIsApplied_andAFailureStillOpensACK() {
        val locale = noComments(source("data/InterfaceLocale.kt"))
        val wrap = RepoFiles.declarationOf(locale.replace("\n    fun wrap", "\n    fun wrap"), "wrap")
        assertTrue(wrap.contains("InterfaceLanguagePolicy.effectiveTag(setting, deviceLanguage)"))
        assertTrue(wrap.contains("ActiveScript.use(tag)"))
        assertTrue("DEVICE must return the context unchanged", wrap.contains("if (!InterfaceLanguagePolicy.mustApply(setting)) return base"))
        assertTrue(wrap.contains("configuration.setLocale(locale)"))
        assertTrue("the layout direction follows the language (Arabic is right to left)", wrap.contains("configuration.setLayoutDirection(locale)"))
        assertTrue(wrap.contains("base.createConfigurationContext(configuration)"))
        // Never blocks ACK from opening, and says only a fixed sentence (nothing typed is ever logged).
        assertTrue(wrap.contains("catch (e: Exception)"))
        assertTrue(wrap.substring(wrap.indexOf("catch (e: Exception)")).contains("            base\n"))
        assertTrue(Regex("""Log\.e\(TAG, "[^"$]+", e\)""").containsMatchIn(wrap))
    }

    @Test
    fun nothingCompetesWithTheInAppChoice_noAndroidPerAppLanguageListIsDeclared() {
        // Android 13's own per-app language screen would be a second switch: an existing install is kept on English by the in-app setting, and a
        // phone-level choice would be silently overridden by it. One source of truth.
        val manifest = RepoFiles.read("app/src/main/AndroidManifest.xml")
        assertFalse(manifest.contains("localeConfig"))
        assertFalse(RepoFiles.file("app/src/main/res/xml/locales_config.xml").exists())
        assertTrue("right to left layouts must stay available", manifest.contains("android:supportsRtl=\"true\""))
    }

    // ---- letter spacing ----------------------------------------------------------------------------------------------------------

    @Test
    fun everyLetterSpacingGoesThroughTheHelperThatDropsItForArabic() {
        val offenders = RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "ScriptSpacing.kt" }.flatMap { file ->
            noComments(file.readText(Charsets.UTF_8)).lines().withIndex()
                .filter { Regex("""letterSpacing\s*=\s*""").containsMatchIn(it.value) && !it.value.contains("looseSpacing(") && !it.value.contains("letterSpacing = letterSpacing") }
                .map { "${file.name}:${it.index + 1}" }
        }.toList()
        assertTrue("letter spacing that is not routed through looseSpacing: $offenders", offenders.isEmpty())
    }

    @Test
    fun theHelperDropsSpacingOnlyThroughTheTestedActiveScript() {
        val helper = noComments(source("ui/ScriptSpacing.kt"))
        assertTrue(helper.contains("fun looseSpacing(spacing: TextUnit): TextUnit = if (ActiveScript.joinsLetters) TextUnit.Unspecified else spacing"))
        val core = source("core/InterfaceLanguage.kt")
        assertTrue(core.contains("joinsLetters = InterfaceLanguagePolicy.joinsLetters(tag)"))
    }

    // ---- the control ---------------------------------------------------------------------------------------------------------------

    @Test
    fun aChoiceAsksFirst_andOnlyTheConfirmingButtonSavesAndRestarts() {
        val section = noComments(source("settings/InterfaceLanguageSection.kt"))
        // Tapping a language only remembers it; it never calls the callback.
        assertTrue(section.contains("onClick = { if (!selected) pending = language }"))
        assertEquals("the callback is called from exactly one place", 1, Regex("""onConfirmed\(""").findAll(section).count() - 0)
        val confirmBlock = section.substring(section.indexOf("NeonButton(stringResource(R.string.interface_language_confirm)"))
        assertTrue(confirmBlock.contains("onConfirmed(choice)"))
        // CANCEL first and in the person's colour; the confirming one is not.
        val cancelAt = section.indexOf("NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor)")
        assertTrue(cancelAt in 0 until section.indexOf("R.string.interface_language_confirm)"))
        assertTrue("tapping outside cancels", section.contains("onDismiss = { pending = null }"))

        val settings = noComments(source("settings/SettingsView.kt"))
        val at = settings.indexOf("InterfaceLanguageSection(")
        assertTrue(at >= 0)
        val call = settings.substring(at, settings.indexOf("item {", at))
        assertTrue(call.contains("AssistPrefs.setInterfaceLanguage(context, language)"))
        assertTrue(call.contains("pendingRestart = true"))
        assertTrue("the restart is the shared, delayed one", settings.contains("restartApp(context)"))
    }

    @Test
    fun theControlIsReadableAndSteady_12spOrLarger_48dpChoices_noVibrationOrAnimation() {
        val section = noComments(source("settings/InterfaceLanguageSection.kt"))
        val sizes = Regex("""fontSize = (\d+)\.sp""").findAll(section).map { it.groupValues[1].toInt() }.toList()
        assertTrue(sizes.isNotEmpty())
        assertTrue("text under 12 sp: $sizes", sizes.all { it >= 12 })
        assertTrue(section.contains("heightIn(min = 48.dp)"))
        assertTrue(section.contains("role = Role.RadioButton"))
        assertFalse(Regex("""Haptic|animate\w*|Animated\w*""").containsMatchIn(section))
        // Each language is named in its own script and is never taken from a translated string.
        assertTrue(section.contains("language.nativeName"))
    }

    @Test
    fun theHeadingIsFixedTextInEveryLanguageSoItCanAlwaysBeFound() {
        val xml = RepoFiles.read("app/src/main/res/values/strings.xml")
        assertTrue(xml.contains("<string name=\"interface_language_all\" translatable=\"false\">"))
        val heading = strings.getValue("interface_language_all")
        for (word in listOf("LANGUAGE", "IDIOMA", "भाषा", "اللغة", "TAAL")) assertTrue(word, heading.contains(word))
    }

    @Test
    fun theControlWordsAreInCapitals_theAppsHouseStyle_andTheBodyTakesTheLanguageName() {
        for (name in strings.keys.filter { it.startsWith("interface_language_") && it != "interface_language_all" } + "common_cancel") {
            val words = strings.getValue(name).replace(Regex("""%(?:\d+\$)?[sdf]"""), "")
            assertEquals(name, words.uppercase(), words)
        }
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(strings.getValue("interface_language_confirm_body")))
        assertTrue(strings.getValue("interface_language_explanation").contains("DRAFT"))
    }

    // ---- backup, checks and the wipe -------------------------------------------------------------------------------------------------

    @Test
    fun theSettingIsInTheBackupAsANullableField_describedByTheExportWarning_notOnTheFingerprintIgnoreList() {
        assertTrue(Regex("""val interfaceLanguage: String\? = null""").containsMatchIn(source("backup/AckBackup.kt")))
        assertTrue("interfaceLanguage" in ExportContents.mappedFields)
        assertFalse("an ordinary setting: changing it should change the fingerprint", "interfaceLanguage" in BackupFingerprint.IGNORED_FIELDS)
        assertTrue(source("backup/TransferManager.kt").contains("interfaceLanguage = AssistPrefs.interfaceLanguageStored(context)"))
    }

    @Test
    fun importRefusesAnUnknownValue_logsWhy_andApplyLeavesTheChoiceAloneWhenTheFileSaysNothing() {
        val transfer = source("backup/TransferManager.kt")
        val at = transfer.indexOf("backup.interfaceLanguage != null")
        assertTrue(at >= 0)
        val block = transfer.substring(at, at + 450)
        assertTrue(block.contains("InterfaceLanguage.fromStored("))
        assertTrue(block.indexOf("Log.e(\"ACK_IMPORT\"") in 0 until block.indexOf("return false"))
        assertTrue("null means nothing to say: fromStored(null) is null, so nothing is written",
            transfer.contains("InterfaceLanguage.fromStored(backup.interfaceLanguage)?.let { AssistPrefs.setInterfaceLanguage(context, it) }"))
    }

    @Test
    fun deleteDataSettingsSaysTheScreenFollowsThePhoneAfterwards() {
        val settings = StorageCatalogue.area(StorageCatalogue.ID_SETTINGS)
        assertTrue(StorageCatalogue.firstConfirmation(settings, "X").any { it.contains("ACK'S OWN WORDS IN THIS PHONE'S LANGUAGE") })
        assertTrue(StorageCatalogue.firstConfirmationEverything("X").any { it.contains("ACK'S OWN WORDS IN THIS PHONE'S LANGUAGE") })
    }
}
