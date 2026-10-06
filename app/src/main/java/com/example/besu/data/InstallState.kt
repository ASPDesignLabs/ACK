// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.InstallClassifier
import com.example.besu.output.VisualPreset
import com.example.besu.output.VisualPresetRepository

/**
 * Records, once, whether this install was fresh when this version first ran, and on a fresh install writes the new
 * safe defaults ("seed, don't flip"):
 *
 *  - the unprocessed ORGANIC voice,
 *  - one visual preset, FULL TEXT, set active, so a whole message is shown on screen, and
 *  - the neutral starter phrases and a small STARTERS Quick Actions deck (StarterSeed), instead of the old built-in wording, and
 *  - the profile-change warning, switched ON (AssistPrefs).
 *
 * Every place that READS these settings keeps its old fallback (CYBER, bypassTruncation = false), so an install that
 * already existed behaves exactly as before. Only an install with nothing stored gets the new defaults, and only once.
 *
 * Called from AckApplication.onCreate, before any screen touches storage: MainActivity's first run writes
 * CUSTOM_VOICES into ack_prefs, which would otherwise make every install look as if it already existed.
 *
 * The decision is in core/InstallClassifier.kt (plain Kotlin, tested). This file is the thin Android edge.
 */
object InstallState {
    private const val TAG = "ACK_INSTALL"
    private const val PREFS = "ack_install_state"
    private const val KEY_RECORDED = "recorded"
    private const val KEY_FRESH = "fresh"
    private const val KEY_DEFAULTS_PROMPT_DISMISSED = "defaults_prompt_dismissed"

    /**
     * Every preference file the app owns. The classifier looks at all of them so that a person who only ever used one
     * feature still reads as an existing install. A longer list can only make an install count as existing, which is the
     * safe direction. "gestures" was written by a setup screen that is gone; older installs may still hold it.
     */
    private val OWNED_PREFS_FILES = listOf(
        "ack_prefs", "app_prefs", "ack_matrix_config", "ack_visual_presets", "ack_voice_recordings", "ack_targets",
        "ack_statements", "ack_geo_secure", "ack_gif_library", "ack_autocomplete_history",
        "ack_training_capture", "ack_training_game", "ack_deck_trainer", "gestures", "ack_starter_seed", "ack_assist_prefs",
        "ack_usage_tally", "ack_partner_card",
    )

    private const val DEFAULT_VOICE = "ORGANIC"
    private const val DEFAULT_PRESET_NAME = "FULL TEXT"

    /**
     * Does nothing if this version already recorded the install. Otherwise classifies it, seeds a fresh one, and writes the
     * flags last, with commit() so they are on disk before anything else reads them. Never throws: a seeding failure is
     * logged and the app carries on with the old defaults.
     */
    fun ensureRecorded(context: Context) {
        try {
            val state = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            if (state.getBoolean(KEY_RECORDED, false)) return

            val keysByFile = OWNED_PREFS_FILES.associateWith { name ->
                context.getSharedPreferences(name, Context.MODE_PRIVATE).all.keys.toSet()
            }
            val fresh = InstallClassifier.isFreshInstall(keysByFile)
            if (fresh) {
                seedFreshInstallDefaults(context)
                // The neutral starter phrases (data/StarterSeed.kt). Deliberately NOT part of seedFreshInstallDefaults, which also runs
                // after a SETTINGS wipe: seeding phrases there would change what an existing person's untouched buttons say.
                StarterSeed.seedFreshInstall(context)
            }

            state.edit().putBoolean(KEY_FRESH, fresh).putBoolean(KEY_RECORDED, true).commit()
            Log.i(TAG, "install recorded: fresh=$fresh")
        } catch (e: Exception) {
            Log.e(TAG, "could not record install state; the app continues with its old defaults", e)
        }
    }

    /** True only if this install was fresh when it was recorded. False before it is recorded, and for any existing install. */
    fun isFreshInstall(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_FRESH, false)

    /**
     * Whether the one-time offer of the newer defaults (AUDIO ARCHITECT's banner, for an install that already existed) has been
     * dismissed or acted on. It is only this device's note that the person has seen it: it is not part of EXPORT .JSON.
     */
    fun isDefaultsPromptDismissed(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY_DEFAULTS_PROMPT_DISMISSED, false)

    /** Hides the offer for good. Changes no setting. commit(), so it is on disk before the person can leave the screen. */
    fun dismissDefaultsPrompt(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY_DEFAULTS_PROMPT_DISMISSED, true).commit()
    }

    /**
     * DELETE DATA > SETTINGS (and EVERYTHING) puts the new-install seeds back, the same ones a fresh install gets, so a wiped
     * phone speaks in the safe default voice and shows whole messages instead of falling back to the robotic voice and the
     * old cut-off. Writes nothing that is already there, so it is safe to call after any wipe.
     */
    fun seedDefaultsAfterWipe(context: Context) = seedFreshInstallDefaults(context)

    // Each seed is its own try so one failing cannot stop the other. The seeds write nothing that is already there.
    private fun seedFreshInstallDefaults(context: Context) {
        try {
            val prefs = context.getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)
            if (!prefs.contains("USER_VOX_PROFILE")) {
                prefs.edit().putString("USER_VOX_PROFILE", DEFAULT_VOICE).commit()
            }
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the default voice", e)
        }
        try {
            if (VisualPresetRepository.getPresets(context).isEmpty()) {
                val preset = VisualPreset(name = DEFAULT_PRESET_NAME, bypassTruncation = true)
                VisualPresetRepository.savePreset(context, preset)
                VisualPresetRepository.setActivePreset(context, preset.id)
                // The repository writes with apply() (in the background). An empty commit() on the same file waits for those
                // writes, so the preset is on disk before the "recorded" flag is. Read from the SharedPreferences contract;
                // not observed on a device.
                context.getSharedPreferences("ack_visual_presets", Context.MODE_PRIVATE).edit().commit()
            }
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the FULL TEXT preset", e)
        }
        // The profile-change warning is given ON, so a new learner is told before a profile change moves what a gesture says. Its own
        // try inside, like the others, and it writes nothing that is already there.
        AssistPrefs.seedFreshInstallDefaults(context)
    }
}
