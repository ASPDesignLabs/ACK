package com.example.besu.ui

import com.example.besu.*
import com.example.besu.backup.*
import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.settings.*
import com.example.besu.ui.theme.*
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.*
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch


data class VariableEditRequest(
    val nodePath: String,
    val nodeLabel: String,
    val index: Int,
    val currentValue: String
)

data class MatrixVariableDisplay(
    val index: Int,
    val tag: String?,
    val localValue: String,
    val displayValue: String,
    val isOverridden: Boolean
)
// --- NEON FLUX PALETTE (DEFINITIONS) ---
val FluxCyan = Color(0xFF00F3FF)
val RadicalRed = Color(0xFFFF0055)
val BioGreen = Color(0xFF00FF41)
val DataOrange = Color(0xFFFF9900)
val NeonViolet = Color(0xFFBD00FF)

// STATUSBOX -- the live TYPING / root-variable strip above the Terminal
// prompt. Deliberately brighter than Graphite (the CMD-block background)
// with the red/green channels held back so it reads as a cyan-tinted panel
// rather than a neutral gray one, distinguishing it from every other
// surface in the Terminal at a glance.
val StatusBoxBg = Color(0xFF1C3238)

// STATUSBOX is deliberately POSIX-menu styled, not another set of neon
// chips: one uniform monospace size for every string that appears in it,
// plain text joined by " - "/" / " delimiters instead of bordered boxes,
// and reverse video (solid fill, dark text) for whatever's currently
// selected instead of a tinted border. STATUSBOX_FONT_SIZE and
// STATUSBOX_PAGE_SIZE are its only tunables.
val STATUSBOX_FONT_SIZE = 14.sp
private const val STATUSBOX_PAGE_SIZE = 3

// ==========================================
//        ATOMIC COMPONENTS (BUTTONS)
// ==========================================

@Composable
fun NeonButton(
    text: String,
    modifier: Modifier = Modifier,
    isActive: Boolean = true,
    mainColor: Color = NeonPalette.DEFAULT_CYAN,
    onClick: () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    val containerColor = Graphite
    
    // VISUALS: Dim if inactive, Bright if active
    val contentColor = if(isActive) mainColor else mainColor.copy(alpha=0.4f)
    val borderColor = if(isActive) mainColor else mainColor.copy(alpha=0.2f)

    Button(
        onClick = { 
            // Always provide haptic feedback, logic check is up to caller
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            onClick() 
        },
        modifier = modifier.height(40.dp),
        shape = CutCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(containerColor = containerColor, contentColor = contentColor),
        border = BorderStroke(1.dp, borderColor),
        contentPadding = PaddingValues(horizontal = 16.dp),
        // FIX: Button is always enabled so we can click it to switch tabs
        enabled = true 
    ) {
        Text(text.uppercase(), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp, fontSize = 12.sp)
    }
}



@Composable
fun PulsingStatusBox(color: Color) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val alpha by infiniteTransition.animateFloat(initialValue = 1f, targetValue = 0.2f, animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse), label = "alpha")
    Box(modifier = Modifier.size(16.dp).border(1.dp, color, CutCornerShape(4.dp)).padding(3.dp).alpha(alpha).background(color, CutCornerShape(2.dp)))
}

// One entry in a STATUSBOX list row -- shared by /v's groupings/variables
// and /t's categories/tree nodes so every picker renders through the same
// two composables below instead of four near-copies of the same styling.
private data class StatusBoxItem(
    val label: String,
    val clickable: Boolean = true,
    val onClick: () -> Unit = {}
)

// A page of items rendered POSIX-select-style: plain monospace text joined
// by " - ", the item at highlightedIndex reverse-videoed (solid fill, dark
// text) instead of bordered/tinted, and a non-clickable item shown dim.
// Pages with more than STATUSBOX_PAGE_SIZE items get "<"/">" tap targets
// at the edges -- discrete paging, no scroll gesture, so it behaves like a
// real terminal select menu rather than a chip carousel. A horizontalScroll
// is still wrapped around the row as a safety net for a page whose labels
// are simply too wide for the screen, but paging is the primary way to
// reach anything beyond the first page.
@Composable
private fun StatusBoxItemRow(
    items: List<StatusBoxItem>,
    highlightedIndex: Int?,
    page: Int,
    onPageChange: (Int) -> Unit,
    color: Color,
    pageSize: Int = STATUSBOX_PAGE_SIZE
) {
    val pageCount = if (items.isEmpty()) 1 else (items.size + pageSize - 1) / pageSize
    val clampedPage = page.coerceIn(0, pageCount - 1)
    val start = clampedPage * pageSize
    val visible = items.drop(start).take(pageSize)
    val hasPrev = clampedPage > 0
    val hasNext = start + pageSize < items.size

    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (hasPrev) {
            Text(
                "<",
                color = color,
                fontFamily = FontFamily.Monospace,
                fontSize = STATUSBOX_FONT_SIZE,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable { onPageChange(clampedPage - 1) }
                    .padding(horizontal = 6.dp, vertical = 6.dp)
            )
        }
        visible.forEachIndexed { i, item ->
            val globalIndex = start + i
            val isHighlighted = globalIndex == highlightedIndex
            Text(
                item.label,
                color = when {
                    isHighlighted -> StatusBoxBg
                    !item.clickable -> color.copy(alpha = 0.35f)
                    else -> color
                },
                fontFamily = FontFamily.Monospace,
                fontSize = STATUSBOX_FONT_SIZE,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .then(
                        if (isHighlighted) {
                            Modifier.background(color, AckHelpShape)
                        } else {
                            Modifier
                        }
                    )
                    .then(
                        if (item.clickable) {
                            Modifier.clickable(onClick = item.onClick)
                        } else {
                            Modifier
                        }
                    )
                    .padding(horizontal = 4.dp, vertical = 6.dp)
            )
            if (i < visible.lastIndex) {
                Text(
                    " - ",
                    color = color.copy(alpha = 0.4f),
                    fontFamily = FontFamily.Monospace,
                    fontSize = STATUSBOX_FONT_SIZE
                )
            }
        }
        if (hasNext) {
            Text(
                ">",
                color = color,
                fontFamily = FontFamily.Monospace,
                fontSize = STATUSBOX_FONT_SIZE,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable { onPageChange(clampedPage + 1) }
                    .padding(horizontal = 6.dp, vertical = 6.dp)
            )
        }
    }
}

// A tappable path trail -- /t's drill-down breadcrumb ("PLACES / DOWNTOWN"),
// or /v's single-segment "which grouping am I in" line. Every segment but
// the last is dim and clickable (tap to jump back to that level); the last
// segment is bright and inert -- you're already there.
@Composable
private fun StatusBoxBreadcrumb(segments: List<StatusBoxItem>, color: Color) {
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.CenterVertically
    ) {
        segments.forEachIndexed { i, segment ->
            val isCurrent = i == segments.lastIndex
            Text(
                segment.label,
                color = if (isCurrent) color else color.copy(alpha = 0.55f),
                fontFamily = FontFamily.Monospace,
                fontSize = STATUSBOX_FONT_SIZE,
                fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                modifier = if (!isCurrent && segment.clickable) {
                    Modifier.clickable(onClick = segment.onClick)
                } else {
                    Modifier
                }
            )
            if (i < segments.lastIndex) {
                Text(
                    " / ",
                    color = color.copy(alpha = 0.4f),
                    fontFamily = FontFamily.Monospace,
                    fontSize = STATUSBOX_FONT_SIZE
                )
            }
        }
    }
}

@Composable
fun RowScope.ThemeOption(
    id: Int, 
    label: String, 
    current: Int, 
    activeColor: Color = FluxCyan, 
    onClick: () -> Unit
) {
    val active = id == current
    val haptic = LocalHapticFeedback.current
    Box(
        modifier = Modifier.weight(1f).height(40.dp)
            .background(if(active) activeColor.copy(alpha=0.1f) else Color.Transparent)
            .border(1.dp, if(active) activeColor else Color.DarkGray, CutCornerShape(8.dp))
            .clickable { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(label, color = if(active) activeColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
    }
}

// ==========================================
//            COMPLEX SCREENS
// ==========================================

// --- TERMINAL SLASH COMMANDS ---
// A real TUI carries context, so the bottom prompt understands a small set
// of slash-prefixed modifiers. Stack any number of them before a phrase
// ("/q /s help is on the way") and they compose; /help, /cls, /backup, and
// /repair are local-only actions that never carry a phrase and
// short-circuit everything else.
private data class TerminalFlags(
    val quiet: Boolean = false,
    val skipLog: Boolean = false,
    val sticky: Boolean = false,
    val emergency: Boolean = false
)

private sealed class TerminalPromptResult {
    data class Dispatch(val flags: TerminalFlags, val phrase: String) : TerminalPromptResult()
    object HelpShown : TerminalPromptResult()
    object Error : TerminalPromptResult()
    // These three need things only the composable has (the log list, the
    // export file picker launcher) so parsing just identifies the intent
    // and logs its own confirmation prompt -- submitPrompt() in
    // TerminalView does the actual work.
    object ClearLog : TerminalPromptResult()
    object RunBackup : TerminalPromptResult()
    object RunRepair : TerminalPromptResult()
    // Needs the composable's own reveal coroutine (line-by-line, shake to
    // stop) -- same "parsing just identifies the intent" split as the
    // three above.
    object ShowInfo : TerminalPromptResult()
}

private val TERMINAL_HELP_LINES = listOf(
    "SLASH COMMANDS:",
    "/help, /?        SHOW THIS LIST",
    "/q, /quiet       SEND WITHOUT AUDIO",
    "/n, /nosave      SEND WITHOUT LOGGING",
    "/s, /sticky      SEND, HOLD TO CLEAR",
    "/e, /emergency   SEND WITH EMERGENCY OVERRIDES",
    "/v               BROWSE SHARED ROOT VARIABLES",
    "/t               BROWSE TARGET COMPUTER ENTRIES",
    "/cls             CLEAR THE LOG (CONFIRM REQUIRED)",
    "/b, /backup      EXPORT ACK DATA (CONFIRM REQUIRED)",
    "/repair          RESTART BACKGROUND SERVICES",
    "/info            SHOW PATCH NOTES"
)

// --- PATCH NOTES (/info) ---
// One entry here = one line revealed every ~2s by TerminalView's reveal
// loop, not a paragraph to be pre-wrapped -- long lines still wrap fine
// inside a CMD block, but keeping each entry to a single idea is what
// makes the line-by-line pacing actually read as a rundown instead of a
// wall of text arriving one row at a time. No blank-string entries --
// each CMD line renders as its own bordered block (see TerminalView), so
// an empty one shows up as a bare box rather than a clean gap; section
// headers do the separating instead. Update this list (and CHANGELOG.md
// at the repo root, which carries the same notes) with each beta.
private val PATCH_NOTES = listOf(
    "=== ACK v1.0-BETA.4 PATCH NOTES ===",
    "-- VOICE RECORDINGS --",
    "- RECORD A VOICE CLIP FOR ANY QUICK ACTION, QUICK-ACCESS KEY, OR MATRIX ENTRY",
    "- AUTOMATIC NOISE REDUCTION + SILENCE TRIMMING ON EVERY RECORDING",
    "- ADJUSTABLE RECORDING-ONLY PLAYBACK GAIN IN PROTOCOL",
    "- MATRIX RECORDINGS CAN SET THEIR OWN VISUAL PROMPT OVERRIDE",
    "- NOTHING DESTRUCTIVE: REMOVING A RECORDING ALWAYS FALLS BACK TO YOUR",
    "  EXISTING TEMPLATE/VARIABLE SETUP, UNCHANGED",
    "-- MANAGE RECORDINGS --",
    "- REBUILT AS A DRILL-DOWN TREE: DECK > PROFILE > POSE > SLOT",
    "- EACH ENTRY SHOWS ITS OVERLAY TEXT, PLAY TIME, AND FILE SIZE",
    "- RE-RECORD, PLAY, OR DELETE DIRECTLY FROM THE TREE",
    "- NEW: OVERLAY-ON-PLAY TOGGLE NEXT TO CLOSE -- SEE A RECORDING'S TEXT",
    "  ON SCREEN WHILE PREVIEWING IT",
    "-- MATRIX EDITOR --",
    "- DESTRUCTIVE CONTROLS NOW COLLAPSED BY DEFAULT -- LESS SCROLLING",
    "-- TERMINAL --",
    "- NEW: /info SHOWS THESE PATCH NOTES, OR TAP THE STATUSBOX SHORTCUT",
    "- SHAKE TO STOP THE READOUT EARLY",
    "-- FIXES --",
    "- FIXED RECORDING PREVIEW PLAYBACK GOING SILENT ON LOW DEVICE VOLUME",
    "=== END PATCH NOTES ==="
)

// Logs a line straight into the Terminal without dispatching any speech --
// matches the same local ACK_LOG broadcast pattern MatrixCategory already
// uses for its own "CONTEXT FOCUS" line. The CMD types render as a bare
// terminal-response block (see TerminalView) instead of the usual
// [time] TYPE :: msg row -- they're feedback about a command, never a
// played prompt, so they don't earn the same log-line treatment.
private fun logTerminalLocal(context: Context, message: String, type: String = "CMD") {
    context.sendBroadcast(
        Intent("ACK_LOG").apply {
            setPackage(context.packageName)
            putExtra("type", type)
            putExtra("msg", message)
        }
    )
}

// --- VARIABLE PICKER (/v) ---
// Not a submit-time flag like the others -- a live composition aid. As
// soon as a standalone "/v" token appears in the prompt, TerminalView's
// STATUSBOX switches from its TYPING indicator to a tap-driven picker:
// row 1 lists every Shared Root Variable grouping (the three fixed poses
// plus any custom context layers), row 2 shows that grouping's A/B/C
// slots (RootOverrideRepository) once one is tapped -- the same [A-C]
// schema TemplateEngine's {VAR:A} tokens use everywhere else in the app.
// Tapping a slot inserts its *current resolved value*, followed by a
// space, at the "/v" token's own position -- not the {VAR:A} token --
// so what's typed is exactly what gets said, no separate resolution step
// at send time.
private val ROOT_VARIABLE_TAGS = listOf("A", "B", "C")
private val VARIABLE_TRIGGER_REGEX = Regex("""(?<![\w/])/v(?![\w])""", RegexOption.IGNORE_CASE)

// Finds the last standalone occurrence of a one-letter slash trigger (not
// "/verify" matching "/v", not a second slash run into it) and hands back
// its character range so a caller can either flag it as unresolved or
// replace it in place. Shared by /v and /t below.
private fun findTrigger(text: String, regex: Regex): IntRange? =
    regex.findAll(text).lastOrNull()?.range

private fun findVariableTrigger(text: String): IntRange? =
    findTrigger(text, VARIABLE_TRIGGER_REGEX)

// --- TARGET PICKER (/t) ---
// The same live composition aid as /v, aimed at Target Computer entries
// instead of Shared Root Variables. Row 1 lists every Target Computer
// category (ComputerRepository.getCategories -- an unlimited, user-editable
// list, same shape as /v's grouping row). Row 2 browses that category's
// tree: Target Computer entries aren't a flat A/B/C, they're an
// arbitrarily-nested tree of CATEGORY/ENTRY nodes (ComputerNode), so row 2
// tracks a drill-down path instead of fixed slots -- tapping a CATEGORY
// node descends into it, tapping an ENTRY node inserts its label. Same
// insert-then-space-then-close behavior as /v either way.
private val TARGET_TRIGGER_REGEX = Regex("""(?<![\w/])/t(?![\w])""", RegexOption.IGNORE_CASE)

private fun findTargetTrigger(text: String): IntRange? =
    findTrigger(text, TARGET_TRIGGER_REGEX)

// Splits a raw prompt submission into recognized flags plus whatever phrase
// is left. Returns Error/HelpShown/ClearLog/RunBackup/RunRepair (having
// already logged its own output) when there's nothing left to dispatch, so
// the caller only ever has to react to the result.
private fun parseTerminalCommand(context: Context, raw: String): TerminalPromptResult {
    if (findVariableTrigger(raw) != null) {
        logTerminalLocal(context, "RESOLVE /v FIRST -- TAP A VARIABLE OR DELETE IT", "CMD_WARN")
        return TerminalPromptResult.Error
    }

    if (findTargetTrigger(raw) != null) {
        logTerminalLocal(context, "RESOLVE /t FIRST -- TAP A TARGET OR DELETE IT", "CMD_WARN")
        return TerminalPromptResult.Error
    }

    if (!raw.startsWith("/")) {
        return TerminalPromptResult.Dispatch(TerminalFlags(), raw)
    }

    val tokens = raw.split(Regex("\\s+"))
    val first = tokens.first().lowercase()
    val rest = tokens.drop(1).joinToString(" ").trim().lowercase()

    if (first == "/help" || first == "/?") {
        logTerminalLocal(context, TERMINAL_HELP_LINES.joinToString("\n"))
        return TerminalPromptResult.HelpShown
    }

    if (first == "/cls") {
        if (rest == "confirm") {
            return TerminalPromptResult.ClearLog
        }
        logTerminalLocal(
            context,
            "CLEAR ENTIRE LOG? THIS CANNOT BE UNDONE.\nTYPE /cls CONFIRM TO PROCEED.",
            "CMD_WARN"
        )
        return TerminalPromptResult.Error
    }

    if (first == "/b" || first == "/backup") {
        if (rest == "confirm") {
            return TerminalPromptResult.RunBackup
        }
        logTerminalLocal(
            context,
            "EXPORT ACK BACKUP?\nTYPE /backup CONFIRM TO PROCEED."
        )
        return TerminalPromptResult.Error
    }

    if (first == "/repair") {
        return TerminalPromptResult.RunRepair
    }

    if (first == "/info") {
        return TerminalPromptResult.ShowInfo
    }

    var flags = TerminalFlags()
    var index = 0
    while (index < tokens.size && tokens[index].startsWith("/")) {
        when (tokens[index].lowercase()) {
            "/q", "/quiet" -> flags = flags.copy(quiet = true)
            "/n", "/nosave" -> flags = flags.copy(skipLog = true)
            "/s", "/sticky" -> flags = flags.copy(sticky = true)
            "/e", "/emergency" -> flags = flags.copy(emergency = true)
            else -> {
                logTerminalLocal(context, "UNKNOWN COMMAND: ${tokens[index]} -- TRY /help", "CMD_ERR")
                return TerminalPromptResult.Error
            }
        }
        index++
    }

    val phrase = tokens.drop(index).joinToString(" ").trim()
    if (phrase.isEmpty()) {
        logTerminalLocal(context, "NO PHRASE GIVEN", "CMD_WARN")
        return TerminalPromptResult.Error
    }

    return TerminalPromptResult.Dispatch(flags, phrase)
}

// /emergency pulls the deck-level overrides (tone, force speaker, boost
// volume, prevent-timed-clear, require-hold-to-clear) from whichever deck
// is *currently active*, exactly the way EmergencyDeck.kt's own PLAY button
// dispatches -- but only when that active deck is actually an Emergency
// deck. If it isn't, the phrase still goes out (never silently drop a
// communication attempt), just without the overrides, and a warning says so.
private fun dispatchTerminalPhrase(context: Context, phrase: String, flags: TerminalFlags) {
    val intent = Intent(context, OutputService::class.java).apply {
        putExtra("phrase", phrase)
        putExtra("robotic", false)
        putExtra("source", OutputService.SOURCE_TERMINAL_PROMPT)
        putExtra("quiet", flags.quiet)
        putExtra("skip_log", flags.skipLog)
        putExtra("sticky", flags.sticky)
    }

    if (flags.emergency) {
        if (CommandRepository.getDeckType(context) == DeckType.EMERGENCY) {
            val config = CommandRepository.getEmergencyConfig(context)
            intent.putExtra("emergency_mode", true)
            intent.putExtra("emergency_force_speaker", config.forceSpeaker)
            intent.putExtra("emergency_boost_volume", config.boostVolume)
            intent.putExtra("emergency_tone", config.tone.name)
            intent.putExtra("emergency_prevent_timed_clear", config.preventTimedClear)
            intent.putExtra("emergency_require_hold_to_clear", config.requireHoldToClear)
        } else {
            logTerminalLocal(context, "NO EMERGENCY DECK ACTIVE -- /e SENT PLAIN", "CMD_WARN")
        }
    }

    context.startService(intent)
}

// /repair -- a lightweight, non-destructive "turn it off and on again" for
// ACK's two long-running foreground services. No confirmation needed, hence
// no gate in parseTerminalCommand: unlike /cls this is easily repeatable
// and never loses anything.
private fun restartBackgroundServices(context: Context) {
    listOf(
        Intent(context, OutputService::class.java),
        Intent(context, AccelerometerTapService::class.java)
    ).forEach { intent ->
        context.stopService(intent)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent)
        } else {
            context.startService(intent)
        }
    }
}

// --- TERMINAL VIEW ---
@OptIn(ExperimentalFoundationApi::class, ExperimentalLayoutApi::class)
@Composable
fun TerminalView(logs: androidx.compose.runtime.snapshots.SnapshotStateList<LogEntry>, context: Context) {
    // Visibility filters live in PROTOCOL now (SettingsView) -- read fresh
    // here rather than owned as local toggle state, since this composable
    // is torn down and rebuilt every time the user leaves and returns to
    // the TERMINAL tab, which already picks up whatever was last set there.
    val hideSystemMessages = TerminalLogStore.getHideSystemMessages(context)
    val hidePathTrace = TerminalLogStore.getHidePathTrace(context)

    // Off by default -- keeps the existing look unless explicitly opted
    // into from PROTOCOL. On, the whole terminal window (log rows, the
    // prompt line, command output, the variable picker) switches to a
    // true monospace font so columns actually line up like a real
    // terminal's; the SAVE TO MEMORY BANK dialog is unaffected, same as
    // every other dialog in the app.
    val terminalFontFamily = if (TerminalLogStore.getMonospaceEnabled(context)) {
        FontFamily.Monospace
    } else {
        FontFamily.Default
    }

    // PATH is the verbose per-tag RESOLVE trace (CommandRepository.debugResolvedPhrase);
    // OUT/EMERGENCY are the actual rationalized phrases that went out and stay
    // visible either way. CMD/CMD_WARN/CMD_ERR are direct feedback on a
    // command the user just typed right here -- hiding those would make the
    // prompt feel like it swallowed the input, so they always show too.
    // Everything else (SYS, GEO, ERR, WARN, INPUT, DATA...) is general
    // system/status noise, gated by the other toggle. With both toggles on,
    // only OUT/EMERGENCY lines remain.
    val visibleLogs = logs.filter { log ->
        when (log.type) {
            "PATH" -> !hidePathTrace
            "OUT", "EMERGENCY", "CMD", "CMD_WARN", "CMD_ERR" -> true
            else -> !hideSystemMessages
        }
    }

    // Long-pressing a replayable line offers to save it into Manual Input's
    // Memory Banks (CommandRepository's QuickPhrase store) under one of the
    // user's existing tags or a new one -- same "ENCODE TO BANK" flow TYPE
    // already uses. saveRefreshKey forces savedPhrases to re-read after a
    // save so the checkmark below PLAY appears immediately.
    var saveDialogTarget by remember { mutableStateOf<LogEntry?>(null) }
    var newTagInput by remember { mutableStateOf("") }
    var saveRefreshKey by remember { mutableIntStateOf(0) }

    val savedPhrases = remember(saveRefreshKey) { CommandRepository.getQuickPhrases(context) }
    val savedPhraseTexts = remember(savedPhrases) { savedPhrases.map { it.text }.toSet() }

    // --- BOTTOM PROMPT: a raw command line, not another flyout ---
    // No target browser, no memory banks, no quick-access row -- just a
    // keyboard and a phrase. Tapping the field is the only affordance;
    // typing and hitting Send/the glyph transmits it exactly like Manual
    // Override does, and focus is reclaimed afterward so the prompt stays
    // ready for the next line without having to tap back in.
    var promptValue by remember { mutableStateOf(TextFieldValue("")) }
    val promptFocusRequester = remember { FocusRequester() }
    val promptHaptic = LocalHapticFeedback.current

    // --- /info (PATCH NOTES) ---
    // Reveals PATCH_NOTES one line every 2s via the same local-log path
    // every other command uses (logTerminalLocal), rather than pushing
    // the whole list in at once like /help does -- both the typed command
    // and the STATUSBOX shortcut button below call this same function, so
    // there's exactly one place that owns the reveal's timing/cancellation.
    val infoRevealScope = rememberCoroutineScope()
    var infoRevealJob by remember { mutableStateOf<Job?>(null) }

    fun startInfoReveal() {
        infoRevealJob?.cancel()
        promptValue = TextFieldValue("")
        infoRevealJob = infoRevealScope.launch {
            for (line in PATCH_NOTES) {
                logTerminalLocal(context, line, "CMD")
                delay(2000)
            }
            infoRevealJob = null
        }
    }

    // Phone-shake kill switch doubles as this reveal's interrupt -- the
    // same broadcast AccelerometerTapService already sends to silence
    // audio/clear the visual overlay, listened for exactly the way
    // SettingsView's shake-test panel already does.
    DisposableEffect(Unit) {
        val shakeReceiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context?, intent: Intent?) {
                infoRevealJob?.cancel()
                infoRevealJob = null
            }
        }
        val filter = IntentFilter(AccelerometerTapService.ACTION_SHAKE_DETECTED)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(shakeReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            context.registerReceiver(shakeReceiver, filter)
        }

        onDispose {
            infoRevealJob?.cancel()
            context.unregisterReceiver(shakeReceiver)
        }
    }

    // /backup confirm reuses PROTOCOL's own export flow exactly --
    // TransferManager.generateBackupJson written to wherever the system
    // document picker points.
    val backupExportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri ->
        if (uri != null) {
            try {
                val jsonStr = TransferManager.generateBackupJson(context)
                context.contentResolver.openOutputStream(uri)?.use { os ->
                    os.write(jsonStr.toByteArray())
                }
                logTerminalLocal(context, "BACKUP EXPORTED")
            } catch (e: Exception) {
                logTerminalLocal(context, "BACKUP EXPORT FAILED: ${e.message}", "CMD_ERR")
            }
        } else {
            logTerminalLocal(context, "BACKUP CANCELLED", "CMD_WARN")
        }
    }

    // --- STATUSBOX state ---
    // A two-row strip that lives above the prompt: a "TYPING" indicator by
    // default, or a live picker (the /v grouping+variable picker, or the
    // /t category+target picker) once one of those triggers is live. It
    // shows whenever the software keyboard is up, and hides the moment the
    // keyboard closes -- the small glyph left of "> " brings it back
    // manually without needing the keyboard open.
    val keyboardVisible = WindowInsets.isImeVisible
    var statusBoxManualVisible by remember { mutableStateOf(false) }
    val showStatusBox = keyboardVisible || statusBoxManualVisible

    LaunchedEffect(keyboardVisible) {
        // The keyboard reopening is itself a fresh reason to show the box --
        // don't let a stale manual toggle suppress it on the next close.
        if (keyboardVisible) statusBoxManualVisible = false
    }

    // Live /v and /t detection -- recomputed on every keystroke since
    // promptValue is already the key, so there's nothing worth memoizing
    // here. It's vanishingly unlikely for both to be live at once (each
    // closes its own picker on insertion), but if they ever are, whichever
    // one appears later in the text -- i.e. whichever was typed most
    // recently -- wins.
    val variableTriggerRange = findVariableTrigger(promptValue.text)
    val targetTriggerRange = findTargetTrigger(promptValue.text)
    val activeTriggerMode = when {
        variableTriggerRange != null && targetTriggerRange != null -> {
            if (targetTriggerRange.first > variableTriggerRange.first) "TARGET" else "VARIABLE"
        }
        variableTriggerRange != null -> "VARIABLE"
        targetTriggerRange != null -> "TARGET"
        else -> null
    }
    val variableTriggerActive = activeTriggerMode == "VARIABLE"
    val targetTriggerActive = activeTriggerMode == "TARGET"

    var selectedVGrouping by remember { mutableStateOf<String?>(null) }
    var vGroupingPage by remember { mutableIntStateOf(0) }
    LaunchedEffect(variableTriggerActive) {
        // The trigger text is gone (typed over, deleted, or just resolved
        // by a tap) -- next time /v appears it should start over at the
        // grouping list, not reopen wherever it was left.
        if (!variableTriggerActive) {
            selectedVGrouping = null
            vGroupingPage = 0
        }
    }

    // /t's picker tracks a category plus a drill-down path (a list of
    // CATEGORY node IDs from that category's root down to the level
    // currently shown in row 3) since Target Computer entries are an
    // arbitrarily-nested tree, not a flat A/B/C. Each row pages
    // independently -- row 1 (categories) and row 3 (whatever level the
    // drill-down is currently on) can each overflow on their own.
    var selectedTCategoryId by remember { mutableStateOf<String?>(null) }
    var tDrillPath by remember { mutableStateOf<List<String>>(emptyList()) }
    var tCategoryPage by remember { mutableIntStateOf(0) }
    var tEntryPage by remember { mutableIntStateOf(0) }
    LaunchedEffect(targetTriggerActive) {
        if (!targetTriggerActive) {
            selectedTCategoryId = null
            tDrillPath = emptyList()
            tCategoryPage = 0
            tEntryPage = 0
        }
    }
    // Changing category or drill depth always lands on a fresh level --
    // row 3's page index from the level you just left doesn't apply here.
    LaunchedEffect(selectedTCategoryId, tDrillPath) {
        tEntryPage = 0
    }

    // Row 1's grouping list: the three fixed poses plus any custom context
    // layers the user has created (CommandRepository), so a layer added
    // after IDENTITY/DEFEND/CONNECT still gets its own Shared Root
    // Variables here, not just those three.
    // Deliberately not remember()'d: /v can stay "active" in the prompt
    // across a trip to another screen (e.g. adding a custom context layer)
    // and back, and this needs to pick up that change the moment the user
    // returns rather than hold onto whatever the list looked like when /v
    // was first typed. Reading SharedPreferences on every keystroke while
    // /v is live is negligible for a handful of groupings.
    val vGroupings = if (variableTriggerActive) {
        POSE_CATEGORIES + CommandRepository.getCustomContextEntries(context).map { it.name }
    } else {
        emptyList()
    }

    val vRootConfig = selectedVGrouping?.let { RootOverrideRepository.getConfig(context, it) }

    // /t's row 1: every Target Computer category (unlimited, user-editable
    // -- same shape as vGroupings above).
    // Same reasoning as vGroupings above -- not remember()'d, so a category
    // created on the Target Computer tab while /t is still live shows up
    // the moment the user comes back, not just on a fresh "/t" retype.
    val tCategories = if (targetTriggerActive) {
        ComputerRepository.getCategories(context)
    } else {
        emptyList()
    }

    val tSelectedCategory = selectedTCategoryId?.let { id -> tCategories.find { it.id == id } }
    // The drill-down nodes on the path, resolved once so both the
    // breadcrumb (row 2) and the current level's children (row 3) read
    // from the same resolved list instead of re-walking the tree twice.
    val tPathNodes = tSelectedCategory?.let { category ->
        tDrillPath.mapNotNull { id -> ComputerRepository.findNode(category, id) }
    } ?: emptyList()

    // Row 2's breadcrumb: the category name, then one segment per drilled
    // level. Every segment but the last is tappable and jumps back to that
    // depth; tapping the category name itself (index 0) returns to the
    // category's own root.
    val tBreadcrumbSegments = tSelectedCategory?.let { category ->
        val labels = listOf(category.label) + tPathNodes.map { it.label }
        labels.mapIndexed { index, label ->
            StatusBoxItem(
                label = label,
                clickable = index != labels.lastIndex,
                onClick = { tDrillPath = tPathNodes.take(index).map { it.id } }
            )
        }
    } ?: emptyList()

    // Row 3's current level: the selected category's root children, or --
    // once drilled down -- whichever CATEGORY node is last on the path.
    val tCurrentChildren = tSelectedCategory?.let { category ->
        val parent = tPathNodes.lastOrNull() ?: category.root
        parent.children
    } ?: emptyList()

    val statusboxTextColor = NeonPalette.getColor(TerminalLogStore.getStatusboxColorIndex(context))

    // Shared by /v and /t: replaces whichever trigger range is still live
    // with the resolved value plus a trailing space, so the cursor lands
    // ready for the next word instead of jammed against it.
    fun insertAtTrigger(trigger: IntRange?, value: String) {
        trigger ?: return
        val insertion = "$value "
        val newText = promptValue.text.replaceRange(trigger, insertion)
        val newCursor = trigger.first + insertion.length
        promptValue = TextFieldValue(newText, TextRange(newCursor))
        promptFocusRequester.requestFocus()
    }

    fun insertVariable(value: String) {
        insertAtTrigger(variableTriggerRange, value)
        selectedVGrouping = null
    }

    fun insertTarget(value: String) {
        insertAtTrigger(targetTriggerRange, value)
        selectedTCategoryId = null
        tDrillPath = emptyList()
    }

    fun submitPrompt() {
        val raw = promptValue.text.trim()
        if (raw.isNotEmpty()) {
            when (val result = parseTerminalCommand(context, raw)) {
                is TerminalPromptResult.Dispatch -> {
                    dispatchTerminalPhrase(context, result.phrase, result.flags)
                    promptValue = TextFieldValue("")
                }
                TerminalPromptResult.HelpShown -> {
                    promptValue = TextFieldValue("")
                }
                TerminalPromptResult.ClearLog -> {
                    TerminalLogStore.clearAll(context, logs)
                    logTerminalLocal(context, "LOG CLEARED")
                    promptValue = TextFieldValue("")
                }
                TerminalPromptResult.RunBackup -> {
                    backupExportLauncher.launch("ack_backup_${System.currentTimeMillis()}.json")
                    promptValue = TextFieldValue("")
                }
                TerminalPromptResult.RunRepair -> {
                    restartBackgroundServices(context)
                    logTerminalLocal(context, "BACKGROUND SERVICES RESTARTED")
                    promptValue = TextFieldValue("")
                }
                TerminalPromptResult.ShowInfo -> {
                    // Clears promptValue itself -- see startInfoReveal.
                    startInfoReveal()
                }
                TerminalPromptResult.Error -> {
                    // Leave the text in place -- a typo'd command or a
                    // flag with no phrase after it shouldn't cost a full
                    // retype, just a fix.
                }
            }
        }
        promptFocusRequester.requestFocus()
    }

    val listState = rememberLazyListState()

    // Sticks the scrollback to the newest line as it arrives -- but only
    // when the user is already sitting at the bottom. Scroll up to review
    // history and new output won't yank you back down.
    LaunchedEffect(visibleLogs.size) {
        if (visibleLogs.isNotEmpty() && listState.firstVisibleItemIndex <= 1) {
            listState.animateScrollToItem(0)
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        // reverseLayout draws the newest line at the bottom and the log
        // grows upward from there, like a real terminal's scrollback --
        // visibleLogs is already newest-first, so index 0 lands at the
        // visual bottom with no re-sorting needed.
        LazyColumn(state = listState, reverseLayout = true, modifier = Modifier.weight(1f)) {
            items(visibleLogs) { log ->
                // CMD/CMD_WARN/CMD_ERR are command feedback, not a played
                // prompt -- no timestamp, no type badge, left-justified
                // against its own background block instead of drawn past
                // the usual columns, closer to what a real shell prints.
                if (log.type == "CMD" || log.type == "CMD_WARN" || log.type == "CMD_ERR") {
                    val cmdColor = when (log.type) {
                        "CMD_ERR" -> RadicalRed
                        "CMD_WARN" -> DataOrange
                        else -> FluxCyan
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp)
                            .background(Graphite)
                            .padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Text(
                            log.msg,
                            color = cmdColor,
                            fontFamily = terminalFontFamily,
                            fontSize = 12.sp,
                            textAlign = TextAlign.Start,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    return@items
                }

                val typeColor = when(log.type) {
                    "ERR" -> RadicalRed
                    "WARN" -> DataOrange
                    "EMERGENCY" -> RadicalRed
                    "SYS" -> BioGreen
                    "OUT" -> FluxCyan
                    "PATH" -> NeonViolet
                    else -> Color.White
                }
                // Only an actual communicated phrase carries replayText (see
                // OutputService.processSpeech) -- status/system log lines never
                // do, so they render plain with no tap/long-press affordance.
                val replayText = log.replayText
                val isSaved = replayText != null && savedPhraseTexts.contains(replayText)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp)
                        .then(
                            if (replayText != null) {
                                Modifier
                                    .background(FluxCyan.copy(alpha = 0.08f))
                                    .combinedClickable(
                                        onClick = {
                                            val intent = Intent(context, OutputService::class.java)
                                            intent.putExtra("phrase", replayText)
                                            intent.putExtra("robotic", false)
                                            intent.putExtra("source", "LOG/REPLAY")
                                            // An emergency message's own boost/tone
                                            // settings aren't in the log, but its
                                            // core safety properties -- audible and
                                            // not auto-clearing -- shouldn't be lost
                                            // just because it's being replayed.
                                            if (log.type == "EMERGENCY") {
                                                intent.putExtra("emergency_mode", true)
                                                intent.putExtra("emergency_force_speaker", true)
                                                intent.putExtra("emergency_prevent_timed_clear", true)
                                            }
                                            context.startService(intent)
                                        },
                                        onLongClick = {
                                            newTagInput = ""
                                            saveDialogTarget = log
                                        }
                                    )
                            } else {
                                Modifier
                            }
                        )
                ) {
                    Column(
                        modifier = Modifier.width(14.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            if (replayText != null) "▶" else " ",
                            color = FluxCyan,
                            fontFamily = terminalFontFamily,
                            fontSize = 12.sp
                        )
                        if (isSaved) {
                            Text(
                                "✓",
                                color = BioGreen,
                                fontFamily = terminalFontFamily,
                                fontSize = 9.sp
                            )
                        }
                    }
                    Text("[${log.time}]", color = Color.DarkGray, fontFamily = terminalFontFamily, fontSize = 12.sp, modifier = Modifier.width(70.dp))
                    Text(log.type, color = typeColor, fontFamily = terminalFontFamily, fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.width(40.dp))
                    Text(" :: ${log.msg}", color = Color.White, fontFamily = terminalFontFamily, fontSize = 12.sp)
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))
        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(FluxCyan.copy(alpha = 0.3f)))
        Spacer(modifier = Modifier.height(6.dp))

        // --- STATUSBOX: POSIX-menu styled, not another set of neon chips.
        // TYPING mode is a compact two-line block; /v and /t expand it to
        // three rows (grouping/category picker, a breadcrumb, the actual
        // entries) via animateContentSize so the height change animates
        // instead of yanking the prompt row beneath it.
        AnimatedVisibility(
            visible = showStatusBox,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(StatusBoxBg, CutCornerShape(4.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp)
                    .animateContentSize()
            ) {
                if (variableTriggerActive) {
                    // Row 1: every Shared Root Variable grouping.
                    StatusBoxItemRow(
                        items = vGroupings.map { grouping ->
                            StatusBoxItem(label = grouping) {
                                promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                selectedVGrouping = grouping
                                vGroupingPage = 0
                            }
                        },
                        highlightedIndex = vGroupings.indexOf(selectedVGrouping).takeIf { it >= 0 },
                        page = vGroupingPage,
                        onPageChange = { vGroupingPage = it },
                        color = statusboxTextColor
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    // Row 2: which grouping you're in -- /v never drills
                    // down, so this is always a single segment (or a dash
                    // until one's tapped).
                    if (selectedVGrouping != null) {
                        StatusBoxBreadcrumb(
                            segments = listOf(StatusBoxItem(label = selectedVGrouping!!, clickable = false)),
                            color = statusboxTextColor
                        )
                    } else {
                        Text(
                            "--",
                            color = statusboxTextColor.copy(alpha = 0.35f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    // Row 3: the selected grouping's A/B/C slots.
                    val config = vRootConfig
                    if (selectedVGrouping != null && config != null) {
                        StatusBoxItemRow(
                            items = ROOT_VARIABLE_TAGS.map { tag ->
                                val slot = config.slots[tag] ?: RootOverrideValue()
                                val hasValue = slot.enabled && slot.value.isNotBlank()
                                StatusBoxItem(
                                    label = "$tag:${if (hasValue) slot.value else "EMPTY"}",
                                    clickable = hasValue,
                                    onClick = {
                                        promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                        insertVariable(slot.value)
                                    }
                                )
                            },
                            highlightedIndex = null,
                            page = 0,
                            onPageChange = {},
                            color = statusboxTextColor
                        )
                    } else {
                        Text(
                            "TAP A ROOT ABOVE TO VIEW ITS VARIABLES",
                            color = statusboxTextColor.copy(alpha = 0.5f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    }
                } else if (targetTriggerActive) {
                    // Row 1: every Target Computer category.
                    if (tCategories.isEmpty()) {
                        Text(
                            "NO TARGET CATEGORIES -- ADD SOME FROM THE TARGET COMPUTER TAB.",
                            color = statusboxTextColor.copy(alpha = 0.5f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    } else {
                        StatusBoxItemRow(
                            items = tCategories.map { category ->
                                StatusBoxItem(label = category.label) {
                                    promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    selectedTCategoryId = category.id
                                    tDrillPath = emptyList()
                                    tCategoryPage = 0
                                }
                            },
                            highlightedIndex = tCategories.indexOfFirst { it.id == selectedTCategoryId }
                                .takeIf { it >= 0 },
                            page = tCategoryPage,
                            onPageChange = { tCategoryPage = it },
                            color = statusboxTextColor
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    // Row 2: the drill-down breadcrumb -- tap any segment
                    // but the last to climb back up to that depth.
                    if (tBreadcrumbSegments.isNotEmpty()) {
                        StatusBoxBreadcrumb(segments = tBreadcrumbSegments, color = statusboxTextColor)
                    } else {
                        Text(
                            "--",
                            color = statusboxTextColor.copy(alpha = 0.35f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    // Row 3: whatever's at the current drill-down level.
                    if (tSelectedCategory == null) {
                        Text(
                            "TAP A CATEGORY ABOVE TO BROWSE IT",
                            color = statusboxTextColor.copy(alpha = 0.5f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    } else if (tCurrentChildren.isEmpty()) {
                        Text(
                            "NOTHING HERE YET.",
                            color = statusboxTextColor.copy(alpha = 0.5f),
                            fontFamily = FontFamily.Monospace,
                            fontSize = STATUSBOX_FONT_SIZE
                        )
                    } else {
                        StatusBoxItemRow(
                            items = tCurrentChildren.map { node ->
                                val isFolder = node.type == ComputerNodeType.CATEGORY
                                StatusBoxItem(label = if (isFolder) "${node.label} ▸" else node.label) {
                                    promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    if (isFolder) {
                                        tDrillPath = tDrillPath + node.id
                                    } else {
                                        insertTarget(node.label)
                                    }
                                }
                            },
                            highlightedIndex = null,
                            page = tEntryPage,
                            onPageChange = { tEntryPage = it },
                            color = statusboxTextColor
                        )
                    }
                } else {
                    // TYPING: a compact two-line block, not the full
                    // three-row picker layout -- there's nothing to browse.
                    // The /INFO shortcut rides on the same row, right-
                    // aligned, reusing StatusBoxItemRow (forced-highlighted,
                    // single item) so it's the exact same reverse-video
                    // POSIX-menu look /t's picker already uses -- a one-tap
                    // shortcut for startInfoReveal(), equivalent to typing
                    // /info and sending it.
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            PulsingStatusBox(color = statusboxTextColor)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                "TYPING",
                                color = statusboxTextColor,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                fontSize = STATUSBOX_FONT_SIZE,
                                letterSpacing = 2.sp
                            )
                        }

                        StatusBoxItemRow(
                            items = listOf(
                                StatusBoxItem(label = "/INFO") {
                                    promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    startInfoReveal()
                                }
                            ),
                            highlightedIndex = 0,
                            page = 0,
                            onPageChange = {},
                            color = statusboxTextColor
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        if (promptValue.text.isNotEmpty()) {
                            "${promptValue.text.length} CHAR${if (promptValue.text.length == 1) "" else "S"}"
                        } else {
                            "AWAITING INPUT"
                        },
                        color = statusboxTextColor.copy(alpha = 0.5f),
                        fontFamily = FontFamily.Monospace,
                        fontSize = STATUSBOX_FONT_SIZE
                    )
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "▣",
                color = if (showStatusBox) statusboxTextColor else Color.DarkGray,
                fontFamily = terminalFontFamily,
                fontSize = 14.sp,
                modifier = Modifier
                    .clickable {
                        promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        statusBoxManualVisible = !statusBoxManualVisible
                    }
                    .padding(6.dp)
            )
            Text(
                "> ",
                color = FluxCyan,
                fontFamily = terminalFontFamily,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp
            )
            Box(modifier = Modifier.weight(1f)) {
                if (promptValue.text.isEmpty()) {
                    Text(
                        "TYPE A COMMAND...",
                        color = Color.DarkGray,
                        fontFamily = terminalFontFamily,
                        fontSize = 14.sp
                    )
                }
                BasicTextField(
                    value = promptValue,
                    onValueChange = { promptValue = it },
                    modifier = Modifier.fillMaxWidth().focusRequester(promptFocusRequester),
                    textStyle = androidx.compose.ui.text.TextStyle(
                        color = FluxCyan,
                        fontFamily = terminalFontFamily,
                        fontSize = 14.sp
                    ),
                    singleLine = true,
                    cursorBrush = SolidColor(FluxCyan),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { submitPrompt() })
                )
            }
            Text(
                "▶",
                color = if (promptValue.text.isNotBlank()) FluxCyan else Color.DarkGray,
                fontFamily = terminalFontFamily,
                fontSize = 16.sp,
                modifier = Modifier
                    .padding(start = 10.dp)
                    .clickable {
                        promptHaptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        submitPrompt()
                    }
                    .padding(6.dp)
            )
        }
    }

    val savingEntry = saveDialogTarget
    val textToSave = savingEntry?.replayText
    if (savingEntry != null && textToSave != null) {
        val existingTags = savedPhrases.map { it.tag }.distinct().sorted()
        val alreadySavedTags = savedPhrases.filter { it.text == textToSave }.map { it.tag }

        TightDialogSurface(
            onDismiss = { saveDialogTarget = null; newTagInput = "" },
            primaryColor = FluxCyan,
            title = "SAVE TO MEMORY BANK"
        ) {
            Text(
                "\"$textToSave\"",
                color = Color.White,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp
            )

            if (alreadySavedTags.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "ALREADY SAVED: ${alreadySavedTags.joinToString(", ")}",
                    color = BioGreen,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            TightSectionLabel("ASSIGN A TAG")
            Spacer(modifier = Modifier.height(12.dp))

            if (existingTags.isNotEmpty()) {
                Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                    existingTags.forEach { tag ->
                        Box(
                            modifier = Modifier
                                .padding(end = 8.dp)
                                .heightIn(min = 44.dp)
                                .border(1.dp, if (newTagInput == tag) FluxCyan else Color.Gray, AckHelpShape)
                                .clickable { newTagInput = tag }
                                .padding(horizontal = 8.dp, vertical = 4.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(tag, color = if (newTagInput == tag) FluxCyan else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
                Spacer(modifier = Modifier.height(12.dp))
            }

            OutlinedTextField(
                value = newTagInput,
                onValueChange = { newTagInput = it.uppercase() },
                placeholder = { Text("NEW TAG") },
                shape = AckHelpShape,
                colors = TextFieldDefaults.colors(focusedTextColor = FluxCyan, unfocusedTextColor = FluxCyan, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = FluxCyan)
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                TightPanelButton("SAVE", modifier = Modifier.weight(1f), mainColor = FluxCyan) {
                    if (newTagInput.isNotEmpty()) {
                        CommandRepository.saveQuickPhrase(context, textToSave, newTagInput)
                        saveRefreshKey++
                        saveDialogTarget = null
                        newTagInput = ""
                    }
                }
                TightPanelButton("CANCEL", modifier = Modifier.weight(1f), isActive = false, mainColor = FluxCyan) {
                    saveDialogTarget = null
                    newTagInput = ""
                }
            }
        }
    }
}

// --- TYPE VIEW ---
@Composable
fun TypeView(
    context: Context,
    recentPhrases: androidx.compose.runtime.snapshots.SnapshotStateList<String>,
    textFieldValue: TextFieldValue,
    onTextFieldValueChange: (TextFieldValue) -> Unit,
    textFieldFocusRequester: FocusRequester,
    onInsertAtCursor: (String) -> Unit
) {
    val primaryColor = NeonPalette.getColor(CommandRepository.getActiveColorIndex(context))

    var refreshKey by remember { mutableIntStateOf(0) }
    var savedPhrases by remember(refreshKey) { mutableStateOf(CommandRepository.getQuickPhrases(context)) }
    var showSaveDialog by remember { mutableStateOf(false) }
    var showMemoryBanks by remember { mutableStateOf(false) }
    var showBrowsePanel by remember { mutableStateOf(false) }
    var newTagInput by remember { mutableStateOf("") }

    val helpManager = LocalHelpManager.current
    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    fun speak(text: String, sourceTag: String) {
        if (text.isNotBlank()) {
            val intent = Intent(context, OutputService::class.java)
            intent.putExtra("phrase", text)
            intent.putExtra("robotic", false)
            intent.putExtra("source", sourceTag)
            context.startService(intent)

            if (recentPhrases.contains(text)) recentPhrases.remove(text)
            recentPhrases.add(0, text)
            if (recentPhrases.size > 10) recentPhrases.removeLast()
            onTextFieldValueChange(TextFieldValue(""))
            // TRANSMIT is a button tap like any other -- it can pull focus
            // away from the field the same way a chip tap can. Reclaim it
            // so the field is immediately ready for the next phrase.
            textFieldFocusRequester.requestFocus()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("MANUAL OVERRIDE", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
        Spacer(modifier = Modifier.height(12.dp))

        OutlinedTextField(
            value = textFieldValue,
            onValueChange = onTextFieldValueChange,
            modifier = Modifier
                .fillMaxWidth()
                .focusRequester(textFieldFocusRequester),
            shape = AckHelpShape,
            colors = TextFieldDefaults.colors(
                focusedTextColor = primaryColor,
                unfocusedTextColor = primaryColor,
                focusedContainerColor = VoidBlack,
                unfocusedContainerColor = VoidBlack,
                focusedIndicatorColor = primaryColor,
                unfocusedIndicatorColor = Color.DarkGray,
                cursorColor = primaryColor
            ),
            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 16.sp),
            placeholder = { Text("ENTER SEQUENCE...", color = Color.Gray, fontFamily = FontFamily.Monospace) },
            maxLines = 3
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            // Encode button relies on isActive for dimming, but logic check inside lambda protects it
            NeonButton("ENCODE", Modifier.weight(0.4f), isActive = textFieldValue.text.isNotBlank(), mainColor = primaryColor) {
                if (textFieldValue.text.isNotBlank()) showSaveDialog = true
            }
            HeroButton("TRANSMIT", Modifier.weight(0.6f), mainColor = primaryColor) {
                speak(textFieldValue.text, "TERM/INPUT")
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // --- TARGET COMPUTER: QUICK ACCESS + FULL BROWSER ---
        TargetQuickAccessRow(
            context = context,
            primaryColor = primaryColor,
            onInsert = onInsertAtCursor
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(
                text = if (showBrowsePanel) "[HIDE TARGET BROWSER]" else "[BROWSE TARGETS]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.MANUAL_TARGET_BROWSE_TOGGLE)
                    .helpTarget(AckTags.MANUAL_TARGET_BROWSE_TOGGLE, primaryColor)
                    .clickable {
                        showBrowsePanel = !showBrowsePanel
                        reportHelpInteraction(AckTags.MANUAL_TARGET_BROWSE_TOGGLE)
                    }
            )

            Text(
                text = if (savedPhrases.isNotEmpty()) "[MEMORY BANKS (${savedPhrases.size})]" else "[MEMORY BANKS]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.MANUAL_MEMORY_BANKS_BTN)
                    .helpTarget(AckTags.MANUAL_MEMORY_BANKS_BTN, primaryColor)
                    .clickable {
                        showMemoryBanks = true
                        reportHelpInteraction(AckTags.MANUAL_MEMORY_BANKS_BTN)
                    }
            )
        }

        if (showBrowsePanel) {
            Spacer(modifier = Modifier.height(8.dp))
            TargetBrowsePanel(
                context = context,
                primaryColor = primaryColor,
                onInsert = onInsertAtCursor
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        // Decoupled from Memory Banks' presence now that Memory Banks lives
        // behind its own popup -- previously a single saved phrase would
        // permanently hide recents from this screen.
        if (recentPhrases.isNotEmpty()) {
            Text("CACHE [RECENT]", color = primaryColor.copy(alpha=0.7f), fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
            Spacer(modifier = Modifier.height(8.dp))
            // Bounded height, not weight(1f) -- the outer Column now scrolls
            // (see below), and weight() only makes sense against a parent
            // with a fixed height to distribute.
            LazyColumn(modifier = Modifier.heightIn(max = 320.dp)) {
                items(recentPhrases) { phrase ->
                    RecentHistoryItem(phrase) { speak(phrase, "CACHE/REPLAY") }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))
    }

    if (showMemoryBanks) {
        TightDialogSurface(
            onDismiss = { showMemoryBanks = false },
            primaryColor = primaryColor,
            title = "MEMORY BANKS",
            dismissLabel = "CLOSE"
        ) {
            if (savedPhrases.isEmpty()) {
                Text(
                    text = "NO SAVED PHRASES YET. ENCODE ONE FROM THE TEXT FIELD ABOVE.",
                    color = Color.DarkGray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            } else {
                QuickAccessAccordion(
                    phrases = savedPhrases,
                    primaryColor = primaryColor,
                    modifier = Modifier.heightIn(max = 420.dp),
                    onPlay = { p -> speak(p.text, "BANK/${p.tag}") },
                    onDelete = { p -> CommandRepository.deleteQuickPhrase(context, p); refreshKey++ }
                )
            }
        }
    }

    if (showSaveDialog) {
        val existingTags = savedPhrases.map { it.tag }.distinct().sorted()
        TightDialogSurface(
            onDismiss = { showSaveDialog = false },
            primaryColor = primaryColor,
            title = "ENCODE TO BANK"
        ) {
                TightSectionLabel("ASSIGN A TAG")
                Spacer(modifier = Modifier.height(12.dp))
                if (existingTags.isNotEmpty()) {
                    Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                        existingTags.forEach { tag ->
                            Box(modifier = Modifier.padding(end = 8.dp).heightIn(min = 44.dp).border(1.dp, if(newTagInput == tag) primaryColor else Color.Gray, AckHelpShape).clickable { newTagInput = tag }.padding(horizontal = 8.dp, vertical = 4.dp), contentAlignment = Alignment.Center) {
                                Text(tag, color = if(newTagInput == tag) primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                }
                OutlinedTextField(
                    value = newTagInput, onValueChange = { newTagInput = it.uppercase() },
                    placeholder = { Text("NEW TAG") },
                    shape = AckHelpShape,
                    colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor)
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton("SAVE", modifier = Modifier.weight(1f), mainColor = primaryColor) {
                        if (newTagInput.isNotEmpty()) {
                            CommandRepository.saveQuickPhrase(context, textFieldValue.text, newTagInput)
                            refreshKey++
                            showSaveDialog = false
                            newTagInput = ""
                        }
                    }
                    TightPanelButton("CANCEL", modifier = Modifier.weight(1f), isActive = false, mainColor = primaryColor) { showSaveDialog = false }
                }
        }
    }
}

// --- HELPER COMPONENTS FOR TYPE VIEW ---

@Composable
fun QuickAccessAccordion(
    phrases: List<QuickPhrase>,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onPlay: (QuickPhrase) -> Unit,
    onDelete: (QuickPhrase) -> Unit
) {
    val grouped = remember(phrases) { phrases.groupBy { it.tag } }
    val expandedStates = remember { mutableStateMapOf<String, Boolean>().apply { if(grouped.isNotEmpty()) this[grouped.keys.first()] = true } }
    var deletingPhrase by remember { mutableStateOf<QuickPhrase?>(null) }

    LazyColumn(modifier = modifier) {
        grouped.forEach { (tag, items) ->
            item {
                val isExpanded = expandedStates[tag] == true
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).background(if(isExpanded) primaryColor.copy(alpha=0.1f) else Graphite).border(1.dp, if(isExpanded) primaryColor else Color.Gray, CutCornerShape(4.dp)).clickable { expandedStates[tag] = !isExpanded }.padding(8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("[$tag]", color = if(isExpanded) primaryColor else Color.Gray, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, letterSpacing = 1.sp)
                    Text(if(isExpanded) "▼" else "▶", color = if(isExpanded) primaryColor else Color.Gray, fontSize = 10.sp)
                }
            }
            if (expandedStates[tag] == true) {
                items(items) { phrase ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(start = 12.dp, bottom = 4.dp).background(VoidBlack).border(BorderStroke(1.dp, primaryColor.copy(alpha=0.3f))).clickable { onPlay(phrase) }.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = phrase.text, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.weight(1f))
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier.size(44.dp).clickable { deletingPhrase = phrase },
                            contentAlignment = Alignment.Center
                        ) {
                            Text("X", color = Color.Red, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                item { Spacer(modifier = Modifier.height(8.dp)) }
            }
        }
    }

    val deleting = deletingPhrase

    if (deleting != null) {
        TightDialogSurface(
            onDismiss = { deletingPhrase = null },
            primaryColor = RadicalRed,
            title = "CONFIRM DELETE",
            dismissLabel = "ABORT"
        ) {
            Text(
                text = "Permanently remove the saved phrase " +
                        "\"${deleting.text}\"? This cannot be undone -- " +
                        "consider exporting a backup first.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton(
                    text = "DELETE PERMANENTLY",
                    modifier = Modifier.fillMaxWidth(),
                    mainColor = RadicalRed
                ) {
                    onDelete(deleting)
                    deletingPhrase = null
                }

                TightPanelButton(
                    text = "CANCEL",
                    modifier = Modifier.fillMaxWidth(),
                    isActive = false,
                    mainColor = primaryColor
                ) {
                    deletingPhrase = null
                }
            }
        }
    }
}

@Composable
fun RecentHistoryItem(phrase: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).background(Graphite, CutCornerShape(4.dp)).border(1.dp, Color.Gray.copy(alpha=0.3f), CutCornerShape(4.dp)).clickable { onClick() }.padding(12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = if (phrase.length > 25) phrase.take(22) + "..." else phrase, color = Color.Gray, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
        Text("REPLAY", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
    }
}

// --- MATRIX EDITOR ---
@Composable
fun MatrixEditor(context: Context, deckName: String, onDialogStateChange: (Boolean) -> Unit) {
    val primaryColor = NeonPalette.getColor(CommandRepository.getActiveColorIndex(context))

    var refreshKey by remember { mutableIntStateOf(0) }
    var matrixData by remember(deckName, refreshKey) { mutableStateOf(CommandRepository.getMatrix(context)) }
    var showDialog by remember { mutableStateOf(false) }
    var showManageContextDialog by remember { mutableStateOf(false) }
    var selectedNode by remember { mutableStateOf<Triple<MatrixNode, String, String>?>(null) }
    var variableEditRequest by remember {
        mutableStateOf<VariableEditRequest?>(null)
    }

    val grouped = matrixData.groupBy { it.first.category }

    LaunchedEffect(showDialog) { onDialogStateChange(showDialog) }

    Column {
        LazyColumn(modifier = Modifier.weight(1f).padding(16.dp)) {
            item {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text("SEQUENCE :: $deckName", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                    Text(
                        "[MANAGE CONTEXT]",
                        color = primaryColor,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .testTag(AckTags.MATRIX_CONTEXT_ADD)
                            .helpTarget(AckTags.MATRIX_CONTEXT_ADD, primaryColor)
                            .clickable { showManageContextDialog = true }
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
            }
            grouped.forEach { (category, nodes) ->
                item {
                    if (deckName == "BUILDER") { BuilderGuideCard(category, primaryColor); Spacer(modifier = Modifier.height(12.dp)) }
                    MatrixCategory(
                        title = category,
                        nodes = nodes,
                        context = context,
                        primaryColor = primaryColor,
                        onEdit = { nodeTriple ->
                            selectedNode = nodeTriple
                            showDialog = true
                        },
                        onEditVariable = { request ->
                            variableEditRequest = request
                        },
                        onRootOverrideChanged = {
                            refreshKey++
                        }
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                }
            }
        }
    }

    if (showDialog && selectedNode != null) {
        val (node, rawPhrase, _) = selectedNode!!

        var tempText by remember(node.path) {
            mutableStateOf(rawPhrase)
        }

        val tempVars = remember(node.path) {
            mutableStateListOf<String>().apply {
                val initialCount = TemplateEngine.countVariables(rawPhrase)
                val savedValues = CommandRepository.getVariableValues(
                    context,
                    node.path
                )

                repeat(initialCount) { index ->
                    add(savedValues.getOrElse(index) { "" })
                }
            }
        }

        val tempComputerFallbacks = remember(node.path) {
            mutableStateListOf<String>().apply {
                val initialCount = TemplateEngine.countComputerTags(rawPhrase)
                val savedValues = CommandRepository.getComputerFallbackValues(
                    context,
                    node.path
                )

                repeat(initialCount) { index ->
                    add(savedValues.getOrElse(index) { "" })
                }
            }
        }

        val computerCategories = remember(refreshKey) { ComputerRepository.getCategories(context) }

        var clearMode by remember(node.path) {
            mutableStateOf<String?>(null)
        }

        // Collapsed by default -- these buttons are rarely used but used to
        // always push the COMMIT/CLOSE row further down the scroll,
        // especially once a recording panel is also showing above.
        var destructiveControlsExpanded by remember(node.path) { mutableStateOf(false) }

        val activeDeckId = CommandRepository.getActiveDeckId(context)
        val activeProfile = CommandRepository.getActiveProfile(context)

        var matrixRecording by remember(node.path) {
            mutableStateOf(
                VoiceRecordingRepository.getForMatrixNode(context, activeDeckId, activeProfile, node.path)
            )
        }

        // One-shot notice shown right after a template edit auto-disables
        // an enabled recording -- see updateTemplate below.
        var showStaleWarning by remember(node.path) { mutableStateOf(false) }

        // Recording a variable-containing prompt suppresses its variables
        // entirely while active, so opening the recording panel for such a
        // node is gated behind an explicit, one-time acknowledgment of
        // that tradeoff (recordingPanelUnlocked). Both reset whenever this
        // dialog is reopened for the node (remember(node.path)), so
        // attaching a fresh recording later always re-confirms.
        var showAttachRecordingWarning by remember(node.path) { mutableStateOf(false) }
        var recordingPanelUnlocked by remember(node.path) { mutableStateOf(false) }

        // What shows on screen while an enabled recording plays, in place
        // of the raw template text (which can carry literal {VAR}/
        // [COMPUTER:X] tokens once resolution is skipped for a recorded
        // node -- see the dispatch sites in MatrixCategory and
        // WearListenerService). Backed by CommandRepository's existing
        // per-node visual override storage (already deck+profile+path
        // scoped and already swept into backups) -- this never touches
        // the template/variable configuration itself, so clearing it (or
        // just removing the recording) falls straight back to today's
        // normal resolved display.
        var visualOverrideText by remember(node.path) {
            mutableStateOf(CommandRepository.getVisualOverride(context, node.path))
        }

        fun closeEditor() {
            // Reload matrix rows from persistent storage so subsequent edits start
            // from the saved prompt rather than the old cached rawPhrase.
            refreshKey++
            showDialog = false
        }



        val variableCount = TemplateEngine.countVariables(tempText)
        val computerTagCount = TemplateEngine.countComputerTags(tempText)

        fun saveVariables() {
            CommandRepository.setVariableValues(
                context = context,
                storagePath = node.path,
                values = tempVars.toList()
            )
        }

        fun saveComputerFallbacks() {
            CommandRepository.setComputerFallbackValues(
                context = context,
                storagePath = node.path,
                values = tempComputerFallbacks.toList()
            )
        }

        fun normalizeVariableSlots(newCount: Int) {
            while (tempVars.size > newCount) {
                tempVars.removeAt(tempVars.lastIndex)
            }

            while (tempVars.size < newCount) {
                tempVars.add("")
            }
        }

        fun normalizeComputerFallbackSlots(newCount: Int) {
            while (tempComputerFallbacks.size > newCount) {
                tempComputerFallbacks.removeAt(tempComputerFallbacks.lastIndex)
            }

            while (tempComputerFallbacks.size < newCount) {
                tempComputerFallbacks.add("")
            }
        }

        fun updateTemplate(newTemplate: String) {
            tempText = newTemplate

            val newVariableCount = TemplateEngine.countVariables(newTemplate)
            val newComputerTagCount = TemplateEngine.countComputerTags(newTemplate)

            // When a token is removed, its local value is removed too.
            // If a token is added later, it receives a fresh blank field.
            normalizeVariableSlots(newVariableCount)
            normalizeComputerFallbackSlots(newComputerTagCount)

            CommandRepository.setPhrase(
                context = context,
                storagePath = node.path,
                phrase = newTemplate
            )

            saveVariables()
            saveComputerFallbacks()

            // The template is live-saved on every keystroke, so this is
            // the only point that can catch "the text changed underneath
            // an enabled recording" -- disable (never delete) and flag the
            // one-shot notice. Guarded on currentRecording.enabled so this
            // only fires once per edit, not on every subsequent keystroke.
            val currentRecording = matrixRecording
            if (currentRecording != null && currentRecording.enabled &&
                newTemplate != currentRecording.boundPhraseSnapshot
            ) {
                VoiceRecordingRepository.setMatrixRecordingEnabled(
                    context = context,
                    id = currentRecording.id,
                    enabled = false
                )
                matrixRecording = currentRecording.copy(enabled = false)
                showStaleWarning = true
            }
        }

        fun commitEditor() {
            /*
             * updateTemplate already persists the template and normalizes/saves
             * associated variable slots. Calling it here makes COMMIT an immediate,
             * explicit final write even though typing is also live-saved.
             */
            updateTemplate(tempText)
            refreshKey++
            showDialog = false
        }

        val helpManager = LocalHelpManager.current
        val density = LocalDensity.current
        val imeBottom = WindowInsets.ime.getBottom(density)

        var macroFieldFocused by remember(node.path) {
            mutableStateOf(false)
        }

        var macroKeyboardOpened by remember(node.path) {
            mutableStateOf(false)
        }

        LaunchedEffect(
            macroFieldFocused,
            macroKeyboardOpened,
            imeBottom
        ) {
            if (macroFieldFocused && imeBottom > 0) {
                macroKeyboardOpened = true
            }

            if (
                macroFieldFocused &&
                macroKeyboardOpened &&
                imeBottom == 0
            ) {
                helpManager?.onEvent(
                    HelpEvent.KeyboardWasDismissed(
                        AckTags.MACRO_TEMPLATE_INPUT
                    )
                )

                macroFieldFocused = false
                macroKeyboardOpened = false
            }
        }

        TightDialogSurface(
            onDismiss = {
                closeEditor()
            },
            primaryColor = primaryColor,
            title = node.label,
            subtitle = "LIVE-SAVE EDITOR",
            surfaceModifier = Modifier.testTag(AckTags.EDIT_NODE_DIALOG)
        ) {
                Column {
                    TightSectionLabel("MACRO TEMPLATE")

                    Spacer(modifier = Modifier.height(6.dp))

                    OutlinedTextField(
                        value = tempText,
                        onValueChange = { newText ->
                            updateTemplate(newText)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(AckTags.MACRO_TEMPLATE_INPUT)
                            .helpTarget(AckTags.MACRO_TEMPLATE_INPUT, primaryColor)
                            .onFocusChanged { state ->
                                if (state.isFocused) {
                                    macroFieldFocused = true
                                }
                            },
                        shape = AckHelpShape,
                        minLines = 3,
                        maxLines = 4,
                        placeholder = {
                            Text(
                                text = "ENTER OUTPUT PHRASE...",
                                color = Color.DarkGray,
                                fontFamily = FontFamily.Monospace
                            )
                        },
                        textStyle = androidx.compose.ui.text.TextStyle(
                            color = primaryColor,
                            fontFamily = FontFamily.Monospace
                        ),
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = VoidBlack,
                            unfocusedContainerColor = VoidBlack,
                            focusedIndicatorColor = primaryColor,
                            unfocusedIndicatorColor = Color.DarkGray,
                            focusedTextColor = primaryColor,
                            unfocusedTextColor = primaryColor,
                            cursorColor = primaryColor
                        )
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    val recordingIsActive = matrixRecording?.enabled == true

                    if (!recordingIsActive) {
                        TightSectionLabel("INSERT VARIABLE TOKEN")

                        Spacer(modifier = Modifier.height(6.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            TightPanelButton(
                                text = "+ VAR",
                                modifier = Modifier.weight(1f),
                                mainColor = primaryColor
                            ) {
                                updateTemplate("$tempText {VAR}")
                            }

                            TightPanelButton(
                                text = "+ A",
                                modifier = Modifier.weight(1f),
                                mainColor = primaryColor
                            ) {
                                updateTemplate("$tempText {VAR:A}")
                            }

                            TightPanelButton(
                                text = "+ B",
                                modifier = Modifier.weight(1f),
                                mainColor = primaryColor
                            ) {
                                updateTemplate("$tempText {VAR:B}")
                            }

                            TightPanelButton(
                                text = "+ C",
                                modifier = Modifier.weight(1f),
                                mainColor = primaryColor
                            ) {
                                updateTemplate("$tempText {VAR:C}")
                            }
                        }

                        if (computerCategories.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(14.dp))

                            TightSectionLabel("INSERT TARGET TAG")

                            Spacer(modifier = Modifier.height(6.dp))

                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(AckTags.MATRIX_INSERT_COMPUTER_TAG)
                                    .helpTarget(AckTags.MATRIX_INSERT_COMPUTER_TAG, primaryColor)
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                computerCategories.forEach { computerCategory ->
                                    TightPanelButton(
                                        text = "+ ${computerCategory.label}",
                                        mainColor = primaryColor
                                    ) {
                                        updateTemplate("$tempText [COMPUTER:${computerCategory.id}]")
                                        helpManager?.onEvent(
                                            HelpEvent.Interacted(AckTags.MATRIX_INSERT_COMPUTER_TAG)
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    val hasDynamicTokens = variableCount > 0 || computerTagCount > 0

                    if (recordingIsActive || !hasDynamicTokens || recordingPanelUnlocked) {
                        VoiceRecordingPanel(
                            context = context,
                            primaryColor = primaryColor,
                            panelKey = "mtx_${activeDeckId}_${activeProfile}_${node.path}",
                            existingRecording = matrixRecording,
                            description = if (recordingIsActive) {
                                "RECORDED PROMPT -- VARIABLES BELOW ARE HIDDEN AND INACTIVE WHILE THIS PLAYS. THEIR VALUES ARE KEPT. REMOVE THIS RECORDING TO GET THEM BACK."
                            } else {
                                "WHEN SET, THIS PLAYS INSTEAD OF THE TEMPLATE ABOVE."
                            },
                            onAccept = { pcm, sampleRate ->
                                val saved = VoiceRecordingRepository.saveForMatrixNode(
                                    context = context,
                                    deckId = activeDeckId,
                                    profile = activeProfile,
                                    path = node.path,
                                    pcm = pcm,
                                    sampleRate = sampleRate,
                                    phraseSnapshot = tempText
                                )
                                matrixRecording = saved
                            },
                            onRemove = {
                                VoiceRecordingRepository.deleteForMatrixNode(context, activeDeckId, activeProfile, node.path)
                                matrixRecording = null
                            }
                        )
                    } else {
                        // Locked behind an explicit, one-time acknowledgment
                        // that recording this entry disables its variables
                        // while active -- see showAttachRecordingWarning.
                        Text(
                            text = "VOICE RECORDING",
                            color = primaryColor,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 2.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "This entry has $variableCount variable(s) and $computerTagCount target tag(s). " +
                                "Recording a voice prompt disables them while active.",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        TightPanelButton(
                            text = "ATTACH VOICE RECORDING",
                            modifier = Modifier.fillMaxWidth(),
                            mainColor = primaryColor
                        ) {
                            showAttachRecordingWarning = true
                        }
                    }

                    if (recordingIsActive) {
                        Spacer(modifier = Modifier.height(14.dp))

                        TightSectionLabel("VISUAL PROMPT OVERRIDE", color = primaryColor)

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = "WHAT SHOWS ON SCREEN WHILE THIS RECORDING PLAYS. LEAVE BLANK " +
                                "TO SHOW THE RAW TEMPLATE TEXT ABOVE AS-IS (VARIABLE TOKENS " +
                                "INCLUDED, UNRESOLVED). YOUR TEMPLATE AND VARIABLES ARE NEVER " +
                                "CHANGED BY THIS -- IT ONLY REPLACES WHAT'S DISPLAYED.",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )

                        Spacer(modifier = Modifier.height(6.dp))

                        OutlinedTextField(
                            value = visualOverrideText,
                            onValueChange = { newValue ->
                                visualOverrideText = newValue
                                CommandRepository.setVisualOverride(context, node.path, newValue)
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = AckHelpShape,
                            minLines = 2,
                            maxLines = 3,
                            placeholder = {
                                Text(
                                    text = "e.g. \"Hi Sarah, nice to see you\"",
                                    color = Color.DarkGray,
                                    fontFamily = FontFamily.Monospace
                                )
                            },
                            textStyle = androidx.compose.ui.text.TextStyle(
                                color = primaryColor,
                                fontFamily = FontFamily.Monospace
                            ),
                            colors = TextFieldDefaults.colors(
                                focusedContainerColor = VoidBlack,
                                unfocusedContainerColor = VoidBlack,
                                focusedIndicatorColor = primaryColor,
                                unfocusedIndicatorColor = Color.DarkGray,
                                focusedTextColor = primaryColor,
                                unfocusedTextColor = primaryColor,
                                cursorColor = primaryColor
                            )
                        )
                    }

                    if (matrixRecording?.enabled == false) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "DISABLED -- this entry's text changed since this recording was made. " +
                                "It won't play until you re-enable it above.",
                            color = RadicalRed,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        TightPanelButton(
                            text = "RE-ENABLE (MATCH CURRENT TEXT)",
                            modifier = Modifier.fillMaxWidth(),
                            mainColor = primaryColor
                        ) {
                            val current = matrixRecording ?: return@TightPanelButton
                            VoiceRecordingRepository.setMatrixRecordingEnabled(
                                context = context,
                                id = current.id,
                                enabled = true,
                                newSnapshot = tempText
                            )
                            matrixRecording = current.copy(enabled = true, boundPhraseSnapshot = tempText)
                        }
                    }

                    if (variableCount > 0 && !recordingIsActive) {
                        Spacer(modifier = Modifier.height(14.dp))

                        Text(
                            text = "LOCAL VARIABLE DATA",
                            color = NeonPalette.SWATCHES[3],
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = "Saved immediately. Tagged A/B/C values can be "
                                    + "replaced by enabled root overrides.",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        repeat(variableCount) { index ->
                            val tag = TemplateEngine
                                .getVariableTags(tempText)
                                .getOrNull(index)

                            val label = if (tag == null) {
                                "VARIABLE ${index + 1}"
                            } else {
                                "VARIABLE ${index + 1} // ROOT $tag"
                            }

                            OutlinedTextField(
                                value = tempVars[index],
                                onValueChange = { newValue ->
                                    tempVars[index] = newValue
                                    saveVariables()
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 52.dp),
                                shape = AckHelpShape,
                                singleLine = true,
                                label = {
                                    Text(
                                        text = label,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp
                                    )
                                },
                                placeholder = {
                                    Text(
                                        text = "ENTER LOCAL FALLBACK...",
                                        color = Color.DarkGray,
                                        fontFamily = FontFamily.Monospace
                                    )
                                },
                                textStyle = androidx.compose.ui.text.TextStyle(
                                    color = Color.White,
                                    fontFamily = FontFamily.Monospace
                                ),
                                colors = TextFieldDefaults.colors(
                                    focusedContainerColor = VoidBlack,
                                    unfocusedContainerColor = VoidBlack,
                                    focusedIndicatorColor = NeonPalette.SWATCHES[3],
                                    unfocusedIndicatorColor = Color.DarkGray,
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    cursorColor = NeonPalette.SWATCHES[3]
                                )
                            )

                            if (index < variableCount - 1) {
                                Spacer(modifier = Modifier.height(8.dp))
                            }
                        }
                    }

                    if (computerTagCount > 0 && !recordingIsActive) {
                        Spacer(modifier = Modifier.height(14.dp))

                        Text(
                            text = "TARGET TAG FALLBACKS",
                            color = NeonPalette.SWATCHES[3],
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = "[COMPUTER:X] resolves to whichever entry is " +
                                "currently active for that category in the Target " +
                                "Computer. If nothing is active, the fallback below " +
                                "is used instead.",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        val computerTagsInOrder = TemplateEngine.getComputerTags(tempText)

                        repeat(computerTagCount) { index ->
                            val categoryId = computerTagsInOrder.getOrNull(index)
                            val categoryLabel = computerCategories
                                .find { it.id == categoryId }
                                ?.label
                                ?: categoryId
                                ?: "?"

                            OutlinedTextField(
                                value = tempComputerFallbacks.getOrElse(index) { "" },
                                onValueChange = { newValue ->
                                    tempComputerFallbacks[index] = newValue
                                    saveComputerFallbacks()
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 52.dp),
                                shape = AckHelpShape,
                                singleLine = true,
                                label = {
                                    Text(
                                        text = "TARGET TAG ${index + 1} // $categoryLabel",
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp
                                    )
                                },
                                placeholder = {
                                    Text(
                                        text = "ENTER LOCAL FALLBACK...",
                                        color = Color.DarkGray,
                                        fontFamily = FontFamily.Monospace
                                    )
                                },
                                textStyle = androidx.compose.ui.text.TextStyle(
                                    color = Color.White,
                                    fontFamily = FontFamily.Monospace
                                ),
                                colors = TextFieldDefaults.colors(
                                    focusedContainerColor = VoidBlack,
                                    unfocusedContainerColor = VoidBlack,
                                    focusedIndicatorColor = NeonPalette.SWATCHES[3],
                                    unfocusedIndicatorColor = Color.DarkGray,
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    cursorColor = NeonPalette.SWATCHES[3]
                                )
                            )

                            if (index < computerTagCount - 1) {
                                Spacer(modifier = Modifier.height(8.dp))
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { destructiveControlsExpanded = !destructiveControlsExpanded },
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = if (destructiveControlsExpanded) "▾ " else "▸ ",
                            color = RadicalRed,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace
                        )
                        TightSectionLabel("DESTRUCTIVE CONTROLS", color = RadicalRed)
                    }

                    if (destructiveControlsExpanded) {
                        Spacer(modifier = Modifier.height(6.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            TightPanelButton(
                                text = "CLEAR VARS",
                                modifier = Modifier.weight(1f),
                                isActive = false,
                                mainColor = RadicalRed
                            ) {
                                clearMode = "VARS"
                            }

                            TightPanelButton(
                                text = "CLEAR PROMPT",
                                modifier = Modifier.weight(1f),
                                isActive = false,
                                mainColor = RadicalRed
                            ) {
                                clearMode = "PROMPT"
                            }
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        TightPanelButton(
                            text = "CLEAR ALL",
                            modifier = Modifier.fillMaxWidth(),
                            isActive = false,
                            mainColor = RadicalRed
                        ) {
                            clearMode = "ALL"
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "COMMIT",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.MATRIX_COMMIT_BUTTON)
                            .helpTarget(AckTags.MATRIX_COMMIT_BUTTON, primaryColor),
                        mainColor = primaryColor
                    ) {
                        commitEditor()

                        helpManager?.onEvent(
                            HelpEvent.Interacted(AckTags.MATRIX_COMMIT_BUTTON)
                        )
                    }

                    TightPanelButton(
                        text = "CLOSE",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        closeEditor()
                    }
                }
        }

        val mode = clearMode

        if (mode != null) {
            val confirmationText = when (mode) {
                "VARS" -> {
                    "Clear every local variable value for this phrase? "
                     "The prompt will remain."
                }

                "PROMPT" -> {
                    "Clear this prompt only? Existing local variable values "
                     "will be preserved."
                }

                else -> {
                    "Clear both the prompt and every local variable value? "
                     "This cannot be undone from this dialog."
                }
            }

            TightDialogSurface(
                onDismiss = {
                    clearMode = null
                },
                primaryColor = RadicalRed,
                title = "CONFIRM CLEAR",
                dismissLabel = "ABORT"
            ) {
                Text(
                    text = confirmationText,
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM",
                        modifier = Modifier.weight(1f),
                        mainColor = RadicalRed
                    ) {
                        when (mode) {
                            "VARS" -> {
                                repeat(tempVars.size) { index ->
                                    tempVars[index] = ""
                                }

                                saveVariables()
                            }

                            "PROMPT" -> {
                                // Prompt-only intentionally preserves the
                                // variable bank for a future replacement prompt.
                                tempText = ""

                                CommandRepository.setPhrase(
                                    context = context,
                                    storagePath = node.path,
                                    phrase = ""
                                )
                            }

                            "ALL" -> {
                                tempText = ""
                                tempVars.clear()

                                CommandRepository.setPhrase(
                                    context = context,
                                    storagePath = node.path,
                                    phrase = ""
                                )

                                saveVariables()
                            }
                        }

                        clearMode = null
                        refreshKey++
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        clearMode = null
                    }
                }
            }
        }

        if (showAttachRecordingWarning) {
            TightDialogSurface(
                onDismiss = { showAttachRecordingWarning = false },
                primaryColor = primaryColor,
                title = "VOICE RECORDING",
                dismissLabel = "CANCEL"
            ) {
                Text(
                    text = "This entry has $variableCount variable(s) and $computerTagCount " +
                        "target tag(s). Attaching a recording plays it back exactly as " +
                        "recorded, ignoring what they'd resolve to. Their values are kept, " +
                        "not deleted -- remove the recording at any time to get them back.",
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        recordingPanelUnlocked = true
                        showAttachRecordingWarning = false
                    }
                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        showAttachRecordingWarning = false
                    }
                }
            }
        }

        if (showStaleWarning) {
            TightDialogSurface(
                onDismiss = { showStaleWarning = false },
                primaryColor = RadicalRed,
                title = "RECORDING DISABLED",
                dismissLabel = "OK"
            ) {
                Text(
                    text = "This entry's text changed since its recording was made, so the " +
                        "recording has been disabled to avoid mismatched audio. It hasn't " +
                        "been deleted -- re-enable it from the VOICE RECORDING panel above " +
                        "once you're happy with the new wording.",
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(16.dp))

                TightPanelButton(
                    text = "OK, GOT IT",
                    modifier = Modifier.fillMaxWidth(),
                    mainColor = RadicalRed
                ) {
                    showStaleWarning = false
                }
            }
        }
    }

    if (variableEditRequest != null) {
        val request = variableEditRequest!!
        var value by remember(request.nodePath, request.index) {
            mutableStateOf(request.currentValue)
        }

        TightDialogSurface(
            onDismiss = { variableEditRequest = null },
            primaryColor = primaryColor,
            title = "${request.nodeLabel} // VAR ${request.index + 1}",
            dismissLabel = "ABORT"
        ) {
                Column {
                    TightSectionLabel("LIVE VARIABLE VALUE")

                    Spacer(modifier = Modifier.height(8.dp))

                    OutlinedTextField(
                        value = value,
                        onValueChange = { value = it },
                        modifier = Modifier.fillMaxWidth(),
                        shape = AckHelpShape,
                        singleLine = true,
                        placeholder = {
                            Text(
                                text = "ENTER VALUE",
                                fontFamily = FontFamily.Monospace
                            )
                        },
                        textStyle = androidx.compose.ui.text.TextStyle(
                            color = primaryColor,
                            fontFamily = FontFamily.Monospace
                        ),
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = VoidBlack,
                            unfocusedContainerColor = VoidBlack,
                            focusedIndicatorColor = primaryColor,
                            unfocusedIndicatorColor = Color.DarkGray,
                            focusedTextColor = primaryColor,
                            unfocusedTextColor = primaryColor,
                            cursorColor = primaryColor
                        )
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "UPDATE",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        val existingValues = CommandRepository.getVariableValues(
                            context,
                            request.nodePath
                        ).toMutableList()

                        while (existingValues.size <= request.index) {
                            existingValues.add("")
                        }

                        existingValues[request.index] = value

                        CommandRepository.setVariableValues(
                            context,
                            request.nodePath,
                            existingValues
                        )

                        refreshKey++
                        variableEditRequest = null
                    }

                    TightPanelButton(
                        text = "ABORT",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        variableEditRequest = null
                    }
                }
        }
    }

    if (showManageContextDialog) {
        ManageContextDialog(
            context = context,
            primaryColor = primaryColor,
            onDismiss = { showManageContextDialog = false },
            onChanged = { refreshKey++ }
        )
    }
}

// --- MANAGE CONTEXT ---
//
// IDENTITY, DEFEND, and CONNECT are the three immutable poses -- they can
// never be renamed, reassigned, reordered, or removed here. Everything below
// them is a custom context layer the wearer added: additional expression
// riding on top of one of those same three physical gestures.
@Composable
fun ManageContextDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onChanged: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var entries by remember(refreshKey) {
        mutableStateOf(CommandRepository.getCustomContextEntries(context))
    }

    var showAddDialog by remember { mutableStateOf(false) }
    var renamingEntry by remember { mutableStateOf<CustomContextEntry?>(null) }
    var reassigningEntry by remember { mutableStateOf<CustomContextEntry?>(null) }
    var deletingEntry by remember { mutableStateOf<CustomContextEntry?>(null) }

    fun refresh() {
        refreshKey++
        onChanged()
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "MANAGE CONTEXT",
        dismissLabel = "DONE"
    ) {
                Text(
                    text = "The three base poses are permanent. Custom " +
                            "context layers ride on top of one pose's " +
                            "gestures and can be reordered, reassigned, " +
                            "renamed, or removed.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(12.dp))

                LazyColumn(
                    modifier = Modifier.heightIn(max = 420.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(POSE_CATEGORIES) { pose ->
                        ImmutablePoseRow(pose = pose, primaryColor = primaryColor)
                    }

                    items(entries, key = { it.name }) { entry ->
                        val index = entries.indexOf(entry)

                        CustomContextRow(
                            entry = entry,
                            primaryColor = primaryColor,
                            canMoveUp = index > 0,
                            canMoveDown = index < entries.lastIndex,
                            onMoveUp = {
                                CommandRepository.moveCustomContextEntry(
                                    context, entry.name, -1
                                )
                                refresh()
                            },
                            onMoveDown = {
                                CommandRepository.moveCustomContextEntry(
                                    context, entry.name, 1
                                )
                                refresh()
                            },
                            onRename = { renamingEntry = entry },
                            onReassign = { reassigningEntry = entry },
                            onDelete = { deletingEntry = entry }
                        )
                    }

                    item {
                        Spacer(modifier = Modifier.height(4.dp))

                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 44.dp)
                                .border(1.dp, primaryColor, AckHelpShape)
                                .background(
                                    primaryColor.copy(alpha = 0.12f),
                                    AckHelpShape
                                )
                                .clickable { showAddDialog = true }
                                .padding(vertical = 12.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "+ ADD CONTEXT",
                                color = primaryColor,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp
                            )
                        }
                    }
                }
    }

    if (showAddDialog) {
        AddContextDialog(
            primaryColor = primaryColor,
            existingNames = entries.map { it.name },
            onDismiss = { showAddDialog = false },
            onCreate = { name, basePose ->
                if (CommandRepository.addCustomContextEntry(context, name, basePose)) {
                    refresh()
                    showAddDialog = false
                }
            }
        )
    }

    val renaming = renamingEntry

    if (renaming != null) {
        RenameContextDialog(
            entry = renaming,
            primaryColor = primaryColor,
            existingNames = entries.map { it.name },
            onDismiss = { renamingEntry = null },
            onConfirm = { newName ->
                if (
                    CommandRepository.renameCustomContextEntry(
                        context, renaming.name, newName
                    )
                ) {
                    refresh()
                    renamingEntry = null
                }
            }
        )
    }

    val reassigning = reassigningEntry

    if (reassigning != null) {
        ReassignPoseDialog(
            entry = reassigning,
            primaryColor = primaryColor,
            onDismiss = { reassigningEntry = null },
            onConfirm = { newPose ->
                CommandRepository.reassignCustomContextPose(
                    context, reassigning.name, newPose
                )
                refresh()
                reassigningEntry = null
            }
        )
    }

    val deleting = deletingEntry

    if (deleting != null) {
        TightDialogSurface(
            onDismiss = { deletingEntry = null },
            primaryColor = RadicalRed,
            title = "CONFIRM DELETE",
            dismissLabel = "ABORT"
        ) {
            Text(
                text = "Permanently remove context layer " +
                        "\"${deleting.name}\"? Every phrase, variable, " +
                        "and shared override saved under it will be " +
                        "deleted across every deck and profile. This " +
                        "cannot be undone -- consider exporting a " +
                        "backup first.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton(
                    text = "DELETE PERMANENTLY",
                    modifier = Modifier.fillMaxWidth(),
                    mainColor = RadicalRed
                ) {
                    CommandRepository.removeCustomContextEntry(context, deleting.name)
                    refresh()
                    deletingEntry = null
                }

                TightPanelButton(
                    text = "CANCEL",
                    modifier = Modifier.fillMaxWidth(),
                    isActive = false,
                    mainColor = primaryColor
                ) {
                    deletingEntry = null
                }
            }
        }
    }
}

@Composable
private fun ImmutablePoseRow(pose: String, primaryColor: Color) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Color.DarkGray, AckHelpShape)
            .padding(horizontal = 10.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "ROOT :: $pose",
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "[IMMUTABLE]",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun CustomContextRow(
    entry: CustomContextEntry,
    primaryColor: Color,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onRename: () -> Unit,
    onReassign: () -> Unit,
    onDelete: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.5f), AckHelpShape)
            .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = entry.name,
                    color = primaryColor,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = "BASED ON: ${entry.basePose}",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                ContextRowIconButton(
                    text = "▲",
                    enabled = canMoveUp,
                    primaryColor = primaryColor,
                    onClick = onMoveUp
                )

                ContextRowIconButton(
                    text = "▼",
                    enabled = canMoveDown,
                    primaryColor = primaryColor,
                    onClick = onMoveDown
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            ContextRowActionButton(
                text = "REASSIGN",
                primaryColor = primaryColor,
                modifier = Modifier.weight(1f),
                onClick = onReassign
            )

            ContextRowActionButton(
                text = "RENAME",
                primaryColor = primaryColor,
                modifier = Modifier.weight(1f),
                onClick = onRename
            )

            ContextRowActionButton(
                text = "DELETE",
                primaryColor = RadicalRed,
                modifier = Modifier.weight(1f),
                onClick = onDelete
            )
        }
    }
}

@Composable
private fun ContextRowIconButton(
    text: String,
    enabled: Boolean,
    primaryColor: Color,
    onClick: () -> Unit
) {
    val color = if (enabled) primaryColor else Color.DarkGray

    Box(
        modifier = Modifier
            .size(44.dp)
            .border(1.dp, color, AckHelpShape)
            .then(
                if (enabled) Modifier.clickable { onClick() } else Modifier
            ),
        contentAlignment = Alignment.Center
    ) {
        Text(text = text, color = color, fontSize = 12.sp)
    }
}

@Composable
private fun ContextRowActionButton(
    text: String,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .heightIn(min = 44.dp)
            .border(1.dp, primaryColor, AckHelpShape)
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = primaryColor,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun PosePicker(
    selected: String,
    primaryColor: Color,
    onSelect: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        POSE_CATEGORIES.forEach { pose ->
            val isSelected = pose == selected
            val color = if (isSelected) primaryColor else Color.Gray

            Box(
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 44.dp)
                    .border(
                        width = if (isSelected) 2.dp else 1.dp,
                        color = color,
                        shape = AckHelpShape
                    )
                    .background(
                        if (isSelected) primaryColor.copy(alpha = 0.14f) else Color.Transparent,
                        AckHelpShape
                    )
                    .clickable { onSelect(pose) }
                    .padding(vertical = 10.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = pose,
                    color = color,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun AddContextDialog(
    primaryColor: Color,
    existingNames: List<String>,
    onDismiss: () -> Unit,
    onCreate: (name: String, basePose: String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var basePose by remember { mutableStateOf(POSE_CATEGORIES[0]) }

    val cleanName = name.trim().uppercase()
    val isValid = cleanName.isNotEmpty() &&
            cleanName !in POSE_CATEGORIES &&
            cleanName !in existingNames

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "ADD CONTEXT"
    ) {
                TightSectionLabel("CONTEXT NAME")

                Spacer(modifier = Modifier.height(6.dp))

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.uppercase().take(24) },
                    placeholder = { Text("E.G. SCHOOL, WORK, PLAY") },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                TightSectionLabel("ASSIGN TO POSE")

                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = "The physical gesture that activates this " +
                            "layer's phrases when it is focused.",
                    color = Color.DarkGray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(8.dp))

                PosePicker(
                    selected = basePose,
                    primaryColor = primaryColor,
                    onSelect = { basePose = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CREATE",
                        modifier = Modifier.weight(1f),
                        isActive = isValid,
                        mainColor = primaryColor
                    ) {
                        if (isValid) {
                            onCreate(cleanName, basePose)
                        }
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
private fun RenameContextDialog(
    entry: CustomContextEntry,
    primaryColor: Color,
    existingNames: List<String>,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var name by remember(entry.name) { mutableStateOf(entry.name) }

    val cleanName = name.trim().uppercase()
    val isValid = cleanName.isNotEmpty() &&
            (cleanName == entry.name ||
                    (cleanName !in POSE_CATEGORIES && cleanName !in existingNames))

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "RENAME CONTEXT"
    ) {
                Text(
                    text = "Every saved phrase, variable, and override " +
                            "moves with the new name.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.uppercase().take(24) },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM RENAME",
                        modifier = Modifier.weight(1f),
                        isActive = isValid,
                        mainColor = primaryColor
                    ) {
                        if (isValid) {
                            onConfirm(cleanName)
                        }
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
private fun ReassignPoseDialog(
    entry: CustomContextEntry,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var basePose by remember(entry.name) { mutableStateOf(entry.basePose) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "REASSIGN POSE // ${entry.name}"
    ) {
                Text(
                    text = "Choose which pose's physical gesture activates " +
                            "this context layer when it is focused.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(10.dp))

                PosePicker(
                    selected = basePose,
                    primaryColor = primaryColor,
                    onSelect = { basePose = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        onConfirm(basePose)
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
fun MatrixCategory(
    title: String,
    nodes: List<Triple<MatrixNode, String, String>>,
    context: Context,
    primaryColor: Color,
    onEdit: (Triple<MatrixNode, String, String>) -> Unit,
    onEditVariable: (VariableEditRequest) -> Unit,
    onRootOverrideChanged: () -> Unit
) {
    val activeCat =
        remember(title) { mutableStateOf(CommandRepository.getActiveCategoryFocus(context)) }
    val isFocused = activeCat.value == title
    val canFocus = title != "DEFEND" && title != "CONNECT"
    val helpManager = LocalHelpManager.current

    Column {
        val headerModifier = if (title == "IDENTITY") {
            Modifier
                .testTag(AckTags.MATRIX_ROOT_IDENTITY)
                .helpTarget(AckTags.MATRIX_ROOT_IDENTITY, primaryColor)
        } else {
            Modifier
        }



        Row(
            modifier = headerModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(
                            color = if (isFocused) {
                                primaryColor
                            } else {
                                Color.Gray
                            },
                            shape = CutCornerShape(2.dp)
                        )
                )

                Spacer(modifier = Modifier.width(8.dp))

                Text(
                    text = "ROOT :: $title",
                    color = if (isFocused) primaryColor else Color.Gray,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 2.sp
                )
            }

            if (canFocus) {
                Box(
                    modifier = Modifier
                        .heightIn(min = 44.dp)
                        .border(
                            width = 1.dp,
                            color = if (isFocused) {
                                primaryColor
                            } else {
                                Color.Gray
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .clickable {
                            CommandRepository.setActiveCategoryFocus(
                                context,
                                title
                            )

                            activeCat.value = title

                            Intent("ACK_LOG").apply {
                                setPackage(context.packageName)
                                putExtra("msg", "CONTEXT FOCUS: $title")
                                putExtra("type", "SYS")
                                context.sendBroadcast(this)
                            }
                        }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (isFocused) "ACTIVE" else "ACTIVATE",
                        color = if (isFocused) primaryColor else Color.Gray,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        RootOverrideStrip(
            category = title,
            context = context,
            primaryColor = primaryColor,
            onChanged = onRootOverrideChanged
        )

        Spacer(modifier = Modifier.height(10.dp))

        val computerCategories = ComputerRepository.getCategories(context)

        Box(modifier = Modifier.padding(start = 3.dp)) {
            Column(
                modifier = Modifier.border(
                    BorderStroke(1.dp, Color.DarkGray),
                    androidx.compose.ui.graphics.RectangleShape
                ).padding(start = 16.dp, top = 8.dp)
            ) {
                // <-- UPDATED LOOP TO DESTRUCTURE THE TRIPLE -->
                nodes.forEach { (node, rawPhrase, resolvedPhrase) ->
                    val isTarget = node.category == "IDENTITY" && node.label.contains("Twist 0")
                    val itemMod = if (isTarget) Modifier
                        .testTag(AckTags.MATRIX_ROW_TARGET)
                        .helpTarget(AckTags.MATRIX_ROW_TARGET, primaryColor)
                    else Modifier

                    val variableCount = TemplateEngine.countVariables(rawPhrase)
                    val savedValues = CommandRepository.getVariableValues(context, node.path)

                    val variableValues = List(variableCount) { index ->
                        savedValues.getOrElse(index) { "" }
                    }

                    val computerTagsInOrder = TemplateEngine.getComputerTags(rawPhrase)
                    val computerFallbacks = CommandRepository.getComputerFallbackValues(context, node.path)

                    val computerTagChips = computerTagsInOrder.mapIndexed { index, categoryId ->
                        val categoryLabel = computerCategories.find { it.id == categoryId }?.label ?: categoryId
                        val activeValue = ComputerRepository.resolveTag(context, categoryId)
                        val displayValue = activeValue
                            .ifBlank { computerFallbacks.getOrNull(index).orEmpty() }
                            .ifBlank { "EMPTY" }
                        categoryLabel to displayValue
                    }

                    // A recording here plays verbatim, ignoring whatever
                    // the variables/tags above would resolve to -- see
                    // MatrixEditor. Only a currently-enabled recording
                    // changes the row's playback and display; a disabled
                    // (stale) one falls back to normal template resolution
                    // exactly like having no recording at all.
                    val nodeRecording = VoiceRecordingRepository.getForMatrixNode(
                        context,
                        CommandRepository.getActiveDeckId(context),
                        CommandRepository.getActiveProfile(context),
                        node.path
                    )
                    val recordingIsActive = nodeRecording?.enabled == true

                    // The user has already "resolved" this node by hand once
                    // they bind a recording -- its visual override (if set)
                    // is the authoritative display text from here on, not
                    // whatever the live variable/root-override state would
                    // otherwise compute. Falls back to the normal resolved
                    // phrase when no override is set, same as before.
                    val recordedDisplayPhrase = if (recordingIsActive) {
                        CommandRepository.getVisualOverride(context, node.path).ifBlank { resolvedPhrase }
                    } else {
                        resolvedPhrase
                    }

                    MatrixNodeItem(
                        label = node.label,
                        phrase = recordedDisplayPhrase,
                        variableValues = if (recordingIsActive) emptyList() else variableValues,
                        computerTagChips = if (recordingIsActive) emptyList() else computerTagChips,
                        isRecorded = recordingIsActive,
                        onOpenComputerTag = { onEdit(Triple(node, rawPhrase, resolvedPhrase)) },
                        modifier = itemMod,
                        playModifier = if (isTarget) Modifier
                            .testTag(AckTags.MATRIX_PLAY_BUTTON)
                            .helpTarget(AckTags.MATRIX_PLAY_BUTTON, primaryColor)
                        else Modifier,
                        primaryColor = primaryColor,
                        onPlay = {
                            if (isTarget) {
                                helpManager?.onEvent(
                                    HelpEvent.Interacted(AckTags.MATRIX_PLAY_BUTTON)
                                )
                            }

                            if (recordingIsActive && nodeRecording != null) {
                                // Same text the row itself is showing right now
                                // (recordedDisplayPhrase) -- the visual override
                                // if one is set, otherwise the normal resolved
                                // phrase. Keeps the log line and on-screen prompt
                                // from ever disagreeing with what's on screen in
                                // the MATRIX list.
                                val intent = Intent(context, OutputService::class.java).apply {
                                    putExtra("phrase", recordedDisplayPhrase)
                                    putExtra("recording_id", nodeRecording.id)
                                    putExtra("robotic", false)
                                    putExtra("source", "MTX/${title.uppercase()}")
                                }
                                context.startService(intent)
                                return@MatrixNodeItem
                            }

                            val debug = CommandRepository.debugResolvedPhrase(
                                context = context,
                                storagePath = node.path
                            )

                            context.sendBroadcast(
                                Intent("ACK_LOG").apply {
                                    setPackage(context.packageName)
                                    // PATH, not SYS -- this is the verbose per-tag
                                    // resolution trace, gated by its own Terminal
                                    // toggle independent of general system messages.
                                    putExtra("type", "PATH")
                                    putExtra("msg", debug.replace("\n", " | "))
                                }
                            )

                            val finalPhrase = CommandRepository.getResolvedPhrase(
                                context = context,
                                storagePath = node.path,
                                // Genuine dispatch (about to speak), not a
                                // preview -- allowed to clear single-use
                                // [COMPUTER:X] picks.
                                consumeSingleUse = true
                            )

                            val intent = Intent(context, OutputService::class.java).apply {
                                putExtra("phrase", finalPhrase)
                                putExtra("robotic", false)
                                putExtra("source", "MTX/${title.uppercase()}")
                            }

                            context.startService(intent)
                        },
                        onClick = {
                            if (isTarget) {
                                helpManager?.onEvent(
                                    HelpEvent.Interacted(AckTags.MATRIX_ROW_TARGET)
                                )
                            }
                            onEdit(Triple(node, rawPhrase, resolvedPhrase))
                        },
                        onEditVariable = { index ->
                            onEditVariable(
                                VariableEditRequest(
                                    nodePath = node.path,
                                    nodeLabel = node.label,
                                    index = index,
                                    currentValue = variableValues[index]
                                )
                            )
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun RootOverrideStrip(
    category: String,
    context: Context,
    primaryColor: Color,
    onChanged: () -> Unit
) {
    var config by remember(category) {
        mutableStateOf(
            RootOverrideRepository.getConfig(context, category)
        )
    }

    // Stored per category/pose, so toggling this block never affects any
    // other pose's or custom layer's own collapsed/expanded state.
    var collapsed by remember(category) {
        mutableStateOf(RootOverrideRepository.isSectionCollapsed(context, category))
    }

    var editingTag by remember { mutableStateOf<String?>(null) }

    fun updateSlot(
        tag: String,
        transform: (RootOverrideValue) -> RootOverrideValue
    ) {
        val currentSlot = config.slots[tag] ?: RootOverrideValue()

        config = config.copy(
            slots = config.slots.toMutableMap().apply {
                put(tag, transform(currentSlot))
            }
        )

        RootOverrideRepository.saveConfig(
            context = context,
            category = category,
            config = config
        )

        onChanged()
    }

    fun toggleCollapsed() {
        collapsed = !collapsed
        RootOverrideRepository.setSectionCollapsed(context, category, collapsed)
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor.copy(alpha = 0.45f),
                shape = CutCornerShape(8.dp)
            )
            .background(
                color = primaryColor.copy(alpha = 0.04f),
                shape = CutCornerShape(8.dp)
            )
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { toggleCollapsed() },
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "SHARED ROOT VARIABLES",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )

            Text(
                text = if (collapsed) "[EXPAND ▼]" else "[COLLAPSE ▲]",
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        AnimatedVisibility(
            visible = collapsed,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Column {
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf("A", "B", "C").forEach { tag ->
                        val slot = config.slots[tag] ?: RootOverrideValue()

                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp)
                                .border(
                                    width = 1.dp,
                                    color = if (slot.enabled) {
                                        primaryColor
                                    } else {
                                        Color.Gray
                                    },
                                    shape = CutCornerShape(4.dp)
                                )
                                .background(
                                    color = if (slot.enabled) {
                                        primaryColor.copy(alpha = 0.18f)
                                    } else {
                                        Color.Transparent
                                    },
                                    shape = CutCornerShape(4.dp)
                                )
                                .clickable {
                                    updateSlot(tag) { current ->
                                        current.copy(enabled = !current.enabled)
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "$tag: ${if (slot.enabled) "ON" else "OFF"}",
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }

        AnimatedVisibility(
            visible = !collapsed,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Column {
            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = "Enabled tags replace matching {VAR:A}, {VAR:B}, or {VAR:C}.",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(10.dp))

            listOf("A", "B", "C").forEach { tag ->
                val slot = config.slots[tag] ?: RootOverrideValue()
                val valueText = slot.value.ifBlank { "NO SHARED VALUE SET" }

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                        .border(
                            width = 1.dp,
                            color = if (slot.enabled) {
                                primaryColor
                            } else {
                                Color.DarkGray
                            },
                            shape = CutCornerShape(6.dp)
                        )
                        .background(
                            color = if (slot.enabled) {
                                primaryColor.copy(alpha = 0.10f)
                            } else {
                                Color.Transparent
                            },
                            shape = CutCornerShape(6.dp)
                        )
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(width = 52.dp, height = 44.dp)
                            .border(
                                width = 1.dp,
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                shape = CutCornerShape(4.dp)
                            )
                            .background(
                                color = if (slot.enabled) {
                                    primaryColor.copy(alpha = 0.18f)
                                } else {
                                    Color.Transparent
                                },
                                shape = CutCornerShape(4.dp)
                            )
                            .clickable {
                                updateSlot(tag) { current ->
                                    current.copy(enabled = !current.enabled)
                                }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = tag,
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 14.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )

                            Text(
                                text = if (slot.enabled) "ON" else "OFF",
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 8.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(10.dp))

                    Column(
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(
                            text = "ROOT $tag",
                            color = if (slot.enabled) primaryColor else Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(3.dp))

                        Text(
                            text = valueText,
                            color = if (slot.value.isBlank()) {
                                Color.DarkGray
                            } else {
                                Color.White
                            },
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    Box(
                        modifier = Modifier
                            .size(width = 64.dp, height = 44.dp)
                            .border(
                                width = 1.dp,
                                color = primaryColor.copy(alpha = 0.75f),
                                shape = CutCornerShape(4.dp)
                            )
                            .clickable {
                                editingTag = tag
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "EDIT",
                            color = primaryColor,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                if (tag != "C") {
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
            }
        }
    }

    val tag = editingTag

    if (tag != null) {
        RootOverrideValueDialog(
            tag = tag,
            category = category,
            initialValue = config.slots[tag]?.value.orEmpty(),
            primaryColor = primaryColor,
            onDismiss = {
                editingTag = null
            },
            onSave = { newValue: String ->
                updateSlot(tag) { current ->
                    current.copy(value = newValue)
                }

                editingTag = null
            }
        )
    }
}

@Composable
fun RootOverrideValueDialog(
    tag: String,
    category: String,
    initialValue: String,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit
) {
    var value by remember(tag, initialValue) {
        mutableStateOf(initialValue)
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "ROOT $category // TAG $tag",
        dismissLabel = "ABORT"
    ) {
                TightSectionLabel("SHARED OVERRIDE VALUE")

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it },
                    modifier = Modifier.fillMaxWidth(),
                    shape = AckHelpShape,
                    singleLine = true,
                    placeholder = {
                        Text(
                            text = "ENTER VALUE",
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    textStyle = androidx.compose.ui.text.TextStyle(
                        color = primaryColor,
                        fontFamily = FontFamily.Monospace
                    ),
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor,
                        unfocusedIndicatorColor = Color.DarkGray,
                        cursorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "COMMIT",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        onSave(value)
                    }

                    TightPanelButton(
                        text = "ABORT",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
fun MatrixNodeItem(
    label: String,
    phrase: String,
    variableValues: List<String>,
    modifier: Modifier = Modifier,
    playModifier: Modifier = Modifier,
    primaryColor: Color,
    onPlay: () -> Unit,
    onClick: () -> Unit,
    onEditVariable: (Int) -> Unit,
    // (category label, currently-resolved display value) per [COMPUTER:X]
    // tag in this node's template. Unlike variableValues, a resolved
    // computer tag disappears entirely into the (often-truncated) preview
    // text below with nothing marking that it was ever there -- these
    // chips are the only visible sign the tag exists at all.
    computerTagChips: List<Pair<String, String>> = emptyList(),
    onOpenComputerTag: () -> Unit = {},
    // True when an enabled voice recording plays instead of this node's
    // template -- variableValues/computerTagChips are expected to already
    // be passed empty by the caller in that case (they're inert), and this
    // just adds the visible marker explaining why.
    isRecorded: Boolean = false
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "├─",
            color = Color.DarkGray,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.width(8.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    1.dp,
                    primaryColor.copy(alpha = 0.3f),
                    CutCornerShape(bottomEnd = 8.dp)
                )
                .background(Graphite)
                .padding(4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .clickable { onClick() }
                    .padding(4.dp)
            ) {
                Text(
                    text = label,
                    color = primaryColor,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = if (phrase.length > 20) {
                        phrase.take(17) + "..."
                    } else {
                        phrase
                    },
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                if (isRecorded) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "● RECORDED",
                        color = RadicalRed,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }

                if (variableValues.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.horizontalScroll(
                            rememberScrollState()
                        ),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        variableValues.forEachIndexed { index, value ->
                            val displayValue = value.ifBlank { "EMPTY" }

                            Box(
                                modifier = Modifier
                                    .border(
                                        1.dp,
                                        color = NeonPalette.SWATCHES[3],
                                        CutCornerShape(4.dp)
                                    )
                                    .background(
                                        NeonPalette.SWATCHES[3].copy(
                                            alpha = 0.08f
                                        ),
                                        CutCornerShape(4.dp)
                                    )
                                    .clickable {
                                        onEditVariable(index)
                                    }
                                    .padding(
                                        horizontal = 6.dp,
                                        vertical = 4.dp
                                    )
                            ) {
                                Text(
                                    text = "V${index + 1}: $displayValue",
                                    color = NeonPalette.SWATCHES[3],
                                    fontSize = 9.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }

                if (computerTagChips.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.horizontalScroll(
                            rememberScrollState()
                        ),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        computerTagChips.forEach { (categoryLabel, displayValue) ->
                            Box(
                                modifier = Modifier
                                    .border(
                                        1.dp,
                                        color = primaryColor,
                                        CutCornerShape(4.dp)
                                    )
                                    .background(
                                        primaryColor.copy(alpha = 0.10f),
                                        CutCornerShape(4.dp)
                                    )
                                    .clickable { onOpenComputerTag() }
                                    .padding(
                                        horizontal = 6.dp,
                                        vertical = 4.dp
                                    )
                            ) {
                                Text(
                                    text = "$categoryLabel: $displayValue",
                                    color = primaryColor,
                                    fontSize = 9.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            Box(
                modifier = playModifier
                    .size(32.dp)
                    .background(
                        Color.DarkGray.copy(alpha = 0.3f),
                        CutCornerShape(4.dp)
                    )
                    .clickable { onPlay() }
                    .border(1.dp, primaryColor, CutCornerShape(4.dp)),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "▶",
                    color = primaryColor,
                    fontSize = 10.sp
                )
            }
        }
    }
}

@Composable
fun BuilderGuideCard(category: String, primaryColor: Color) {
    val (title, body) = when(category) {
        "IDENTITY" -> "POSE: ARM RAISED UP" to "Use for: Status reporting."
        "DEFEND" -> "POSE: ARM FLAT / PALM DOWN" to "Use for: Boundaries, stops."
        "CONNECT" -> "POSE: HANDSHAKE / SIDEWAYS" to "Use for: Social protocols."
        else -> "UNKNOWN" to "No data available."
    }
    Column(modifier = Modifier.fillMaxWidth().border(1.dp, primaryColor, CutCornerShape(8.dp)).background(primaryColor.copy(alpha = 0.05f)).padding(12.dp)) {
        Text("// TACTICAL GUIDE: $title", color = primaryColor, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
        Spacer(modifier = Modifier.height(4.dp))
        Text(body, color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
    }
}
