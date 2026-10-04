// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** Which language a profile with **no voice of its own** speaks in (a profile that chose a voice uses that voice; the cloned voice is separate). */
enum class SpeechLanguage(val stored: String) {
    /** Follow the phone's language. */
    DEVICE("DEVICE"),

    /** Always English (US), as ACK has always done. */
    ENGLISH_US("ENGLISH_US");

    companion object {
        /** Null for anything that is not exactly a stored name (an unknown value is not a setting, it is ignored). */
        fun fromStored(value: String?): SpeechLanguage? = values().firstOrNull { it.stored == value }
    }
}

/**
 * The decisions behind SPEECH LANGUAGE. Plain Kotlin; OutputService only asks the engine.
 *
 *  - **Nothing stored is ENGLISH (US)**, so an install that already existed speaks exactly as before: a phone set to German that has always spoken
 *    English phrases must not suddenly read them with a German accent.
 *  - **A new install is given DEVICE**, and so is a phone after DELETE DATA > SETTINGS (the confirmation says so).
 *  - **A language the engine does not have is never silence:** the engine keeps its own default language.
 */
object SpeechLanguagePolicy {
    val FALLBACK: SpeechLanguage = SpeechLanguage.ENGLISH_US
    val FRESH_INSTALL: SpeechLanguage = SpeechLanguage.DEVICE

    private const val ENGLISH_US_TAG = "en-US"

    /** The language tag to ask the engine for. A phone that reports nothing usable gets English (US) rather than no language at all. */
    fun localeTag(setting: SpeechLanguage, deviceTag: String): String = when (setting) {
        SpeechLanguage.ENGLISH_US -> ENGLISH_US_TAG
        SpeechLanguage.DEVICE -> deviceTag.trim().let { if (it.isEmpty() || it.equals("und", ignoreCase = true)) ENGLISH_US_TAG else it }
    }

    /**
     * `TextToSpeech.setLanguage` returns LANG_AVAILABLE (0), LANG_COUNTRY_AVAILABLE (1) or LANG_COUNTRY_VAR_AVAILABLE (2) when it took the language, and
     * LANG_MISSING_DATA (-1) or LANG_NOT_SUPPORTED (-2) when it did not.
     */
    fun engineAccepted(result: Int): Boolean = result >= 0

    /**
     * Whether the language must be asked of the engine before this utterance: the first time, when the setting changed, or when a profile earlier chose
     * a voice (the engine keeps that voice, so a profile with none would otherwise inherit it).
     */
    fun needsApplying(desiredTag: String, appliedTag: String?, voiceSetByProfile: Boolean): Boolean =
        appliedTag != desiredTag || voiceSetByProfile
}

/**
 * The words around SPEECH LANGUAGE (AUDIO ARCHITECT), read through [TextSource] so they are in the chosen language. MY VOICE is a name, not a
 * translation: it is passed in, so the explanation and the chip can never disagree about it.
 */
object SpeechLanguageText {
    const val LABEL_DEVICE = "speech_language_device"
    const val LABEL_ENGLISH_US = "speech_language_english"
    const val EXPLANATION_WHO = "speech_language_explanation_who"
    const val EXPLANATION_MISSING = "speech_language_explanation_missing"

    fun label(text: TextSource, setting: SpeechLanguage): String = text.get(
        when (setting) {
            SpeechLanguage.DEVICE -> LABEL_DEVICE
            SpeechLanguage.ENGLISH_US -> LABEL_ENGLISH_US
        }
    )

    /** Two sentences joined here (Android trims a space left at the end of a string): who it affects, and that a missing language is never silence. */
    fun explanation(text: TextSource): String =
        listOf(text.get(EXPLANATION_WHO, CustomVoiceRemoval.MY_VOICE_LABEL), text.get(EXPLANATION_MISSING)).joinToString(" ")
}
