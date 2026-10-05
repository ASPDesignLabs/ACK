// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.training

import com.example.besu.R
import com.example.besu.core.LabelKey
import com.example.besu.core.TrainingOutcome
import com.example.besu.core.TrainingText
import com.example.besu.help.*
import com.example.besu.ui.*
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

// Live watch telemetry, unpaced -- for free-form gesture practice, or (toggle
// on) a scored drill. Distinct from HelpCoachPanel: no fixed steps, and the
// watch's normal timing is left alone (see BackgroundSensorService.TrainingMode.LIVE).
@Composable
fun TrainingGroundPanel(
    stateLabel: String,
    poseLabel: String,
    twistLevel: Int,
    primaryColor: Color,
    onClose: () -> Unit
) {
    val context = LocalContext.current
    val game = rememberTrainingGameController(context)
    var gameModeEnabled by remember { mutableStateOf(false) }
    val text = rememberText()
    val poseWords = rememberTrainingPoseWords()

    // A "fire" is the edge where state just became COOLDOWN -- poseLabel/
    // twistLevel at that instant are what the watch actually just fired, since
    // BackgroundSensorService only resets them on the later COOLDOWN->IDLE step.
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
                            text = stringResource(R.string.train_title),
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

                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = stringResource(R.string.train_game_mode),
                            color = Color.White.copy(alpha = 0.8f),
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = looseSpacing(0.8.sp)
                        )

                        NeonToggle(
                            checked = gameModeEnabled,
                            onCheckedChange = { enabled ->
                                if (!enabled) {
                                    if (game.isActive) game.abort()
                                    game.dismissResults()
                                }
                                gameModeEnabled = enabled
                            },
                            activeColor = primaryColor
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    if (gameModeEnabled) {
                        when {
                            game.isFinished -> ResultsScreen(
                                game = game,
                                primaryColor = primaryColor,
                                onDone = {
                                    game.dismissResults()
                                    gameModeEnabled = false
                                }
                            )
                            game.isActive -> PlayingScreen(
                                game = game,
                                primaryColor = primaryColor
                            )
                            else -> ConfigScreen(
                                game = game,
                                primaryColor = primaryColor
                            )
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                    } else {
                        Text(
                            text = stringResource(R.string.train_free_note),
                            color = Color.White.copy(alpha = 0.7f),
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace,
                            lineHeight = 14.sp
                        )

                        Spacer(modifier = Modifier.height(14.dp))
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        // The state is what the watch sent (and the header and the watch's own screen show it in English), so only its label is translated.
                        TelemetryReadout(label = stringResource(R.string.train_state), value = stateLabel, primaryColor = primaryColor)
                        TelemetryReadout(label = labelFor(LabelKey.POSE), value = TrainingText.poseValue(text, poseLabel, poseWords), primaryColor = primaryColor)
                        TelemetryReadout(label = stringResource(R.string.train_mod), value = twistLevel.toString(), primaryColor = primaryColor)
                    }
                }
            }
        }
    }
}

@Composable
private fun ConfigScreen(
    game: TrainingGameController,
    primaryColor: Color
) {
    var selectedDifficulty by remember { mutableStateOf(game.difficulty) }
    var selectedDuration by remember { mutableIntStateOf(game.durationSeconds) }
    var isDurationExpanded by remember { mutableStateOf(false) }
    val text = rememberText()

    Column {
        Text(
            text = stringResource(R.string.train_difficulty),
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        GameDifficulty.entries.forEach { difficulty ->
            DifficultyRow(
                difficulty = difficulty,
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
                steps = 8, // (300-30)/30 - 1 intervals -> 30s snap increments
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

        GameActionButton(
            text = stringResource(R.string.train_start),
            primaryColor = primaryColor,
            onClick = {
                game.configure(selectedDifficulty, selectedDuration)
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

            HistoryList(results = game.history.take(5), primaryColor = primaryColor)
        }
    }
}

@Composable
private fun PlayingScreen(
    game: TrainingGameController,
    primaryColor: Color
) {
    val text = rememberText()
    val poseWords = rememberTrainingPoseWords()
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
                text = stringResource(R.string.train_requested),
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = looseSpacing(1.sp)
            )

            Spacer(modifier = Modifier.height(4.dp))

            val targetText = TrainingText.requested(text, poseWords[game.targetPoseLabel] ?: game.targetPoseLabel, game.targetMod)
            Text(
                text = targetText,
                color = primaryColor,
                fontSize = 16.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                letterSpacing = looseSpacing(0.8.sp)
            )
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

        GameActionButton(
            text = stringResource(R.string.train_end),
            primaryColor = Color.Gray,
            onClick = { game.abort() }
        )
    }
}

@Composable
private fun ResultsScreen(
    game: TrainingGameController,
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
                GameActionButton(
                    text = stringResource(R.string.train_play_again),
                    primaryColor = primaryColor,
                    onClick = { game.dismissResults() }
                )
            }
            Box(modifier = Modifier.weight(1f)) {
                GameActionButton(
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

            HistoryList(results = game.history.take(5), primaryColor = primaryColor)
        }
    }
}

@Composable
private fun DifficultyRow(
    difficulty: GameDifficulty,
    isSelected: Boolean,
    primaryColor: Color,
    onClick: () -> Unit
) {
    val text = rememberText()
    val poseWord = labelFor(LabelKey.POSE)
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
            text = TrainingText.difficultyName(text, difficulty.name),
            color = textColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(0.8.sp)
        )

        Spacer(modifier = Modifier.height(3.dp))

        Text(
            text = TrainingText.groundDescription(text, difficulty.name, poseWord, difficulty.penaltyPoints),
            color = Color.Gray,
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun GameActionButton(
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
private fun HistoryList(
    results: List<TrainingGameResult>,
    primaryColor: Color
) {
    val text = rememberText()
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        results.forEach { result ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // A saved difficulty is its enum name; it is shown through the language's word and never rewritten.
                Text(
                    text = TrainingText.groundHistoryLine(text, result.difficulty, formatClock(result.durationSeconds)),
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
private fun TelemetryReadout(
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

// The words for the three poses (IDENTITY, DEFEND, CONNECT), keyed by the stored pose name: the label table's word, so PLAIN WORDS and the chosen language apply.
// Shared with the Deck Trainer; a pose's stored name is logic and never changes, only the word drawn for it.
@Composable
internal fun rememberTrainingPoseWords(): Map<String, String> {
    val identity = poseLabel("IDENTITY")
    val defend = poseLabel("DEFEND")
    val connect = poseLabel("CONNECT")
    return remember(identity, defend, connect) {
        mapOf("IDENTITY" to identity, "DEFEND" to defend, "CONNECT" to connect)
    }
}
