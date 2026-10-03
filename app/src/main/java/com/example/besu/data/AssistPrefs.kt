// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.AssistSettings

/**
 * The person-chosen switches (core/AssistSettings.kt holds the decisions and names). Today: WARN BEFORE PROFILE CHANGES. The thin Android
 * edge over one small preference file, in the shape of backup/BackupState.kt.
 *
 * The switch itself travels in EXPORT .JSON (a nullable AckBackup field: a person who restores onto a new phone expects their choice
 * back). The "offer dismissed" note is per phone and never travels. The file is wiped with DELETE DATA > SETTINGS, after which the new-install
 * default is put back (InstallState.seedDefaultsAfterWipe).
 */
object AssistPrefs {
    private const val TAG = "ACK_ASSIST_PREFS"

    // Literal on purpose: the storage scan (StorageCatalogueTest) finds preference files by their literal names, and
    // ProfileWarningWiringTest checks these equal core/AssistSettings.
    private const val PREFS = "ack_assist_prefs"
    private const val KEY_WARN_PROFILE_CHANGE = "warn_profile_change"
    private const val KEY_WARN_OFFER_DISMISSED = "warn_profile_change_offer_dismissed"

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
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the profile-change warning", e)
        }
    }
}
