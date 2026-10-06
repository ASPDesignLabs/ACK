// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.AssistSettings
import com.example.besu.core.InterfaceLanguage
import com.example.besu.core.InterfaceLanguagePolicy
import com.example.besu.core.SpeechLanguage
import com.example.besu.core.SpeechLanguagePolicy

/**
 * The person-chosen switches (core/AssistSettings.kt holds the decisions and names). Today: WARN BEFORE PROFILE CHANGES and WORD SUGGESTIONS. The thin Android
 * edge over one small preference file, in the shape of backup/BackupState.kt.
 *
 * The switch itself travels in EXPORT .JSON (a nullable AckBackup field: a person who restores onto a new phone expects their choice
 * back). WORD SUGGESTIONS is a choice about this phone and does not travel: it is never seeded and never in a backup, so a restore never
 * turns a learning feature on. The "offer dismissed" notes are per phone and never travel. The file is wiped with DELETE DATA > SETTINGS, after which the new-install
 * default is put back (InstallState.seedDefaultsAfterWipe).
 */
object AssistPrefs {
    private const val TAG = "ACK_ASSIST_PREFS"

    // Literal on purpose: the storage scan (StorageCatalogueTest) finds preference files by their literal names, and
    // ProfileWarningWiringTest checks these equal core/AssistSettings.
    private const val PREFS = "ack_assist_prefs"
    private const val KEY_WARN_PROFILE_CHANGE = "warn_profile_change"
    private const val KEY_WARN_OFFER_DISMISSED = "warn_profile_change_offer_dismissed"
    private const val KEY_SPEECH_LANGUAGE = "speech_language"
    private const val KEY_INTERFACE_LANGUAGE = "interface_language"
    private const val KEY_PLAIN_WORDS = "plain_words"
    private const val KEY_PLAIN_WORDS_OFFER_DISMISSED = "plain_words_offer_dismissed"
    private const val KEY_WORD_SUGGESTIONS = "word_suggestions"
    private const val KEY_WORD_OFFER_DISMISSED = "word_suggestions_offer_dismissed"

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Whether to ask before a profile change would change what a gesture says. Off when nothing is stored (an existing install is unchanged). */
    fun isProfileChangeWarningOn(context: Context): Boolean =
        prefs(context).getBoolean(KEY_WARN_PROFILE_CHANGE, AssistSettings.WARN_FALLBACK)

    /** The stored choice, or null if there is none (the person never chose and the phone was never seeded). Backed up as a nullable field. */
    fun profileChangeWarningStored(context: Context): Boolean? {
        val p = prefs(context)
        return if (p.contains(KEY_WARN_PROFILE_CHANGE)) p.getBoolean(KEY_WARN_PROFILE_CHANGE, AssistSettings.WARN_FALLBACK) else null
    }

    /** commit(), so the choice is on disk before the person can leave the screen. */
    fun setProfileChangeWarning(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_WARN_PROFILE_CHANGE, on).commit()
    }

    fun isProfileWarningOfferDismissed(context: Context): Boolean = prefs(context).getBoolean(KEY_WARN_OFFER_DISMISSED, false)

    /** Hides the offer for good. Changes no setting. */
    fun dismissProfileWarningOffer(context: Context) {
        prefs(context).edit().putBoolean(KEY_WARN_OFFER_DISMISSED, true).commit()
    }

    /**
     * A new install (and a phone after DELETE DATA > SETTINGS) is given the warning ON. Writes nothing that is already there, so it
     * never overrides a choice. Never throws: a failure is logged and the switch simply stays at its fallback (off).
     */
    fun seedFreshInstallDefaults(context: Context) {
        try {
            val p = prefs(context)
            if (!p.contains(KEY_WARN_PROFILE_CHANGE)) {
                p.edit().putBoolean(KEY_WARN_PROFILE_CHANGE, AssistSettings.WARN_FRESH_INSTALL).commit()
            }
            // A new install follows the phone's language; one that already existed keeps English (US) until the person changes it.
            if (!p.contains(KEY_SPEECH_LANGUAGE)) {
                p.edit().putString(KEY_SPEECH_LANGUAGE, SpeechLanguagePolicy.FRESH_INSTALL.stored).commit()
            }
            // The same for the language of ACK's own words: a new install follows the phone, one that already existed stays English until chosen.
            if (!p.contains(KEY_INTERFACE_LANGUAGE)) {
                p.edit().putString(KEY_INTERFACE_LANGUAGE, InterfaceLanguagePolicy.FRESH_INSTALL.stored).commit()
            }
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the profile-change warning", e)
        }
    }

    /** Whether the Statement Composer learns words and offers them. Off when nothing is stored, on every install: it starts only when the person turns it on. */
    fun isWordSuggestionsOn(context: Context): Boolean =
        prefs(context).getBoolean(KEY_WORD_SUGGESTIONS, AssistSettings.WORD_SUGGESTIONS_FALLBACK)

    /** commit(), so the choice is on disk before the person leaves the screen. Choosing either way also answers the one-time offer. */
    fun setWordSuggestions(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_WORD_SUGGESTIONS, on).putBoolean(KEY_WORD_OFFER_DISMISSED, true).commit()
    }

    fun isWordSuggestionsOfferDismissed(context: Context): Boolean = prefs(context).getBoolean(KEY_WORD_OFFER_DISMISSED, false)

    /** NOT NOW: hides the offer for good and changes no setting. */
    fun dismissWordSuggestionsOffer(context: Context) {
        prefs(context).edit().putBoolean(KEY_WORD_OFFER_DISMISSED, true).commit()
    }

    /** The language a profile with no voice of its own speaks in. English (US) when nothing (or something unreadable) is stored, so an existing install is unchanged. */
    fun speechLanguage(context: Context): SpeechLanguage =
        SpeechLanguage.fromStored(prefs(context).getString(KEY_SPEECH_LANGUAGE, null)) ?: SpeechLanguagePolicy.FALLBACK

    /** The stored value, or null if there is none (never chosen, never seeded). Backed up as a nullable field. */
    fun speechLanguageStored(context: Context): String? = prefs(context).getString(KEY_SPEECH_LANGUAGE, null)

    /** commit(), so the choice is on disk before the person leaves the screen. */
    fun setSpeechLanguage(context: Context, setting: SpeechLanguage) {
        prefs(context).edit().putString(KEY_SPEECH_LANGUAGE, setting.stored).commit()
    }

    /** The language of ACK's own words. English when nothing (or something unreadable) is stored, so an existing install is unchanged. */
    fun interfaceLanguage(context: Context): InterfaceLanguage =
        InterfaceLanguage.fromStored(prefs(context).getString(KEY_INTERFACE_LANGUAGE, null)) ?: InterfaceLanguagePolicy.FALLBACK

    /** The stored value, or null if there is none (never chosen, never seeded). Backed up as a nullable field. */
    fun interfaceLanguageStored(context: Context): String? = prefs(context).getString(KEY_INTERFACE_LANGUAGE, null)

    /** commit(), so the choice is on disk before ACK restarts to apply it. */
    fun setInterfaceLanguage(context: Context, setting: InterfaceLanguage) {
        prefs(context).edit().putString(KEY_INTERFACE_LANGUAGE, setting.stored).commit()
    }

    /** Whether labels are shown in everyday words. Off when nothing is stored, on every install (never seeded: the developer's decision). */
    fun isPlainWordsOn(context: Context): Boolean = prefs(context).getBoolean(KEY_PLAIN_WORDS, AssistSettings.PLAIN_WORDS_FALLBACK)

    /** The stored choice, or null if there is none. Backed up as a nullable field. */
    fun plainWordsStored(context: Context): Boolean? {
        val p = prefs(context)
        return if (p.contains(KEY_PLAIN_WORDS)) p.getBoolean(KEY_PLAIN_WORDS, AssistSettings.PLAIN_WORDS_FALLBACK) else null
    }

    /** commit(), so the choice is on disk before the person leaves the screen. Choosing either way also answers the one-time offer. */
    fun setPlainWords(context: Context, on: Boolean) {
        prefs(context).edit().putBoolean(KEY_PLAIN_WORDS, on).putBoolean(KEY_PLAIN_WORDS_OFFER_DISMISSED, true).commit()
    }

    fun isPlainWordsOfferDismissed(context: Context): Boolean = prefs(context).getBoolean(KEY_PLAIN_WORDS_OFFER_DISMISSED, false)

    /** NOT NOW: hides the offer for good and changes no setting. */
    fun dismissPlainWordsOffer(context: Context) {
        prefs(context).edit().putBoolean(KEY_PLAIN_WORDS_OFFER_DISMISSED, true).commit()
    }
}
