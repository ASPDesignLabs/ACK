// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** A starter phrase the seed wrote: where it is stored, where the seed noted it, and the exact text it wrote. */
data class SeededPhrase(val storageKey: String, val recordKey: String, val text: String)

/**
 * The one narrow exception to "a restore never removes anything the backup does not mention" (see CLAUDE.md, BACKUP & RESTORE).
 * Plain Kotlin (no `android.*`) so the rule is tested without a phone; data/StarterSeed.kt carries it out.
 *
 * Why it exists: a backup never records a phrase that was left at the built-in text. Restore a backup from a phone that showed
 * the built-in wording onto a phone that was given the starter phrases, and every slot the person never touched would show a
 * starter instead of what the old phone showed. A starter phrase nobody ever edited is not the person's data, so it can be taken
 * back; everything else follows the usual additive rule.
 */
object StarterRestore {

    /**
     * The seed's note (record key to the text it wrote, as the note file holds it) as phrases. Anything that is not one of the
     * twelve starters, or is not text, is ignored. Only the DEFAULT deck is ever noted: a Matrix deck made later did not exist
     * when an older backup was made, so its starters are never taken back.
     */
    fun seededPhrases(note: Map<String, *>): List<SeededPhrase> =
        StarterSets.matrixPhrases.mapNotNull { phrase ->
            val recordKey = StarterSets.recordKey(phrase.path)
            val text = note[recordKey] as? String ?: return@mapNotNull null
            SeededPhrase(PhraseKeys.storageKey("DEFAULT", "DEFAULT", phrase.path), recordKey, text)
        }

    /**
     * The starters to take back before a backup is restored.
     *
     * @param seeded what the seed wrote on this phone ([seededPhrases])
     * @param current what the matrix preferences hold now, key to text (a key that is not stored is simply absent)
     * @param backupKeys the phrase keys the backup file mentions; the file wins for those, so they are never taken back
     * @param backupFromSeededPhone true if the file came from a phone that was given the starters (its phrases already say what
     *   that phone showed); false if that phone had none; null if the file is older than the marker. Only a true keeps them.
     *
     * A starter is taken back only if the file does not mention it AND it still holds exactly the text the seed wrote (so a person's
     * edit, even of one space, keeps it).
     */
    fun toTakeBack(
        seeded: List<SeededPhrase>,
        current: Map<String, String>,
        backupKeys: Set<String>,
        backupFromSeededPhone: Boolean?
    ): List<SeededPhrase> {
        if (backupFromSeededPhone == true) return emptyList()
        return seeded.filter { it.storageKey !in backupKeys && current[it.storageKey] == it.text }
    }
}
