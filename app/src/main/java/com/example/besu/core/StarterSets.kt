// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** What a starter phrase is for. A fresh install should cover every kind in [StarterSets.REQUIRED_FUNCTIONS]. */
enum class StarterFunction {
    YES, NO, UNSURE, HELP, REPAIR, TURN_HOLDING, NAME_OR_ID, BREAK, BOUNDARY, SOCIAL
}

/**
 * One of the 12 Matrix slots. The slot (path, pose, gesture) never moves, because a person learns a gesture by repetition;
 * only the words change. A data class so a later field (a picture, a symbol) can be added without disturbing the rest.
 */
data class StarterPhrase(
    /** The Matrix storage path, e.g. "/std/id/0". The same 12 paths as CommandRepository.BASE_TEMPLATE. */
    val path: String,
    val pose: String,
    /** The physical gesture for the slot, in plain words (a drift test keeps the slots themselves in step with BASE_TEMPLATE). */
    val gesture: String,
    val phrase: String,
    val function: StarterFunction
)

/** One Quick Actions button: what its face says and what is spoken. */
data class StarterSlot(val label: String, val phrase: String, val function: StarterFunction)

data class StarterGroup(val label: String, val slots: List<StarterSlot>)

/**
 * The neutral starter phrases a NEW install begins with (L1): wording that suits anyone, grouped by what a message does
 * (yes, no, help, repair, turn-holding, name or ID, break, boundary), instead of the developer's own words. Plain Kotlin so
 * the sets are tested without a phone; data/StarterSeed.kt writes them.
 *
 * This is a DRAFT for the developer and an SLP to review (docs/STARTER_PHRASES.md shows it as a table, and a test keeps the
 * document and this file the same). It is never applied to an install that already exists unless the person asks.
 *
 * The old built-in text in CommandRepository.BASE_TEMPLATE must never be edited: a button with no saved value falls back to
 * it, so editing it would silently change what an existing person's untouched buttons say. The starters are saved values.
 */
object StarterSets {

    /** The kinds of message a fresh install must be able to say. */
    val REQUIRED_FUNCTIONS: Set<StarterFunction> = setOf(
        StarterFunction.YES, StarterFunction.NO, StarterFunction.HELP, StarterFunction.REPAIR,
        StarterFunction.TURN_HOLDING, StarterFunction.NAME_OR_ID, StarterFunction.BREAK, StarterFunction.BOUNDARY,
    )

    /** The 12 Matrix slots, in BASE_TEMPLATE order. */
    val matrixPhrases: List<StarterPhrase> = listOf(
        StarterPhrase("/std/id/0", "IDENTITY", "thumbs up", "Yes.", StarterFunction.YES),
        StarterPhrase("/std/id/1", "IDENTITY", "wave", "Hello.", StarterFunction.SOCIAL),
        StarterPhrase("/std/id/2", "IDENTITY", "ask name", "Please say that again.", StarterFunction.REPAIR),
        StarterPhrase("/std/id/3", "IDENTITY", "name", "I am using a communication device.", StarterFunction.NAME_OR_ID),

        StarterPhrase("/std/def/0", "DEFEND", "stop", "Stop.", StarterFunction.BOUNDARY),
        StarterPhrase("/std/def/1", "DEFEND", "wait", "Please wait, I am typing.", StarterFunction.TURN_HOLDING),
        StarterPhrase("/std/def/2", "DEFEND", "break", "I need a break.", StarterFunction.BREAK),
        StarterPhrase("/std/def/3", "DEFEND", "leave alone", "I need some space.", StarterFunction.BOUNDARY),

        StarterPhrase("/std/con/0", "CONNECT", "nice", "No.", StarterFunction.NO),
        StarterPhrase("/std/con/1", "CONNECT", "same", "Thank you.", StarterFunction.SOCIAL),
        StarterPhrase("/std/con/2", "CONNECT", "sorry", "I need help.", StarterFunction.HELP),
        StarterPhrase("/std/con/3", "CONNECT", "meet", "Nice to meet you.", StarterFunction.SOCIAL),
    )

    /**
     * A fixed id, so seeding twice can never make two decks. createDeck's own ids are "DECK_<time>", which this cannot collide with.
     */
    const val QUICK_ACTIONS_DECK_ID = "DECK_STARTERS"

    /** Already upper case and under the 40 characters createDeck allows. */
    const val QUICK_ACTIONS_DECK_NAME = "STARTERS"

    /**
     * A small Quick Actions deck, grouped by function, that keeps the greetings and "sorry" the Matrix set had to give up
     * room for, and repeats the most important message (waiting while typing) where it is easiest to reach.
     */
    val quickActionsGroups: List<StarterGroup> = listOf(
        StarterGroup(
            "ANSWERS",
            listOf(
                StarterSlot("YES", "Yes.", StarterFunction.YES),
                StarterSlot("NO", "No.", StarterFunction.NO),
                StarterSlot("DON'T KNOW", "I don't know.", StarterFunction.UNSURE),
                StarterSlot("MAYBE", "Maybe.", StarterFunction.UNSURE),
            )
        ),
        StarterGroup(
            "REPAIR",
            listOf(
                StarterSlot("AGAIN", "Please say that again.", StarterFunction.REPAIR),
                StarterSlot("SLOWER", "Please speak more slowly.", StarterFunction.REPAIR),
                StarterSlot("DON'T UNDERSTAND", "I don't understand.", StarterFunction.REPAIR),
                StarterSlot("I'M TYPING", "Please wait, I am typing.", StarterFunction.TURN_HOLDING),
            )
        ),
        StarterGroup(
            "SOCIAL",
            listOf(
                StarterSlot("HELLO", "Hello.", StarterFunction.SOCIAL),
                StarterSlot("THANK YOU", "Thank you.", StarterFunction.SOCIAL),
                StarterSlot("SORRY", "Sorry.", StarterFunction.SOCIAL),
                StarterSlot("HELP", "I need help.", StarterFunction.HELP),
            )
        ),
    )

    /**
     * The key under which data/StarterSeed.kt notes that it wrote the phrase for [path]. One shared function, so the seed, the
     * restore rule and InstallClassifier.SEED_KEYS cannot disagree about it.
     */
    fun recordKey(path: String): String = "seeded:$path"
}
