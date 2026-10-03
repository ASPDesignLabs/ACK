// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What deleting the trained voice does to the voice profiles, decided in one place so the first confirmation (which lists
 * what will change) and the change itself (applied after the second) can never disagree. Plain Kotlin (no `android.*`) so
 * it is tested without a phone; settings/AudioView.kt passes in the live profiles and applies the result.
 *
 * Two things use the custom voice: the fixed MY VOICE preset (when it is the active voice), and any custom profile whose
 * "USE MY VOICE" switch is on. Once the voice is gone neither can speak with it, so MY VOICE as the active voice becomes the
 * unprocessed ORGANIC voice, and a custom profile just has the switch turned off (it keeps its name and DSP settings).
 * Speech must keep working: without this every message would try the deleted voice and fall back with an error line.
 */
object CustomVoiceRemoval {
    const val MY_VOICE_ID = "MY_VOICE"
    const val MY_VOICE_LABEL = "MY VOICE"

    /** The normal voice MY VOICE falls back to: the unprocessed voice, as everywhere else a voice goes missing. */
    const val FALLBACK_PROFILE_ID = "ORGANIC"

    class Profile(val id: String, val label: String, val useCustomVoice: Boolean)

    class Impact(
        /** Names to show the person before they confirm: MY VOICE first (if active), then custom profiles in list order. */
        val affectedLabels: List<String>,
        /** What the active voice becomes: ORGANIC if it was MY VOICE, otherwise unchanged. */
        val newActiveProfileId: String,
        val activeProfileChanges: Boolean,
        /** Custom profiles whose "USE MY VOICE" switch is turned off. */
        val profileIdsToClear: Set<String>,
    ) {
        val anyAffected: Boolean get() = affectedLabels.isNotEmpty()
    }

    fun impact(activeProfileId: String, customProfiles: List<Profile>): Impact {
        val labels = ArrayList<String>()
        val clear = LinkedHashSet<String>()
        val activeIsMyVoice = activeProfileId == MY_VOICE_ID
        if (activeIsMyVoice) labels.add(MY_VOICE_LABEL)
        for (p in customProfiles) {
            if (p.useCustomVoice) {
                labels.add(p.label)
                clear.add(p.id)
            }
        }
        return Impact(
            affectedLabels = labels,
            newActiveProfileId = if (activeIsMyVoice) FALLBACK_PROFILE_ID else activeProfileId,
            activeProfileChanges = activeIsMyVoice,
            profileIdsToClear = clear,
        )
    }
}
