package com.example.besu

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

// Root difficulty splits along two independent axes the user asked for:
// usesMod (root pose only vs. a specific modifier twist within it) and
// hasPenalty (failures ignored vs. costing half the reward).
enum class GameDifficulty(
    val label: String,
    val usesMod: Boolean,
    val hasPenalty: Boolean,
    val rewardPoints: Int
) {
    EASY(
        label = "EASY",
        usesMod = false,
        hasPenalty = false,
        rewardPoints = 10
    ),
    NORMAL(
        label = "NORMAL",
        usesMod = true,
        hasPenalty = false,
        rewardPoints = 20
    ),
    HARD(
        label = "HARD",
        usesMod = false,
        hasPenalty = true,
        rewardPoints = 10
    ),
    EUROPEAN_EXTREME(
        label = "EUROPEAN EXTREME",
        usesMod = true,
        hasPenalty = true,
        rewardPoints = 20
    );

    val penaltyPoints: Int get() = rewardPoints / 2
}

// Wire code (matches BackgroundSensorService.Pose.wireLabel()) to display name.
private val GAME_POSES = listOf(
    "ID" to "IDENTITY",
    "DEF" to "DEFEND",
    "CON" to "CONNECT"
)

@Serializable
data class TrainingGameResult(
    val timestampMillis: Long,
    val difficulty: String,
    val durationSeconds: Int,
    val score: Int
)

object TrainingGameHistory {
    private const val PREFS_NAME = "ack_training_game"
    private const val HISTORY_KEY = "history"
    private const val MAX_ENTRIES = 50

    fun load(context: Context): List<TrainingGameResult> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(HISTORY_KEY, "[]") ?: "[]"
        return try {
            Json.decodeFromString(raw)
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun append(context: Context, result: TrainingGameResult) {
        val updated = (listOf(result) + load(context)).take(MAX_ENTRIES)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(HISTORY_KEY, Json.encodeToString(updated)).apply()
    }
}

// Drives one Training Ground gamification round: rolls a target pose (and, on
// NORMAL/EUROPEAN_EXTREME, a target modifier twist count), scores each fire
// the watch reports against it, and always rolls a fresh target next --
// whether that fire matched or not. See TrainingGroundPanel for how a "fire"
// is detected from the live watch telemetry it already tracks.
class TrainingGameController(private val context: Context) {
    var difficulty by mutableStateOf(GameDifficulty.EASY)
        private set
    var durationSeconds by mutableIntStateOf(60)
        private set

    var isActive by mutableStateOf(false)
        private set
    var isFinished by mutableStateOf(false)
        private set

    var score by mutableIntStateOf(0)
        private set
    var timeRemainingSeconds by mutableIntStateOf(0)
        private set

    var targetPoseCode by mutableStateOf(GAME_POSES[0].first)
        private set
    var targetPoseLabel by mutableStateOf(GAME_POSES[0].second)
        private set
    var targetMod by mutableStateOf<Int?>(null)
        private set

    var lastOutcome by mutableStateOf<String?>(null)
        private set

    var history by mutableStateOf(TrainingGameHistory.load(context))
        private set

    fun configure(newDifficulty: GameDifficulty, newDurationSeconds: Int) {
        difficulty = newDifficulty
        durationSeconds = newDurationSeconds
    }

    fun start() {
        score = 0
        timeRemainingSeconds = durationSeconds
        lastOutcome = null
        isFinished = false
        isActive = true
        rollTarget()
    }

    fun tick() {
        if (!isActive) return
        timeRemainingSeconds -= 1
        if (timeRemainingSeconds <= 0) {
            finish()
        }
    }

    fun abort() {
        if (!isActive) return
        finish()
    }

    fun dismissResults() {
        isFinished = false
    }

    // pose is the wire code (ID/DEF/CON) and twistLevel the modifier count the
    // watch reported at the moment it fired.
    fun onFireDetected(pose: String, twistLevel: Int) {
        if (!isActive) return

        val effectiveMod = twistLevel.coerceAtMost(3)
        val poseMatches = pose == targetPoseCode
        val modMatches = !difficulty.usesMod || effectiveMod == targetMod
        val correct = poseMatches && modMatches

        lastOutcome = when {
            correct -> {
                score += difficulty.rewardPoints
                "+${difficulty.rewardPoints}"
            }
            difficulty.hasPenalty -> {
                score -= difficulty.penaltyPoints
                "-${difficulty.penaltyPoints}"
            }
            else -> "MISS"
        }

        rollTarget()
    }

    private fun rollTarget() {
        val (code, label) = GAME_POSES.random()
        targetPoseCode = code
        targetPoseLabel = label
        targetMod = if (difficulty.usesMod) (0..3).random() else null
    }

    private fun finish() {
        isActive = false
        isFinished = true
        TrainingGameHistory.append(
            context,
            TrainingGameResult(
                timestampMillis = System.currentTimeMillis(),
                difficulty = difficulty.name,
                durationSeconds = durationSeconds,
                score = score
            )
        )
        history = TrainingGameHistory.load(context)
    }
}

@Composable
fun rememberTrainingGameController(context: Context): TrainingGameController {
    return remember { TrainingGameController(context) }
}
