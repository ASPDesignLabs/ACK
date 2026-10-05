// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.capture.CaptureConstants
import com.example.besu.capture.CaptureNotice
import com.example.besu.capture.ClipFlags
import com.example.besu.capture.ClipState
import com.example.besu.capture.DiskRoom
import com.example.besu.capture.NoiseVerdict
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

    // ---- the recording screen: setup, the quiet check, the live card, free speech and the summary --------------------------------------------

    /** The setup line about the cards: how many, and (when the session starts partway) how many are already recorded. [pending] is how many this session would record. */
    fun setupCardsLine(text: TextSource, cards: Int, pending: Int, includeDone: Boolean): String =
        if (pending < cards && !includeDone) text.get("capture_setup_cards_skipping", cards, cards - pending) else text.get("capture_setup_cards", cards)

    /** What the toggle says it is doing: including or skipping the cards that already have a clip (the screen's own state, never read back from this word). */
    fun includeDoneLabel(text: TextSource, includeDone: Boolean, allDone: Boolean): String =
        text.get(if (includeDone || allDone) "capture_including_done" else "capture_skipping_done")

    /** "CARDS ARE SIZED FOR 2.6 WORDS A SECOND (...)"; [own] is true when the pace is the person's measured one. */
    fun paceLine(text: TextSource, pace: Double, own: Boolean): String = text.get(if (own) "capture_pace_own" else "capture_pace_typical", oneDecimal(pace))

    /** How long a quiet gap ends a card, in seconds with one decimal ([endWaitHops] is in 10 ms hops). */
    fun waitNote(text: TextSource, endWaitHops: Int): String = text.get("capture_wait_note", oneDecimal(endWaitHops / 100.0))

    /** The button that starts the quiet check, with its real length ([CaptureConstants.NOISE_CHECK_S]). */
    fun startQuietLabel(text: TextSource): String = text.get("capture_start_quiet", CaptureConstants.NOISE_CHECK_S.toInt())

    /** The paragraph about anyone nearby on the free-speech setup screen, with the engine's own limit in minutes. */
    fun freeNoticeSetup(text: TextSource): String = text.get("capture_free_notice_setup", CaptureConstants.MAX_FREE_SESSION_S / 60)

    /** The note under the free recording's timer, with the engine's own limit in minutes. */
    fun freeNote(text: TextSource): String = text.get("capture_free_note", CaptureConstants.MAX_FREE_SESSION_S / 60)

    /** What the quiet check heard. [floorDbfs] is the room level to one decimal, as the check measured it (negative; it is written as a number and never changed). */
    fun noiseVerdict(text: TextSource, verdict: NoiseVerdict, floorDbfs: Double?): String = when (verdict) {
        NoiseVerdict.GOOD -> text.get("capture_noise_good", floorDbfs.toString())
        NoiseVerdict.LOUD_ROOM -> text.get("capture_noise_loud", floorDbfs.toString())
        NoiseVerdict.NO_SIGNAL -> text.get("capture_noise_none")
        NoiseVerdict.INTERRUPTED -> text.get("capture_noise_interrupted")
    }

    /** "CARD 3 OF 10", and "  (TRY 2)" after it from the second try on. [card] counts from 1. */
    fun cardHeading(text: TextSource, card: Int, total: Int, attempt: Int): String =
        text.get("capture_card_of", card, total) + if (attempt > 1) "  " + text.get("capture_try", attempt) else ""

    fun keptLeft(text: TextSource, kept: Int, left: Int): String = text.get("capture_kept_left", kept, left)

    /** What a script session is doing now: paused, hearing the person, or waiting for them. */
    fun scriptStatus(text: TextSource, paused: Boolean, inSpeech: Boolean): String =
        text.get(if (paused) "capture_paused" else if (inSpeech) "capture_hearing" else "capture_listening")

    /** What a free recording is doing now. */
    fun freeStatus(text: TextSource, paused: Boolean, inSpeech: Boolean): String =
        text.get(if (paused) "capture_paused" else if (inSpeech) "capture_free_hearing" else "capture_free_talk")

    /** The line about the card after this one: its text as written, cut to 70 characters with "..." when longer. */
    fun nextLine(text: TextSource, cardText: String): String = text.get("capture_next", cardText.take(70) + if (cardText.length > 70) "..." else "")

    /** "LAST SAVED: CARD 4, 3.2 S. MARK IT IF NEEDED:". */
    fun lastSaved(text: TextSource, card: Int, seconds: Double): String = text.get("capture_last_saved", card, oneDecimal(seconds))

    /** How a session ended, carried by what happened (never by a sentence). */
    sealed interface SessionSummary {
        data class Script(val kept: Int, val cardsLeft: Int) : SessionSummary
        data class Free(val durationS: Double, val pieces: Int) : SessionSummary
        object NothingRecorded : SessionSummary
    }

    fun summary(text: TextSource, summary: SessionSummary): String = when (summary) {
        is SessionSummary.Script -> text.get(if (summary.cardsLeft > 0) "capture_summary_script_left" else "capture_summary_script_all", summary.kept, summary.cardsLeft)
        is SessionSummary.Free -> text.get("capture_summary_free", clock(summary.durationS), summary.pieces)
        SessionSummary.NothingRecorded -> text.get("capture_nothing_recorded")
    }

    /** The paragraph after a session ends; it names the SAVE TO A FILE button as that button reads in the language. */
    fun finishedNote(text: TextSource): String = text.get("capture_finished_note", text.get("capture_save_file"))

    // ---- what the engines, the microphone and the screen report ----------------------------------------------------------------------------

    /** "500 MB free, room for about 20 minutes of recording" (English keeps its lower case; the numbers are the engine's). */
    fun roomLeft(text: TextSource, room: DiskRoom): String = text.get("capture_room_left", room.megabytes, room.minutes)

    fun notice(text: TextSource, notice: CaptureNotice): String = when (notice) {
        is CaptureNotice.CouldNotSave -> text.get("capture_n_save_failed", notice.detail ?: text.get("capture_n_storage_error"))
        is CaptureNotice.OutOfRoomKeptClipsSafe -> text.get("capture_n_room_clips", roomLeft(text, notice.room))
        is CaptureNotice.OutOfRoomRecordingSaved -> text.get("capture_n_room_free", roomLeft(text, notice.room))
        is CaptureNotice.NothingHeard -> text.get("capture_n_idle", notice.seconds)
        is CaptureNotice.LongestRecording -> text.get("capture_n_longest", notice.minutes)
        CaptureNotice.MicNotAllowed -> text.get("capture_n_mic_not_allowed")
        CaptureNotice.MicDenied -> text.get("capture_n_mic_denied")
        CaptureNotice.MicCouldNotOpen -> text.get("capture_n_mic_open")
        is CaptureNotice.MicTrouble -> text.get("capture_n_mic_trouble", notice.detail)
        is CaptureNotice.MicStopped -> text.get("capture_n_mic_stopped", notice.errorCode)
        is CaptureNotice.NotEnoughRoomToStart -> text.get("capture_n_no_room", roomLeft(text, notice.room), notice.needMegabytes)
        CaptureNotice.ScriptGone -> text.get("capture_n_script_gone")
        is CaptureNotice.ScriptUnreadable -> notice.detail ?: text.get("capture_n_script_unreadable")
        is CaptureNotice.CouldNotStart -> notice.detail ?: text.get("capture_n_start_failed")
    }
}
