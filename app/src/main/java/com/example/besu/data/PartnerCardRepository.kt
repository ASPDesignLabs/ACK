// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.PartnerCardBackup
import com.example.besu.core.PartnerCardSettings

/**
 * Keeps what the person chose for the partner card (core/PartnerCard.kt): which sentences are on, and the one or two sentences they wrote themselves. The thin Android edge over
 * core/PartnerCardSettings.kt, which holds every rule and is tested without a phone.
 *
 * Rules that must stay true (PartnerCardWiringTest holds them):
 *  - **Its own small preference file, `ack_partner_card`**: three values (`own_1`, `own_2`, `off`) and nothing else. Nothing is written until the person turns a sentence off or writes one.
 *  - **It is the person's words, so it is wiped with DELETE DATA > MESSAGES AND DECKS and travels in EXPORT .JSON** (named in that warning). A restore only ADDS into empty slots and never
 *    overwrites a sentence written since; the on/off choices are this phone's own and are not in the backup.
 *  - **Reading changes nothing and never throws.** [save] writes with `commit()` and says whether it worked, so a screen only shows a sentence as saved once it is.
 *  - **No sentence is ever logged**, not in an error either: every `Log` line here is a fixed sentence.
 */
object PartnerCardRepository {
    private const val TAG = "ACK_PARTNER_CARD"

    // Literal on purpose: the storage scan (StorageCatalogueTest) finds preference files by their literal names; a test keeps this equal to PartnerCardSettings.PREFS_FILE.
    private const val PREFS = "ack_partner_card"

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** What is stored, or the card as it always was when nothing is. */
    fun load(context: Context): PartnerCardSettings = try {
        val p = prefs(context)
        PartnerCardSettings.fromStored(p.getString(PartnerCardSettings.KEY_OWN_1, null), p.getString(PartnerCardSettings.KEY_OWN_2, null), p.getString(PartnerCardSettings.KEY_OFF, null))
    } catch (e: Exception) {
        Log.w(TAG, "the partner card choice could not be read")
        PartnerCardSettings.DEFAULT
    }

    /** Stores [settings]. Returns whether it is on disk now. */
    fun save(context: Context, settings: PartnerCardSettings): Boolean = try {
        val edit = prefs(context).edit()
        for ((key, value) in settings.toStored()) edit.putString(key, value)
        edit.commit()
    } catch (e: Exception) {
        Log.w(TAG, "the partner card choice could not be saved")
        false
    }

    /** The own sentences for EXPORT .JSON, or null when none is written (nothing to say). */
    fun exportForBackup(context: Context): PartnerCardBackup? {
        val written = load(context).own.filter { it.isNotEmpty() }
        return if (written.isEmpty()) null else PartnerCardBackup(written)
    }

    /** Adds a restored backup's sentences to the empty slots of this phone. Never overwrites a sentence, never touches the on/off choices. */
    fun mergeFromBackup(context: Context, backup: PartnerCardBackup) {
        try {
            val device = load(context)
            val merged = PartnerCardSettings.mergeOwn(device, backup.ownSentences)
            if (merged != device && !save(context, merged)) Log.w(TAG, "the restored partner card sentences could not be saved")
        } catch (e: Exception) {
            Log.w(TAG, "restoring the partner card sentences failed")
        }
    }
}
