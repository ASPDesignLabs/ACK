// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Training Ground and the Deck Trainer read their words from string resources. The panels cannot be compiled here (they use the SDK; they are syntax-checked), so this reads them: the old English
 * literals are gone, every string they name exists in every language and none is unused, each word sits on the control that does what it says, and what is logic (the watch's state words and pose codes,
 * the saved difficulty's enum name, the stored pose names, the profile ids) was not translated. TrainingTextTest holds the decisions. The two controllers are rules, not screens: they stay free of labels and words.
 */
class TrainingWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val ground get() = noComments(RepoFiles.read("$base/training/TrainingGroundPanel.kt"))
    private val deck get() = noComments(RepoFiles.read("$base/training/DeckTrainerPanel.kt"))
    private val groundGame get() = noComments(RepoFiles.read("$base/training/TrainingGame.kt"))
    private val deckGame get() = noComments(RepoFiles.read("$base/training/DeckTrainerGame.kt"))
    private val text get() = noComments(RepoFiles.read("$base/core/TrainingText.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    private val names get() = english.keys.filter { it.startsWith("train_") || it.startsWith("deck_trainer_") }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringThePanelsNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val referenced = Regex("""R\.string\.((?:train|deck_trainer)_[a-z_]+)""").findAll(ground + "\n" + deck).map { it.groupValues[1] }.toSet() +
            Regex(""""((?:train|deck_trainer)_[a-z_]+)"""").findAll(text).map { it.groupValues[1] }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        assertEquals("defined but never used", emptyList<String>(), names.filter { it !in referenced })
        assertEquals("used but not defined", emptyList<String>(), referenced.filter { it !in names })
    }

    @Test
    fun theOldLiteralsAreGone_fromBothPanels() {
        val literals = listOf(
            "\"TRAINING GROUND\"", "\"DECK TRAINER\"", "\"[EXIT]\"", "\"GAME MODE\"", "GESTURE FREELY", "\"DIFFICULTY\"", "\"[START ROUND]\"", "\"[END ROUND]\"", "\"[PLAY AGAIN]\"", "\"[DONE]\"",
            "\"[EXPAND]\"", "\"[COLLAPSE]\"", "\"PREVIOUS SCORES\"", "\"ROUND COMPLETE\"", "FINAL SCORE", "\"SCORE\"", "\"TIME\"", "\"REQUESTED\"", "\"SAY THIS\"", "\"STATE\"", "\"POSE\"", "\"MOD\"",
            "DURATION:", "PROFILE:", "DECK:", " PTS", "ANY MODIFIER", "ROOT POSES ONLY", "MUST MATCH", "PHRASE ONLY", "SPECIFIC MODIFIER", " + MOD ", "\"IDENTITY\"", "\"NONE\"",
            "(no group bound", "(blank slot)", "(unmapped)", "\"MISS\"",
        )
        for ((panel, source) in listOf("TrainingGroundPanel" to ground, "DeckTrainerPanel" to deck)) {
            // The pose helper in TrainingGroundPanel names the three stored pose names; they are logic, handed to the label table, and are the only quoted capitals allowed.
            val scope = source.replace(Regex("""poseLabel\("(IDENTITY|DEFEND|CONNECT)"\)"""), "").replace(Regex("""mapOf\("IDENTITY" to identity.*\)"""), "")
            for (literal in literals) assertFalse("$panel still holds $literal", scope.contains(literal))
        }
    }

    @Test
    fun theControlsThatChooseALanguageOrALabelAreNotDrawnFromTheEnumsEnglishNorFromASavedName() {
        for ((panel, source) in listOf("TrainingGroundPanel" to ground, "DeckTrainerPanel" to deck)) {
            assertFalse("$panel draws the enum's English label", source.contains("difficulty.label") || source.contains(".label,"))
            assertFalse("$panel rewrites a saved name itself", source.contains("replace(\"_\"") || source.contains("replace('_'"))
            assertFalse("$panel reads the outcome back from its text", source.contains("startsWith(\"-\")") || source.contains("== \"MISS\""))
            assertFalse("$panel still draws the number by hand", source.contains("score.toString()") || source.contains("\" PTS\""))
            assertTrue("$panel: the difficulty's name goes through the language", source.contains("TrainingText.difficultyName(text, difficulty.name)"))
            assertTrue("$panel: the outcome is a kind, coloured by kind", source.contains("TrainingText.outcome(text, outcome)") && source.contains("TrainingOutcome.Kind.PENALTY -> Color.Red"))
            assertTrue("$panel: the score is a number in the language", source.contains("TrainingText.number(text, game.score)") && source.contains("TrainingText.finalScore(text, game.score)"))
            assertTrue("$panel: the history's points", source.contains("TrainingText.points(text, result.score)"))
            assertTrue("$panel: the pose readout", source.contains("TrainingText.poseValue(text, poseLabel, poseWords)"))
        }
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------

    @Test
    fun theButtonsDoWhatTheirWordsSay_inBothPanels() {
        assertTrue(Regex("""R\.string\.train_start\),[\s\S]{0,400}?game\.configure\(selectedDifficulty, selectedDuration\)[\s\S]{0,100}?game\.start\(\)""").containsMatchIn(ground))
        assertTrue(Regex("""R\.string\.train_start\),[\s\S]{0,400}?game\.configure\(selectedDeck, selectedProfile, selectedDifficulty, selectedDuration\)[\s\S]{0,100}?game\.start\(\)""").containsMatchIn(deck))
        for ((panel, source) in listOf("ground" to ground, "deck" to deck)) {
            assertTrue("$panel: END ROUND ends the round", Regex("""R\.string\.train_end\),[\s\S]{0,200}?game\.abort\(\)""").containsMatchIn(source))
            assertTrue("$panel: PLAY AGAIN goes back to the setup", Regex("""R\.string\.train_play_again\),[\s\S]{0,200}?game\.dismissResults\(\)""").containsMatchIn(source))
            assertTrue("$panel: DONE leaves the results", Regex("""R\.string\.train_done\),[\s\S]{0,200}?onClick = onDone""").containsMatchIn(source))
            assertTrue("$panel: EXIT ends a round in progress and closes", Regex("""R\.string\.train_exit\),[\s\S]{0,700}?if \(game\.isActive\) game\.abort\(\)\s*onClose\(\)""").containsMatchIn(source))
            assertTrue("$panel: the clock's toggle", Regex("""R\.string\.train_collapse else R\.string\.train_expand""").containsMatchIn(source))
        }
        assertTrue("GAME MODE is the switch that follows it", Regex("""R\.string\.train_game_mode\),[\s\S]{0,700}?NeonToggle\(""").containsMatchIn(ground))
        assertTrue("the free-practice note is the one shown when game mode is off", Regex("""\} else \{\s*Text\(\s*text = stringResource\(R\.string\.train_free_note\)""").containsMatchIn(ground))
    }

    @Test
    fun theTitlesAreTheirPanels_andTheDeckTrainersTitleTakesTheDeckLabel() {
        assertTrue(ground.contains("text = stringResource(R.string.train_title),"))
        assertTrue(deck.contains("text = stringResource(R.string.deck_trainer_title, labelFor(LabelKey.DECK)),"))
        assertTrue("the deck list's header reads the DECK label", deck.contains("TrainingText.deckLine(deckWord, selectedDeck.name)") && deck.contains("val deckWord = labelFor(LabelKey.DECK)"))
        assertTrue("a deck's type reads the deck-type labels", deck.contains("labelFor(LabelKey.DECK_TYPE_MATRIX)") && deck.contains("labelFor(LabelKey.DECK_TYPE_QUICK)"))
        assertTrue("the profile line", deck.contains("TrainingText.profileLine(text, selectedProfile)"))
        assertTrue("the profile choices are the saved ids, as saved", Regex("""CommandRepository\.PROFILES\.forEach \{ prof ->\s*PickRow\(\s*label = prof,""").containsMatchIn(deck))
    }

    @Test
    fun theTelemetryReadoutShowsTheWatchsStateAsItWasSent_andOnlyItsLabelsAreWords() {
        for ((panel, source) in listOf("ground" to ground, "deck" to deck)) {
            assertTrue("$panel: the state is shown as received", Regex("""label = stringResource\(R\.string\.train_state\), value = stateLabel,""").containsMatchIn(source))
            assertTrue("$panel: the POSE label follows PLAIN WORDS", Regex("""label = labelFor\(LabelKey\.POSE\), value = TrainingText\.poseValue""").containsMatchIn(source))
            assertTrue("$panel: the twist count is a number", Regex("""label = stringResource\(R\.string\.train_mod\), value = twistLevel\.toString\(\),""").containsMatchIn(source))
            assertTrue("$panel: a fire is still the edge into COOLDOWN", source.contains("""if (stateLabel == "COOLDOWN" && lastSeenState != "COOLDOWN") {"""))
            assertTrue("$panel: the fire is reported with the wire code and the twist", source.contains("game.onFireDetected(poseLabel, twistLevel)"))
        }
    }

    @Test
    fun theDeckTrainersTargetShowsTheStatementThroughTheLanguage_andTheTwistOnlyWhenTheLevelAsksForIt() {
        assertTrue(deck.contains("text = TrainingText.statement(text, game.target.statement, poseWords),"))
        assertFalse("the statement is never drawn raw", deck.contains("text = game.target.statement"))
        assertTrue(deck.contains("if (game.difficulty.usesMod) game.target.twist else null"))
        assertTrue(deck.contains("if (game.difficulty != GameDifficulty.EUROPEAN_EXTREME) {"))
        assertTrue(deck.contains("if (!game.difficulty.usesMod) {"))
        assertTrue(deck.contains("TrainingText.anyModifier(text, poseWord)"))
        assertTrue("the Training Ground's target", ground.contains("TrainingText.requested(text, poseWords[game.targetPoseLabel] ?: game.targetPoseLabel, game.targetMod)"))
    }

    @Test
    fun theHeadingsSitOverTheBoxesTheyName_inBothPanels() {
        assertTrue("SAY THIS heads the statement", Regex("""R\.string\.deck_trainer_say\),[\s\S]{0,500}?TrainingText\.statement\(""").containsMatchIn(deck))
        assertTrue("REQUESTED heads the requested pose", Regex("""R\.string\.train_requested\),[\s\S]{0,500}?TrainingText\.requested\(""").containsMatchIn(ground))
        for ((panel, source) in listOf("ground" to ground, "deck" to deck)) {
            assertTrue("$panel: SCORE labels the score", Regex("""label = stringResource\(R\.string\.train_score\),\s*value = TrainingText\.number\(text, game\.score\),""").containsMatchIn(source))
            assertTrue("$panel: TIME labels the clock", Regex("""label = stringResource\(R\.string\.train_time\),\s*value = formatClock\(game\.timeRemainingSeconds\),""").containsMatchIn(source))
            assertTrue("$panel: ROUND COMPLETE heads the final score", Regex("""R\.string\.train_round_complete\),[\s\S]{0,400}?TrainingText\.finalScore\(""").containsMatchIn(source))
            assertTrue("$panel: PREVIOUS SCORES heads the history", Regex("""R\.string\.train_previous_scores\),[\s\S]{0,300}?HistoryList\(results = game\.history\.take\(5\)""").containsMatchIn(source))
        }
    }

    @Test
    fun theDifficultyDescriptionsAreGivenThePoseLabelAndTheEnumsOwnPenalty() {
        assertTrue(ground.contains("TrainingText.groundDescription(text, difficulty.name, poseWord, difficulty.penaltyPoints)"))
        assertTrue(ground.contains("val poseWord = labelFor(LabelKey.POSE)"))
        assertTrue(deck.contains("TrainingText.deckDescription(text, difficulty.name, labelFor(LabelKey.POSE), difficulty.penaltyPoints)"))
    }

    @Test
    fun theDeckTrainersPoseWordIsTheLabelTablesWordForTheStoredPose() {
        assertTrue(deck.contains("val poseWord = poseWords[game.target.poseLabel] ?: game.target.poseLabel"))
        assertTrue("the three pose words come from the label table, keyed by the stored names",
            Regex("""poseLabel\("IDENTITY"\)[\s\S]{0,120}poseLabel\("DEFEND"\)[\s\S]{0,120}poseLabel\("CONNECT"\)[\s\S]{0,300}mapOf\("IDENTITY" to identity, "DEFEND" to defend, "CONNECT" to connect\)""").containsMatchIn(RepoFiles.read("$base/training/TrainingGroundPanel.kt")))
    }

    @Test
    fun theHistoryRowsKeepTheirPointsVisibleWhateverTheLanguageOrTheDeckNameAdds() {
        assertTrue(Regex("""TrainingText\.groundHistoryLine\([^\n]*\),\s*modifier = Modifier\.weight\(1f\),""").containsMatchIn(ground))
        assertTrue(Regex("""TrainingText\.deckHistoryLine\([^\n]*\),\s*modifier = Modifier\.weight\(1f\),""").containsMatchIn(deck))
        assertTrue(Regex("""TrainingText\.duration\([^\n]*\),\s*modifier = Modifier\.weight\(1f\),""").containsMatchIn(ground))
        assertTrue(Regex("""TrainingText\.duration\([^\n]*\),\s*modifier = Modifier\.weight\(1f\),""").containsMatchIn(deck))
        assertTrue(Regex("""text = label,\s*modifier = Modifier\.weight\(1f\),""").containsMatchIn(deck))
    }

    // ---- the controllers are rules: no words, no labels, and the same scoring as before -----------------------------------------------

    @Test
    fun theControllersReadNoLabelsAndNoWords() {
        for ((name, source) in listOf("TrainingGame" to groundGame, "DeckTrainerGame" to deckGame)) {
            for (forbidden in listOf("labelFor", "poseLabel(", "stringResource", "R.string", "ResourceText", "rememberText", "LabelText", "PlainWordsState", "context.getString(", "getString(R.")) { // prefs.getString is the saved history, not a word
                assertFalse("$name reads words: $forbidden", source.contains(forbidden))
            }
            assertTrue("$name: the outcome is a kind", source.contains("var lastOutcome by mutableStateOf<TrainingOutcome?>(null)"))
            assertFalse("$name: no outcome made of text", source.contains("\"+\${") || source.contains("\"-\${") || source.contains("\"MISS\""))
        }
        assertFalse("no words for a missing phrase in the controller", deckGame.contains("(no group") || deckGame.contains("(blank slot)") || deckGame.contains("(unmapped)"))
    }

    @Test
    fun theScoringIsAsItWas_aHitScoresTheRewardAPenaltyCostsHalfAndAMissCostsNothing() {
        for ((name, source) in listOf("TrainingGame" to groundGame, "DeckTrainerGame" to deckGame)) {
            assertTrue("$name", Regex("""correct -> \{\s*score \+= difficulty\.rewardPoints\s*TrainingOutcome\.hit\(difficulty\.rewardPoints\)\s*\}""").containsMatchIn(source))
            assertTrue("$name", Regex("""difficulty\.hasPenalty -> \{\s*score -= difficulty\.penaltyPoints\s*TrainingOutcome\.penalty\(difficulty\.penaltyPoints\)\s*\}""").containsMatchIn(source))
            assertTrue("$name", Regex("""else -> TrainingOutcome\.MISS""").containsMatchIn(source))
            assertTrue("$name: the twist counts at most three", source.contains("twistLevel.coerceAtMost(3)"))
            assertTrue("$name: the saved difficulty is its enum name", source.contains("difficulty = difficulty.name,"))
        }
        assertTrue(groundGame.contains("val penaltyPoints: Int get() = rewardPoints / 2"))
    }

    @Test
    fun theEnumsNamesRewardsAndEnglishLabelsAreWhatTheDescriptionsAndHistoryAssume() {
        val entries = Regex("""(EASY|NORMAL|HARD|EUROPEAN_EXTREME)\(\s*label = "([^"]+)",\s*usesMod = (true|false),\s*hasPenalty = (true|false),\s*rewardPoints = (\d+)""").findAll(groundGame).toList()
        assertEquals(listOf("EASY", "NORMAL", "HARD", "EUROPEAN_EXTREME"), entries.map { it.groupValues[1] })
        // The label is the English name (what the enum's name is saved as, spaced); the language's name for it comes from TrainingText.
        for (e in entries) assertEquals(e.groupValues[1], e.groupValues[2].replace(' ', '_'), e.groupValues[1])
        for (e in entries) assertEquals(e.groupValues[1], english.getValue("train_diff_" + e.groupValues[1].lowercase().replace("european_extreme", "extreme")), e.groupValues[2])
        assertEquals(listOf("false/false/10", "true/false/20", "false/true/10", "true/true/20"), entries.map { "${it.groupValues[3]}/${it.groupValues[4]}/${it.groupValues[5]}" })
        // The descriptions say a penalty exactly where the enum has one, and no number where it has none.
        val hasPenalty = entries.associate { it.groupValues[1] to (it.groupValues[4] == "true") }
        for ((level, charges) in hasPenalty) {
            assertEquals(level, charges, TrainingText.groundDescription(EnglishText, level, "POSE", 5).contains("-5"))
            assertEquals(level, charges, TrainingText.deckDescription(EnglishText, level, "POSE", 5).contains("-5"))
        }
    }

    @Test
    fun theThreePoseListsAgree_theWireCodeToTheStoredPoseName() {
        val pair = Regex("""\"(ID|DEF|CON)\" to \"(IDENTITY|DEFEND|CONNECT)\"""")
        val inGround = pair.findAll(groundGame).map { it.groupValues[1] to it.groupValues[2] }.toList()
        val inDeck = pair.findAll(deckGame).map { it.groupValues[1] to it.groupValues[2] }.toList()
        assertEquals(TrainingPoses.WIRE_TO_CATEGORY, inGround)
        assertEquals(TrainingPoses.WIRE_TO_CATEGORY, inDeck)
    }

    @Test
    fun theDeckTrainerStillResolvesTheSameWays_aQuickActionsGroupAMatrixSlotOrNeither() {
        assertTrue(deckGame.contains("?: return TrainingStatement.NoGroup(category)"))
        assertTrue(deckGame.contains("} ?: return TrainingStatement.Unmapped"))
        assertEquals("two places turn a resolved phrase into a statement", 2, Regex("""TrainingStatement\.fromResolved\(""").findAll(deckGame).count())
        assertTrue(deckGame.contains("CommandRepository.resolveQuickAction("))
        assertTrue(deckGame.contains("CommandRepository.getResolvedPhrase("))
        assertTrue("the stored pose name, not a drawn word, is what is looked up", deckGame.contains("it.boundPose == category") && deckGame.contains("node.category == category &&"))
    }
}
