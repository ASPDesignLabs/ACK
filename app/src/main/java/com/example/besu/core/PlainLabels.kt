// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Every label that needs the glossary, by name. Plain Kotlin (no `android.*`). The words themselves are string resources, in two forms each:
 * `label_<key>` (the standard wording, exactly what the app has always shown) and `label_<key>_plain` (an everyday name), in `res/values/strings.xml` and
 * in every translation. PlainLabelsTest keeps the two forms complete and the plain wording honest; docs/PLAIN_LANGUAGE.md is the review page.
 *
 * Labels are display text only. A key never renames an `AckTags` constant, a storage key, a deck or category id, a `[COMPUTER:..]` / `{VAR}` token or
 * anything the person typed, and a plain label never changes what a button does.
 */
enum class LabelKey {
    NAV_MATRIX,
    NAV_LOGS,
    NAV_TARGETS,
    NAV_ZONES,
    NAV_AUDIO,
    NAV_TYPE,
    SETTINGS_ENTRY,
    APP_TAGLINE,
    DECK,
    DECKS,
    DECK_MANAGE,
    DECK_CREATE,
    DECK_NAME,
    DECK_TYPE_MATRIX,
    DECK_TYPE_QUICK,
    DECK_TYPE_EMERGENCY,
    DECK_TYPE_EMOJI,
    DECK_TYPE_GIF,
    POSE,
    POSE_IDENTITY,
    POSE_DEFEND,
    POSE_CONNECT,
    WATCH_POSE,
    TARGET_COMPUTER,
    TARGET_ENTRY,
    TARGET_CATEGORY,
    CONTACT_CARDS,
    SHARED_VARIABLES,
    VARIABLE_CONTEXT,
    INSERT_TARGET_TAG,
    INSERT_VARIABLE,
    BROWSE_TARGETS,
    MEMORY_BANKS,
    SAVE_TO_MEMORY_BANK,
    MANUAL_OVERRIDE,
    COMPOSER,
    MY_STATEMENTS,
    LIVE_PREVIEW,
    AUDIO_ARCHITECT,
    VOICE_PROFILE,
    ROBOTIC_OVERLAY,
    BITCRUSH,
    CUSTOM_VOICE,
    RECORD_TRAINING,
    GEO_PROTOCOL,
    GEO_GRID,
    GEO_ENGINE,
    TERMINAL,
    TERMINAL_LOG,
    STATUSBOX,
    DATA_PORT,
    EXPORT_JSON,
    FULL_RESTORE,
    IMPORT_MATRIX,
    SAFETY_COPIES,
    UPLOAD_PROTOCOL,
    VOX,
    CRYO,
    SHAKE_KILL,
    ENV_SENSOR,
    HARDWARE_CONFIG,
    TWIST_SENS,
    QUICK_ACCESS_KEYS,
    TRAIN_TEST,
    FORCE_SPEAKER,
    SILENT_MODE,
    TWIST_0,
    TWIST_0_MAPPED,
    TWIST_1,
    TWIST_1_MAPPED,
    TWIST_2,
    TWIST_2_MAPPED,
    TWIST_3,
    TWIST_3_MAPPED,
    VARIABLE,
    VARIABLE_TAG,
    GEO_NODES,
    GEO_ADD_NODE,
    DSP_CHAIN,
    ;

    /** The string resource that holds this label's standard text, or its plain text. */
    fun resourceName(plain: Boolean): String = "label_" + name.lowercase() + if (plain) "_plain" else ""

    companion object {
        /** The key called [name], or null if there is none (a HELP placeholder with a typo must not crash anything). */
        fun fromName(name: String): LabelKey? = values().firstOrNull { it.name == name }
    }
}

object PlainLabels {
    /**
     * The key for a stored Matrix slot name (CommandRepository stores "Twist 0 (Default)", "Twist 1", "Twist 2 (Mapped)" and so on, and the screens
     * draw that stored text). Only an exact match counts: a name the person typed is never renamed.
     */
    fun slotLabelKey(stored: String): LabelKey? = slotNames[stored]

    private val slotNames: Map<String, LabelKey> = mapOf(
        "Twist 0 (Default)" to LabelKey.TWIST_0,
        "Twist 1" to LabelKey.TWIST_1,
        "Twist 2" to LabelKey.TWIST_2,
        "Twist 3" to LabelKey.TWIST_3,
        "Twist 0 (Mapped)" to LabelKey.TWIST_0_MAPPED,
        "Twist 1 (Mapped)" to LabelKey.TWIST_1_MAPPED,
        "Twist 2 (Mapped)" to LabelKey.TWIST_2_MAPPED,
        "Twist 3 (Mapped)" to LabelKey.TWIST_3_MAPPED,
    )
}

/**
 * HELP steps are fixed text, written before anyone chose PLAIN WORDS. A step names a label with `{{KEY:Original}}`: [substitute] shows the Original exactly as it
 * has always read when PLAIN WORDS is off, and the plain label when it is on, so HELP always shows the words the person sees on screen. A placeholder with
 * no original (`{{KEY}}`) shows the standard label. Nothing here can show braces or a blank: an unknown key or a missing label falls back to the original.
 */
object HelpPlaceholders {
    private val pattern = Regex("""\{\{([A-Z0-9_]+)(?::([^{}]*))?\}\}""")

    /** Every key named in [text], in order (for the drift test; unknown names included). */
    fun keysIn(text: String): List<String> = pattern.findAll(text).map { it.groupValues[1] }.toList()

    fun substitute(text: String, plain: Boolean, resolve: (LabelKey, Boolean) -> String?): String =
        pattern.replace(text) { match ->
            val name = match.groupValues[1]
            val original = match.groups[2]?.value
            val key = LabelKey.fromName(name)
            when {
                key == null -> original ?: name
                plain -> resolve(key, true) ?: original ?: name
                else -> original ?: resolve(key, false) ?: name
            }
        }
}
