// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The neutral starter phrases (L1). They are data for a person and an SLP to review, so these tests pin the things that
 * must never change by accident: which slots exist, that every kind of message is covered, that nothing is personal, and
 * that the old built-in text in CommandRepository.BASE_TEMPLATE is left exactly as it is.
 */
class StarterSetsTest {

    private val commandRepository = RepoFiles.read("app/src/main/java/com/example/besu/data/CommandRepository.kt")
    private val transferManager = RepoFiles.read("app/src/main/java/com/example/besu/backup/TransferManager.kt")

    private class BaseNode(val path: String, val trigger: String, val phrase: String, val category: String)

    // The 12 built-in nodes, read from the source so the starter set is held to the real slots.
    private fun baseTemplate(): List<BaseNode> =
        Regex("""MatrixNode\("(/std/[a-z]+/\d)",\s*"(/gesture/[a-z_]+)",\s*"[^"]*",\s*"([^"]*)",\s*"([A-Z]+)"\)""")
            .findAll(commandRepository)
            .map { BaseNode(it.groupValues[1], it.groupValues[2], it.groupValues[3], it.groupValues[4]) }
            .toList()

    private fun constant(name: String): Int =
        Regex("""const val $name = (\d+)""").find(transferManager)?.groupValues?.get(1)?.toInt()
            ?: error("TransferManager.kt no longer defines $name the way this test reads it")

    private val allPhrases: List<String>
        get() = StarterSets.matrixPhrases.map { it.phrase } + StarterSets.quickActionsGroups.flatMap { g -> g.slots.map { it.phrase } }

    // ---- the slots -------------------------------------------------------------------------------------------------

    @Test
    fun theMatrixSet_coversExactlyTheTwelveBuiltInSlots_inTheSameOrder() {
        val base = baseTemplate()
        assertEquals("the test could not read the 12 built-in nodes", 12, base.size)
        assertEquals(base.map { it.path }, StarterSets.matrixPhrases.map { it.path })
    }

    @Test
    fun eachMatrixPhrase_staysWithItsOwnPose() {
        val byPath = baseTemplate().associateBy { it.path }
        for (p in StarterSets.matrixPhrases) {
            assertEquals("pose of ${p.path}", byPath.getValue(p.path).category, p.pose)
        }
    }

    @Test
    fun theQuickActionsDeck_fitsTheDeckModel_threeGroupsOfFourSlots() {
        assertEquals(3, StarterSets.quickActionsGroups.size)
        for (g in StarterSets.quickActionsGroups) {
            assertEquals("slots in ${g.label}", 4, g.slots.size)
            assertEquals("labels in ${g.label} are distinct", g.slots.size, g.slots.map { it.label }.toSet().size)
        }
        assertEquals("the group labels are distinct", 3, StarterSets.quickActionsGroups.map { it.label }.toSet().size)
    }

    // ---- what is covered ---------------------------------------------------------------------------------------------

    @Test
    fun everyKindOfMessageIsCovered_byTheMatrixSetAlone() {
        val present = StarterSets.matrixPhrases.map { it.function }.toSet()
        assertEquals("missing from the Matrix set", emptySet<StarterFunction>(), StarterSets.REQUIRED_FUNCTIONS - present)
    }

    @Test
    fun theRequiredList_isTheEightKindsTheTrackerNames() {
        assertEquals(
            setOf(
                StarterFunction.YES, StarterFunction.NO, StarterFunction.HELP, StarterFunction.REPAIR,
                StarterFunction.TURN_HOLDING, StarterFunction.NAME_OR_ID, StarterFunction.BREAK, StarterFunction.BOUNDARY,
            ),
            StarterSets.REQUIRED_FUNCTIONS
        )
    }

    // ---- limits and content ----------------------------------------------------------------------------------------

    @Test
    fun noPhraseIsBlank_unTrimmed_orOverTheBackupLimit() {
        val limit = constant("MAX_PHRASE_LENGTH")
        for (phrase in allPhrases) {
            assertTrue("blank phrase", phrase.isNotBlank())
            assertEquals("phrase has stray spaces at its ends: '$phrase'", phrase.trim(), phrase)
            assertFalse("double space in '$phrase'", phrase.contains("  "))
            assertTrue("'$phrase' is over $limit", phrase.length <= limit)
        }
    }

    @Test
    fun theLabelsAndTheDeckName_fitTheirLimits() {
        val limit = constant("MAX_LABEL_LENGTH")
        val labels = StarterSets.quickActionsGroups.flatMap { g -> listOf(g.label) + g.slots.map { it.label } }
        for (label in labels) {
            assertTrue("blank label", label.isNotBlank())
            assertTrue("label '$label' is over $limit", label.length <= limit)
        }
        // CommandRepository.createDeck cuts a deck name to 40 characters and upper-cases it.
        assertTrue(StarterSets.QUICK_ACTIONS_DECK_NAME.length <= 40)
        assertEquals(StarterSets.QUICK_ACTIONS_DECK_NAME.uppercase(), StarterSets.QUICK_ACTIONS_DECK_NAME)
    }

    @Test
    fun noPhraseIsPersonal_andNoneHoldsATokenThatWouldFillInLater() {
        for (phrase in allPhrases) {
            assertFalse("'$phrase' names the developer", phrase.contains("snakesan", ignoreCase = true))
            assertTrue("'$phrase' holds a token", TextInsertion.tokenSpans(phrase).isEmpty())
        }
    }

    @Test
    fun starterPhrasesAreWrittenForAnyone_noPhraseIsInTheFirstPersonAboutAPersonalFact() {
        // A starter phrase must read the same whoever uses it: no names, no "my name is", no places.
        for (phrase in allPhrases) {
            assertFalse("'$phrase'", phrase.contains("my name", ignoreCase = true))
            assertFalse("'$phrase'", phrase.contains("handle", ignoreCase = true))
        }
    }

    // ---- the old built-in text is never edited (trap 1) -------------------------------------------------------------

    @Test
    fun theBuiltInText_isLeftExactlyAsItWas() {
        // An untouched button with no saved value falls back to this text. Editing it would change what an existing person's
        // untouched buttons say, which is exactly the silent flip the project forbids. New defaults are SEEDED instead.
        val expected = listOf(
            "Acknowledged.", "Systems Online.", "Identify yourself.", "Handle is Snakesan.",
            "Stop.", "Please wait.", "I need a break.", "Leave me alone.",
            "Greetings.", "Me too.", "Sorry.", "Pleasure meeting you.",
        )
        assertEquals(expected, baseTemplate().map { it.phrase })
    }

    // ---- bookkeeping -----------------------------------------------------------------------------------------------

    @Test
    fun theDeckId_isFixedSoSeedingTwiceCanNeverMakeTwoDecks() {
        assertEquals("DECK_STARTERS", StarterSets.QUICK_ACTIONS_DECK_ID)
    }

    @Test
    fun theRecordKeyForAPhrase_isStable() {
        assertEquals("seeded:/std/id/0", StarterSets.recordKey("/std/id/0"))
    }
}
