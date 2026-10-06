// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Which language ACK's own words (the label table, PLAIN WORDS text and the other string resources) are shown in. This is the language of the screens,
 * not of what is spoken (that is SPEECH LANGUAGE, core/SpeechLanguage.kt) and not of anything the person typed, which is never translated.
 */
enum class InterfaceLanguage(val stored: String, val tag: String?, val nativeName: String) {
    /** Follow the phone's language (English where the phone's language is not one ACK has). */
    DEVICE("DEVICE", null, ""),

    /** Always English, as ACK has always been. */
    ENGLISH("ENGLISH", "en", "ENGLISH"),
    SPANISH("ES", "es", "ESPAÑOL"),
    PORTUGUESE("PT", "pt", "PORTUGUÊS"),
    HINDI("HI", "hi", "हिन्दी"),
    ARABIC("AR", "ar", "العربية"),
    AFRIKAANS("AF", "af", "AFRIKAANS");

    companion object {
        /** Null for anything that is not exactly a stored name (an unknown value is not a setting, it is ignored). */
        fun fromStored(value: String?): InterfaceLanguage? = values().firstOrNull { it.stored == value }

        /** The languages a person can pick by name, in the order the control lists them (DEVICE is its own, first option). */
        val named: List<InterfaceLanguage> = values().filter { it.tag != null }
    }
}

/**
 * The decisions behind INTERFACE LANGUAGE. Plain Kotlin; the Android edge (data/InterfaceLocale.kt) only applies the answer.
 *
 *  - **Nothing stored is ENGLISH**, so an install that already existed looks exactly as before, even on a phone set to Spanish. Translated words reach
 *    an existing person only through their own choice in SETTINGS (the developer's decision, as for SPEECH LANGUAGE).
 *  - **A new install is given DEVICE**, and so is a phone after DELETE DATA > SETTINGS (the confirmation says so).
 *  - **A phone language ACK has no words for is English**, never a blank or a key name.
 */
object InterfaceLanguagePolicy {
    val FALLBACK: InterfaceLanguage = InterfaceLanguage.ENGLISH
    val FRESH_INSTALL: InterfaceLanguage = InterfaceLanguage.DEVICE

    private const val ENGLISH_TAG = "en"

    /** The language tags ACK has translated words for (English is the base text, so it needs no folder of its own). */
    val translatedTags: Set<String> = InterfaceLanguage.named.mapNotNull { it.tag }.filter { it != ENGLISH_TAG }.toSet()

    /** The language the screens will be in: the chosen one, or the phone's if that is one ACK has, otherwise English. */
    fun effectiveTag(setting: InterfaceLanguage, deviceLanguage: String): String {
        val tag = setting.tag
        if (tag != null) return tag
        val device = deviceLanguage.trim().lowercase()
        return if (device in translatedTags) device else ENGLISH_TAG
    }

    /**
     * Whether ACK has to set the language itself. DEVICE leaves the phone's own choice alone (so Android picks the matching resources); any named language,
     * English included, is applied, so an English install on a Spanish phone really stays English.
     */
    fun mustApply(setting: InterfaceLanguage): Boolean = setting.tag != null

    /**
     * Whether letter spacing must be switched off. Arabic letters join into words, and spacing added between them pulls the word apart (and stops the
     * joined forms from forming), so the app's wide letter spacing, a house style for the capitals of Latin text, is dropped for it.
     */
    fun joinsLetters(tag: String): Boolean = tag == "ar"
}

/**
 * The language and script of the screens in this run of ACK, set once when the main screen starts (a change of language restarts ACK, so it cannot change
 * under a running screen). The script is read wherever letter spacing is chosen (ui/ScriptSpacing.kt) and the tag wherever a date is written in the
 * words' own language (data/ResourceText.kt). Plain Kotlin so both the Android edge and the screens can use it.
 */
object ActiveScript {
    @Volatile
    var joinsLetters: Boolean = false
        private set

    /** The language the words are in: the one [InterfaceLanguagePolicy.effectiveTag] chose, English until the main screen has started. */
    @Volatile
    var tag: String = "en"
        private set

    fun use(tag: String) {
        this.tag = tag
        joinsLetters = InterfaceLanguagePolicy.joinsLetters(tag)
    }
}
