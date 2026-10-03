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

/** The words around SPEECH LANGUAGE (AUDIO ARCHITECT). Capitals, like the rest of the app. */
object SpeechLanguageText {
    fun label(setting: SpeechLanguage): String = "SPEECH LANGUAGE: " + when (setting) {
        SpeechLanguage.DEVICE -> "THIS PHONE'S LANGUAGE"
        SpeechLanguage.ENGLISH_US -> "ENGLISH (US)"
    }

    const val EXPLANATION =
        "THE LANGUAGE A PROFILE SPEAKS IN WHEN IT HAS NO VOICE OF ITS OWN. A PROFILE THAT HAS CHOSEN A VOICE USES THAT VOICE, AND MY VOICE IS NOT AFFECTED. " +
            "IF THE PHONE'S SPEECH ENGINE DOES NOT HAVE THE LANGUAGE, ACK USES THE ENGINE'S OWN DEFAULT: A LANGUAGE THAT IS NOT AVAILABLE NEVER MEANS SILENCE."
}
