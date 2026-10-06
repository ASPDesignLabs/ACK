// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What EXPORT .JSON (and the Terminal's /backup) tells the person the file contains, and that it is not protected.
 *
 * One source for what is said, so the settings dialog and the Terminal can never say different things. Plain Kotlin (no
 * `android.*`) so it is tested without a phone. The words are string resources (`export_*` in strings.xml, so they are in the chosen language);
 * this holds which of them are said and in what order, and a [TextSource] supplies them. The screens only display what is here.
 *
 * Every field of `AckBackup` must be named in exactly one category (or in [formatFields]). A test reads
 * `backup/AckBackup.kt` and fails if a field is missing, so whoever adds a backed-up field has to decide how this warning
 * describes it. There is deliberately no "everything else" catch-all: that would let a new, sensitive field slip through
 * described as "settings".
 *
 * No password option or app lock is mentioned: neither exists, and neither is planned.
 */
object ExportContents {

    /** [key] names the line's string resource (`export_cat_<key>`); [fields] are the AckBackup fields it describes. */
    class Category(val key: String, val fields: Set<String>) {
        val resource: String get() = "export_cat_$key"
    }

    val categories: List<Category> = listOf(
        Category(
            "emergency_card",
            setOf("emergencyInfoCard"),
        ),
        Category(
            "people_places",
            setOf("computerCategories", "targets"),
        ),
        Category(
            "saved_locations",
            setOf("geoZones"),
        ),
        Category(
            "voice_recordings",
            setOf("voiceRecordings"),
        ),
        Category(
            "messages",
            setOf(
                "matrixData", "quickPhrases", "quickActionsDecks", "emergencyDecks", "savedStatementTree",
                "headerShortcuts", "rootOverrides", "customContextEntries", "decks", "trainingScripts", "syntaxRules",
            ),
        ),
        Category(
            "learned_words",
            setOf("learnedWords"),
        ),
        Category(
            "partner_card",
            setOf("partnerCard"),
        ),
        Category(
            "settings",
            setOf(
                "dsp", "voiceRecordingGainPercent", "autocompleteHistory", "geoEngineMode", "geoMasterToggle",
                "visualPresets", "activeVisualPresetId", "forceDeviceRotation", "outputRouteMode",
                "outputRouteBtAddress", "outputRouteBtLabel", "terminalRetentionDays", "terminalHideSystemMessages",
                "terminalHidePathTrace", "terminalMonospaceEnabled", "terminalStatusboxColorIndex", "shakeThreshold",
                "rootOverrideCollapsed", "activeDeckId", "activeDeckColorIndex", "activeProfile", "activeCategoryFocus",
                "warnBeforeProfileChange", "speechLanguage", "interfaceLanguage", "plainWords",
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

    // Resource names, not words: the text is in strings.xml, in every language.
    const val CONTAINS_HEADING = "export_contains_heading"
    const val NOT_PROTECTED = "export_not_protected"
    const val WHERE_TO_SAVE = "export_where_to_save"
    const val TERMINAL_QUESTION = "export_terminal_question"
    const val TERMINAL_CONFIRM = "export_terminal_confirm"
    const val EXPORTED = "backup_exported"
    const val FAILED = "backup_failed"

    /** What the toast and the Terminal say after a good export. */
    fun exportedText(text: TextSource): String = text.get(EXPORTED)

    /**
     * What they say after a failed one: that it failed, why in words, and that nothing was saved. [reason] is the NAME of a reason string
     * (`backup_fail_*`, chosen by BackupExporter), never any of the person's own data.
     */
    fun failedText(text: TextSource, reason: String): String = text.get(FAILED, text.get(reason))

    /** The settings dialog's body as plain text: what the screen shows, line for line. */
    fun dialogText(text: TextSource): String = buildString {
        appendLine(text.get(CONTAINS_HEADING))
        categories.forEach { appendLine("- ${text.get(it.resource)}") }
        appendLine()
        appendLine(text.get(NOT_PROTECTED))
        appendLine()
        append(text.get(WHERE_TO_SAVE))
    }

    /**
     * The Terminal's reply to a bare /backup: the same facts, then the line that still has to be typed. Each line is its
     * own row in the Terminal's response block, so the lines stay short.
     */
    fun terminalText(text: TextSource): String = buildString {
        appendLine(text.get(TERMINAL_QUESTION))
        appendLine(text.get(CONTAINS_HEADING))
        categories.forEach { appendLine("- ${text.get(it.resource)}") }
        appendLine(text.get(NOT_PROTECTED))
        appendLine(text.get(WHERE_TO_SAVE))
        append(text.get(TERMINAL_CONFIRM))
    }
}
