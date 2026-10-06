// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.training

import com.example.besu.R
import com.example.besu.core.LabelKey
import com.example.besu.core.TrainingOutcome
import com.example.besu.core.TrainingText
import com.example.besu.ui.labelFor
import com.example.besu.ui.looseSpacing
import com.example.besu.ui.rememberText
import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.ui.theme.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.besu.ui.theme.Graphite
import kotlinx.coroutines.delay

// Deck-aware sibling of TrainingGroundPanel: trains against the user's own
// Matrix (+ profile) or Quick Actions configuration, so the prompt is a real
// statement pulled from their deck rather than a bare pose/mod label. Always
// scored (no free-telemetry toggle) -- that's what TrainingGroundPanel is for.
// TrainingGroundPanel/TrainingGame are unrelated and untouched.
@Composable
fun DeckTrainerPanel(
    stateLabel: String,
    poseLabel: String,
    twistLevel: Int,
    decks: List<DeckMeta>,
    primaryColor: Color,
    onClose: () -> Unit
) {
    val context = LocalContext.current
    val game = rememberDeckTrainerController(context)
    val text = rememberText()
    val poseWords = rememberTrainingPoseWords()

    // A "fire" is the edge where state just became COOLDOWN -- see
    // TrainingGroundPanel for why that instant (rather than the eventual
    // COOLDOWN->IDLE reset) is when poseLabel/twistLevel reflect the fire.
    var lastSeenState by remember { mutableStateOf("") }
    LaunchedEffect(stateLabel, poseLabel, twistLevel) {
        if (stateLabel == "COOLDOWN" && lastSeenState != "COOLDOWN") {
            game.onFireDetected(poseLabel, twistLevel)
        }
        lastSeenState = stateLabel
    }

    LaunchedEffect(game.isActive) {
        while (game.isActive) {
            delay(1000)
            game.tick()
        }
    }

    Dialog(
        onDismissRequest = {
            if (game.isActive) game.abort()
            onClose()
        },
        properties = DialogProperties(usePlatformDefaultWidth = false)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 560.dp)
                    .border(
                        width = 1.dp,
                        color = primaryColor,
                        shape = AckHelpShape
                    ),
                color = Graphite,
                shape = AckHelpShape
            ) {
                Column(
                    modifier = Modifier
                        .padding(16.dp)
                        .heightIn(max = 640.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = stringResource(R.string.deck_trainer_title, labelFor(LabelKey.DECK)),
                            color = primaryColor,
                            fontSize = 13.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Black,
                            letterSpacing = looseSpacing(1.sp)
                        )

                        Text(
                            text = stringResource(R.string.train_exit),
                            color = Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .clickable {
                                    if (game.isActive) game.abort()
                                    onClose()
                                }
                                .padding(4.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    when {
                        game.isFinished -> DeckResultsScreen(
                            game = game,
                            primaryColor = primaryColor,
                            onDone = { game.dismissResults() }
                        )
                        game.isActive -> DeckPlayingScreen(
                            game = game,
                            primaryColor = primaryColor
                        )
                        else -> DeckConfigScreen(
                            game = game,
                            decks = decks,
                            primaryColor = primaryColor
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        // The state is what the watch sent (and the header and the watch's own screen show it in English), so only its label is translated.
                        DeckTelemetryReadout(label = stringResource(R.string.train_state), value = stateLabel, primaryColor = primaryColor)
                        DeckTelemetryReadout(label = labelFor(LabelKey.POSE), value = TrainingText.poseValue(text, poseLabel, poseWords), primaryColor = primaryColor)
                        DeckTelemetryReadout(label = stringResource(R.string.train_mod), value = twistLevel.toString(), primaryColor = primaryColor)
                    }
                }
            }
        }
    }
}

@Composable
private fun DeckConfigScreen(
    game: DeckTrainerController,
    decks: List<DeckMeta>,
    primaryColor: Color
) {
    val eligibleDecks = remember(decks) {
        listOf(defaultDeckMeta) + decks.filter {
            it.type == DeckType.MATRIX || it.type == DeckType.QUICK_ACTIONS
        }
    }

    var selectedDeck by remember {
        mutableStateOf(eligibleDecks.find { it.id == game.deck.id } ?: eligibleDecks.first())
    }
    var selectedProfile by remember { mutableStateOf(game.profile) }
    var selectedDifficulty by remember { mutableStateOf(game.difficulty) }
    var selectedDuration by remember { mutableIntStateOf(game.durationSeconds) }
    var isDeckExpanded by remember { mutableStateOf(false) }
    var isProfileExpanded by remember { mutableStateOf(false) }
    var isDurationExpanded by remember { mutableStateOf(false) }
    val text = rememberText()
    val deckWord = labelFor(LabelKey.DECK)
    val matrixWord = labelFor(LabelKey.DECK_TYPE_MATRIX)
    val quickWord = labelFor(LabelKey.DECK_TYPE_QUICK)

    Column {
        ExpandableHeaderRow(
            label = TrainingText.deckLine(deckWord, selectedDeck.name),
            isExpanded = isDeckExpanded,
            primaryColor = primaryColor,
            onToggle = { isDeckExpanded = !isDeckExpanded }
        )

        if (isDeckExpanded) {
            Spacer(modifier = Modifier.height(4.dp))

            eligibleDecks.forEach { deckMeta ->
                PickRow(
                    label = TrainingText.deckPickLine(deckMeta.name, TrainingText.deckTypeWord(deckMeta.type.name, matrixWord, quickWord)),
                    isSelected = deckMeta.id == selectedDeck.id,
                    primaryColor = primaryColor,
                    onClick = { selectedDeck = deckMeta }
                )
                Spacer(modifier = Modifier.height(6.dp))
            }
        }

        if (selectedDeck.type == DeckType.MATRIX) {
            Spacer(modifier = Modifier.height(8.dp))

            ExpandableHeaderRow(
                label = TrainingText.profileLine(text, selectedProfile),
                isExpanded = isProfileExpanded,
                primaryColor = primaryColor,
                onToggle = { isProfileExpanded = !isProfileExpanded }
            )

            if (isProfileExpanded) {
                Spacer(modifier = Modifier.height(4.dp))

                CommandRepository.PROFILES.forEach { prof ->
                    PickRow(
                        label = prof,
                        isSelected = prof == selectedProfile,
                        primaryColor = primaryColor,
                        onClick = { selectedProfile = prof }
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = stringResource(R.string.train_difficulty),
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        GameDifficulty.entries.forEach { difficulty ->
            PickRow(
                label = TrainingText.difficultyName(text, difficulty.name),
                description = TrainingText.deckDescription(text, difficulty.name, labelFor(LabelKey.POSE), difficulty.penaltyPoints),
                isSelected = difficulty == selectedDifficulty,
                primaryColor = primaryColor,
                onClick = { selectedDifficulty = difficulty }
            )
            Spacer(modifier = Modifier.height(6.dp))
        }

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { isDurationExpanded = !isDurationExpanded }
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = TrainingText.duration(text, formatClock(selectedDuration)),
                modifier = Modifier.weight(1f),
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = looseSpacing(0.8.sp)
            )

            Text(
                text = stringResource(if (isDurationExpanded) R.string.train_collapse else R.string.train_expand),
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        if (isDurationExpanded) {
            Spacer(modifier = Modifier.height(4.dp))

            Slider(
                value = selectedDuration.toFloat(),
                onValueChange = { selectedDuration = it.toInt() },
                valueRange = 30f..300f,
                steps = 8,
                colors = SliderDefaults.colors(
                    thumbColor = primaryColor,
                    activeTrackColor = primaryColor
                )
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("0:30", color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
                Text("5:00", color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        DeckActionButton(
            text = stringResource(R.string.train_start),
            primaryColor = primaryColor,
            onClick = {
                game.configure(selectedDeck, selectedProfile, selectedDifficulty, selectedDuration)
                game.start()
            }
        )

        if (game.history.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = stringResource(R.string.train_previous_scores),
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = looseSpacing(1.sp)
            )

            Spacer(modifier = Modifier.height(6.dp))

            DeckHistoryList(results = game.history.take(5), primaryColor = primaryColor)
        }
    }
}

@Composable
private fun DeckPlayingScreen(
    game: DeckTrainerController,
    primaryColor: Color
) {
    val text = rememberText()
    val poseWords = rememberTrainingPoseWords()
    // The target's pose is the stored name (IDENTITY...); only the word drawn for it follows the language and PLAIN WORDS.
    val poseWord = poseWords[game.target.poseLabel] ?: game.target.poseLabel
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            LabeledStat(
                label = stringResource(R.string.train_score),
                value = TrainingText.number(text, game.score),
                color = if (game.score < 0) Color.Red else primaryColor
            )
            LabeledStat(
                label = stringResource(R.string.train_time),
                value = formatClock(game.timeRemainingSeconds),
                color = primaryColor
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(width = 1.dp, color = primaryColor, shape = AckHelpShape)
                .background(color = primaryColor.copy(alpha = 0.08f), shape = AckHelpShape)
                .padding(14.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = stringResource(R.string.deck_trainer_say),
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = looseSpacing(1.sp)
            )

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = TrainingText.statement(text, game.target.statement, poseWords),
                color = primaryColor,
                fontSize = 15.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            // EUROPEAN_EXTREME is the final reinforcement step: recall the
            // gesture from the phrase alone, with no pose/mod hint at all.
            if (game.difficulty != GameDifficulty.EUROPEAN_EXTREME) {
                Spacer(modifier = Modifier.height(8.dp))

                val gestureText = TrainingText.requested(
                    text,
                    poseWord,
                    if (game.difficulty.usesMod) game.target.twist else null
                )
                Text(
                    text = gestureText,
                    color = primaryColor.copy(alpha = 0.7f),
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = looseSpacing(0.6.sp)
                )
            }

            if (!game.difficulty.usesMod) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = TrainingText.anyModifier(text, poseWord),
                    color = Color.Gray,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        game.lastOutcome?.let { outcome ->
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = TrainingText.outcome(text, outcome),
                color = when (outcome.kind) {
                    TrainingOutcome.Kind.PENALTY -> Color.Red
                    TrainingOutcome.Kind.MISS -> Color.Gray
                    TrainingOutcome.Kind.HIT -> primaryColor
                },
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        DeckActionButton(
            text = stringResource(R.string.train_end),
            primaryColor = Color.Gray,
            onClick = { game.abort() }
        )
    }
}

@Composable
private fun DeckResultsScreen(
    game: DeckTrainerController,
    primaryColor: Color,
    onDone: () -> Unit
) {
    val text = rememberText()
    Column {
        Text(
            text = stringResource(R.string.train_round_complete),
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(0.8.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = TrainingText.finalScore(text, game.score),
            color = if (game.score < 0) Color.Red else primaryColor,
            fontSize = 16.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black
        )

        Spacer(modifier = Modifier.height(14.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(modifier = Modifier.weight(1f)) {
                DeckActionButton(
                    text = stringResource(R.string.train_play_again),
                    primaryColor = primaryColor,
                    onClick = { game.dismissResults() }
                )
            }
            Box(modifier = Modifier.weight(1f)) {
                DeckActionButton(
                    text = stringResource(R.string.train_done),
                    primaryColor = Color.Gray,
                    onClick = onDone
                )
            }
        }

        if (game.history.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = stringResource(R.string.train_previous_scores),
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = looseSpacing(1.sp)
            )

            Spacer(modifier = Modifier.height(6.dp))

            DeckHistoryList(results = game.history.take(5), primaryColor = primaryColor)
        }
    }
}

// Same collapsed-summary/[EXPAND]/[COLLAPSE] shape as the duration control
// below it -- used for DECK and PROFILE so picking either doesn't force a
// full list onto the screen every time the config screen is open.
@Composable
private fun ExpandableHeaderRow(
    label: String,
    isExpanded: Boolean,
    primaryColor: Color,
    onToggle: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle)
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            modifier = Modifier.weight(1f),
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(0.8.sp)
        )

        Text(
            text = stringResource(if (isExpanded) R.string.train_collapse else R.string.train_expand),
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun PickRow(
    label: String,
    description: String? = null,
    isSelected: Boolean,
    primaryColor: Color,
    onClick: () -> Unit
) {
    val borderColor = if (isSelected) Color.White else primaryColor.copy(alpha = 0.5f)
    val textColor = if (isSelected) Color.White else primaryColor

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(width = 1.dp, color = borderColor, shape = AckHelpShape)
            .background(
                color = if (isSelected) primaryColor.copy(alpha = 0.16f) else Color.Transparent,
                shape = AckHelpShape
            )
            .clickable(onClick = onClick)
            .padding(10.dp)
    ) {
        Text(
            text = label,
            color = textColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(0.8.sp)
        )

        if (description != null) {
            Spacer(modifier = Modifier.height(3.dp))

            Text(
                text = description,
                color = Color.Gray,
                fontSize = 8.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}

@Composable
private fun DeckActionButton(
    text: String,
    primaryColor: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .border(width = 1.dp, color = primaryColor, shape = AckHelpShape)
            .background(color = primaryColor.copy(alpha = 0.12f), shape = AckHelpShape)
            .clickable(onClick = onClick)
            .padding(vertical = 11.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(1.sp)
        )
    }
}

@Composable
private fun LabeledStat(
    label: String,
    value: String,
    color: Color
) {
    Column {
        Text(
            text = label,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(2.dp))

        Text(
            text = value,
            color = color,
            fontSize = 16.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black
        )
    }
}

@Composable
private fun DeckHistoryList(
    results: List<DeckTrainerResult>,
    primaryColor: Color
) {
    val text = rememberText()
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        results.forEach { result ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // The deck's saved name and the profile are shown as saved; a saved difficulty is its enum name, shown through the language's word and never rewritten.
                Text(
                    text = TrainingText.deckHistoryLine(text, result.deckName, result.profile, result.difficulty),
                    modifier = Modifier.weight(1f),
                    color = Color.Gray,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )

                Text(
                    text = TrainingText.points(text, result.score),
                    color = if (result.score < 0) Color.Red else primaryColor,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

private fun formatClock(totalSeconds: Int): String {
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "$minutes:${seconds.toString().padStart(2, '0')}"
}

@Composable
private fun DeckTelemetryReadout(
    label: String,
    value: String,
    primaryColor: Color
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = label,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = value,
            color = primaryColor,
            fontSize = 18.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Black
        )
    }
}
