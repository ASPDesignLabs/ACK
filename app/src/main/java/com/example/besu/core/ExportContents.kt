// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What EXPORT .JSON (and the Terminal's /backup) tells the person the file contains, and that it is not protected.
 *
 * One source for the wording, so the settings dialog and the Terminal can never say different things. Plain Kotlin (no
 * `android.*`) so it is tested without a phone. The screens only display what is here.
 *
 * Every field of `AckBackup` must be named in exactly one category (or in [formatFields]). A test reads
 * `backup/AckBackup.kt` and fails if a field is missing, so whoever adds a backed-up field has to decide how this warning
 * describes it. There is deliberately no "everything else" catch-all: that would let a new, sensitive field slip through
 * described as "settings".
 *
 * No password option or app lock is mentioned: neither exists, and neither is planned.
 */
object ExportContents {

    class Category(val label: String, val fields: Set<String>)

    val categories: List<Category> = listOf(
        Category(
            "EMERGENCY INFO CARD",
            setOf("emergencyInfoCard"),
        ),
        Category(
            "PEOPLE AND PLACES, WITH PHONE NUMBERS AND ADDRESSES",
            setOf("computerCategories", "targets"),
        ),
        Category(
            "SAVED LOCATIONS (MAP COORDINATES)",
            setOf("geoZones"),
        ),
        Category(
            "YOUR VOICE RECORDINGS (THE AUDIO ITSELF)",
            setOf("voiceRecordings"),
        ),
        Category(
            "MESSAGES, STATEMENTS AND DECKS",
            setOf(
                "matrixData", "quickPhrases", "quickActionsDecks", "emergencyDecks", "savedStatementTree",
                "headerShortcuts", "rootOverrides", "customContextEntries", "decks", "trainingScripts", "syntaxRules",
            ),
        ),
        Category(
            "SETTINGS AND HISTORY",
            setOf(
                "dsp", "voiceRecordingGainPercent", "autocompleteHistory", "geoEngineMode", "geoMasterToggle",
                "visualPresets", "activeVisualPresetId", "forceDeviceRotation", "outputRouteMode",
                "outputRouteBtAddress", "outputRouteBtLabel", "terminalRetentionDays", "terminalHideSystemMessages",
                "terminalHidePathTrace", "terminalMonospaceEnabled", "terminalStatusboxColorIndex", "shakeThreshold",
                "rootOverrideCollapsed", "activeDeckId", "activeDeckColorIndex", "activeProfile", "activeCategoryFocus",
            ),
        ),
    )

    /**
     * Fields that describe the file itself (its format number, when it was made, and whether its phone was given the starter
     * phrases), not anything the person stored.
     */
    val formatFields: Set<String> = setOf("version", "timestamp", "starterPhrasesSeeded")

    /** Every field name the warning accounts for. */
    val mappedFields: Set<String> get() = categories.flatMapTo(HashSet(formatFields)) { it.fields }

    const val CONTAINS_HEADING = "THIS FILE CAN CONTAIN:"

    const val NOT_PROTECTED =
        "IT IS NOT ENCRYPTED AND HAS NO PASSWORD. ANYONE WHO OPENS IT CAN READ ALL OF IT."

    const val WHERE_TO_SAVE =
        "SAVE IT WHERE YOU CONTROL WHO CAN SEE IT: THIS PHONE'S OWN STORAGE, OR YOUR OWN COMPUTER BY CABLE. " +
            "AVOID GOOGLE DRIVE, ONEDRIVE AND OTHER ONLINE FOLDERS. THEIR APP WOULD UPLOAD IT."

    const val TERMINAL_QUESTION = "EXPORT ACK BACKUP?"
    const val TERMINAL_CONFIRM = "TYPE /backup CONFIRM TO PROCEED."

    /** The settings dialog's body as plain text: what the screen shows, line for line. */
    fun dialogText(): String = buildString {
        appendLine(CONTAINS_HEADING)
        categories.forEach { appendLine("- ${it.label}") }
        appendLine()
        appendLine(NOT_PROTECTED)
        appendLine()
        append(WHERE_TO_SAVE)
    }

    /**
     * The Terminal's reply to a bare /backup: the same facts, then the line that still has to be typed. Each line is its
     * own row in the Terminal's response block, so the lines stay short.
     */
    fun terminalText(): String = buildString {
        appendLine(TERMINAL_QUESTION)
        appendLine(CONTAINS_HEADING)
        categories.forEach { appendLine("- ${it.label}") }
        appendLine(NOT_PROTECTED)
        appendLine(WHERE_TO_SAVE)
        append(TERMINAL_CONFIRM)
    }
}
