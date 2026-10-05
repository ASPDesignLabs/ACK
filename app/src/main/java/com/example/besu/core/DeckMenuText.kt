// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the deck menu in MainActivity's header says that is decided, not just drawn: the SYSTEM DEFAULT row, a deck's row, the MANAGE mode's hint and its locked notice, the edit panel's title and the two
 * confirmations that delete a deck. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`deckmenu_*`, in the chosen language) read through a [TextSource].
 *
 * **A saved name is shown as saved.** A deck's name is the person's own (or the English type name a new deck was saved with) and is handed to a sentence as an argument, never part of the format.
 * The words for the deck and for a deck's type come in as arguments too (`labelFor(LabelKey.DECK)` and the deck-type labels), so they follow PLAIN WORDS and the language like every other screen.
 *
 * **Deleting a deck asks twice and never deletes on the first.** The first question marks the deck for deletion; the second names what is lost (the deck, its local configuration, and for a GIF deck its
 * GIF files), says it cannot be undone and what to back up first, and is the only place the delete button is. The GIF sentence and the back-up advice are part of the decision ([finalConfirmation]) so a test can
 * check they are said, in every language, for the right kind of deck.
 */
object DeckMenuText {
    /** The always-present Matrix deck's row. [matrixWord] is the deck-type label for Matrix (it follows PLAIN WORDS). */
    fun systemDefaultRow(text: TextSource, matrixWord: String): String = text.get("deckmenu_system_default", matrixWord)

    /** Another deck's row: its saved name, then its type's word. */
    fun deckRow(deckName: String, typeWord: String): String = "$deckName // $typeWord"

    /** The MANAGE mode's one-line hint. [deckWord] is the DECK label. */
    fun manageHint(text: TextSource, deckWord: String): String = text.get("deckmenu_manage_hint", deckWord)

    /** The notice that the permanent Matrix deck cannot be changed: its heading, then its sentence. A language may put the two words in either order. */
    fun lockedTitle(text: TextSource, matrixWord: String, deckWord: String): String = text.get("deckmenu_locked_title", matrixWord, deckWord)
    fun lockedBody(text: TextSource, matrixWord: String, deckWord: String): String = text.get("deckmenu_locked_body", matrixWord, deckWord)

    /** The small tag at the end of a MANAGE row: [LOCKED] for the permanent deck, [EDIT] for any other. */
    fun rowTag(text: TextSource, locked: Boolean): String = text.get(if (locked) "deckmenu_locked_tag" else "deckmenu_edit_tag")

    /** The edit panel's title. [typeWord] is the deck's type word. */
    fun editTitle(text: TextSource, typeWord: String): String = text.get("deckmenu_edit_title", typeWord)

    /** The first deletion dialog: its title ([deckWord] is the DECK label) and the question that names the deck exactly as saved. */
    fun deleteTitle(text: TextSource, deckWord: String): String = text.get("deckmenu_delete_title", deckWord)
    fun deleteQuestion(text: TextSource, deckName: String): String = text.get("deckmenu_delete_question", deckName)

    /**
     * The words the back-up advice points at, each as the screen it names words it (so they follow PLAIN WORDS and the language): [exportJson] the EXPORT .JSON label; for a GIF deck, whose files are not in that
     * file, [gifExportEntry] the GIF screen's EXPORT DECK (.ZIP) entry, [gifBackupMenu] its BACKUP button and [gifLabel] the GIF deck-type label.
     */
    class BackupWords(val exportJson: String, val gifExportEntry: String, val gifBackupMenu: String, val gifLabel: String)

    /**
     * The final deletion dialog's body. [gifWarning] is null for every deck but a GIF deck, whose files are deleted with it. [backupAdvice] is always said: that it cannot be undone, then what to back up first. Every
     * other deck's configuration is in EXPORT .JSON; a GIF deck's files are not, so its advice is the GIF screen's own BACKUP menu.
     */
    class FinalConfirmation(val question: String, val removes: String, val gifWarning: String?, val backupAdvice: String)

    fun finalConfirmation(text: TextSource, deckName: String, deckWord: String, isGifDeck: Boolean, words: BackupWords): FinalConfirmation = FinalConfirmation(
        question = text.get("deckmenu_final_question", deckName),
        removes = text.get("deckmenu_final_removes", deckWord),
        gifWarning = if (isGifDeck) text.get("deckmenu_final_gif", deckWord) else null,
        backupAdvice = listOf(
            text.get("storage_cannot_undo"),
            if (isGifDeck) text.get("deckmenu_final_backup_gif", words.gifExportEntry, words.gifBackupMenu, words.gifLabel) else text.get("deckmenu_final_backup", words.exportJson),
        ).joinToString(" "),
    )
}
