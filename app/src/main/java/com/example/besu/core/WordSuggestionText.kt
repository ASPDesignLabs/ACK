// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words around WORD SUGGESTIONS (SETTINGS and the one-time offer in the Statement Composer). One source, so the screens only display what
 * is here and a test can hold the wording to what the feature really does. Capitals, like the rest of the app.
 */
object WordSuggestionText {
    fun switchLabel(on: Boolean): String = "WORD SUGGESTIONS: ${if (on) "ON" else "OFF"}"

    const val SWITCH_EXPLANATION =
        "WHEN ON, THE STATEMENT COMPOSER OFFERS WORDS UNDER THE TEXT BOX: THE REST OF THE WORD YOU ARE TYPING, OR THE WORD THAT USUALLY COMES NEXT. " +
            "NOTHING IS ADDED UNTIL YOU TAP IT. " +
            "IT STARTS EMPTY AND LEARNS ONLY FROM STATEMENTS YOU SAVE, SPEAK OR COPY, AND FROM NAMES YOU ALREADY KEEP IN TARGET COMPUTER AND SHARED VARIABLES. " +
            "IT NEVER LEARNS FROM THE EMERGENCY DECK, THE TERMINAL, MANUAL OVERRIDE, TAGS OR NUMBERS. " +
            "THE WORDS ARE KEPT ON THIS PHONE ONLY AND ARE INCLUDED IF YOU SAVE EXPORT .JSON. FORGET WORDS REMOVES THEM."

    // For everyone: said once, dismissible, and nothing is learned unless it is tapped.
    const val OFFER_TEXT =
        "NEW: WORD SUGGESTIONS IN THE STATEMENT COMPOSER. IT IS OFF AND NOTHING IS LEARNED UNLESS YOU TURN IT ON."
    const val OFFER_TURN_ON = "TURN ON"
    const val OFFER_NOT_NOW = "NOT NOW"

    // ---- FORGET WORDS (SETTINGS) ----------------------------------------------------------------------------------------------

    const val FORGET_BUTTON = "FORGET WORDS"
    const val FORGET_TITLE = "FORGET WORDS"
    const val FORGET_EMPTY =
        "NO WORDS LEARNED YET. THEY APPEAR HERE AFTER YOU SAVE, SPEAK OR COPY A STATEMENT WITH WORD SUGGESTIONS ON."

    fun countLine(count: Int): String = "WORDS LEARNED: ${if (count <= 0) "NONE YET" else count.toString()}"

    fun usedLine(times: Int): String = "USED $times ${if (times == 1) "TIME" else "TIMES"}"

    // One word: removing it only takes one more tap to confirm, and it can be learned again.
    const val REMOVE_QUESTION = "REMOVE THIS WORD? IT CAN BE LEARNED AGAIN LATER."
    const val REMOVE = "REMOVE"
    const val REMOVE_CANCEL = "KEEP"

    // All of them: asks twice, names the backup first, and says what is not touched.
    const val FORGET_ALL = "FORGET ALL WORDS"
    const val BACK_UP_FIRST = "BACK UP FIRST"
    const val CONTINUE = "CONTINUE"
    const val CANCEL = "CANCEL"
    // The same two sentences DELETE DATA says (strings.xml `storage_cannot_undo`, `storage_not_elsewhere`). This screen's own words move to string
    // resources in a later change; until then they stay word for word, and WordSuggestionTextTest fails if the two ever differ.
    const val FORGET_ALL_SECOND = "THIS CANNOT BE UNDONE."
    const val NOT_ELSEWHERE =
        "THIS DOES NOT DELETE FILES YOU SAVED ELSEWHERE (EXPORTS, PACKAGES, BACKUPS) OR ANYTHING YOU COPIED TO ANOTHER APP."

    fun forgetAllFirstConfirmation(count: Int): List<String> = listOf(
        "THIS REMOVES ${if (count == 1) "THE 1 LEARNED WORD" else "ALL $count LEARNED WORDS"} AND WHICH WORDS FOLLOW WHICH.",
        "THEY ARE IN EXPORT .JSON. SAVE IT FIRST IF YOU MIGHT WANT THEM BACK.",
        "NAMES FROM TARGET COMPUTER AND SHARED VARIABLES ARE NOT AFFECTED: THEY ARE NOT STORED HERE.",
        "WORD SUGGESTIONS STAYS ON OR OFF AS IT IS. WHILE IT IS ON, WORDS ARE LEARNED AGAIN AS YOU SAVE, SPEAK OR COPY.",
        NOT_ELSEWHERE,
    )
}
