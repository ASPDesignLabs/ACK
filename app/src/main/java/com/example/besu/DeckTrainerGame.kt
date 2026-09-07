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

// Wire code (matches BackgroundSensorService.Pose.wireLabel()) to the category
// name used everywhere else -- MatrixNode.category, QuickActionGroup.boundPose.
// Kept as a private copy rather than reusing TrainingGame's GAME_POSES so that
// file can stay exactly as it is.
private val TRAINABLE_POSES = listOf(
    "ID" to "IDENTITY",
    "DEF" to "DEFEND",
    "CON" to "CONNECT"
)

// One rolled prompt: which physical pose+twist the watch must report, and the
// actual statement that combo currently resolves to for the deck/profile this
// round is training against (root-variable substitution included).
data class DeckTrainerTarget(
    val poseCode: String,
    val poseLabel: String,
    val twist: Int,
    val statement: String
)

@Serializable
data class DeckTrainerResult(
    val timestampMillis: Long,
    val deckId: String,
    val deckName: String,
    val deckType: String,
    val profile: String?,
    val difficulty: String,
    val durationSeconds: Int,
    val score: Int
)

object DeckTrainerHistory {
    private const val PREFS_NAME = "ack_deck_trainer"
    private const val HISTORY_KEY = "history"
    private const val MAX_ENTRIES = 50

    fun load(context: Context): List<DeckTrainerResult> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(HISTORY_KEY, "[]") ?: "[]"
        return try {
            Json.decodeFromString(raw)
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun append(context: Context, result: DeckTrainerResult) {
        val updated = (listOf(result) + load(context)).take(MAX_ENTRIES)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(HISTORY_KEY, Json.encodeToString(updated)).apply()
    }
}

// Deck-aware sibling of TrainingGame: same round/scoring shape (roll a target,
// score each watch fire against it, always roll a fresh target next), but the
// target's "statement" is resolved from the user's own Matrix (+ profile) or
// Quick Actions configuration instead of a bare pose/mod label, so the drill
// teaches where a real phrase lives rather than the raw gesture alphabet.
// TrainingGame/TrainingGroundPanel are unrelated and untouched.
class DeckTrainerController(private val context: Context) {
    var difficulty by mutableStateOf(GameDifficulty.EASY)
        private set
    var durationSeconds by mutableIntStateOf(60)
        private set

    var deck by mutableStateOf(defaultDeckMeta)
        private set
    var profile by mutableStateOf("DEFAULT")
        private set

    var isActive by mutableStateOf(false)
        private set
    var isFinished by mutableStateOf(false)
        private set

    var score by mutableIntStateOf(0)
        private set
    var timeRemainingSeconds by mutableIntStateOf(0)
        private set

    var target by mutableStateOf(DeckTrainerTarget("ID", "IDENTITY", 0, ""))
        private set

    var lastOutcome by mutableStateOf<String?>(null)
        private set

    var history by mutableStateOf(DeckTrainerHistory.load(context))
        private set

    fun configure(
        newDeck: DeckMeta,
        newProfile: String,
        newDifficulty: GameDifficulty,
        newDurationSeconds: Int
    ) {
        deck = newDeck
        profile = newProfile
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

        val current = target
        val effectiveMod = twistLevel.coerceAtMost(3)
        val poseMatches = pose == current.poseCode
        val modMatches = !difficulty.usesMod || effectiveMod == current.twist
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
        val (code, label) = TRAINABLE_POSES.random()

        // EASY/HARD don't require the mod to match (see onFireDetected), so
        // any twist under the right pose scores a hit -- but the screen still
        // shows one specific statement. Pinning that to twist 0 keeps it a
        // real, verifiable phrase: mod 0 is always a valid way to produce it,
        // rather than a random twist whose phrase might differ from whatever
        // twist the user actually fires.
        val twist = if (difficulty.usesMod) (0..3).random() else 0

        target = DeckTrainerTarget(
            poseCode = code,
            poseLabel = label,
            twist = twist,
            statement = resolveStatement(deck, profile, label, twist)
        )
    }

    private fun resolveStatement(
        deckMeta: DeckMeta,
        activeProfile: String,
        category: String,
        twist: Int
    ): String {
        return when (deckMeta.type) {
            DeckType.QUICK_ACTIONS -> {
                val config = CommandRepository.getQuickActionsConfig(context, deckMeta.id)
                val group = config.groups.find { it.boundPose == category }
                    ?: return "(no group bound to $category)"

                CommandRepository.resolveQuickAction(
                    context,
                    deckMeta.id,
                    group.groupIndex,
                    twist
                ).ifBlank { "(blank slot)" }
            }
            else -> {
                val node = CommandRepository.BASE_TEMPLATE.find { node ->
                    node.category == category &&
                        node.path.substringAfterLast("/").toIntOrNull() == twist
                } ?: return "(unmapped)"

                CommandRepository.getResolvedPhrase(
                    context,
                    node.path,
                    deckMeta.id,
                    activeProfile
                ).ifBlank { "(blank slot)" }
            }
        }
    }

    private fun finish() {
        isActive = false
        isFinished = true
        DeckTrainerHistory.append(
            context,
            DeckTrainerResult(
                timestampMillis = System.currentTimeMillis(),
                deckId = deck.id,
                deckName = deck.name,
                deckType = deck.type.name,
                profile = if (deck.type == DeckType.MATRIX) profile else null,
                difficulty = difficulty.name,
                durationSeconds = durationSeconds,
                score = score
            )
        )
        history = DeckTrainerHistory.load(context)
    }
}

@Composable
fun rememberDeckTrainerController(context: Context): DeckTrainerController {
    return remember { DeckTrainerController(context) }
}
