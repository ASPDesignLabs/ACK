package com.example.besu

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import com.google.android.gms.wearable.Wearable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import android.content.pm.ActivityInfo
import androidx.compose.foundation.Canvas
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics

private enum class BottomNavIcon {
    SPEAK,
    TERMINAL,
    CROSSHAIR,
    MAP,
    KEYBOARD,
    AUDIO

}
class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private val logBuffer = mutableStateListOf<LogEntry>()
    private var ttsSystem: TextToSpeech? = null
    val availableSystemVoices = mutableStateListOf<Voice>()



    private val systemReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if(intent?.action == "ACK_LOG") {
                val msg = intent.getStringExtra("msg") ?: "Unknown"
                val type = intent.getStringExtra("type") ?: "INFO"
                addLog(msg, type)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ttsSystem = TextToSpeech(this, this)

        // Request Wide Color Gamut / HDR Surface
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            window.colorMode = ActivityInfo.COLOR_MODE_WIDE_COLOR_GAMUT
        }
        // If targeting Android 14+ (API 34), you can specifically request HDR
        if (Build.VERSION.SDK_INT >= 34) {
            window.colorMode = ActivityInfo.COLOR_MODE_HDR
        }


        val filter = IntentFilter("ACK_LOG")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(systemReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(systemReceiver, filter)
        }

        checkBatteryOptimization()
        startOutputService()

        setContent {
            MainScreen(logs = logBuffer, context = this, systemVoices = availableSystemVoices)
        }
        addLog("SYSTEM BOOT COMPLETE", "SYS")
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            try {
                val voices = ttsSystem?.voices?.filter { it.locale.language == "en" }?.sortedBy { it.name }
                if (voices != null) {
                    availableSystemVoices.clear()
                    availableSystemVoices.addAll(voices)
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    private fun checkBatteryOptimization() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    val intent = Intent().apply {
                        action = Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
                        data = Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                } catch (e: Exception) { e.printStackTrace() }
            }
        }
    }

    private fun startOutputService() {
        try {
            val intent = Intent(this, OutputService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        } catch (e: Exception) { }
    }

    private fun addLog(text: String, type: String) {
        val timestamp = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        logBuffer.add(0, LogEntry(timestamp, type, text))
        if (logBuffer.size > 100) logBuffer.removeLast()
    }

    override fun onDestroy() {
        unregisterReceiver(systemReceiver)
        ttsSystem?.shutdown()
        super.onDestroy()
    }
}

data class LogEntry(val time: String, val type: String, val msg: String)

@Composable
fun MainScreen(logs: List<LogEntry>, context: Context, systemVoices: List<Voice>) {
    var viewMode by remember { mutableStateOf("TERMINAL") }
    var headerShortcuts by remember(viewMode) {
        mutableStateOf(CommandRepository.getHeaderShortcuts(context))
    }
    var currentDeckId by remember { mutableStateOf(CommandRepository.getActiveDeckId(context)) }
    var primaryColor by remember {
        mutableStateOf(
            NeonPalette.getColor(
                CommandRepository.getActiveColorIndex(
                    context
                )
            )
        )
    }
    var currentDeckName by remember(currentDeckId) {
        mutableStateOf(
            if (currentDeckId == "DEFAULT") "DEFAULT" else CommandRepository.getDecks(
                context
            ).find { it.id == currentDeckId }?.name ?: "UNKNOWN"
        )
    }
    var isDeckMenuOpen by remember { mutableStateOf(false) }
    var currentProfile by remember { mutableStateOf(CommandRepository.getActiveProfile(context)) }
    var isProfileMenuOpen by remember { mutableStateOf(false) }
    var isDialogOpen by remember { mutableStateOf(false) }

    var helpMenuCategory by remember {
        mutableStateOf<HelpCategory?>(null)
    }

    var showCreateDeckDialog by remember {
        mutableStateOf(false)
    }
    val recentPhrases = remember { mutableStateListOf<String>() }
    val helpManager = remember {
        HelpManager(HelpRegistry.modules)
    }

    var showHelpMenu by remember {
        mutableStateOf(false)
    }
    var isLiveLinkActive by remember { mutableStateOf(false) }
    var watchStateLabel by remember { mutableStateOf("OFFLINE") }
    var watchPoseLabel by remember { mutableStateOf("---") }
    var watchTwistLevel by remember { mutableIntStateOf(0) }
    var isDeckManageMode by remember {
        mutableStateOf(false)
    }

    var managedDeckId by remember {
        mutableStateOf<String?>(null)
    }

    var showDeleteDeckConfirm by remember {
        mutableStateOf(false)
    }

    var showDeleteDeckFinalConfirm by remember {
        mutableStateOf(false)
    }

    var deckRevision by remember {
        mutableIntStateOf(0)
    }

    val decks = remember(deckRevision) {
        CommandRepository.getDecks(context)
    }

    fun currentDeckType(): DeckType {
        return CommandRepository.getDeckType(
            context = context,
            deckId = currentDeckId
        )
    }

    fun exitDeckManageMode() {
        isDeckManageMode = false
        managedDeckId = null
        showDeleteDeckConfirm = false
        showDeleteDeckFinalConfirm = false
    }

    LaunchedEffect(Unit) {
        val prefs = context.getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)
        val existingJson = prefs.getString("CUSTOM_VOICES", "[]") ?: "[]"
        if (existingJson == "[]" || existingJson.length < 10) {
            val defaults = listOf(
                VoiceProfile("USER_1", "CUSTOM A", 1.0f, 1.0f, 0f, 0f, 0f),
                VoiceProfile("USER_2", "CUSTOM B", 0.7f, 0.85f, 30f, 0.4f, 0.4f),
                VoiceProfile("USER_3", "CUSTOM C", 1.2f, 1.2f, 50f, 0.6f, 0.3f)
            )
            prefs.edit().putString("CUSTOM_VOICES", Json.encodeToString(defaults)).apply()
        }
        val intent = Intent(context, OutputService::class.java)
        intent.action = "UPDATE_DSP"
        intent.putExtra("user_profile", prefs.getString("USER_VOX_PROFILE", "CYBER"))
        intent.putExtra("tutorial_profile", prefs.getString("TUT_VOX_PROFILE", "MECH"))
        intent.putExtra("cadence", prefs.getFloat("VOX_CADENCE", 0f))
        intent.putExtra("speaker", prefs.getBoolean("FORCE_SPEAKER", false))
        intent.putExtra("master_gain", prefs.getFloat("MASTER_GAIN", 1.0f))
        intent.putExtra("custom_voices_json", prefs.getString("CUSTOM_VOICES", "[]"))
        context.startService(intent)

        val cIdx = CommandRepository.getActiveColorIndex(context)
        WatchSync.sendDeckConfig(context, cIdx, currentDeckName)
        WatchSync.sendDeckList(context)
        WatchSync.sendProfileConfig(context, currentProfile)

        val crownSens = prefs.getInt("CROWN_SENS", 2)
        val twist = prefs.getFloat("MOT_TWIST", 7.0f)
        val pose = prefs.getFloat("MOT_POSE", 6.0f)
        val toneTheme = prefs.getInt("TONE_THEME", 1)
        val toneVol = prefs.getFloat("TONE_VOLUME", 0.8f)

        WatchSync.sendCrownSensitivity(context, crownSens)
        WatchSync.sendMotionConfig(context, twist, pose)
        WatchSync.sendAudioConfig(context, toneTheme, toneVol)
    }

    DisposableEffect(context) {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context?, intent: Intent?) {
                when (intent?.action) {
                    "ACK_WATCH_STATUS" -> {
                        watchStateLabel = intent.getStringExtra("state") ?: "ERR"
                        watchPoseLabel = intent.getStringExtra("pose") ?: "---"
                        watchTwistLevel = intent.getIntExtra("twist", 0)
                        if (watchStateLabel == "ARMED") {
                            helpManager.onEvent(
                                HelpEvent.WatchInput("ARMED")
                            )
                        }
                        if (watchStateLabel == "LOCKED" && watchPoseLabel == "ID") {
                            helpManager.onEvent(
                                HelpEvent.WatchInput("POSE_ID")
                            )
                        }

                        if (watchStateLabel == "LOCKED" && watchTwistLevel > 0) {
                            helpManager.onEvent(
                                HelpEvent.WatchInput("MODIFIED")
                            )
                        }

                        // COOLDOWN is entered the instant the watch fires a command,
                        // whether or not the real /gesture/* output was suppressed for
                        // training -- so this is the FIRE signal, not the echoed output.
                        if (watchStateLabel == "COOLDOWN") {
                            helpManager.onEvent(
                                HelpEvent.WatchInput("FIRE")
                            )
                        }
                    }

                    "ACK_DECK_CHANGE" -> {
                        val newId = intent.getStringExtra("deckId") ?: "DEFAULT"
                        val newColorIdx = intent.getIntExtra("colorIdx", 0)
                        currentDeckId = newId
                        primaryColor = NeonPalette.getColor(newColorIdx)
                    }
                }
            }
        }
        val filter = IntentFilter().apply {
            addAction("ACK_WATCH_STATUS")
            addAction("ACK_DECK_CHANGE")
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            context.registerReceiver(receiver, filter)
        }
        onDispose { context.unregisterReceiver(receiver) }
    }



    LaunchedEffect(helpManager.completedCategory) {
        val category = helpManager.completedCategory
            ?: return@LaunchedEffect

        helpMenuCategory = category
        showHelpMenu = true
        helpManager.completionHandled()
    }

    LaunchedEffect(
        helpManager.activeModule?.id,
        helpManager.currentStepIndex
    ) {
        val module = helpManager.activeModule ?: return@LaunchedEffect
        val step = helpManager.currentStep ?: return@LaunchedEffect

        val spokenText = buildString {
            append(step.title)
            append(". ")
            append(step.body)
        }

        val intent = Intent(context, OutputService::class.java).apply {
            putExtra("phrase", spokenText)
            putExtra("robotic", true)
            putExtra("source", "HELP/${module.id}")
        }

        context.startService(intent)
    }

    LaunchedEffect(helpManager.activeModule?.id) {
        val isGestureTraining = helpManager.activeModule?.id == FieldOpsHelp.module.id
        WatchSync.sendTrainingMode(context, isGestureTraining)
    }

    fun activateDeck(id: String, colorIdx: Int) {
        CommandRepository.activateDeck(context, id, colorIdx)

        currentDeckId = id
        currentDeckName = CommandRepository.getDeckName(
            context = context,
            deckId = id
        )
        primaryColor = NeonPalette.getColor(colorIdx)

        exitDeckManageMode()

        isDeckMenuOpen = false
        isProfileMenuOpen = false
        viewMode = "MATRIX"

        if (currentDeckType() == DeckType.MATRIX) {
            helpManager.onEvent(
                HelpEvent.DeckWasSelected(AckTags.DECK_SELECTOR)
            )
        }
    }

    LaunchedEffect(helpManager.destinationRequest) {
        val destination = helpManager.destinationRequest
            ?: return@LaunchedEffect

        val module = helpManager.activeModule

        if (
            destination == HelpDestination.MATRIX &&
            module?.requiresMatrixDeck == true &&
            currentDeckType() != DeckType.MATRIX
        ) {
            activateDeck(
                id = "DEFAULT",
                colorIdx = 0
            )
        }

        viewMode = destination.viewMode
        helpManager.destinationHandled(destination)
    }


    fun toggleLiveLink() {
        isLiveLinkActive = !isLiveLinkActive
        val path = if (isLiveLinkActive) "/sys/stream_start" else "/sys/stream_stop"
        Wearable.getNodeClient(context).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node ->
                Wearable.getMessageClient(context).sendMessage(node.id, path, null)
            }
        }
        if (!isLiveLinkActive) {
            watchStateLabel = "OFFLINE"; watchPoseLabel = "---"
        }
        helpManager.onEvent(
            HelpEvent.Interacted(AckTags.LIVE_LINK)
        )
    }

    CompositionLocalProvider(
        LocalHelpManager provides helpManager
    ) {
        Scaffold(
            containerColor = VoidBlack,
            contentWindowInsets = WindowInsets.systemBars
        ) { paddingValues ->
            Box(modifier = Modifier.fillMaxSize()) {
                Column(modifier = Modifier.fillMaxSize().padding(paddingValues).padding(12.dp)) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(
                                BorderStroke(1.dp, primaryColor),
                                CutCornerShape(topStart = 20.dp, bottomEnd = 20.dp)
                            )
                            .background(
                                Graphite,
                                CutCornerShape(topStart = 20.dp, bottomEnd = 20.dp)
                            )
                            .padding(16.dp)

                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.Top
                        ) {
                            Column(
                                modifier = Modifier.weight(1f)
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "ACK",
                                        color = primaryColor,
                                        fontSize = 28.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Black,
                                        letterSpacing = 4.sp
                                    )

                                    Spacer(modifier = Modifier.width(16.dp))

                                    Row(
                                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        headerShortcuts.forEach { shortcut ->
                                            if (shortcut.phrase.isNotEmpty()) {
                                                Box(
                                                    modifier = Modifier
                                                        .testTag(AckTags.HEADER_SHORTCUTS)
                                                        .helpTarget(AckTags.HEADER_SHORTCUTS, primaryColor)
                                                        .border(
                                                            1.dp,
                                                            primaryColor,
                                                            CutCornerShape(4.dp)
                                                        )
                                                        .clickable {
                                                            val intent = Intent(
                                                                context,
                                                                OutputService::class.java
                                                            )

                                                            intent.putExtra(
                                                                "phrase",
                                                                shortcut.phrase
                                                            )
                                                            intent.putExtra("robotic", false)
                                                            intent.putExtra("source", "M-KEY")

                                                            context.startService(intent)
                                                        }
                                                        .padding(
                                                            horizontal = 8.dp,
                                                            vertical = 4.dp
                                                        )
                                                ) {
                                                    Text(
                                                        text = shortcut.label,
                                                        color = primaryColor,
                                                        fontSize = 10.sp,
                                                        fontFamily = FontFamily.Monospace,
                                                        fontWeight = FontWeight.Bold
                                                    )
                                                }
                                            }
                                        }
                                    }
                                }

                                Text(
                                    text = "AUGMENTED COMM LINK",
                                    color = if (isLiveLinkActive) {
                                        NeonPalette.SWATCHES[2]
                                    } else {
                                        Color.Gray
                                    },
                                    fontSize = 8.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 2.sp
                                )

                                Spacer(modifier = Modifier.height(8.dp))

                                Row(
                                    modifier = Modifier
                                        .testTag(AckTags.DECK_SELECTOR)
                                        .helpTarget(AckTags.DECK_SELECTOR, primaryColor)
                                        .clickable {
                                            isDeckMenuOpen = !isDeckMenuOpen
                                            isProfileMenuOpen = false

                                            if (!isDeckMenuOpen) {
                                                exitDeckManageMode()
                                            }

                                            helpManager.onEvent(
                                                HelpEvent.Interacted(AckTags.DECK_SELECTOR)
                                            )
                                        },

                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "DECK: ",
                                        color = Color.Gray,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace,
                                        letterSpacing = 1.sp
                                    )

                                    Text(
                                        text = currentDeckName,
                                        color = primaryColor,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold
                                    )

                                    Text(
                                        text = if (isDeckMenuOpen) " [▲]" else " [▼]",
                                        color = primaryColor,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }


                                if (currentDeckType() == DeckType.MATRIX) {
                                    Spacer(modifier = Modifier.height(4.dp))

                                    Row(
                                        modifier = Modifier
                                            .testTag(AckTags.PROFILE_SELECTOR)
                                            .helpTarget(AckTags.PROFILE_SELECTOR, primaryColor)
                                            .clickable {
                                                isProfileMenuOpen = !isProfileMenuOpen
                                                isDeckMenuOpen = false

                                                helpManager.onEvent(
                                                    HelpEvent.Interacted(AckTags.PROFILE_SELECTOR)
                                                )
                                            },
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = "PROFILE: ",
                                            color = Color.Gray,
                                            fontSize = 10.sp,
                                            fontFamily = FontFamily.Monospace
                                        )

                                        val profileColor = if (currentProfile == "DEFAULT") {
                                            Color.White
                                        } else {
                                            primaryColor
                                        }

                                        Text(
                                            text = currentProfile,
                                            color = profileColor,
                                            fontSize = 10.sp,
                                            fontFamily = FontFamily.Monospace
                                        )

                                        Text(
                                            text = if (isProfileMenuOpen) " [▲]" else " [▼]",
                                            color = Color.Gray,
                                            fontSize = 10.sp,
                                            fontFamily = FontFamily.Monospace
                                        )
                                    }
                                }
                            }

                            Column(
                                horizontalAlignment = Alignment.End
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    if (isLiveLinkActive || watchStateLabel != "OFFLINE") {
                                        Column(
                                            horizontalAlignment = Alignment.End,
                                            modifier = Modifier.padding(end = 8.dp)
                                        ) {
                                            Text(
                                                text = watchStateLabel,
                                                color = if (watchStateLabel == "LOCKED") {
                                                    NeonPalette.SWATCHES[3]
                                                } else {
                                                    primaryColor
                                                },
                                                fontSize = 10.sp,
                                                fontFamily = FontFamily.Monospace,
                                                fontWeight = FontWeight.Bold
                                            )

                                            Text(
                                                text = "$watchPoseLabel [$watchTwistLevel]",
                                                color = Color.Gray,
                                                fontSize = 8.sp,
                                                fontFamily = FontFamily.Monospace
                                            )
                                        }
                                    }

                                    val statusColor = when {
                                        isLiveLinkActive -> NeonPalette.SWATCHES[2]
                                        watchStateLabel == "CRYO" -> Color.Blue
                                        else -> primaryColor.copy(alpha = 0.5f)
                                    }

                                    Box(
                                        modifier = Modifier
                                            .testTag(AckTags.LIVE_LINK)
                                            .helpTarget(AckTags.LIVE_LINK, primaryColor)
                                            .clickable {
                                                toggleLiveLink()
                                            }
                                            .padding(4.dp)
                                    ) {
                                        PulsingStatusBox(color = statusColor)
                                    }
                                }

                                Spacer(modifier = Modifier.height(12.dp))

                                Box(
                                    modifier = Modifier
                                        .testTag(AckTags.CONFIG_BUTTON)
                                        .helpTarget(AckTags.CONFIG_BUTTON, primaryColor)
                                        .border(
                                            1.dp,
                                            if (viewMode == "SETTINGS") Color.White else primaryColor,
                                            CutCornerShape(4.dp)
                                        )
                                        .clickable {
                                            viewMode = if (viewMode == "SETTINGS") {
                                                "TERMINAL"
                                            } else {
                                                "SETTINGS"
                                            }

                                            helpManager.onEvent(
                                                HelpEvent.Interacted(AckTags.CONFIG_BUTTON)
                                            )
                                        }
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                ) {
                                    Text(
                                        text = "PROTOCOL",
                                        color = if (viewMode == "SETTINGS") {
                                            Color.White
                                        } else {
                                            primaryColor
                                        },
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }

                                Spacer(modifier = Modifier.height(8.dp))

                                Box(
                                    modifier = Modifier
                                        .testTag(AckTags.HELP_BUTTON)
                                        .helpTarget(AckTags.HELP_BUTTON, primaryColor)
                                        .border(
                                            width = 1.dp,
                                            color = primaryColor,
                                            shape = CutCornerShape(4.dp)
                                        )
                                        .clickable {
                                            helpMenuCategory = null
                                            showHelpMenu = true
                                        }
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                ) {
                                    Text(
                                        text = "HELP",
                                        color = primaryColor,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }
                        }

                        AnimatedVisibility(
                            visible = isDeckMenuOpen,
                            enter = expandVertically(),
                            exit = shrinkVertically()
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 12.dp)
                                    .background(VoidBlack)
                                    .border(1.dp, primaryColor)
                                    .padding(8.dp)
                            ) {
                                if (!isDeckManageMode) {
                                    DeckItem(
                                        name = "SYSTEM DEFAULT // MATRIX",
                                        color = NeonPalette.DEFAULT_CYAN,
                                        isActive = currentDeckId == "DEFAULT"
                                    ) {
                                        activateDeck("DEFAULT", 0)
                                    }

                                    decks.forEach { deck ->
                                        DeckItem(
                                            name = buildString {
                                                append(deck.name)
                                                append(" // ")
                                                append(
                                                    deck.type.name.replace('_', ' ')
                                                )
                                            },
                                            color = NeonPalette.getColor(
                                                deck.colorIndex
                                            ),
                                            isActive = currentDeckId == deck.id
                                        ) {
                                            activateDeck(
                                                deck.id,
                                                deck.colorIndex
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(8.dp))

                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(
                                            8.dp
                                        )
                                    ) {
                                        DeckMenuAction(
                                            text = "+ CREATE DECK",
                                            color = primaryColor,
                                            modifier = Modifier
                                                .weight(1f)
                                                .testTag(AckTags.DECK_CREATE_BUTTON)
                                                .helpTarget(AckTags.DECK_CREATE_BUTTON, primaryColor)
                                        ) {
                                            showCreateDeckDialog = true
                                            isDeckMenuOpen = false

                                            helpManager.onEvent(
                                                HelpEvent.Interacted(AckTags.DECK_CREATE_BUTTON)
                                            )
                                        }

                                        DeckMenuAction(
                                            text = "MANAGE",
                                            color = Color.White,
                                            modifier = Modifier.weight(1f)
                                        ) {
                                            isDeckManageMode = true
                                            managedDeckId = null
                                        }
                                    }
                                } else {
                                    Text(
                                        text = "MANAGE DECKS",
                                        color = Color.White,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Black,
                                        letterSpacing = 1.sp
                                    )

                                    Spacer(modifier = Modifier.height(8.dp))

                                    Text(
                                        text = "SELECT A DECK TO RENAME, RECOLOR, OR DELETE",
                                        color = Color.Gray,
                                        fontSize = 9.sp,
                                        fontFamily = FontFamily.Monospace
                                    )

                                    Spacer(modifier = Modifier.height(10.dp))

                                    DeckManageItem(
                                        name = "SYSTEM DEFAULT // MATRIX",
                                        color = NeonPalette.DEFAULT_CYAN,
                                        selected = managedDeckId == "DEFAULT",
                                        locked = true
                                    ) {
                                        managedDeckId = "DEFAULT"
                                    }

                                    decks.forEach { deck ->
                                        DeckManageItem(
                                            name = buildString {
                                                append(deck.name)
                                                append(" // ")
                                                append(
                                                    deck.type.name.replace('_', ' ')
                                                )
                                            },
                                            color = NeonPalette.getColor(
                                                deck.colorIndex
                                            ),
                                            selected = managedDeckId == deck.id,
                                            locked = false
                                        ) {
                                            managedDeckId = deck.id
                                        }
                                    }

                                    val managedDeck = decks.find { deck ->
                                        deck.id == managedDeckId
                                    }

                                    if (managedDeckId == "DEFAULT") {
                                        Spacer(modifier = Modifier.height(12.dp))

                                        Text(
                                            text = "SYSTEM MATRIX DECK LOCKED",
                                            color = Color.Gray,
                                            fontSize = 10.sp,
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Bold
                                        )

                                        Spacer(modifier = Modifier.height(4.dp))

                                        Text(
                                            text = "THE PERMANENT MATRIX DECK " +
                                                    "CANNOT BE EDITED OR DELETED.",
                                            color = Color.Gray,
                                            fontSize = 9.sp,
                                            fontFamily = FontFamily.Monospace
                                        )
                                    } else if (managedDeck != null) {
                                        Spacer(modifier = Modifier.height(12.dp))

                                        DeckManageEditor(
                                            deck = managedDeck,
                                            primaryColor = primaryColor,
                                            onSave = { name, colorIndex ->
                                                val updated =
                                                    CommandRepository.updateDeckMeta(
                                                        context = context,
                                                        deckId = managedDeck.id,
                                                        name = name,
                                                        colorIndex = colorIndex
                                                    )

                                                if (updated != null) {
                                                    /*
                                                 * Reload the selector list
                                                 * immediately, without requiring
                                                 * the user to close and reopen it.
                                                 */
                                                    deckRevision++

                                                    if (
                                                        currentDeckId == updated.id
                                                    ) {
                                                        currentDeckName = updated.name
                                                        primaryColor = NeonPalette
                                                            .getColor(
                                                                updated.colorIndex
                                                            )
                                                    }

                                                    WatchSync.sendDeckList(context)
                                                }
                                            },
                                            onDelete = {
                                                showDeleteDeckConfirm = true
                                            }
                                        )
                                    }

                                    Spacer(modifier = Modifier.height(12.dp))

                                    DeckMenuAction(
                                        text = "EXIT MANAGE",
                                        color = Color.Gray,
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        exitDeckManageMode()
                                    }
                                }
                            }
                        }

                        AnimatedVisibility(
                            visible = isProfileMenuOpen &&
                                    currentDeckType() == DeckType.MATRIX,
                            enter = expandVertically(),
                            exit = shrinkVertically()
                        ) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 12.dp)
                                    .background(VoidBlack)
                                    .border(1.dp, Color.Gray)
                                    .padding(8.dp)
                            ) {
                                CommandRepository.PROFILES.forEach { profile ->
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable {
                                                CommandRepository.setActiveProfile(
                                                    context,
                                                    profile
                                                )

                                                currentProfile = profile
                                                isProfileMenuOpen = false

                                                WatchSync.sendProfileConfig(
                                                    context,
                                                    profile
                                                )

                                                helpManager.onEvent(
                                                    HelpEvent.ProfileWasSelected(AckTags.PROFILE_SELECTOR)
                                                )
                                            }
                                            .padding(vertical = 8.dp)
                                    ) {
                                        Text(
                                            text = profile,
                                            color = if (profile == currentProfile) {
                                                Color.White
                                            } else {
                                                Color.Gray
                                            },
                                            fontFamily = FontFamily.Monospace
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .testTag(AckTags.MATRIX_VIEW)
                            .border(
                                BorderStroke(1.dp, primaryColor),
                                CutCornerShape(topStart = 8.dp, bottomEnd = 8.dp)
                            )
                            .background(
                                Graphite.copy(alpha = 0.6f),
                                CutCornerShape(topStart = 8.dp, bottomEnd = 8.dp)
                            )
                    ) {
                        when (viewMode) {
                            "TERMINAL" -> TerminalView(logs)
                            "MATRIX" -> {
                                when (currentDeckType()) {
                                    DeckType.MATRIX -> {
                                        MatrixEditor(
                                            context = context,
                                            deckName = if (currentDeckId == "DEFAULT") {
                                                currentProfile
                                            } else {
                                                "$currentDeckName // $currentProfile"
                                            }
                                        ) { isOpen ->
                                            isDialogOpen = isOpen

                                            if (isOpen) {
                                                helpManager.onEvent(
                                                    HelpEvent.Interacted(AckTags.EDIT_NODE_DIALOG)
                                                )
                                            }
                                        }
                                    }

                                    DeckType.QUICK_ACTIONS -> {
                                        QuickActionsDeck(
                                            context = context,
                                            deckId = currentDeckId,
                                            primaryColor = primaryColor
                                        )
                                    }

                                    DeckType.EMERGENCY -> {
                                        EmergencyDeck(
                                            context = context,
                                            deckId = currentDeckId,
                                            primaryColor = primaryColor
                                        )
                                    }

                                    DeckType.EMOJI -> {
                                        EmojiDeck(
                                            context = context,
                                            deckId = currentDeckId,
                                            primaryColor = primaryColor
                                        )
                                    }

                                    DeckType.GIF -> {
                                        GifDeck(
                                            context = context,
                                            deckId = currentDeckId,
                                            primaryColor = primaryColor
                                        )
                                    }
                                }
                            }

                            "SETTINGS" -> SettingsView(
                                context = context,
                                primaryColor = primaryColor,
                                onUploadClick = {
                                    WatchSync.sendDeckList(context)

                                    helpManager.onEvent(
                                        HelpEvent.Interacted(AckTags.UPLOAD_BTN)
                                    )
                                }
                            )

                            "TYPE" -> TypeView(context, recentPhrases)
                            "AUDIO" -> AudioArchitectView(context, primaryColor, systemVoices)
                            "TARGETS" -> TargetView(context, primaryColor)
                            "GEO" -> GeoProtocolView(
                                context = context,
                                primaryColor = primaryColor
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))



                    if (viewMode != "SETTINGS") {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            NeonIconButton(
                                icon = BottomNavIcon.SPEAK,
                                description = "Matrix",
                                modifier = Modifier.weight(1f),
                                isActive = viewMode == "MATRIX",
                                mainColor = primaryColor
                            ) {
                                viewMode = "MATRIX"

                                helpManager.onEvent(
                                    HelpEvent.Interacted(AckTags.MODE_TOGGLE_BTN)
                                )
                            }

                            NeonIconButton(
                                icon = BottomNavIcon.TERMINAL,
                                description = "Logs",
                                modifier = Modifier
                                    .weight(1f)
                                    .testTag(AckTags.TERMINAL_VIEW)
                                    .helpTarget(AckTags.TERMINAL_VIEW, primaryColor),
                                isActive = viewMode == "TERMINAL",
                                mainColor = primaryColor
                            ) {
                                viewMode = "TERMINAL"
                            }

                            NeonIconButton(
                                icon = BottomNavIcon.CROSSHAIR,
                                description = "Targets",
                                modifier = Modifier
                                    .weight(1f)
                                    .testTag(AckTags.TARGETS_VIEW)
                                    .helpTarget(AckTags.TARGETS_VIEW, primaryColor),
                                isActive = viewMode == "TARGETS",
                                mainColor = primaryColor
                            ) {
                                viewMode = "TARGETS"
                            }

                            NeonIconButton(
                                icon = BottomNavIcon.MAP,
                                description = "Zones",
                                modifier = Modifier
                                    .weight(1f)
                                    .testTag(AckTags.GEO_VIEW)
                                    .helpTarget(AckTags.GEO_VIEW, primaryColor),
                                isActive = viewMode == "GEO",
                                mainColor = primaryColor
                            ) {
                                viewMode = "GEO"
                            }

                            NeonIconButton(
                                icon = BottomNavIcon.AUDIO,
                                description = "Audio Architect",
                                modifier = Modifier.weight(1f),
                                isActive = viewMode == "AUDIO",
                                mainColor = primaryColor
                            ) {
                                viewMode = "AUDIO"
                            }

                            NeonIconButton(
                                icon = BottomNavIcon.KEYBOARD,
                                description = "Type",
                                modifier = Modifier
                                    .weight(1f)
                                    .testTag(AckTags.MANUAL_INPUT_BTN)
                                    .helpTarget(AckTags.MANUAL_INPUT_BTN, primaryColor),
                                isActive = viewMode == "TYPE",
                                mainColor = primaryColor
                            ) {
                                viewMode = "TYPE"
                                helpManager.onEvent(
                                    HelpEvent.Interacted(AckTags.MANUAL_INPUT_BTN)
                                )
                            }
                        }
                    }

                    if (showHelpMenu) {
                        HelpMenuDialog(
                            modules = HelpRegistry.modules,
                            context = HelpContext(
                                viewMode = viewMode,
                                deckId = currentDeckId,
                                deckType = currentDeckType(),
                                profile = currentProfile
                            ),
                            primaryColor = primaryColor,
                            initialCategory = helpMenuCategory,
                            onDismiss = {
                                helpMenuCategory = null
                                showHelpMenu = false
                            },
                            onLaunch = { module ->
                                showHelpMenu = false
                                helpManager.start(module.id)
                            }
                        )
                    }


                    /*
             * These must be siblings of showTrainMenu, not children of it.
             */
                    if (showDeleteDeckConfirm) {
                        val deck = decks.find { it.id == managedDeckId }

                        if (deck != null) {
                            AlertDialog(
                                onDismissRequest = {
                                    showDeleteDeckConfirm = false
                                },
                                containerColor = Graphite,
                                title = {
                                    Text(
                                        text = "CONFIRM DECK DELETION",
                                        color = Color.Red,
                                        fontSize = 14.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Black
                                    )
                                },
                                text = {
                                    Text(
                                        text = "MARK ${deck.name} FOR DELETION?",
                                        color = Color.White,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                },
                                confirmButton = {
                                    Text(
                                        text = "[CONTINUE]",
                                        color = Color.Red,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier
                                            .clickable {
                                                showDeleteDeckConfirm = false
                                                showDeleteDeckFinalConfirm = true
                                            }
                                            .padding(8.dp)
                                    )
                                },
                                dismissButton = {
                                    Text(
                                        text = "[CANCEL]",
                                        color = Color.Gray,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace,
                                        modifier = Modifier
                                            .clickable {
                                                showDeleteDeckConfirm = false
                                            }
                                            .padding(8.dp)
                                    )
                                }
                            )
                        } else {
                            showDeleteDeckConfirm = false
                        }
                    }

                    if (showCreateDeckDialog) {
                        CreateDeckDialog(
                            primaryColor = primaryColor,
                            onDismiss = {
                                showCreateDeckDialog = false
                            },
                            onCreate = { name, colorIndex, type ->
                                val newDeck = CommandRepository.createDeck(
                                    context = context,
                                    name = name,
                                    colorIndex = colorIndex,
                                    type = type
                                )

                                /*
                             * Refresh the currently visible deck-selector
                             * list, then immediately activate the new deck.
                             */
                                deckRevision++

                                activateDeck(
                                    id = newDeck.id,
                                    colorIdx = newDeck.colorIndex
                                )

                                WatchSync.sendDeckList(context)

                                showCreateDeckDialog = false
                            }
                        )
                    }



                    if (showDeleteDeckFinalConfirm) {
                        val deck = decks.find { it.id == managedDeckId }

                        if (deck != null) {
                            AlertDialog(
                                onDismissRequest = {
                                    showDeleteDeckFinalConfirm = false
                                },
                                containerColor = Graphite,
                                title = {
                                    Text(
                                        text = "FINAL CONFIRMATION",
                                        color = Color.Red,
                                        fontSize = 14.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Black
                                    )
                                },
                                text = {
                                    Column {
                                        Text(
                                            text = "DELETE ${deck.name} PERMANENTLY?",
                                            color = Color.White,
                                            fontSize = 12.sp,
                                            fontFamily = FontFamily.Monospace
                                        )

                                        Spacer(modifier = Modifier.height(8.dp))

                                        Text(
                                            text = "THIS REMOVES THE DECK AND ITS " +
                                                    "LOCAL CONFIGURATION.",
                                            color = Color.Gray,
                                            fontSize = 10.sp,
                                            fontFamily = FontFamily.Monospace
                                        )

                                        if (deck.type == DeckType.GIF) {
                                            Spacer(modifier = Modifier.height(8.dp))

                                            Text(
                                                text = "GIF FILES BELONGING TO THIS " +
                                                        "DECK WILL ALSO BE REMOVED.",
                                                color = Color.Red.copy(alpha = 0.8f),
                                                fontSize = 10.sp,
                                                fontFamily = FontFamily.Monospace
                                            )
                                        }
                                    }
                                },
                                confirmButton = {
                                    Text(
                                        text = "[DELETE PERMANENTLY]",
                                        color = Color.Red,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier
                                            .clickable {
                                                val deletedDeckId = deck.id
                                                val wasActive =
                                                    currentDeckId == deletedDeckId

                                                val deleted =
                                                    CommandRepository.deleteDeck(
                                                        context = context,
                                                        deckId = deletedDeckId
                                                    )

                                                if (deleted) {
                                                    deckRevision++

                                                    WatchSync.sendDeckList(context)

                                                    if (wasActive) {
                                                        currentDeckId = "DEFAULT"
                                                        currentDeckName = "DEFAULT"
                                                        primaryColor =
                                                            NeonPalette.DEFAULT_CYAN
                                                        viewMode = "MATRIX"
                                                    }
                                                }

                                                exitDeckManageMode()
                                                isDeckMenuOpen = false
                                            }
                                            .padding(8.dp)
                                    )
                                },
                                dismissButton = {
                                    Text(
                                        text = "[CANCEL]",
                                        color = Color.Gray,
                                        fontSize = 12.sp,
                                        fontFamily = FontFamily.Monospace,
                                        modifier = Modifier
                                            .clickable {
                                                showDeleteDeckFinalConfirm = false
                                            }
                                            .padding(8.dp)
                                    )

                                }
                            )
                        } else {
                            showDeleteDeckFinalConfirm = false
                        }

                    }

                }
                if (helpManager.isActive) {
                    val coachPlacement = helpManager.currentStep?.coachPlacement
                        ?: HelpCoachPlacement.BOTTOM

                    val coachModifier = when (coachPlacement) {
                        HelpCoachPlacement.TOP -> {
                            Modifier
                                .align(Alignment.TopCenter)
                                .padding(
                                    start = 20.dp,
                                    top = 20.dp,
                                    end = 20.dp
                                )
                        }

                        HelpCoachPlacement.BOTTOM -> {
                            Modifier
                                .align(Alignment.BottomCenter)
                                .padding(
                                    start = 20.dp,
                                    end = 20.dp,
                                    bottom = 74.dp
                                )
                        }
                    }

                    HelpCoachPanel(
                        manager = helpManager,
                        primaryColor = primaryColor,
                        modifier = coachModifier
                    )
                }
            }
        }
    }
}
    @Composable
    private fun DeckMenuAction(
        text: String,
        color: Color,
        modifier: Modifier = Modifier,
        onClick: () -> Unit
    ) {
        Box(
            modifier = modifier
                .border(
                    width = 1.dp,
                    color = color,
                    shape = CutCornerShape(4.dp)
                )
                .clickable(onClick = onClick)
                .padding(12.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = text,
                color = color,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
        }
    }

    @Composable
    private fun DeckManageItem(
        name: String,
        color: Color,
        selected: Boolean,
        locked: Boolean,
        onClick: () -> Unit
    ) {
        val borderColor = if (selected) {
            Color.White
        } else {
            color
        }

        val labelColor = if (selected) {
            Color.White
        } else {
            color
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 3.dp)
                .border(
                    width = 1.dp,
                    color = borderColor,
                    shape = CutCornerShape(4.dp)
                )
                .clickable(onClick = onClick)
                .padding(horizontal = 10.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = name,
                color = labelColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f)
            )

            Text(
                text = if (locked) "[LOCKED]" else "[EDIT]",
                color = if (locked) Color.Gray else labelColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }


    @Composable
    private fun NeonIconButton(
        icon: BottomNavIcon,
        description: String,
        modifier: Modifier = Modifier,
        isActive: Boolean,
        mainColor: Color,
        onClick: () -> Unit
    ) {
        val borderColor = if (isActive) {
            Color.White
        } else {
            mainColor
        }

        val iconColor = if (isActive) {
            Color.White
        } else {
            mainColor
        }

        Box(
            modifier = modifier
                .height(44.dp)
                .semantics {
                    contentDescription = description
                }
                .border(
                    width = 1.dp,
                    color = borderColor,
                    shape = CutCornerShape(5.dp)
                )
                .background(
                    color = if (isActive) {
                        mainColor.copy(alpha = 0.16f)
                    } else {
                        Color.Transparent
                    },
                    shape = CutCornerShape(5.dp)
                )
                .clickable(onClick = onClick),
            contentAlignment = Alignment.Center
        ) {
            BottomNavGlyph(
                icon = icon,
                color = iconColor,
                modifier = Modifier.size(24.dp)
            )
        }
    }

    @Composable
    private fun BottomNavGlyph(
        icon: BottomNavIcon,
        color: Color,
        modifier: Modifier = Modifier
    ) {
        Canvas(modifier = modifier) {
            when (icon) {
                BottomNavIcon.SPEAK -> {
                    drawSpeakingHead(color)
                }

                BottomNavIcon.TERMINAL -> {
                    drawTerminalWindow(color)
                }

                BottomNavIcon.CROSSHAIR -> {
                    drawCrosshair(color)
                }

                BottomNavIcon.MAP -> {
                    drawMap(color)
                }

                BottomNavIcon.AUDIO -> {
                    drawAudioArchitect(color)
                }

                BottomNavIcon.KEYBOARD -> {
                    drawKeyboard(color)
                }
            }
        }
    }

    private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawSpeakingHead(
        color: Color
    ) {
        val stroke = Stroke(width = size.minDimension * 0.09f)
        val width = size.width
        val height = size.height

        /*
         * Angular side-profile head. The three lines are speech transmission
         * waves, rather than a generic microphone symbol.
         */
        val head = androidx.compose.ui.graphics.Path().apply {
            moveTo(width * 0.43f, height * 0.15f)
            lineTo(width * 0.61f, height * 0.15f)
            lineTo(width * 0.70f, height * 0.31f)
            lineTo(width * 0.66f, height * 0.47f)
            lineTo(width * 0.76f, height * 0.55f)
            lineTo(width * 0.65f, height * 0.63f)
            lineTo(width * 0.61f, height * 0.82f)
            lineTo(width * 0.37f, height * 0.82f)
            lineTo(width * 0.29f, height * 0.68f)
            lineTo(width * 0.29f, height * 0.31f)
            close()
        }

        drawPath(
            path = head,
            color = color,
            style = stroke
        )

        drawLine(
            color = color,
            start = Offset(width * 0.47f, height * 0.43f),
            end = Offset(width * 0.57f, height * 0.43f),
            strokeWidth = stroke.width,
            cap = StrokeCap.Square
        )

        val waveStartX = width * 0.80f

        drawLine(
            color = color,
            start = Offset(waveStartX, height * 0.36f),
            end = Offset(width * 0.91f, height * 0.30f),
            strokeWidth = stroke.width,
            cap = StrokeCap.Square
        )

        drawLine(
            color = color,
            start = Offset(waveStartX, height * 0.51f),
            end = Offset(width * 0.96f, height * 0.51f),
            strokeWidth = stroke.width,
            cap = StrokeCap.Square
        )

        drawLine(
            color = color,
            start = Offset(waveStartX, height * 0.66f),
            end = Offset(width * 0.91f, height * 0.72f),
            strokeWidth = stroke.width,
            cap = StrokeCap.Square
        )
    }

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawAudioArchitect(
    color: Color
) {
    val strokeWidth = size.minDimension * 0.08f
    val width = size.width
    val height = size.height

    /*
     * Three vertical control channels with adjustable nodes.
     * This represents an audio mixer / DSP architecture rather than
     * a basic speaker or media-playback button.
     */
    val leftX = width * 0.25f
    val centerX = width * 0.50f
    val rightX = width * 0.75f

    val topY = height * 0.14f
    val bottomY = height * 0.86f
    val nodeRadius = size.minDimension * 0.115f

    drawLine(
        color = color,
        start = Offset(leftX, topY),
        end = Offset(leftX, bottomY),
        strokeWidth = strokeWidth,
        cap = StrokeCap.Square
    )

    drawLine(
        color = color,
        start = Offset(centerX, topY),
        end = Offset(centerX, bottomY),
        strokeWidth = strokeWidth,
        cap = StrokeCap.Square
    )

    drawLine(
        color = color,
        start = Offset(rightX, topY),
        end = Offset(rightX, bottomY),
        strokeWidth = strokeWidth,
        cap = StrokeCap.Square
    )

    drawCircle(
        color = color,
        radius = nodeRadius,
        center = Offset(leftX, height * 0.35f),
        style = Stroke(width = strokeWidth)
    )

    drawCircle(
        color = color,
        radius = nodeRadius,
        center = Offset(centerX, height * 0.67f),
        style = Stroke(width = strokeWidth)
    )

    drawCircle(
        color = color,
        radius = nodeRadius,
        center = Offset(rightX, height * 0.47f),
        style = Stroke(width = strokeWidth)
    )
}

    private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawTerminalWindow(
        color: Color
    ) {
        val strokeWidth = size.minDimension * 0.09f
        val left = size.width * 0.10f
        val top = size.height * 0.16f
        val width = size.width * 0.80f
        val height = size.height * 0.68f

        drawRect(
            color = color,
            topLeft = Offset(left, top),
            size = Size(width, height),
            style = Stroke(width = strokeWidth)
        )

        drawLine(
            color = color,
            start = Offset(left, top + height * 0.22f),
            end = Offset(left + width, top + height * 0.22f),
            strokeWidth = strokeWidth
        )

        drawCircle(
            color = color,
            radius = strokeWidth * 0.45f,
            center = Offset(left + width * 0.13f, top + height * 0.11f)
        )

        drawCircle(
            color = color,
            radius = strokeWidth * 0.45f,
            center = Offset(left + width * 0.24f, top + height * 0.11f)
        )

        drawLine(
            color = color,
            start = Offset(left + width * 0.20f, top + height * 0.48f),
            end = Offset(left + width * 0.34f, top + height * 0.59f),
            strokeWidth = strokeWidth,
            cap = StrokeCap.Square
        )

        drawLine(
            color = color,
            start = Offset(left + width * 0.34f, top + height * 0.59f),
            end = Offset(left + width * 0.20f, top + height * 0.70f),
            strokeWidth = strokeWidth,
            cap = StrokeCap.Square
        )

        drawLine(
            color = color,
            start = Offset(left + width * 0.46f, top + height * 0.70f),
            end = Offset(left + width * 0.72f, top + height * 0.70f),
            strokeWidth = strokeWidth,
            cap = StrokeCap.Square
        )
    }

    private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawCrosshair(
        color: Color
    ) {
        val strokeWidth = size.minDimension * 0.09f
        val center = Offset(size.width / 2f, size.height / 2f)
        val radius = size.minDimension * 0.30f

        drawCircle(
            color = color,
            radius = radius,
            center = center,
            style = Stroke(width = strokeWidth)
        )

        drawCircle(
            color = color,
            radius = size.minDimension * 0.07f,
            center = center
        )

        drawLine(
            color = color,
            start = Offset(center.x, size.height * 0.05f),
            end = Offset(center.x, center.y - radius),
            strokeWidth = strokeWidth
        )

        drawLine(
            color = color,
            start = Offset(center.x, center.y + radius),
            end = Offset(center.x, size.height * 0.95f),
            strokeWidth = strokeWidth
        )

        drawLine(
            color = color,
            start = Offset(size.width * 0.05f, center.y),
            end = Offset(center.x - radius, center.y),
            strokeWidth = strokeWidth
        )

        drawLine(
            color = color,
            start = Offset(center.x + radius, center.y),
            end = Offset(size.width * 0.95f, center.y),
            strokeWidth = strokeWidth
        )
    }

    private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawMap(
        color: Color
    ) {
        val strokeWidth = size.minDimension * 0.08f
        val width = size.width
        val height = size.height

        val mapPath = androidx.compose.ui.graphics.Path().apply {
            moveTo(width * 0.12f, height * 0.22f)
            lineTo(width * 0.38f, height * 0.12f)
            lineTo(width * 0.63f, height * 0.22f)
            lineTo(width * 0.88f, height * 0.12f)
            lineTo(width * 0.88f, height * 0.78f)
            lineTo(width * 0.63f, height * 0.88f)
            lineTo(width * 0.38f, height * 0.78f)
            lineTo(width * 0.12f, height * 0.88f)
            close()
        }

        drawPath(
            path = mapPath,
            color = color,
            style = Stroke(width = strokeWidth)
        )

        drawLine(
            color = color,
            start = Offset(width * 0.38f, height * 0.12f),
            end = Offset(width * 0.38f, height * 0.78f),
            strokeWidth = strokeWidth
        )

        drawLine(
            color = color,
            start = Offset(width * 0.63f, height * 0.22f),
            end = Offset(width * 0.63f, height * 0.88f),
            strokeWidth = strokeWidth
        )

        drawCircle(
            color = color,
            radius = size.minDimension * 0.08f,
            center = Offset(width * 0.51f, height * 0.49f)
        )
    }

    private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawKeyboard(
        color: Color
    ) {
        val strokeWidth = size.minDimension * 0.08f
        val left = size.width * 0.08f
        val top = size.height * 0.22f
        val width = size.width * 0.84f
        val height = size.height * 0.56f

        drawRect(
            color = color,
            topLeft = Offset(left, top),
            size = Size(width, height),
            style = Stroke(width = strokeWidth)
        )

        val keyWidth = width * 0.13f
        val keyHeight = height * 0.16f
        val startX = left + width * 0.12f
        val firstRowY = top + height * 0.18f

        repeat(4) { index ->
            val x = startX + index * width * 0.18f

            drawRect(
                color = color,
                topLeft = Offset(x, firstRowY),
                size = Size(keyWidth, keyHeight)
            )

            drawRect(
                color = color,
                topLeft = Offset(x, firstRowY + height * 0.25f),
                size = Size(keyWidth, keyHeight)
            )
        }

        drawRect(
            color = color,
            topLeft = Offset(left + width * 0.25f, top + height * 0.69f),
            size = Size(width * 0.50f, keyHeight)
        )
    }

    @Composable
    private fun DeckManageEditor(
        deck: DeckMeta,
        primaryColor: Color,
        onSave: (String, Int) -> Unit,
        onDelete: () -> Unit
    ) {
        var editedName by remember(deck.id, deck.name) {
            mutableStateOf(deck.name)
        }

        var selectedColorIndex by remember(deck.id, deck.colorIndex) {
            mutableIntStateOf(deck.colorIndex)
        }

        val selectedColor = NeonPalette.getColor(selectedColorIndex)

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    width = 1.dp,
                    color = selectedColor,
                    shape = CutCornerShape(4.dp)
                )
                .padding(10.dp)
        ) {
            Text(
                text = "EDIT: ${deck.type.name.replace('_', ' ')}",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = editedName,
                onValueChange = { value ->
                    editedName = value.take(40)
                },
                label = {
                    Text(
                        text = "DECK NAME",
                        fontFamily = FontFamily.Monospace
                    )
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = "UI COLOR",
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(6.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                NeonPalette.SWATCHES.forEachIndexed { index, color ->
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(28.dp)
                            .border(
                                width = if (index == selectedColorIndex) {
                                    2.dp
                                } else {
                                    1.dp
                                },
                                color = if (index == selectedColorIndex) {
                                    Color.White
                                } else {
                                    color
                                },
                                shape = CutCornerShape(4.dp)
                            )
                            .background(
                                color.copy(alpha = 0.25f),
                                CutCornerShape(4.dp)
                            )
                            .clickable {
                                selectedColorIndex = index
                            }
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                DeckMenuAction(
                    text = "SAVE",
                    color = selectedColor,
                    modifier = Modifier.weight(1f)
                ) {
                    onSave(
                        editedName,
                        selectedColorIndex
                    )
                }

                DeckMenuAction(
                    text = "DELETE",
                    color = Color.Red,
                    modifier = Modifier.weight(1f)
                ) {
                    onDelete()
                }
            }
        }
    }

