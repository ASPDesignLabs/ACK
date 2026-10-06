// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the Training Ground and the Deck Trainer say that is decided, in English exactly as it always was and in every language: the outcome of a fire, the difficulty names and their one-line
 * descriptions, the score and points, the pose the person is asked for, the pose readout, the statement shown when there is no phrase, and the history rows. The numbers stay Latin digits with their
 * sign, and in Arabic a left-to-right mark keeps a minus sign on the left of its number (a score can go below zero).
 */
class TrainingTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val lrm = "‎"
    private fun strip(s: String) = s.replace(lrm, "")
    private fun count(text: String, part: String) = Regex(Regex.escape(part)).findAll(text).count()
    private fun hasNumber(text: String, number: String) = Regex("(?<![\\d])${Regex.escape(number)}(?![\\d])").containsMatchIn(text)
    private val poseWords = mapOf("IDENTITY" to "PI", "DEFEND" to "PD", "CONNECT" to "PC")

    // ---- English is exactly what the panels always said -------------------------------------------------------------------------------

    @Test
    fun theEnglishOutcomesAreExactlyWhatTheRoundAlwaysShowed() {
        assertEquals("+10", TrainingText.outcome(t, TrainingOutcome.hit(10)))
        assertEquals("+20", TrainingText.outcome(t, TrainingOutcome.hit(20)))
        assertEquals("-5", TrainingText.outcome(t, TrainingOutcome.penalty(5)))
        assertEquals("-10", TrainingText.outcome(t, TrainingOutcome.penalty(10)))
        assertEquals("MISS", TrainingText.outcome(t, TrainingOutcome.MISS))
    }

    @Test
    fun theEnglishDifficultyNamesAndDescriptionsAreExactlyWhatTheScreensAlwaysSaid() {
        assertEquals(listOf("EASY", "NORMAL", "HARD", "EUROPEAN EXTREME"), listOf("EASY", "NORMAL", "HARD", "EUROPEAN_EXTREME").map { TrainingText.difficultyName(t, it) })
        assertEquals("ROOT POSES ONLY. NO PENALTY FOR A MISS.", TrainingText.groundDescription(t, "EASY", "POSE", 5))
        assertEquals("POSE PLUS A SPECIFIC MODIFIER. NO PENALTY FOR A MISS.", TrainingText.groundDescription(t, "NORMAL", "POSE", 5))
        assertEquals("ROOT POSES ONLY. -5 FOR A MISS.", TrainingText.groundDescription(t, "HARD", "POSE", 5))
        assertEquals("POSE PLUS A SPECIFIC MODIFIER. -10 FOR A MISS.", TrainingText.groundDescription(t, "EUROPEAN_EXTREME", "POSE", 10))
        assertEquals("ANY MODIFIER UNDER THE RIGHT POSE COUNTS. NO PENALTY FOR A MISS.", TrainingText.deckDescription(t, "EASY", "POSE", 5))
        assertEquals("MUST MATCH THE EXACT STATEMENT SHOWN. NO PENALTY FOR A MISS.", TrainingText.deckDescription(t, "NORMAL", "POSE", 5))
        assertEquals("ANY MODIFIER UNDER THE RIGHT POSE COUNTS. -5 FOR A MISS.", TrainingText.deckDescription(t, "HARD", "POSE", 5))
        assertEquals("PHRASE ONLY -- NO POSE/MOD HINT SHOWN. -10 FOR A MISS.", TrainingText.deckDescription(t, "EUROPEAN_EXTREME", "POSE", 10))
    }

    @Test
    fun theEnglishScoreLinesAndRequestedPoseAreExactlyWhatTheScreensAlwaysSaid() {
        assertEquals("25", TrainingText.number(t, 25))
        assertEquals("-15", TrainingText.number(t, -15))
        assertEquals("FINAL SCORE: 25", TrainingText.finalScore(t, 25))
        assertEquals("FINAL SCORE: -15", TrainingText.finalScore(t, -15))
        assertEquals("25 PTS", TrainingText.points(t, 25))
        assertEquals("-15 PTS", TrainingText.points(t, -15))
        assertEquals("DURATION: 1:30", TrainingText.duration(t, "1:30"))
        assertEquals("IDENTITY", TrainingText.requested(t, "IDENTITY", null))
        assertEquals("IDENTITY + MOD 0", TrainingText.requested(t, "IDENTITY", 0))
        assertEquals("CONNECT + MOD 3", TrainingText.requested(t, "CONNECT", 3))
        assertEquals("ANY MODIFIER UNDER DEFEND COUNTS", TrainingText.anyModifier(t, "DEFEND"))
        assertEquals("PROFILE: HIGH_STRESS", TrainingText.profileLine(t, "HIGH_STRESS"))
    }

    @Test
    fun theEnglishPoseReadoutAndStatementsAreExactlyWhatThePanelsAlwaysSaid() {
        val words = mapOf("IDENTITY" to "IDENTITY", "DEFEND" to "DEFEND", "CONNECT" to "CONNECT")
        assertEquals(listOf("IDENTITY", "DEFEND", "CONNECT", "NONE"), listOf("ID", "DEF", "CON", "---").map { TrainingText.poseValue(t, it, words) })
        assertEquals("(no group bound to DEFEND)", TrainingText.statement(t, TrainingStatement.NoGroup("DEFEND"), words))
        assertEquals("(blank slot)", TrainingText.statement(t, TrainingStatement.Blank, words))
        assertEquals("(unmapped)", TrainingText.statement(t, TrainingStatement.Unmapped, words))
    }

    @Test
    fun theEnglishHistoryRowsAndDeckListAreExactlyWhatTheScreensAlwaysSaid() {
        assertEquals("EUROPEAN EXTREME // 1:00", TrainingText.groundHistoryLine(t, "EUROPEAN_EXTREME", "1:00"))
        assertEquals("EASY // 0:30", TrainingText.groundHistoryLine(t, "EASY", "0:30"))
        assertEquals("MY DECK // WORK // HARD", TrainingText.deckHistoryLine(t, "MY DECK", "WORK", "HARD"))
        assertEquals("MY DECK // HARD", TrainingText.deckHistoryLine(t, "MY DECK", null, "HARD"))
        assertEquals("QUICK // EUROPEAN EXTREME", TrainingText.deckHistoryLine(t, "QUICK", null, "EUROPEAN_EXTREME"))
        assertEquals("MATRIX // MATRIX", TrainingText.deckPickLine("MATRIX", TrainingText.deckTypeWord("MATRIX", "MATRIX", "QUICK ACTIONS")))
        assertEquals("OURS // QUICK ACTIONS", TrainingText.deckPickLine("OURS", TrainingText.deckTypeWord("QUICK_ACTIONS", "MATRIX", "QUICK ACTIONS")))
        assertEquals("DECK: DEFAULT", TrainingText.deckLine("DECK", "DEFAULT"))
    }

    // ---- what is logic or saved is never rewritten ------------------------------------------------------------------------------------

    @Test
    fun aSavedDifficultyThisBuildDoesNotKnowReadsTheWayItAlwaysDid_underscoresAsSpaces_inEveryLanguage() {
        for (tag in listOf("en") + translations.keys) {
            val text = if (tag == "en") t else FileText(tag)
            assertEquals(tag, "SOMETHING NEW", TrainingText.difficultyName(text, "SOMETHING_NEW"))
            assertEquals(tag, "", TrainingText.difficultyName(text, ""))
            assertEquals(tag, "easy", TrainingText.difficultyName(text, "easy")) // saved names are exact capitals: a lower-case one is not EASY
            assertEquals(tag, "SOMETHING NEW // 1:00", TrainingText.groundHistoryLine(text, "SOMETHING_NEW", "1:00"))
        }
    }

    @Test
    fun theDeckAndProfileInAHistoryRowAreShownExactlyAsSaved_whateverTheyHold() {
        val names = listOf("Hello", "100% %s %d", "price \$5 \$1", "she said \"no\"", "")
        for (tag in translations.keys) {
            val f = FileText(tag)
            for (name in names) {
                val row = TrainingText.deckHistoryLine(f, name, "HIGH_STRESS", "HARD")
                assertTrue("$tag: '$name' in '$row'", row.startsWith("$name // HIGH_STRESS // "))
                assertEquals("$tag: the profile once", 1, count(row, "HIGH_STRESS"))
                assertFalse("$tag: a placeholder leaked", row.removePrefix(name).contains("%"))
                assertEquals("$tag", "$name // BBB", TrainingText.deckPickLine(name, "BBB"))
                assertEquals("$tag", "DDD: $name", TrainingText.deckLine("DDD", name))
            }
        }
    }

    @Test
    fun aDeckTypeWordIsOnlyForMatrixAndQuickActions_anythingElseReadsAsItsNameWithSpaces() {
        assertEquals("MMM", TrainingText.deckTypeWord("MATRIX", "MMM", "QQQ"))
        assertEquals("QQQ", TrainingText.deckTypeWord("QUICK_ACTIONS", "MMM", "QQQ"))
        assertEquals("EMERGENCY", TrainingText.deckTypeWord("EMERGENCY", "MMM", "QQQ"))
        assertEquals("SOME NEW TYPE", TrainingText.deckTypeWord("SOME_NEW_TYPE", "MMM", "QQQ"))
        assertEquals("matrix", TrainingText.deckTypeWord("matrix", "MMM", "QQQ"))
    }

    @Test
    fun theWireCodesAreLogic_onlyTheThreePoseCodesMeanAPose() {
        assertEquals(listOf("ID" to "IDENTITY", "DEF" to "DEFEND", "CON" to "CONNECT"), TrainingPoses.WIRE_TO_CATEGORY)
        assertEquals("IDENTITY", TrainingPoses.categoryFor("ID"))
        assertEquals("DEFEND", TrainingPoses.categoryFor("DEF"))
        assertEquals("CONNECT", TrainingPoses.categoryFor("CON"))
        for (other in listOf("---", "", "id", "Id", "IDENTITY", " ID", "ID ", "DEFEND", "CONNECT", "XYZ")) assertNull("'$other'", TrainingPoses.categoryFor(other))
        assertEquals("---", TrainingPoses.NONE_WIRE)
    }

    @Test
    fun theWatchsPoseCodeBecomesThePosesWordOnlyForThePoseCodes_everythingElseIsShownAsReceived() {
        for (tag in listOf("en") + translations.keys) {
            val text = if (tag == "en") t else FileText(tag)
            assertEquals(tag, listOf("PI", "PD", "PC"), listOf("ID", "DEF", "CON").map { TrainingText.poseValue(text, it, poseWords) })
            assertEquals("$tag: the NONE code reads as the language's NONE", text.get("train_pose_none"), TrainingText.poseValue(text, "---", poseWords))
            for (other in listOf("", "id", "XYZ", "IDENTITY", "-- -", "%s")) assertEquals("$tag: '$other'", other, TrainingText.poseValue(text, other, poseWords))
            // A pose with no word in the map is shown as its stored name rather than disappearing.
            assertEquals(tag, "IDENTITY", TrainingText.poseValue(text, "ID", emptyMap()))
        }
    }

    @Test
    fun aResolvedPhraseIsShownExactlyAsItResolved_andOnlyAnEmptyOneIsTheBlankSlot() {
        assertEquals(TrainingStatement.Blank, TrainingStatement.fromResolved(""))
        assertEquals(TrainingStatement.Blank, TrainingStatement.fromResolved(" "))
        assertEquals(TrainingStatement.Blank, TrainingStatement.fromResolved("\n\t  "))
        assertEquals(TrainingStatement.Phrase("a"), TrainingStatement.fromResolved("a"))
        assertEquals(TrainingStatement.Phrase(" a "), TrainingStatement.fromResolved(" a ")) // never trimmed
        assertEquals(TrainingStatement.Phrase("(blank slot)"), TrainingStatement.fromResolved("(blank slot)")) // a phrase that happens to read like the placeholder is still a phrase
        val awkward = listOf("Hello there", "100% sure %s %d", "price \$5 and \$1", "she said \"no\"", "line one\nline two", "(unmapped)", "  padded  ", "ends with a break\n", "\tstarts with a tab")
        for (tag in listOf("en") + translations.keys) {
            val text = if (tag == "en") t else FileText(tag)
            for (phrase in awkward) assertEquals("$tag: '$phrase'", phrase, TrainingText.statement(text, TrainingStatement.Phrase(phrase), poseWords))
        }
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theOutcomesKeepTheirSignAndTheirNumberInEveryLanguage_andAnArabicMinusStaysOnTheLeftOfItsNumber() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val hit = TrainingText.outcome(f, TrainingOutcome.hit(10))
            val penalty = TrainingText.outcome(f, TrainingOutcome.penalty(5))
            val miss = TrainingText.outcome(f, TrainingOutcome.MISS)
            assertEquals("$tag", "+10", strip(hit))
            assertEquals("$tag", "-5", strip(penalty))
            assertTrue("$tag: MISS is a word of the language, not the English one ($miss)", miss.isNotBlank() && miss != "MISS" && !miss.contains("%"))
            assertEquals("$tag: three different outcomes", 3, setOf(hit, penalty, miss).size)
            if (tag == "ar") {
                assertEquals("ar: the mark is in front of the sign", lrm + "+10", hit)
                assertEquals("ar: the mark is in front of the sign", lrm + "-5", penalty)
            } else {
                assertEquals("$tag: nothing but the sign and the number", "+10", hit)
                assertEquals("$tag: nothing but the sign and the number", "-5", penalty)
            }
        }
    }

    @Test
    fun aScoreIsALatinNumberWithItsSignInEveryLanguage_andAnArabicOneIsMarkedLeftToRight() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            for (n in listOf(0, 5, -5, 10, -10, 95, -95, 100, -100, 1000)) {
                val number = TrainingText.number(f, n)
                assertEquals("$tag/$n", n.toString(), strip(number))
                assertEquals("$tag/$n: the mark only in Arabic", tag == "ar", number.contains(lrm))
                // Wherever a number can be negative, its sign is directly after the mark (Arabic) and never loose.
                for (line in listOf(TrainingText.finalScore(f, n), TrainingText.points(f, n))) {
                    assertTrue("$tag/$n: the number once in '$line'", hasNumber(strip(line), n.toString()))
                    if (tag == "ar") assertTrue("ar/$n: the mark before the number in '$line'", line.contains(lrm + n.toString()))
                    else assertFalse("$tag/$n: no mark in '$line'", line.contains(lrm))
                    assertFalse("$tag/$n: a placeholder leaked in '$line'", line.contains("%"))
                }
            }
            assertNotEquals("$tag: final score is not English", "FINAL SCORE: 5", TrainingText.finalScore(f, 5))
        }
    }

    @Test
    fun theDifficultyNamesAreFourDifferentWords_theNameOfTheHardestStayingAsItIsInEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val names = listOf("EASY", "NORMAL", "HARD", "EUROPEAN_EXTREME").map { TrainingText.difficultyName(f, it) }
            assertEquals("$tag: four different names $names", 4, names.toSet().size)
            assertTrue("$tag: none blank or leaking", names.all { it.isNotBlank() && !it.contains("%") })
            assertEquals("$tag: EUROPEAN EXTREME is a name, like CYBER and MECH", "EUROPEAN EXTREME", names[3])
            assertNotEquals("$tag: EASY is a word of the language", "EASY", names[0])
            assertNotEquals("$tag: HARD is a word of the language", "HARD", names[2])
        }
    }

    @Test
    fun theDescriptionsNameThePenaltyAndThePoseOnlyWhereTheyShould_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val ground = listOf("EASY", "NORMAL", "HARD", "EUROPEAN_EXTREME")
            for (penalty in listOf(5, 10)) {
                val g = ground.associateWith { strip(TrainingText.groundDescription(f, it, "QQQ", penalty)) }
                val d = ground.associateWith { strip(TrainingText.deckDescription(f, it, "QQQ", penalty)) }
                for ((which, set) in listOf("ground" to g, "deck" to d)) {
                    for ((level, line) in set) {
                        assertTrue("$tag/$which/$level: not blank", line.isNotBlank())
                        assertFalse("$tag/$which/$level: a placeholder leaked: $line", line.contains("%"))
                        val charges = level == "HARD" || level == "EUROPEAN_EXTREME"
                        assertEquals("$tag/$which/$level/$penalty: the penalty exactly when the level has one: $line", charges, hasNumber(line, "-$penalty"))
                        val other = if (penalty == 5) "10" else "5"
                        assertFalse("$tag/$which/$level/$penalty: only the given penalty: $line", hasNumber(line, other))
                    }
                    assertEquals("$tag/$which: four different sentences", 4, set.values.toSet().size)
                }
                // The pose's word goes where the sentence names the pose, and nowhere else.
                assertEquals(tag, mapOf("EASY" to 0, "NORMAL" to 1, "HARD" to 0, "EUROPEAN_EXTREME" to 1), g.mapValues { count(it.value, "QQQ") })
                assertEquals(tag, mapOf("EASY" to 1, "NORMAL" to 0, "HARD" to 1, "EUROPEAN_EXTREME" to 1), d.mapValues { count(it.value, "QQQ") })
            }
            assertNotEquals("$tag: still English", "ROOT POSES ONLY. NO PENALTY FOR A MISS.", TrainingText.groundDescription(f, "EASY", "POSE", 5))
            assertNotEquals("$tag: still English", "MUST MATCH THE EXACT STATEMENT SHOWN. NO PENALTY FOR A MISS.", TrainingText.deckDescription(f, "NORMAL", "POSE", 5))
        }
    }

    @Test
    fun anArabicPenaltyKeepsItsMinusOnTheLeftOfTheNumber() {
        val f = FileText("ar")
        assertTrue(TrainingText.groundDescription(f, "HARD", "P", 5).contains(lrm + "-5"))
        assertTrue(TrainingText.groundDescription(f, "EUROPEAN_EXTREME", "P", 10).contains(lrm + "-10"))
        assertTrue(TrainingText.deckDescription(f, "HARD", "P", 5).contains(lrm + "-5"))
        assertTrue(TrainingText.deckDescription(f, "EUROPEAN_EXTREME", "P", 10).contains(lrm + "-10"))
        for (tag in listOf("es", "pt", "af", "hi")) {
            val g = FileText(tag)
            assertFalse(tag, TrainingText.groundDescription(g, "HARD", "P", 5).contains(lrm))
            assertFalse(tag, TrainingText.deckDescription(g, "EUROPEAN_EXTREME", "P", 10).contains(lrm))
        }
    }

    @Test
    fun theRequestedPoseHoldsItsWordAndItsTwistOnceEach_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: no twist asked, only the pose", "QQQ", TrainingText.requested(f, "QQQ", null))
            for (mod in 0..3) {
                val line = TrainingText.requested(f, "QQQ", mod)
                assertEquals("$tag/$mod: the pose once in '$line'", 1, count(line, "QQQ"))
                assertEquals("$tag/$mod: the twist once in '$line'", 1, Regex("\\d").findAll(line).count())
                assertTrue("$tag/$mod: the twist is $mod in '$line'", line.contains(mod.toString()))
                assertFalse("$tag/$mod: a placeholder leaked", line.contains("%"))
            }
            assertEquals("$tag: three different words for 'MOD' lines", 4, (0..3).map { TrainingText.requested(f, "QQQ", it) }.toSet().size)
            val any = TrainingText.anyModifier(f, "QQQ")
            assertEquals("$tag: the pose once in '$any'", 1, count(any, "QQQ"))
            assertNotEquals("$tag: still English", "ANY MODIFIER UNDER QQQ COUNTS", any)
        }
    }

    @Test
    fun theStatementShownWhenThereIsNoPhraseSaysWhy_inEveryLanguage_andNamesThePoseOnlyWhenItIsTheReason() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val none = TrainingText.statement(f, TrainingStatement.NoGroup("DEFEND"), poseWords)
            val blank = TrainingText.statement(f, TrainingStatement.Blank, poseWords)
            val unmapped = TrainingText.statement(f, TrainingStatement.Unmapped, poseWords)
            assertEquals("$tag: the pose's word once in '$none'", 1, count(none, "PD"))
            assertFalse("$tag: only the pose that has no group", none.contains("PI") || none.contains("PC"))
            for (line in listOf(none, blank, unmapped)) {
                assertTrue("$tag: in brackets, as a note and not a phrase: $line", line.startsWith("(") && line.endsWith(")"))
                assertFalse("$tag: a placeholder leaked: $line", line.contains("%"))
            }
            assertEquals("$tag: three different notes", 3, setOf(none, blank, unmapped).size)
            // A pose with no word in the map is named by its stored name rather than left out.
            assertTrue("$tag", TrainingText.statement(f, TrainingStatement.NoGroup("DEFEND"), emptyMap()).contains("DEFEND"))
            assertNotEquals("$tag: still English", "(blank slot)", blank)
            assertNotEquals("$tag: still English", "(unmapped)", unmapped)
        }
    }

    @Test
    fun theHistoryRowsAreTranslatedWordsWithTheSavedDifficultyUntouched_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val easy = TrainingText.groundHistoryLine(f, "EASY", "0:30")
            assertEquals("$tag", TrainingText.difficultyName(f, "EASY") + " // 0:30", easy)
            assertNotEquals("$tag: still English", "EASY // 0:30", easy)
            assertEquals("$tag", "DDD // WORK // " + TrainingText.difficultyName(f, "HARD"), TrainingText.deckHistoryLine(f, "DDD", "WORK", "HARD"))
            assertEquals("$tag", "DDD // " + TrainingText.difficultyName(f, "EUROPEAN_EXTREME"), TrainingText.deckHistoryLine(f, "DDD", null, "EUROPEAN_EXTREME"))
        }
    }

    @Test
    fun theDurationAndTheProfileLineHoldTheirArgumentOnce_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val duration = TrainingText.duration(f, "9:99")
            assertEquals("$tag: the clock once in '$duration'", 1, count(duration, "9:99"))
            assertNotEquals("$tag: still English", "DURATION: 9:99", duration)
            for (profile in listOf("DEFAULT", "HIGH_STRESS", "100% %s")) {
                val line = TrainingText.profileLine(f, profile)
                assertEquals("$tag: the profile once in '$line'", 1, count(line, profile))
                assertEquals("$tag: a placeholder leaked", count(line, "%"), count(profile, "%"))
            }
            assertNotEquals("$tag: still English", "PROFILE: DEFAULT", TrainingText.profileLine(f, "DEFAULT"))
        }
    }

    @Test
    fun theWordsOfTheTwoPanelsThatAnswerDifferentQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "train_start" to "train_end", "train_play_again" to "train_done", "train_expand" to "train_collapse", "train_score" to "train_time", "train_state" to "train_mod",
            "train_requested" to "deck_trainer_say", "train_title" to "train_game_mode", "train_previous_scores" to "train_round_complete", "train_difficulty" to "train_duration",
            "train_exit" to "train_done", "train_outcome_hit" to "train_outcome_penalty",
        )
        for ((tag, map) in translations) {
            for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
            // The brackets belong to the resource (the house style of a button's name).
            for (name in listOf("train_exit", "train_start", "train_end", "train_play_again", "train_done", "train_expand", "train_collapse")) {
                assertTrue("$tag/$name: in brackets", map.getValue(name).startsWith("[") && map.getValue(name).endsWith("]"))
                assertTrue("$tag/$name: in brackets (English)", english.getValue(name).startsWith("[") && english.getValue(name).endsWith("]"))
            }
        }
    }

    @Test
    fun aNameAllowedToMatchEnglishDoesSoOnlyInTheLanguagesThatReallyWriteItThatWay() {
        // TranslationsTest's allowlist is by name, so on its own it would let any language keep these in English; this holds each to the languages that really write it that way.
        val signsOnly = setOf("es", "pt", "af", "hi") // Arabic puts a left-to-right mark in front, so it always differs
        val allowed = mapOf(
            "train_diff_extreme" to translations.keys, // a name
            "train_diff_normal" to setOf("es", "pt"), // NORMAL
            "train_mod" to setOf("es", "pt", "af"), "train_requested_mod" to setOf("es", "pt", "af"), // MOD abbreviates the word for modifier
            "train_points" to setOf("es", "pt"), // PTS abbreviates puntos and pontos
            "train_outcome_hit" to signsOnly, "train_outcome_penalty" to signsOnly, "train_number" to signsOnly,
        )
        for ((name, languages) in allowed) for ((tag, map) in translations) {
            assertTrue("$tag/$name is still English", tag in languages || map.getValue(name) != english.getValue(name))
        }
    }

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        val expected = mapOf(
            "train_desc_easy" to "", "train_desc_normal" to "%1\$s", "train_desc_hard" to "%1\$d", "train_desc_extreme" to "%1\$s %2\$d",
            "deck_trainer_desc_easy" to "%1\$s", "deck_trainer_desc_normal" to "", "deck_trainer_desc_hard" to "%1\$s %2\$d", "deck_trainer_desc_extreme" to "%1\$s %2\$d",
            "train_duration" to "%1\$s", "train_final_score" to "%1\$s", "train_requested_mod" to "%1\$s %2\$d", "train_outcome_hit" to "%1\$d", "train_outcome_penalty" to "%1\$d",
            "train_number" to "%1\$d", "train_points" to "%1\$d", "train_outcome_miss" to "", "deck_trainer_title" to "%1\$s", "deck_trainer_profile_line" to "%1\$s",
            "deck_trainer_any_modifier" to "%1\$s", "deck_trainer_no_group" to "%1\$s", "deck_trainer_blank" to "", "deck_trainer_unmapped" to "",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for ((name, args) in expected) {
                val found = Regex("""%\d\$[sd]""").findAll(map.getValue(name)).map { it.value }.toList()
                assertEquals("$tag/$name: each argument once, in the order the code gives them", args.split(" ").filter { it.isNotEmpty() }.toSet(), found.toSet())
                assertEquals("$tag/$name: no argument twice", found.size, found.toSet().size)
            }
        }
    }
}
