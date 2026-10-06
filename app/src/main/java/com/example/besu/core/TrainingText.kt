// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What a drill round decided about one watch fire. The Training Ground and the Deck Trainer used to keep this as the text they drew ("+10", "-5", "MISS") and read it back to choose a
 * colour (a "-" at the front, the word MISS). Once the word is translated that comparison would quietly stop working, so the decision is carried as a kind and the words are made from it.
 */
data class TrainingOutcome(val kind: Kind, val points: Int) {
    enum class Kind { HIT, PENALTY, MISS }

    companion object {
        fun hit(points: Int): TrainingOutcome = TrainingOutcome(Kind.HIT, points)
        fun penalty(points: Int): TrainingOutcome = TrainingOutcome(Kind.PENALTY, points)
        val MISS: TrainingOutcome = TrainingOutcome(Kind.MISS, 0)
    }
}

/**
 * The statement a Deck Trainer target asks the person to say, as a decision and not as text. The person's own phrase is shown exactly as saved; the three things the trainer says when there
 * is no phrase (no Quick Actions group is bound to that pose, the slot is blank, there is no such Matrix slot) are made into words at draw time, in the chosen language.
 */
sealed interface TrainingStatement {
    /** What the slot resolves to, exactly as it resolved. Never blank (see [fromResolved]). */
    data class Phrase(val text: String) : TrainingStatement

    /** No Quick Actions group is bound to [category] (a stored pose name: IDENTITY, DEFEND or CONNECT). */
    data class NoGroup(val category: String) : TrainingStatement

    /** The slot exists but says nothing. */
    object Blank : TrainingStatement

    /** There is no Matrix slot for this pose and twist. */
    object Unmapped : TrainingStatement

    companion object {
        /** A resolved phrase, or [Blank] when it is empty or only white space (what the trainer has always said for an empty slot). */
        fun fromResolved(resolved: String): TrainingStatement = if (resolved.isBlank()) Blank else Phrase(resolved)
    }
}

/** The wire codes the watch sends for a pose, and the stored pose name each one means. These are logic: the words for them are made in [TrainingText.poseValue]. */
object TrainingPoses {
    const val NONE_WIRE = "---"

    /** (wire code, stored category) in the order the drills have always rolled them. TrainingGame.kt and DeckTrainerGame.kt keep their own copies; a test holds all three equal. */
    val WIRE_TO_CATEGORY: List<Pair<String, String>> = listOf("ID" to "IDENTITY", "DEF" to "DEFEND", "CON" to "CONNECT")

    /** The stored pose name for a wire code, or null for anything else (including [NONE_WIRE]). */
    fun categoryFor(wire: String): String? = WIRE_TO_CATEGORY.firstOrNull { it.first == wire }?.second
}

/**
 * What the Training Ground and the Deck Trainer say that is decided, not just drawn. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`train_*`
 * and `deck_trainer_*`, in the chosen language) read through a [TextSource].
 *
 * **Logic is never translated.** The watch's state words (ARMED, LOCKED, COOLDOWN...) and pose codes (ID, DEF, CON, ---) are what the watch sends and what the drills react to, so the panels
 * show the state exactly as received (the watch's own screen and the header show it in English too). A round's saved difficulty is the enum's own name (EASY, EUROPEAN_EXTREME...): history
 * is *shown* through [difficultyName], and a name this build does not know is shown the way it always was (underscores as spaces), never rewritten. A saved deck name and a profile id are shown as saved.
 *
 * **A number's sign stays on its left.** Scores can go below zero. In a right-to-left language a minus sign in front of a bare number is drawn after it ("5-"), so the Arabic resources put a
 * left-to-right mark in front of the number; the Latin digits and the "+" / "-" themselves never change.
 */
object TrainingText {
    private val DIFFICULTY_NAMES = mapOf(
        "EASY" to "train_diff_easy",
        "NORMAL" to "train_diff_normal",
        "HARD" to "train_diff_hard",
        "EUROPEAN_EXTREME" to "train_diff_extreme",
    )

    /** The name of a difficulty from its saved (enum) name. A name this build does not know reads as it always did: the saved text with its underscores as spaces. */
    fun difficultyName(text: TextSource, stored: String): String =
        DIFFICULTY_NAMES[stored]?.let { text.get(it) } ?: stored.replace("_", " ")

    /** The Training Ground's one-line description of a difficulty. [poseWord] is the POSE label (it follows PLAIN WORDS); [penalty] is the points lost for a miss on the levels that have one. */
    fun groundDescription(text: TextSource, stored: String, poseWord: String, penalty: Int): String = when (stored) {
        "EASY" -> text.get("train_desc_easy")
        "NORMAL" -> text.get("train_desc_normal", poseWord)
        "HARD" -> text.get("train_desc_hard", penalty)
        "EUROPEAN_EXTREME" -> text.get("train_desc_extreme", poseWord, penalty)
        else -> ""
    }

    /** The Deck Trainer's one-line description of a difficulty (it asks for a phrase, not a bare pose). */
    fun deckDescription(text: TextSource, stored: String, poseWord: String, penalty: Int): String = when (stored) {
        "EASY" -> text.get("deck_trainer_desc_easy", poseWord)
        "NORMAL" -> text.get("deck_trainer_desc_normal")
        "HARD" -> text.get("deck_trainer_desc_hard", poseWord, penalty)
        "EUROPEAN_EXTREME" -> text.get("deck_trainer_desc_extreme", poseWord, penalty)
        else -> ""
    }

    /** What the round just said about the last fire: "+10", "-5" or MISS. */
    fun outcome(text: TextSource, outcome: TrainingOutcome): String = when (outcome.kind) {
        TrainingOutcome.Kind.HIT -> text.get("train_outcome_hit", outcome.points)
        TrainingOutcome.Kind.PENALTY -> text.get("train_outcome_penalty", outcome.points)
        TrainingOutcome.Kind.MISS -> text.get("train_outcome_miss")
    }

    /** A score or a count of points as a number on its own (Latin digits, a minus sign in front when below zero, kept on its left in a right-to-left language). */
    fun number(text: TextSource, value: Int): String = text.get("train_number", value)

    /** "FINAL SCORE: 25". */
    fun finalScore(text: TextSource, score: Int): String = text.get("train_final_score", number(text, score))

    /** A history row's points: "25 PTS". */
    fun points(text: TextSource, score: Int): String = text.get("train_points", score)

    /** "DURATION: 1:00", [clock] being the already formatted minutes and seconds. */
    fun duration(text: TextSource, clock: String): String = text.get("train_duration", clock)

    /** The pose the person is asked for: the pose's word, with "+ MOD n" after it when the difficulty also asks for a twist ([mod] is null when it does not). */
    fun requested(text: TextSource, poseWord: String, mod: Int?): String =
        if (mod == null) poseWord else text.get("train_requested_mod", poseWord, mod)

    /** "ANY MODIFIER UNDER IDENTITY COUNTS" ([poseWord] is the pose's word). */
    fun anyModifier(text: TextSource, poseWord: String): String = text.get("deck_trainer_any_modifier", poseWord)

    /** The POSE readout from what the watch sent: the pose's word for ID, DEF and CON (taken from [poseWords], keyed by stored name), NONE for the no-pose code, anything else exactly as received. */
    fun poseValue(text: TextSource, wire: String, poseWords: Map<String, String>): String {
        val category = TrainingPoses.categoryFor(wire)
        return when {
            category != null -> poseWords[category] ?: category
            wire == TrainingPoses.NONE_WIRE -> text.get("train_pose_none")
            else -> wire
        }
    }

    /** What the SAY THIS box shows. A phrase is shown exactly as it resolved; [poseWords] (keyed by stored pose name) names the pose in the one sentence that mentions it. */
    fun statement(text: TextSource, statement: TrainingStatement, poseWords: Map<String, String>): String = when (statement) {
        is TrainingStatement.Phrase -> statement.text
        is TrainingStatement.NoGroup -> text.get("deck_trainer_no_group", poseWords[statement.category] ?: statement.category)
        TrainingStatement.Blank -> text.get("deck_trainer_blank")
        TrainingStatement.Unmapped -> text.get("deck_trainer_unmapped")
    }

    /** A Training Ground history row's left side: the round's difficulty and its length. */
    fun groundHistoryLine(text: TextSource, storedDifficulty: String, clock: String): String =
        difficultyName(text, storedDifficulty) + " // " + clock

    /** A Deck Trainer history row's left side: the deck's saved name, the profile when the deck had one, and the difficulty. */
    fun deckHistoryLine(text: TextSource, deckName: String, profile: String?, storedDifficulty: String): String =
        listOfNotNull(deckName, profile, difficultyName(text, storedDifficulty)).joinToString(" // ")

    /** The word for a deck's type in the deck list: the Matrix or Quick Actions word it was given, anything else as it always read (the type's name with its underscores as spaces). */
    fun deckTypeWord(typeName: String, matrixWord: String, quickWord: String): String = when (typeName) {
        "MATRIX" -> matrixWord
        "QUICK_ACTIONS" -> quickWord
        else -> typeName.replace('_', ' ')
    }

    /** A row in the deck list: the deck's saved name, then its type's word. */
    fun deckPickLine(deckName: String, typeWord: String): String = "$deckName // $typeWord"

    /** The collapsed DECK row: the DECK label (it follows PLAIN WORDS) and the chosen deck's saved name. */
    fun deckLine(deckWord: String, deckName: String): String = "$deckWord: $deckName"

    /** The collapsed PROFILE row: the word and the profile's saved id exactly as saved. */
    fun profileLine(text: TextSource, profile: String): String = text.get("deck_trainer_profile_line", profile)
}
