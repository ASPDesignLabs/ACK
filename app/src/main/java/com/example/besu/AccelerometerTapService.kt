package com.example.besu

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.core.app.NotificationCompat
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * Phone-side kill switch: shake the phone to immediately stop whatever ACK
 * is currently saying/showing. Complements the watch's tap-to-cancel --
 * that only helps if you catch a mistaken pose before it fires, this helps
 * once something has already started playing, wherever the mistake came
 * from (a watch misfire, a wrong tap on the phone, anything).
 *
 * Detection requires [REQUIRED_PULSES] separate high-acceleration samples
 * within [SHAKE_WINDOW_MS] of each other, so a single bump or the phone
 * being set down hard doesn't trigger it -- only a genuine back-and-forth
 * shake does.
 */
class AccelerometerTapService : Service(), SensorEventListener {
    private var sensorManager: SensorManager? = null
    private var accelerometer: Sensor? = null
    private var vibrator: Vibrator? = null

    // Phone-tunable via Settings -> SHAKE_THRESHOLD ("ack_prefs").
    private var shakeThreshold = DEFAULT_SHAKE_THRESHOLD

    private var pulseCount = 0
    private var windowStartTime = 0L
    private var lastShakeTime = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(1338, createNotification())

        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        accelerometer = sensorManager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator

        loadConfig()

        accelerometer?.let {
            sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }

        broadcastLog("SHAKE KILL SWITCH ARMED", "SYS")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "UPDATE_CONFIG") {
            loadConfig()
        }
        return START_STICKY
    }

    private fun loadConfig() {
        val prefs = getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)
        shakeThreshold = prefs.getFloat("SHAKE_THRESHOLD", DEFAULT_SHAKE_THRESHOLD)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event?.sensor?.type != Sensor.TYPE_ACCELEROMETER) {
            return
        }

        val magnitude = sqrt(
            event.values[0] * event.values[0] +
                event.values[1] * event.values[1] +
                event.values[2] * event.values[2]
        )

        // Gravity-subtracted -- so holding the phone still, or tilting it
        // slowly, never counts as a pulse regardless of orientation.
        val netMagnitude = abs(magnitude - SensorManager.GRAVITY_EARTH)

        if (netMagnitude < shakeThreshold) {
            return
        }

        val now = SystemClock.uptimeMillis()

        if (now - lastShakeTime < SHAKE_COOLDOWN_MS) {
            return
        }

        if (now - windowStartTime > SHAKE_WINDOW_MS) {
            pulseCount = 0
            windowStartTime = now
        }

        pulseCount++

        if (pulseCount >= REQUIRED_PULSES) {
            pulseCount = 0
            lastShakeTime = now
            triggerKillSwitch()
        }
    }

    private fun triggerKillSwitch() {
        broadcastLog("SHAKE DETECTED -- KILLING OUTPUT", "INPUT")

        // Haptic-only confirmation -- an audible beep right after cutting
        // off a mistaken utterance is its own small announcement.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(
                VibrationEffect.createOneShot(120, VibrationEffect.DEFAULT_AMPLITUDE)
            )
        }

        startService(
            Intent(this, OutputService::class.java).setAction("KILL_OUTPUT")
        )
        startService(
            Intent(this, VisualPromptService::class.java)
                .setAction(VisualPromptService.ACTION_FORCE_CLEAR)
        )

        // Lets a calibration/training screen show a live "detected" pulse
        // using the real detector -- not a separate simulated one.
        sendBroadcast(Intent(ACTION_SHAKE_DETECTED).setPackage(packageName))
    }

    private fun broadcastLog(msg: String, type: String) {
        val intent = Intent("ACK_LOG")
        intent.setPackage(packageName)
        intent.putExtra("msg", msg)
        intent.putExtra("type", type)
        sendBroadcast(intent)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) { }

    override fun onDestroy() {
        sensorManager?.unregisterListener(this)
        super.onDestroy()
    }

    private fun createNotification(): Notification {
        val chanId = "ack_shake_kill"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(
                    chanId,
                    "ACK Shake Kill Switch",
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }
        return NotificationCompat.Builder(this, chanId)
            .setContentTitle("ACK // SHAKE ARMED")
            .setContentText("Shake the phone to stop output")
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode_off)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_SHAKE_DETECTED = "com.example.besu.ACTION_SHAKE_DETECTED"

        const val DEFAULT_SHAKE_THRESHOLD = 15f

        private const val REQUIRED_PULSES = 3
        private const val SHAKE_WINDOW_MS = 700L
        private const val SHAKE_COOLDOWN_MS = 1500L
    }
}
