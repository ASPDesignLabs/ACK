package com.example.besu

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
                            text = "DECK TRAINER",
                            color = primaryColor,
                            fontSize = 13.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Black,
                            letterSpacing = 1.sp
                        )

                        Text(
                            text = "[EXIT]",
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
                        DeckTelemetryReadout(label = "STATE", value = stateLabel, primaryColor = primaryColor)
                        DeckTelemetryReadout(label = "POSE", value = deckFullPoseName(poseLabel), primaryColor = primaryColor)
                        DeckTelemetryReadout(label = "MOD", value = twistLevel.toString(), primaryColor = primaryColor)
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
    var isDurationExpanded by remember { mutableStateOf(false) }

    Column {
        Text(
            text = "DECK",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 1.sp
        )

        Spacer(modifier = Modifier.height(6.dp))

        eligibleDecks.forEach { deckMeta ->
            PickRow(
                label = "${deckMeta.name} // ${deckMeta.type.name.replace('_', ' ')}",
                isSelected = deckMeta.id == selectedDeck.id,
                primaryColor = primaryColor,
                onClick = { selectedDeck = deckMeta }
            )
            Spacer(modifier = Modifier.height(6.dp))
        }

        if (selectedDeck.type == DeckType.MATRIX) {
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "PROFILE",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(6.dp))

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

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "DIFFICULTY",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 1.sp
        )

        Spacer(modifier = Modifier.height(6.dp))

        GameDifficulty.entries.forEach { difficulty ->
            PickRow(
                label = difficulty.label,
                description = describeDeckDifficulty(difficulty),
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
                text = "DURATION: ${formatClock(selectedDuration)}",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp
            )

            Text(
                text = if (isDurationExpanded) "[COLLAPSE]" else "[EXPAND]",
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
            text = "[START ROUND]",
            primaryColor = primaryColor,
            onClick = {
                game.configure(selectedDeck, selectedProfile, selectedDifficulty, selectedDuration)
                game.start()
            }
        )

        if (game.history.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "PREVIOUS SCORES",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 1.sp
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
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            LabeledStat(
                label = "SCORE",
                value = game.score.toString(),
                color = if (game.score < 0) Color.Red else primaryColor
            )
            LabeledStat(
                label = "TIME",
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
                text = "SAY THIS",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = game.target.statement,
                color = primaryColor,
                fontSize = 15.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            val gestureText = game.target.poseLabel +
                if (game.difficulty.usesMod) " + MOD ${game.target.twist}" else ""
            Text(
                text = gestureText,
                color = primaryColor.copy(alpha = 0.7f),
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.6.sp
            )

            if (!game.difficulty.usesMod) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "ANY MODIFIER UNDER ${game.target.poseLabel} COUNTS",
                    color = Color.Gray,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        game.lastOutcome?.let { outcome ->
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = outcome,
                color = when {
                    outcome.startsWith("-") -> Color.Red
                    outcome == "MISS" -> Color.Gray
                    else -> primaryColor
                },
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        DeckActionButton(
            text = "[END ROUND]",
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
    Column {
        Text(
            text = "ROUND COMPLETE",
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.8.sp
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = "FINAL SCORE: ${game.score}",
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
                    text = "[PLAY AGAIN]",
                    primaryColor = primaryColor,
                    onClick = { game.dismissResults() }
                )
            }
            Box(modifier = Modifier.weight(1f)) {
                DeckActionButton(
                    text = "[DONE]",
                    primaryColor = Color.Gray,
                    onClick = onDone
                )
            }
        }

        if (game.history.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "PREVIOUS SCORES",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(6.dp))

            DeckHistoryList(results = game.history.take(5), primaryColor = primaryColor)
        }
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
            letterSpacing = 0.8.sp
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
            letterSpacing = 1.sp
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
            letterSpacing = 1.sp
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
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        results.forEach { result ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                val profileSuffix = result.profile?.let { " // $it" }.orEmpty()
                Text(
                    text = "${result.deckName}$profileSuffix // " +
                        result.difficulty.replace("_", " "),
                    color = Color.Gray,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )

                Text(
                    text = "${result.score} PTS",
                    color = if (result.score < 0) Color.Red else primaryColor,
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

private fun describeDeckDifficulty(difficulty: GameDifficulty): String = when (difficulty) {
    GameDifficulty.EASY -> "ANY MODIFIER UNDER THE RIGHT POSE COUNTS. NO PENALTY FOR A MISS."
    GameDifficulty.NORMAL -> "MUST MATCH THE EXACT STATEMENT SHOWN. NO PENALTY FOR A MISS."
    GameDifficulty.HARD -> "ANY MODIFIER UNDER THE RIGHT POSE COUNTS. -${difficulty.penaltyPoints} FOR A MISS."
    GameDifficulty.EUROPEAN_EXTREME -> "MUST MATCH THE EXACT STATEMENT SHOWN. -${difficulty.penaltyPoints} FOR A MISS."
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
            letterSpacing = 1.sp
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

// Same wire-code expansion as TrainingGroundPanel's private fullPoseName --
// duplicated here so that file can stay exactly as it is.
private fun deckFullPoseName(poseLabel: String): String = when (poseLabel) {
    "ID" -> "IDENTITY"
    "DEF" -> "DEFEND"
    "CON" -> "CONNECT"
    "---" -> "NONE"
    else -> poseLabel
}
