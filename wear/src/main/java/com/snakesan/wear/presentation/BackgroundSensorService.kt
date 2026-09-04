package com.example.besu.wear

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.IBinder
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import androidx.compose.ui.graphics.toArgb
import androidx.core.app.NotificationCompat
import com.example.besu.wear.theme.NeonPalette
import com.google.android.gms.wearable.Wearable
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.sqrt

class BackgroundSensorService : Service(), SensorEventListener {

    private lateinit var sensorManager: SensorManager

    private var accelerometer: Sensor? = null
    private var gyroscope: Sensor? = null
    private var vibrator: Vibrator? = null

    // LOGIC STATE
    private enum class State { IDLE, GATE_READY, ARMED, POSE_LOCKED, COOLDOWN, CRYO }
    private enum class Pose { NONE, ARM_UP, STOP, HANDSHAKE }

    private var currentState = State.IDLE
    private var currentPose = Pose.NONE
    private var twistCount = 0
    private var commandTwistCount = 0
    private var stateStartTime = 0L
    private var lastModifierTime = 0L

    // TRAINING MODE (set by the phone via /sys/training_mode)
    // OFF   - normal live behavior.
    // PACED - guided pose walkthroughs. Real output is suppressed AND the
    //         ARMED/POSE_LOCKED auto-timeouts are suspended so a learner has time
    //         to read/hear each step before the state machine moves on.
    // LIVE  - Training Ground free practice. Real output is suppressed but timing
    //         is untouched, so gestures behave exactly as they would live.
    private enum class TrainingMode { OFF, PACED, LIVE }
    private var trainingMode = TrainingMode.OFF

    private fun isPacedTraining() = trainingMode == TrainingMode.PACED

    // Normal live timings.
    private val armedTimeoutMs = 6000L
    private val poseLockedTimeoutMs = 6000L
    private val normalFireDelayMs = 800L

    // Paced training stretches the hold-to-fire window so there's time to react
    // to the instruction before the pose auto-fires.
    private val pacedFireDelayMs = 4000L
    
    // TARGET STATE
    private var activeTargetIndex = -1 // -1 = None/Cleared

    // PHYSICS CONFIG
    private var lastX = 0f; private var lastY = 0f; private var lastZ = 0f
    private var activeTwistThreshold = 7.0f
    private var activePoseThreshold = 6.0f

    // --- GYROSCOPE TWIST DETECTION ---

    // Keep this false for an accelerometer-only baseline.
// Turn it true after confirming gyro behavior on the Pixel Watch 4.
    private var useGyroForTwist = true

    // Typical starting point. Units are radians per second.
// Tune this on-device after logging real values.
    private var gyroTwistThreshold = 10.5f

    // Lower than the trigger threshold so a sustained rotation does not trigger
// over and over on every sensor event.
    private var gyroReleaseThreshold = 1.5f

    private var gyroTwistLatched = false
    private var lastGyroTwistTime = 0L

    private val gyroTwistCooldownMs = 180L

    // --- IPC RECEIVER (Remote Control) ---
    private val controlReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val action = intent?.action ?: return
            
            // KILL SWITCH
            if (action == "com.snakesan.overseer.KILL_COMMAND") {
                Log.d("ACK_BG", "Kill command received.")
                feedback(500)
                stopSelf()
                return
            }

            // REMOTE CONTROLS (From Overseer Face)
            if (action == "com.snakesan.overseer.ACK_CONTROL") {
                val cmdRaw = intent.getStringExtra("CMD") ?: ""


                // 1. Handle Explicit Target Set (From Overlay List)
                if (cmdRaw.startsWith("SET_TARGET:")) {
                    try {
                        val index = cmdRaw.substringAfter(":").toInt()

                        // OLD: This triggered both Haptics AND Audio (Sfx.MODIFIER)
                        // setTargetExplicit(index)

                        // NEW: Manually update state, send sync, but use HAPTIC ONLY feedback
                        activeTargetIndex = index
                        broadcastStatus()
                        sendToPhone("/sys/req_target", activeTargetIndex.toString().toByteArray(Charsets.UTF_8))

                        // Haptic only (no TechSynth enum passed)
                        feedback(50)

                    } catch(e: Exception) {
                        Log.e("ACK_BG", "Parse error", e)
                    }
                }
                // 2. Handle Standard Commands
                else {
                    when(cmdRaw) {
                        "NEXT", "NEXT_DECK" -> cycleDeck(true)
                        "PREV", "PREV_DECK" -> cycleDeck(false)
                        "CRYO_TOGGLE" -> {
                            if (currentState == State.CRYO) wakeFromCryo() else enterCryo()
                        }
                    }
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(99, createNotification())

        val filter = IntentFilter().apply {
            addAction("com.snakesan.overseer.KILL_COMMAND")
            addAction("com.snakesan.overseer.ACK_CONTROL")
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(controlReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(controlReceiver, filter)
        }

        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager

        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)

        vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator

        if (gyroscope == null) {
            Log.w(
                "ACK_GYRO",
                "No gyroscope detected. Using accelerometer twist fallback.",
            )
        }

        val prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)
        activeTwistThreshold = prefs.getFloat("cfg_twist", 7.0f)
        activePoseThreshold = prefs.getFloat("cfg_pose", 6.0f)

        registerSensors(
            accelerometerRate = SensorManager.SENSOR_DELAY_UI,
            gyroscopeRate = SensorManager.SENSOR_DELAY_UI,
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            "UPDATE_CONFIG" -> {
                 val prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)
                 activeTwistThreshold = prefs.getFloat("cfg_twist", 7.0f)
                 activePoseThreshold = prefs.getFloat("cfg_pose", 6.0f)
            }
            "ACTION_ENTER_CRYO" -> enterCryo()
            "ACTION_WAKE_CRYO" -> wakeFromCryo()
            PoseActions.ACTION_SET_TRAINING_MODE -> {
                val raw = intent.getStringExtra(PoseActions.EXTRA_TRAINING_MODE) ?: "OFF"
                trainingMode = try {
                    TrainingMode.valueOf(raw)
                } catch (e: IllegalArgumentException) {
                    TrainingMode.OFF
                }
                Log.d("ACK_BG", "Training mode set to $trainingMode")
                broadcastStatus()
            }
        }
        return START_STICKY
    }

    private fun registerSensors(
        accelerometerRate: Int = SensorManager.SENSOR_DELAY_UI,
        gyroscopeRate: Int = SensorManager.SENSOR_DELAY_UI,
    ) {
        accelerometer?.let { sensor ->
            sensorManager.registerListener(
                this,
                sensor,
                accelerometerRate,
            )
        }

        if (useGyroForTwist) {
            gyroscope?.let { sensor ->
                sensorManager.registerListener(
                    this,
                    sensor,
                    gyroscopeRate,
                )
            }
        }
    }
    
    private fun enterCryo() {
        if (currentState != State.CRYO) {
            currentState = State.CRYO
            sensorManager.unregisterListener(this)
            broadcastStatus()
            feedback(300, TechSynth.Sfx.LOCK)
        }
    }

    private fun wakeFromCryo() {
        if (currentState == State.CRYO) {
            currentState = State.IDLE

            setSensorSpeed(
                accelerometerRate = SensorManager.SENSOR_DELAY_NORMAL,
                gyroscopeRate = SensorManager.SENSOR_DELAY_UI,
            )

            broadcastStatus()
            feedback(100, TechSynth.Sfx.UNLOCK)
        }
    }

    // --- DECK LOGIC ---
    private fun cycleDeck(next: Boolean) {
        if (currentState == State.CRYO) return

        val prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)
        val rawList = prefs.getString("cached_deck_list", "") ?: ""
        
        val decks = rawList.split(";").mapNotNull { 
            val p = it.split("|")
            if(p.size == 3) DeckLite(p[0], p[1], p[2].toIntOrNull()?:0) else null 
        }
        
        if (decks.isEmpty()) return

        val currentName = prefs.getString("active_deck_name", "DEFAULT")
        val currentIdx = decks.indexOfFirst { it.name == currentName }.coerceAtLeast(0)
        
        val newIdx = if (next) {
            (currentIdx + 1) % decks.size
        } else {
            if (currentIdx - 1 < 0) decks.size - 1 else currentIdx - 1
        }
        
        val target = decks[newIdx]
        
        prefs.edit().putString("active_deck_name", target.name)
            .putInt("active_color_idx", target.colorIdx).apply()
            
        broadcastStatus(overrideDeck = target.name, overrideColor = target.colorIdx)
        
        sendToPhone("/sys/req_deck_change", target.id.toByteArray(Charsets.UTF_8))
        feedback(10, TechSynth.Sfx.TICK)
    }
    
    // --- TARGET LOGIC ---
    
    private fun setTargetExplicit(index: Int) {
        activeTargetIndex = index
        
        // 1. Notify Overseer immediately (Instant Visuals)
        broadcastStatus()
        
        // 2. Tell Phone (Logic Source of Truth)
        // 0-7 or -1
        sendToPhone("/sys/req_target", activeTargetIndex.toString().toByteArray(Charsets.UTF_8))
        
        feedback(20, TechSynth.Sfx.MODIFIER)
    }

    // Gyro Twist Control

    private fun isGyroTwist(
        x: Float,
        y: Float,
        z: Float,
        time: Long,
    ): Boolean {
        val angularVelocity = sqrt(x * x + y * y + z * z)

        if (angularVelocity < gyroReleaseThreshold) {
            gyroTwistLatched = false
            return false
        }

        val exceedsThreshold = angularVelocity >= gyroTwistThreshold
        val canTriggerAgain = time - lastGyroTwistTime >= gyroTwistCooldownMs

        if (
            exceedsThreshold &&
            !gyroTwistLatched &&
            canTriggerAgain
        ) {
            gyroTwistLatched = true
            lastGyroTwistTime = time

            Log.d(
                "ACK_GYRO",
                "Twist detected. Angular velocity: $angularVelocity rad/s",
            )

            return true
        }

        return false
    }

    // --- SENSOR LOGIC ---
    override fun onSensorChanged(event: SensorEvent?) {
        event ?: return

        val time = System.currentTimeMillis()

        when (event.sensor.type) {
            Sensor.TYPE_GYROSCOPE -> {
                if (!useGyroForTwist) {
                    return
                }

                val isTwist = isGyroTwist(
                    x = event.values[0],
                    y = event.values[1],
                    z = event.values[2],
                    time = time,
                )

                advanceMotionState(time)

                if (isTwist) {
                    handleTwist(time)
                }
            }

            Sensor.TYPE_ACCELEROMETER -> {
                val x = event.values[0]
                val y = event.values[1]
                val z = event.values[2]

                val deltaX = abs(x - lastX)
                val deltaY = abs(y - lastY)
                val deltaZ = abs(z - lastZ)

                val maxDelta = max(deltaX, max(deltaY, deltaZ))

                lastX = x
                lastY = y
                lastZ = z

                advanceMotionState(time)

                // Accelerometer detection remains as a fallback only.
                if (!useGyroForTwist) {
                    val isTwist = maxDelta > activeTwistThreshold

                    if (isTwist) {
                        handleTwist(time)
                    }
                }

                handlePose(x, y, z, time)
            }
        }
    }

    private fun advanceMotionState(time: Long) {
        when (currentState) {
            State.GATE_READY -> {
                if (time - stateStartTime > 800L) {
                    feedback(20, TechSynth.Sfx.TICK)
                    transition(State.ARMED, time)
                }
            }

            State.ARMED -> {
                // Paced training suspends this timeout entirely -- otherwise a
                // learner mid-instruction gets silently bumped back to IDLE.
                if (!isPacedTraining() && time - stateStartTime > armedTimeoutMs) {
                    transition(State.IDLE, time)
                }
            }

            State.POSE_LOCKED -> {
                if (!isPacedTraining() && time - stateStartTime > poseLockedTimeoutMs) {
                    transition(State.IDLE, time)
                    return
                }

                val fireDelay = if (isPacedTraining()) pacedFireDelayMs else normalFireDelayMs
                if (time - stateStartTime > fireDelay) {
                    fireCommand()
                }
            }

            State.COOLDOWN -> {
                if (time - stateStartTime > 2000L) {
                    transition(State.IDLE, time)
                }
            }

            State.IDLE,
            State.CRYO -> Unit
        }
    }

    private fun handleTwist(time: Long) {
        when (currentState) {
            State.IDLE -> {
                if (time - lastModifierTime > 1200L) {
                    twistCount = 0
                }

                twistCount++
                lastModifierTime = time

                if (twistCount < 3) {
                    feedback(15)
                }

                if (twistCount >= 3) {
                    feedback(100, TechSynth.Sfx.UNLOCK)
                    transition(State.GATE_READY, time)
                }
            }

            State.POSE_LOCKED -> {
                if (time - lastModifierTime <= 400L) {
                    return
                }

                commandTwistCount++
                lastModifierTime = time
                stateStartTime = time

                feedback(20, TechSynth.Sfx.MODIFIER)
                broadcastStatus()
            }

            State.GATE_READY,
            State.ARMED,
            State.COOLDOWN,
            State.CRYO -> Unit
        }
    }

    private fun handlePose(
        x: Float,
        y: Float,
        z: Float,
        time: Long,
    ) {
        if (currentState != State.ARMED) {
            return
        }

        val absX = abs(x)
        val absY = abs(y)
        val absZ = abs(z)

        when {
            absX > activePoseThreshold &&
                    absX > absY &&
                    absX > absZ -> {
                setPose(Pose.ARM_UP, time)
            }

            absZ > activePoseThreshold &&
                    absZ > absX &&
                    absZ > absY -> {
                setPose(Pose.STOP, time)
            }

            absY > activePoseThreshold &&
                    absY > absX &&
                    absY > absZ -> {
                setPose(Pose.HANDSHAKE, time)
            }
        }
    }

    private fun transition(newState: State, time: Long) {
        currentState = newState
        stateStartTime = time

        // Reset counters logic (Keep existing)
        if (newState == State.IDLE) {
            twistCount = 0; commandTwistCount = 0; currentPose = Pose.NONE
        }

        // --- NEW: DYNAMIC POLLING SWITCH ---
        when (newState) {
            State.IDLE -> {
                setSensorSpeed(
                    accelerometerRate = SensorManager.SENSOR_DELAY_NORMAL,
                    gyroscopeRate = SensorManager.SENSOR_DELAY_UI,
                )
            }

            State.GATE_READY -> {
                setSensorSpeed(
                    accelerometerRate = SensorManager.SENSOR_DELAY_UI,
                    gyroscopeRate = SensorManager.SENSOR_DELAY_GAME,
                )
            }

            State.ARMED -> {
                setSensorSpeed(
                    accelerometerRate = SensorManager.SENSOR_DELAY_UI,
                    gyroscopeRate = SensorManager.SENSOR_DELAY_UI,
                )
            }

            State.POSE_LOCKED -> {
                setSensorSpeed(
                    accelerometerRate = SensorManager.SENSOR_DELAY_UI,
                    gyroscopeRate = SensorManager.SENSOR_DELAY_UI,
                )
            }

            State.COOLDOWN -> {
                setSensorSpeed(
                    accelerometerRate = SensorManager.SENSOR_DELAY_NORMAL,
                    gyroscopeRate = SensorManager.SENSOR_DELAY_NORMAL,
                )
            }

            State.CRYO -> {
                sensorManager.unregisterListener(this)
            }
        }

        broadcastStatus()
    }

    private fun setPose(pose: Pose, time: Long) {
        currentPose = pose
        commandTwistCount = 0
        feedback(50, TechSynth.Sfx.LOCK)
        transition(State.POSE_LOCKED, time)
    }
    // Shifting of Sensor Polling

    private fun setSensorSpeed(
        accelerometerRate: Int,
        gyroscopeRate: Int = accelerometerRate,
    ) {
        sensorManager.unregisterListener(this)

        registerSensors(
            accelerometerRate = accelerometerRate,
            gyroscopeRate = gyroscopeRate,
        )

        Log.d(
            "ACK_PWR",
            "Sensor gear shifted: accel=$accelerometerRate gyro=$gyroscopeRate",
        )
    }
    private fun fireCommand() {
        val path = when (currentPose) {
            Pose.ARM_UP -> when (commandTwistCount) { 0 -> "/gesture/thumbsup"; 1 -> "/gesture/wave"; 2 -> "/gesture/ask_name"; else -> "/gesture/name" }
            Pose.STOP -> when (commandTwistCount) { 0 -> "/gesture/stop"; 1 -> "/gesture/wait"; 2 -> "/gesture/break"; else -> "/gesture/leave_alone" }
            Pose.HANDSHAKE -> when (commandTwistCount) { 0 -> "/gesture/nice"; 1 -> "/gesture/same"; 2 -> "/gesture/sorry_wait"; else -> "/gesture/meet_pleasure" }
            else -> "/gesture/generic"
        }

        // In any training mode (paced or live), the pose/fire cycle is reported
        // via status telemetry only (see broadcastStatus) -- no real command is
        // sent, so nothing is spoken and no deck/target state changes.
        if (trainingMode == TrainingMode.OFF) {
            sendToPhone(path)
        }

        feedback(150, TechSynth.Sfx.FIRE)
        transition(State.COOLDOWN, System.currentTimeMillis())
    }

    private fun sendToPhone(path: String, payload: ByteArray? = null) {
        Wearable.getNodeClient(this).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> Wearable.getMessageClient(this).sendMessage(node.id, path, payload) }
        }
    }

    // Consolidated Broadcast Logic
    private fun broadcastStatus(overrideDeck: String? = null, overrideColor: Int? = null) {
        val prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)
        val deckName = overrideDeck ?: prefs.getString("active_deck_name", "DEFAULT")
        val deckColor = overrideColor ?: NeonPalette.getColor(prefs.getInt("active_color_idx", 0)).toArgb()
        
        val intent = Intent("com.snakesan.overseer.UPDATE_STATUS")
        intent.putExtra("source_app", "ACK_SENSOR")
        intent.putExtra("sensor_state", currentState.name)
        intent.putExtra("sensor_pose", currentPose.name)
        intent.putExtra("sensor_mod", commandTwistCount)
        
        // Deck Info (Redundant but safe for UI sync)
        intent.putExtra("active_deck", deckName)
        intent.putExtra("deck_color", deckColor)
        
        // NEW: Send Active Target to Overseer
        val targetLabel = if(activeTargetIndex == -1) "NONE" else TargetCache.getLabel(activeTargetIndex)
        intent.putExtra("active_target", targetLabel)

        sendBroadcast(intent)

        // Phone-facing status telemetry (drives the header readout and the
        // ARMED/POSE_ID/MODIFIED/FIRE HelpEvents). Sent on every status change,
        // training or not.
        sendToPhone(
            "/sys/status_update",
            "${currentState.wireLabel()},${currentPose.wireLabel()},$commandTwistCount"
                .toByteArray(Charsets.UTF_8)
        )
    }

    // Maps internal enum names onto the short codes the phone app (WearListenerService/
    // MainActivity) expects over /sys/status_update, decoupling the wire contract from
    // these enums' own names.
    private fun State.wireLabel(): String = when (this) {
        State.IDLE -> "IDLE"
        State.GATE_READY -> "GATE_READY"
        State.ARMED -> "ARMED"
        State.POSE_LOCKED -> "LOCKED"
        State.COOLDOWN -> "COOLDOWN"
        State.CRYO -> "CRYO"
    }

    private fun Pose.wireLabel(): String = when (this) {
        Pose.NONE -> "---"
        Pose.ARM_UP -> "ID"
        Pose.STOP -> "DEF"
        Pose.HANDSHAKE -> "CON"
    }

    private fun feedback(duration: Long, sfx: TechSynth.Sfx? = null) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE))
        }
        sfx?.let { TechSynth.play(it) }
    }
    
    private fun createNotification(): Notification {
        val chanId = "ack_sensor_bg"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(chanId, "ACK Motion Core", NotificationManager.IMPORTANCE_LOW)
            )
        }
        return NotificationCompat.Builder(this, chanId)
            .setContentTitle("ACK Core Active")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .build()
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        TechSynth.release()

        try {
            unregisterReceiver(controlReceiver)
        } catch (_: Exception) {
        }

        sensorManager.unregisterListener(this)
        super.onDestroy()
    }
}
