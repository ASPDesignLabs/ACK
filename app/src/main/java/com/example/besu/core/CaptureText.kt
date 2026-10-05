// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.capture.ClipFlags
import com.example.besu.capture.ClipState
import java.util.Locale

/**
 * What the RECORD TRAINING DATA screens say that is decided, not just drawn: the library's lines and notices, the script editor's counts and warnings, a session's and a clip's lines in the detail dialog,
 * and the messages after saving a package. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`capture_*`, in the chosen language) read through a [TextSource].
 *
 * **Stored words are logic and are never translated.** A session's mode (`script` / `free`), a script's line setting (`join` / `keep`), a clip's state, a mark's id (`noise`, `unclear`, `laugh`, `cough`, `stumble`, and the
 * automatic `long`, `short`, `no_end`), a session's microphone source (`UNPROCESSED`) and every id are saved in the notes and read by the computer; only the word *drawn* for them follows the language, and one with no word
 * here is shown as it is (a mark the person's computer added, say). A session's name, a script's title and the person's typed text are shown exactly as typed.
 *
 * **Numbers and units stay as they were written**: Latin digits (`Locale.ROOT`), `MB`, `KHZ`, `DB`, `S` and `UTC` are symbols, and the `//` between parts is the app's own separator, added here and never inside a
 * resource. Counts are written as "SESSIONS: 3" in a translation so no language has to agree a word with a number; English keeps its exact wording ("3 SESSIONS", "SESSION(S)").
 *
 * **What the storage and package layers say stays as they say it.** A `StoreException` or a package problem is a technical sentence (a file that cannot be read, a checksum that differs); it is shown as it comes, inside
 * a sentence of ours that says what it means for the person's recordings. Only the screens' own fallbacks are translated.
 */
object CaptureText {
    private const val SEPARATOR = "  //  "

    // ---- numbers, as the screens always wrote them ---------------------------------------------------------------------------------

    /** "12.3 MB": a size with one decimal. */
    fun megabytes(bytes: Long): String = String.format(Locale.ROOT, "%.1f MB", bytes / 1_048_576.0)

    /** "1:05" for a minute and five seconds, "1:02:03" from an hour on. */
    fun clock(seconds: Double): String {
        val s = seconds.toInt()
        return if (s >= 3600) String.format(Locale.ROOT, "%d:%02d:%02d", s / 3600, (s / 60) % 60, s % 60) else String.format(Locale.ROOT, "%d:%02d", s / 60, s % 60)
    }

    fun oneDecimal(value: Double): String = String.format(Locale.ROOT, "%.1f", value)

    fun wholeNumber(value: Double): String = String.format(Locale.ROOT, "%.0f", value)

    // ---- the library -----------------------------------------------------------------------------------------------------------------

    /** The tip about the walkthrough. [helpButton] is the HELP button's word and [screenName] the RECORD TRAINING DATA label (both follow the language and PLAIN WORDS), so the sentence points at things that exist. */
    fun helpOffer(text: TextSource, helpButton: String, screenName: String): String = text.get("capture_help_offer", helpButton, screenName)

    /** "ON THIS PHONE: 3 SESSIONS, 12.3 MB USED, 4000.0 MB FREE"; [used] and [free] are sizes already written by [megabytes]. */
    fun phoneLine(text: TextSource, sessions: Int, used: String, free: String): String = text.get("capture_on_phone", sessions, used, free)

    /** What was repaired after the app closed unexpectedly, or, when some recordings could not be repaired, the first thing that went wrong (as the storage layer worded it). */
    fun recoveryNotice(text: TextSource, sessionsClosed: Int, clipsRecovered: Int, problems: List<String>): String =
        if (problems.isEmpty()) text.get("capture_recovered", sessionsClosed, clipsRecovered) else text.get("capture_recovery_problem", problems.first())

    enum class DamagedKind { SCRIPT, SESSION }

    /** A script or a session the phone could not read: its kind and its folder name, as they are on the phone. */
    data class Damaged(val kind: DamagedKind, val name: String)

    /** "COULD NOT READ: script a1, session b2. THEIR FILES WERE LEFT AS THEY ARE." */
    fun damagedNotice(text: TextSource, items: List<Damaged>): String =
        text.get("capture_damaged", items.joinToString(", ") { text.get(if (it.kind == DamagedKind.SCRIPT) "capture_damaged_script" else "capture_damaged_session", it.name) })

    /** A script's card count and how many are recorded, with "(ALL DONE)" once every card has a clip (and there is at least one). */
    fun scriptCardsLine(text: TextSource, cards: Int, done: Int): String {
        val base = text.get("capture_script_cards", cards, done)
        return if (done >= cards && cards > 0) listOf(base, text.get("capture_all_done")).joinToString(" ") else base
    }

    /** The free-speech paragraph; [minutes] is the engine's own limit ([com.example.besu.capture.CaptureConstants.MAX_FREE_SESSION_S] in minutes), so the screen cannot say a limit the engine does not keep. */
    fun freeIntro(text: TextSource, minutes: Int): String = text.get("capture_free_intro", minutes)

    /** A session's heading: its script's title as saved (or the word SCRIPT when it has none), or FREE SPEECH, then the name the person gave it after " // ". */
    fun sessionTitle(text: TextSource, mode: String, scriptTitle: String?, label: String): String {
        val kind = if (mode == "script") scriptTitle ?: text.get("capture_script_word") else text.get("capture_free_speech")
        return kind + if (label.isNotEmpty()) " // $label" else ""
    }

    /** A session's second line: when it started (UTC, as saved), what was kept or how long it is, its size, and NOT ENDED while it is still open. [durationS] is the free recording's length, null when there is none. */
    fun sessionLine(text: TextSource, started: String, mode: String, kept: Int, durationS: Double?, bytes: Long, closed: Boolean): String = listOfNotNull(
        started.replace('T', ' ').removeSuffix("Z") + " UTC",
        if (mode == "script") text.get("capture_kept_count", kept) else (durationS?.let { clock(it) } ?: text.get("capture_no_recording")),
        megabytes(bytes),
        if (!closed) text.get("capture_not_ended") else null,
    ).joinToString(SEPARATOR)

    fun heldLine(text: TextSource, held: Int): String = text.get("capture_held", held)

    fun savingLine(text: TextSource, index: Int, total: Int): String = text.get("capture_saving", index, total)

    fun savingBytes(text: TextSource, done: Long, total: Long): String = text.get("capture_saving_bytes", megabytes(done), megabytes(total))

    /** What deleting a session removes: its size when it is known, otherwise "its recordings". */
    fun deleteSessionBody(text: TextSource, bytes: Long?): String =
        if (bytes != null) text.get("capture_delete_session_body", megabytes(bytes)) else text.get("capture_delete_session_body_unknown")

    /** Why a save did not happen or did not stay. A technical detail ([FailedCheck.first], [CouldNotMake.detail], [Failed.detail]) is the package layer's own sentence, shown inside ours. */
    sealed interface SaveNotice {
        object NothingToSave : SaveNotice
        data class TooBig(val sessions: List<String>) : SaveNotice
        object CouldNotOpen : SaveNotice
        object CouldNotReadBack : SaveNotice
        data class FailedCheck(val first: String) : SaveNotice
        data class CouldNotMake(val detail: String?) : SaveNotice
        data class Failed(val detail: String) : SaveNotice
    }

    fun saveNotice(text: TextSource, notice: SaveNotice): String = when (notice) {
        SaveNotice.NothingToSave -> text.get("capture_nothing_to_save")
        is SaveNotice.TooBig -> text.get("capture_too_big", notice.sessions.joinToString())
        SaveNotice.CouldNotOpen -> text.get("capture_pkg_open")
        SaveNotice.CouldNotReadBack -> text.get("capture_pkg_readback")
        is SaveNotice.FailedCheck -> text.get("capture_pkg_check", notice.first)
        is SaveNotice.CouldNotMake -> notice.detail ?: text.get("capture_pkg_make")
        is SaveNotice.Failed -> text.get("capture_pkg_failed", notice.detail)
    }

    // ---- the script editor -----------------------------------------------------------------------------------------------------------

    /** "120 OF 20000 CHARACTERS". */
    fun charsLine(text: TextSource, length: Int, max: Int): String = text.get("capture_chars", length, max)

    /** What the chosen line-break setting does (`join` or `keep`, the stored values). */
    fun lineBreakNote(text: TextSource, lines: String): String = text.get(if (lines == "join") "capture_join_note" else "capture_keep_note")

    /** The cards a text will become: how many, about how many minutes at what pace, and whether the pace is the person's own. [minutes] and [pace] are written with [wholeNumber] and [oneDecimal]. */
    fun cardsSummary(text: TextSource, cards: Int, minutes: Double, pace: Double, measured: Boolean): String =
        text.get(if (measured) "capture_cards_own" else "capture_cards_typical", cards, wholeNumber(minutes), oneDecimal(pace))

    fun symbolCards(text: TextSource, count: Int): String = text.get("capture_symbol_cards", count)

    fun andMore(text: TextSource, count: Int): String = text.get("capture_and_more", count)

    /** The language code must look like [example] (EN-US is what English shows). */
    fun languageCodeBad(text: TextSource, example: String): String = text.get("capture_language_code_bad", example)

    /** The question when an existing script is saved: its title as saved, in quotes. */
    fun saveChangesBody(text: TextSource, title: String?): String = text.get("capture_save_changes_body", title ?: "")

    // ---- the session detail dialog -------------------------------------------------------------------------------------------------

    /** The line of facts under a session's heading: its id, the sample rate, the microphone source as saved, the room's level when one was measured, and NOT ENDED while it is open. */
    fun detailsLine(text: TextSource, id: String, sampleRate: Int, source: String, noiseFloorDbfs: Double?, closed: Boolean): String = listOfNotNull(
        id,
        (sampleRate / 1000.0).toString() + " KHZ",
        source,
        noiseFloorDbfs?.let { text.get("capture_room_db", it.toString()) },
        if (!closed) text.get("capture_not_ended") else null,
    ).joinToString(SEPARATOR)

    /** A free recording's line: how long it is, how many pieces the phone suggests cutting it into, and what state it is in. */
    fun recordingLine(text: TextSource, durationS: Double, pieces: Int, state: String): String =
        text.get("capture_recorded_pieces", clock(durationS), pieces) + SEPARATOR + recordingState(text, state)

    fun recordingState(text: TextSource, state: String): String = text.get(
        when (state) {
            ClipState.DONE -> "capture_state_kept"
            ClipState.RECOVERED -> "capture_state_repaired_waiting"
            else -> "capture_state_unfinished"
        }
    )

    fun clipState(text: TextSource, state: String): String = text.get(
        when (state) {
            ClipState.DONE -> "capture_state_kept"
            ClipState.REDONE -> "capture_state_set_aside"
            ClipState.RECOVERED -> "capture_state_repaired_decide"
            else -> "capture_state_unfinished"
        }
    )

    /** A clip's line: its card, which try it was, its length and its state. */
    fun clipLine(text: TextSource, card: Int, attempt: Int, durationS: Double, state: String): String =
        text.get("capture_clip_line", card, attempt) + SEPARATOR + oneDecimal(durationS) + " S" + SEPARATOR + clipState(text, state)

    /** How many clips are kept and how many are set aside or still waiting. */
    fun keptAside(text: TextSource, kept: Int, others: Int): String = text.get("capture_kept_aside", kept, others)

    private val MARK_WORDS = mapOf(
        "noise" to "capture_mark_noise", "unclear" to "capture_mark_unclear", "laugh" to "capture_mark_laugh", "cough" to "capture_mark_cough", "stumble" to "capture_mark_stumble",
        "long" to "capture_mark_long", "short" to "capture_mark_short", "no_end" to "capture_mark_no_end",
    )

    /** The word for a mark (the stored id: noise, unclear...). A mark this build has no word for is shown as its id in capitals, as it always was. */
    fun markWord(text: TextSource, flag: String): String = MARK_WORDS[flag]?.let { text.get(it) } ?: flag.uppercase()

    /** "NOTES: LONG, NOISE": the marks on a clip that the person did not set (the automatic ones), in words. */
    fun notesLine(text: TextSource, flags: List<String>): String = text.get("capture_notes", flags.filter { it !in ClipFlags.PERSON }.joinToString(", ") { markWord(text, it) })
}
