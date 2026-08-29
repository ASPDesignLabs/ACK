package com.example.besu.wear

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.CountDownTimer
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import android.view.WindowManager
import androidx.activity.compose.setContent
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.fragment.app.FragmentActivity
import androidx.wear.ambient.AmbientModeSupport
import com.example.besu.wear.theme.NeonPalette
import com.google.android.gms.wearable.MessageClient
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.system.exitProcess

// Simple data class for Watch-side deck cache
data class DeckLite(val id: String, val name: String, val colorIdx: Int)

class MainActivity : FragmentActivity(), MessageClient.OnMessageReceivedListener, AmbientModeSupport.AmbientCallbackProvider {

    private var vibrator: Vibrator? = null
    private lateinit var prefs: SharedPreferences

    // HARDCODED PROFILES (Matches Phone)
    private val PROFILES = listOf("DEFAULT", "WORK", "HIGH_STRESS", "SOCIAL", "BUILDER")

    // UI VISUAL STATE (Driven by Broadcasts)
    private var uiState by mutableStateOf("CRYO")
    private var uiPose by mutableStateOf("OFFLINE")
    private var uiTwist by mutableIntStateOf(0)

    
    // DECK & THEME STATE
    private var activePrimaryColor by mutableStateOf(NeonPalette.DEFAULT_CYAN)
    private var activeDeckLabel by mutableStateOf("DEFAULT")
    private var activeProfileLabel by mutableStateOf("DEFAULT")
    
    // --- NAVIGATION STATE ---
    private val availableDecks = mutableStateListOf<DeckLite>()
    private var crownThresholdPx by mutableFloatStateOf(96f)

    // Deck Selection
    private var isSelectingDeck by mutableStateOf(false)
    private var selectorIndex by mutableIntStateOf(0)
    
    // Context Selection
    private var isSelectingContext by mutableStateOf(false)
    private var contextIndex by mutableIntStateOf(0)
    
    // --- TARGET SELECTION STATE ---
    private var isTargetMenuVisible by mutableStateOf(false)
    private var activeTargetIndex by mutableIntStateOf(-1) // -1 = None/Clear
    
    // TELEMETRY
    private var isStreaming = false
    
    // CRYO UI STATE
    private var currentStateName = "CRYO"
    private var isCryoMenuVisible by mutableStateOf(false)
    private var cryoDurationMinutes by mutableIntStateOf(5)
    private var cryoRemainingSeconds by mutableLongStateOf(0L)
    private var cryoTimer: CountDownTimer? = null
    
    // AUTO-CRYO
    private val inactivityHandler = Handler(Looper.getMainLooper())
    private var inactivityTimeout = 10 * 60 * 1000L 
    private val enterAutoCryoRunnable = Runnable { enterCryostasis(-1) }

    // --- KILL SWITCH RECEIVER ---
    private val killReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == "com.snakesan.overseer.KILL_COMMAND") {
                Log.d("ACK_UI", "Kill command received. Closing UI.")
                finishAffinity()
                exitProcess(0) 
            }
        }
    }

    // RECEIVER FOR SENSOR SERVICE UPDATES
    private val sensorReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == "com.snakesan.overseer.UPDATE_STATUS" && intent.getStringExtra("source_app") == "ACK_SENSOR") {
                val state = intent.getStringExtra("sensor_state") ?: "IDLE"
                val pose = intent.getStringExtra("sensor_pose") ?: "NONE"
                val mods = intent.getIntExtra("sensor_mod", 0)

                // Update UI Variables
                currentStateName = state
                uiState = state
                uiPose = pose
                uiTwist = mods
                
                // Keep screen on if active (ARMED/LOCKED)
                updateScreenPower(state != "IDLE" && state != "COOLDOWN" && state != "CRYO")
                
                // Reset Auto-Cryo timer on any activity
                if (state != "IDLE" && state != "CRYO") resetInactivityTimer()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AmbientModeSupport.attach(this)
        updateScreenPower(true)
        
        prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)
        cryoDurationMinutes = prefs.getInt("last_cryo_duration", 5)
        
        // Init Defaults
        activePrimaryColor = NeonPalette.getColor(prefs.getInt("active_color_idx", 0))
        activeDeckLabel = prefs.getString("active_deck_name", "DEFAULT") ?: "DEFAULT"
        activeProfileLabel = prefs.getString("active_profile_name", "DEFAULT") ?: "DEFAULT"
        
        val savedSens = prefs.getInt("crown_sensitivity_level", 2)
        crownThresholdPx = (savedSens * 48f)

        loadCachedDecks()
        
        @Suppress("DEPRECATION")
        vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator

        // --- START THE BACKGROUND BRAIN ---
        // val serviceIntent = Intent(this, BackgroundSensorService::class.java)
        // if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        //     startForegroundService(serviceIntent)
        // } else {
        //     startService(serviceIntent)
        // }

        // resetInactivityTimer()

        setContent {
            val focusRequester = remember { FocusRequester() }
            val scope = rememberCoroutineScope()
            var scrollAccumulator by remember { mutableFloatStateOf(0f) }
            
            // Timestamps for auto-commit
            var lastRotaryAction by remember { mutableLongStateOf(0L) }
            var lastContextAction by remember { mutableLongStateOf(0L) }
            
            var hapticJob by remember { mutableStateOf<Job?>(null) }
            
            // Auto-Commits
            LaunchedEffect(lastRotaryAction) {
                if (isSelectingDeck) { delay(1000); commitDeckSelection() }
            }
            LaunchedEffect(lastContextAction) {
                if (isSelectingContext) { delay(3000); commitContextSelection() }
            }

            LaunchedEffect(Unit) { focusRequester.requestFocus() }

            Box(modifier = Modifier
                .fillMaxSize()
                // ONLY ENABLE ROTARY IF TARGET MENU IS NOT VISIBLE
                .onRotaryScrollEvent {
                    if (isCryo()) {
                        return@onRotaryScrollEvent false
                    }

                    if (isTargetMenuVisible) {
                        return@onRotaryScrollEvent false
                    }

                    if (availableDecks.isNotEmpty()) {
                        // Wake up Deck Selector
                        if (!isSelectingDeck && !isSelectingContext) {
                            isSelectingDeck = true
                            val currIdx = availableDecks.indexOfFirst { it.name == activeDeckLabel }
                            selectorIndex = if(currIdx != -1) currIdx else 0
                            lastRotaryAction = System.currentTimeMillis() 
                            feedback(10)
                            
                            hapticJob?.cancel()
                            hapticJob = scope.launch { delay(200); playIdentityHaptics(selectorIndex + 1) }
                            return@onRotaryScrollEvent true
                        }

                        if (isSelectingContext) lastContextAction = System.currentTimeMillis()
                        if (isSelectingDeck) lastRotaryAction = System.currentTimeMillis()

                        hapticJob?.cancel() 
                        scrollAccumulator += it.verticalScrollPixels
                        val threshold = crownThresholdPx 
                        
                        if (abs(scrollAccumulator) > threshold) {
                            val direction = if (scrollAccumulator > 0) 1 else -1
                            
                            if (isSelectingContext) {
                                val newIndex = (contextIndex + direction) % PROFILES.size
                                contextIndex = if (newIndex < 0) newIndex + PROFILES.size else newIndex
                                hapticJob = scope.launch { delay(200); playIdentityHaptics(contextIndex + 1) }
                            } else {
                                val newIndex = (selectorIndex + direction) % availableDecks.size
                                selectorIndex = if (newIndex < 0) newIndex + availableDecks.size else newIndex
                                val nextDeck = availableDecks.getOrNull(selectorIndex)
                                if (nextDeck != null) activePrimaryColor = NeonPalette.getColor(nextDeck.colorIdx)
                                hapticJob = scope.launch { delay(400); playIdentityHaptics(selectorIndex + 1) }
                            }

                            feedback(20) 
                            scrollAccumulator -= (direction * threshold)
                        }
                        
                        resetInactivityTimer()
                        true
                    } else false
                }
                .focusRequester(focusRequester)
                .focusable()
            ) {
                AckRootContainer(
                    onDoubleTap = { exitPauseOrCryo() },
                    onTap = { 
                        if (isSelectingDeck) {
                            feedback(50, TechSynth.Sfx.TICK)
                            commitDeckSelection(silent = true) 
                            isSelectingDeck = false; isSelectingContext = true
                            val currCtx = PROFILES.indexOf(activeProfileLabel)
                            contextIndex = if(currCtx != -1) currCtx else 0
                            lastContextAction = System.currentTimeMillis() 
                            hapticJob?.cancel()
                            hapticJob = scope.launch { delay(400); playIdentityHaptics(contextIndex + 1) }
                        } else if (isSelectingContext) {
                            commitContextSelection()
                        } else {
                            val now = System.currentTimeMillis()
                            if ((now - lastRotaryAction > 5000L) && (now - lastContextAction > 5000L)) {
                                handleTap() 
                            }
                        }
                    },
                    onLongPress = {
                        if (!isCryo() && !isCryoMenuVisible && !isTargetMenuVisible) {
                            isCryoMenuVisible = true
                            feedback(50, TechSynth.Sfx.TICK)
                        }
                    },
                    onTapTapHold = {
                        if (!isCryo()) {
                            isTargetMenuVisible = true
                            feedback(100, TechSynth.Sfx.MODIFIER)
                        }
                    }
                ) {
                    if (isSelectingContext) {
                        AckWatchHud("PROFILE 0${contextIndex + 1}", "ROTARY INPUT", 0, activePrimaryColor, activeDeckLabel, PROFILES[contextIndex])
                    } 
                    else if (isSelectingDeck) {
                        val deck = availableDecks.getOrNull(selectorIndex)
                        if (deck != null) {
                            AckWatchHud("DECK 0${selectorIndex + 1}", "TAP FOR CTX >", 0, NeonPalette.getColor(deck.colorIdx), deck.name, activeProfileLabel)
                        }
                    } else {
                        // Render State from Background Service
                        AckWatchHud(uiState, uiPose, uiTwist, activePrimaryColor, activeDeckLabel, activeProfileLabel)
                    }
                    
                    //if (currentStateName == "CRYO") {
                    //    val displayTime = if (cryoRemainingSeconds == -1L) null else cryoRemainingSeconds
                    //    CryoHud("CRYOSTASIS", "DOUBLE TAP TO WAKE", displayTime)
                    //}
                    // else if (currentStateName == "PAUSED") CryoHud("SYSTEM PAUSED", "TAP TO RESUME", null)
                    
                    // --- TARGET MENU OVERLAY ---
                    if (isTargetMenuVisible) {
                        TargetSelectionOverlay(
                            activeTargetIndex = activeTargetIndex,
                            // FIX: Now accepts index AND sticky boolean
                            onSelect = { index, isSticky ->
                                activeTargetIndex = index
                                isTargetMenuVisible = false
                                
                                // Stronger feedback if locked
                                if (isSticky) feedback(300, TechSynth.Sfx.LOCK) 
                                else feedback(50, TechSynth.Sfx.TICK)
                                
                                sendTargetSelection(index, isSticky)
                            },
                            onDismiss = { isTargetMenuVisible = false }
                        )
                    }

                    if (isCryoMenuVisible) {
                        CryoMenuOverlay(
                            minutes = cryoDurationMinutes,
                            onIncrement = { cryoDurationMinutes = (cryoDurationMinutes + 5).coerceAtMost(60); feedback(20); resetInactivityTimer() },
                            onDecrement = { cryoDurationMinutes = (cryoDurationMinutes - 5).coerceAtLeast(5); feedback(20); resetInactivityTimer() },
                            onConfirm = { enterCryostasis(cryoDurationMinutes) }
                        )
                    }
                }
            }
        }
    }

    // --- BROADCASTS & STATE ---

    override fun onResume() { 
        super.onResume()
        Wearable.getMessageClient(this).addListener(this)
        resetInactivityTimer()
        updateScreenPower(!(currentStateName == "CRYOSTASIS" || currentStateName == "PAUSED"))
        broadcastDeckToHUD()
        
        val sensorFilter = IntentFilter("com.snakesan.overseer.UPDATE_STATUS")
        val killFilter = IntentFilter("com.snakesan.overseer.KILL_COMMAND")
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(sensorReceiver, sensorFilter, Context.RECEIVER_EXPORTED)
            registerReceiver(killReceiver, killFilter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(sensorReceiver, sensorFilter)
            registerReceiver(killReceiver, killFilter)
        }
    }
    
    override fun onPause() { 
        super.onPause()
        Wearable.getMessageClient(this).removeListener(this)
        try { 
            unregisterReceiver(sensorReceiver) 
            unregisterReceiver(killReceiver)
        } catch(e:Exception){}
    }

    override fun onDestroy() {
        TechSynth.release()
        super.onDestroy()
    }

    // --- NEURAL INPUT ---
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.data?.let { uri ->
            if (uri.scheme == "besu") {
                handleNeuralInput(uri)
            }
        }
    }

    private fun handleNeuralInput(uri: Uri) {
        when (uri.host) {
            "cryo" -> {
                val min = uri.getQueryParameter("min")?.toIntOrNull() ?: 10
                enterCryostasis(min)
                feedback(50, TechSynth.Sfx.LOCK)
            }
            "deck" -> {
                val name = uri.getQueryParameter("name") ?: "DEFAULT"
                activeProfileLabel = name
                prefs.edit().putString("active_profile_name", name).apply()
                feedback(100, TechSynth.Sfx.UNLOCK)
                sendContextRequest(name)
                broadcastDeckToHUD()
            }
            "pause" -> {
                handleTap() 
            }
        }
    }

    private fun broadcastDeckToHUD(overrideDeck: String? = null, overrideContext: String? = null, overrideColor: Int? = null) {
        val deckName = overrideDeck ?: activeDeckLabel
        val contextName = overrideContext ?: activeProfileLabel
        val colorInt = overrideColor ?: activePrimaryColor.toArgb()
        
        val intent = Intent("com.snakesan.overseer.UPDATE_STATUS")
        intent.setPackage("com.snakesan.overseer") 
        intent.putExtra("source_app", "ACK")
        intent.putExtra("active_deck", deckName.uppercase()) 
        intent.putExtra("active_context", contextName.uppercase())
        intent.putExtra("theme_color", colorInt)
        intent.putExtra("deck_color", colorInt)
        sendBroadcast(intent)
    }

    // --- DECK LOGIC ---
    private fun commitDeckSelection(silent: Boolean = false) {
        val selectedDeck = availableDecks.getOrNull(selectorIndex)
        if (selectedDeck != null) {
            isSelectingDeck = false
            activeDeckLabel = selectedDeck.name
            sendDeckRequest(selectedDeck.id)
            if (!silent) feedback(150, TechSynth.Sfx.LOCK)
            broadcastDeckToHUD()
        } else {
            isSelectingDeck = false
        }
    }

    private fun commitContextSelection() {
        val selectedContext = PROFILES.getOrNull(contextIndex)
        if (selectedContext != null) {
            isSelectingContext = false
            activeProfileLabel = selectedContext
            sendContextRequest(selectedContext)
            feedback(150, TechSynth.Sfx.LOCK)
            broadcastDeckToHUD()
        } else {
            isSelectingContext = false
        }
    }

    private suspend fun playIdentityHaptics(number: Int) {
        val fives = number / 5; val ones = number % 5
        repeat(fives) { feedback(150); delay(200) }
        repeat(ones) { feedback(50); delay(150) }
    }

    private fun loadCachedDecks() {
        val raw = prefs.getString("cached_deck_list", "") ?: ""
        parseDeckList(raw)
    }

    private fun parseDeckList(raw: String) {
        availableDecks.clear()
        var foundValid = false
        if (raw.isNotEmpty()) {
            val list = raw.split(";").mapNotNull { entry ->
                val parts = entry.split("|")
                if (parts.size == 3) {
                    DeckLite(parts[0], parts[1], parts[2].toIntOrNull() ?: 0)
                } else null
            }
            if (list.isNotEmpty()) {
                availableDecks.addAll(list)
                foundValid = true
            }
        }
        if (!foundValid) {
            availableDecks.add(DeckLite("DEFAULT", "DEFAULT", 0))
        }
    }

    private fun sendDeckRequest(deckId: String) {
        val data = deckId.toByteArray(Charsets.UTF_8)
        Wearable.getNodeClient(this).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> Wearable.getMessageClient(this).sendMessage(node.id, "/sys/req_deck_change", data) }
        }
    }

    private fun sendContextRequest(profileName: String) {
        val data = profileName.toByteArray(Charsets.UTF_8)
        Wearable.getNodeClient(this).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> Wearable.getMessageClient(this).sendMessage(node.id, "/sys/req_context_change", data) }
        }
    }
    
    // --- UPDATED: TARGET REQUEST ---
    private fun sendTargetSelection(index: Int, isSticky: Boolean) {
        // Payload: "INDEX|IS_STICKY"
        val payload = "$index|$isSticky"
        val data = payload.toByteArray(Charsets.UTF_8)
        
        Wearable.getNodeClient(this).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> 
                Wearable.getMessageClient(this).sendMessage(node.id, "/sys/req_target", data) 
            }
        }
    }

    // --- UTILS ---
    private fun resetInactivityTimer() {
        if (currentStateName == "CRYO") return
        inactivityHandler.removeCallbacks(enterAutoCryoRunnable)
        inactivityHandler.postDelayed(enterAutoCryoRunnable, inactivityTimeout)
    }

    private fun feedback(duration: Long, sfx: TechSynth.Sfx? = null) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) vibrator?.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE))
        sfx?.let { TechSynth.play(it) }
    }

    private fun updateScreenPower(keepOn: Boolean) {
        if (keepOn) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun isCryo(): Boolean {
        return currentStateName == "CRYO"
    }

    private fun presentCryoUi() {
        currentStateName = "CRYO"
        uiState = "CRYO"
        uiPose = "OFFLINE"
        uiTwist = 0

        isSelectingDeck = false
        isSelectingContext = false
        isTargetMenuVisible = false
        isCryoMenuVisible = false

        updateScreenPower(false)
    }

    private fun requestPoseListening() {
        val intent = Intent(this, BackgroundSensorService::class.java).apply {
            action = PoseActions.ACTION_ENABLE_POSE_LISTENING
            putExtra(
                PoseActions.EXTRA_DURATION_MS,
                PoseActions.DEFAULT_LISTENING_DURATION_MS,
            )
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        currentStateName = "PTT_READY"
        uiState = "PTT_READY"
        uiPose = "LISTENING"
        uiTwist = 0

        updateScreenPower(true)
        feedback(80, TechSynth.Sfx.UNLOCK)
    }

    private fun handleTap() {
        when {
            isCryoMenuVisible -> {
                isCryoMenuVisible = false
            }

            isTargetMenuVisible -> {
                isTargetMenuVisible = false
            }

            isCryo() -> {
                requestPoseListening()
            }

            else -> {
                enterCryostasis(minutes = -1)
            }
        }
    }

    private fun exitPauseOrCryo() {
        cryoTimer?.cancel()
        requestPoseListening()
    }

    private fun enterCryostasis(minutes: Int = -1) {
        presentCryoUi()

        val intent = Intent(this, BackgroundSensorService::class.java).apply {
            action = PoseActions.ACTION_ENTER_CRYO
        }

        startService(intent)
        feedback(150, TechSynth.Sfx.LOCK)
    }

    override fun getAmbientCallback(): AmbientModeSupport.AmbientCallback = MyAmbientCallback()
    private inner class MyAmbientCallback : AmbientModeSupport.AmbientCallback() {
        override fun onEnterAmbient(ambientDetails: Bundle?) { super.onEnterAmbient(ambientDetails); updateScreenPower(false) }
        override fun onExitAmbient() { super.onExitAmbient(); updateScreenPower(true) }
    }

    override fun onMessageReceived(e: MessageEvent) { 
        when (e.path) {
            "/sys/audio_config" -> {
                try { val p = String(e.data).split(","); if(p.size==2) { TechSynth.updateConfig(p[0].toInt(), p[1].toFloat()); feedback(100, TechSynth.Sfx.TICK) } } catch(_:Exception){}
            }
            "/sys/pwr_config" -> {
                try {
                    val minutes = String(e.data).toInt()
                    inactivityTimeout = minutes * 60 * 1000L
                    resetInactivityTimer()
                    feedback(50, TechSynth.Sfx.TICK)
                } catch(_:Exception){}
            }
            "/sys/stream_start" -> { isStreaming = true; feedback(50, TechSynth.Sfx.TICK) }
            "/sys/stream_stop" -> { isStreaming = false; feedback(50, TechSynth.Sfx.LOCK) }
            
            "/sys/deck_update" -> {
                try {
                    val parts = String(e.data).split(",")
                    if (parts.size >= 2) {
                        val idx = parts[0].toInt()
                        val name = parts[1]
                        val newColor = NeonPalette.getColor(idx)
                        activePrimaryColor = newColor
                        activeDeckLabel = name
                        prefs.edit().putInt("active_color_idx", idx).putString("active_deck_name", name).apply()
                        feedback(50, TechSynth.Sfx.UNLOCK)
                        broadcastDeckToHUD(overrideDeck = name, overrideColor = newColor.toArgb())
                    }
                } catch(e: Exception) { Log.e("ACK_MSG", "Deck Update Error", e) }
            }
            
            "/sys/context_update" -> {
                val name = String(e.data)
                activeProfileLabel = name
                prefs.edit().putString("active_profile_name", name).apply()
                feedback(30, TechSynth.Sfx.TICK) 
                broadcastDeckToHUD(overrideContext = name)
            }
            
            "/sys/deck_list" -> {
                val raw = String(e.data)
                prefs.edit().putString("cached_deck_list", raw).apply()
                parseDeckList(raw)
            }
            
            "/sys/crown_sens" -> {
                try {
                    val level = String(e.data).toInt().coerceIn(1, 5)
                    crownThresholdPx = (level * 48f)
                    prefs.edit().putInt("crown_sensitivity_level", level).apply()
                    feedback(50, TechSynth.Sfx.TICK) 
                } catch(e: Exception) {}
            }

            "/sys/motion_config" -> {
                try {
                    val parts = String(e.data).split(",")
                    if (parts.size == 2) {
                        prefs.edit()
                            .putFloat("cfg_twist", parts[0].toFloat())
                            .putFloat("cfg_pose", parts[1].toFloat())
                            .apply()
                        
                        val i = Intent(this, BackgroundSensorService::class.java)
                        i.action = "UPDATE_CONFIG"
                        startService(i)
                        
                        feedback(50, TechSynth.Sfx.MODIFIER)
                    }
                } catch(e: Exception) {}
            }
            
            "/sys/target_list" -> {
                val raw = String(e.data, Charsets.UTF_8)
                TargetCache.update(raw)
                feedback(20)
            }
        }
    }
}
