package com.example.besu

import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import kotlin.math.abs

class AccelerometerTapService : Service(), SensorEventListener {
    private var sensorManager: SensorManager? = null
    private var accelerometer: Sensor? = null
    private var vibrator: Vibrator? = null
    private var toneGenerator: ToneGenerator? = null

    private var tapCount = 0
    private var lastTapTime = 0L
    private val tapTimeout = 600L
    private val requiredTaps = 3

    // Detection thresholds
    private val tapThreshold = 5f
    private var lastZ = 0f

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        accelerometer = sensorManager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        
        try {
            toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 100)
        } catch (e: Exception) { e.printStackTrace() }

        // We rely on the OutputService to keep the app alive, so we don't strictly 
        // need another Foreground notification here if OutputService is running, 
        // but for safety in Android 14+, it's good practice to register the listener.
        accelerometer?.let {
            sensorManager?.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
        
        broadcastLog("TAP SENSOR ARMED", "SYS")
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event?.sensor?.type == Sensor.TYPE_ACCELEROMETER) {
            val z = event.values[2]
            val zDelta = abs(z - lastZ)
            
            if (zDelta > tapThreshold) {
                handleTap()
            }
            lastZ = z
        }
    }

    private fun handleTap() {
        val currentTime = SystemClock.uptimeMillis()

        if (currentTime - lastTapTime <= tapTimeout) {
            tapCount++
        } else {
            tapCount = 1
        }

        lastTapTime = currentTime

        if (tapCount >= requiredTaps) {
            tapCount = 0
            triggerAction()
        }
    }

    private fun triggerAction() {
        // 1. Log to Terminal
        broadcastLog("PHYSICAL TAP DETECTED", "INPUT")

        // 2. Physical Feedback (Haptic + Sound)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE))
        }
        toneGenerator?.startTone(ToneGenerator.TONE_PROP_ACK)
        
        // 3. Optional: Trigger a TTS macro via broadcast if you want the phone to speak
        // For now, we just acknowledge the input.
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
        toneGenerator?.release()
        super.onDestroy()
    }
}
