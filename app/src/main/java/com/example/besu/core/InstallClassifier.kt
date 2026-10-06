// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Tells a fresh install from one that already holds a person's settings. Plain Kotlin on purpose (no `android.*`), like
 * `capture/`, so the tools/kotlin_check harness can test it without a phone.
 *
 * Why it exists: new defaults (the unprocessed voice, full messages on screen) are written once, on a fresh install only,
 * so nobody already using the app has a setting change under them. Nothing else records whether an install is new.
 */
object InstallClassifier {
    /**
     * The keys the seed itself writes, per preference file. They are ignored when classifying, so a seed that was
     * interrupted part-way (the keys exist, the "recorded" flag was never written) still reads as fresh on the next launch
     * and simply finishes. The exemption is per file: the same key name in another file is a real setting.
     *
     * If the seed (data/InstallState.kt) gains a key, add it here; a test pins this list so the two cannot drift silently.
     */
    val SEED_KEYS: Map<String, Set<String>> = mapOf(
        "ack_prefs" to setOf("USER_VOX_PROFILE"),
        "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
        // The starter phrases (data/StarterSeed.kt): twelve phrases for the DEFAULT deck, the deck list, the STARTERS deck, and
        // the seed's own record of what it wrote.
        StarterSets.MATRIX_FILE to StarterSets.matrixSeedKeys,
        StarterSets.RECORD_FILE to StarterSets.recordKeys,
        // The profile-change warning (data/AssistPrefs.kt): a new install is given it ON.
        AssistSettings.FILE to AssistSettings.SEED_KEYS,
    )

    /**
     * [keysByFile] maps each preference file the app owns to the set of keys it currently holds. Fresh means no file holds
     * any key other than the seed keys above. A missing file, or a file with no keys, counts for nothing.
     */
    fun isFreshInstall(keysByFile: Map<String, Set<String>>): Boolean =
        keysByFile.all { (file, keys) -> (keys - (SEED_KEYS[file] ?: emptySet())).isEmpty() }
}
