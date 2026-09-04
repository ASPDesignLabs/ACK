package com.example.besu

import android.content.Context
import android.content.Intent
import com.google.android.gms.wearable.Wearable

object WatchSync {
    
    // --- EXISTING FUNCTIONS ---

    // --- NEW: TARGET LIST SYNC ---
    fun sendTargetList(context: Context) {
        // 1. Get List from Repository
        val targets = TargetRepository.getTargets(context)

        // 2. Format: "0:LABEL|1:LABEL"
        val sb = StringBuilder()
        targets.forEachIndexed { i, slot ->
            if (i > 0) sb.append("|")
            sb.append("${slot.index}:${slot.label}")
        }

        val payload = sb.toString().toByteArray(Charsets.UTF_8)

        // 3. Send
        sendMessage(context, "/sys/target_list", payload, "TARGET LIST SYNC")
    }

    fun sendDeckConfig(context: Context, colorIndex: Int, deckName: String) {
        val path = "/sys/deck_update"
        val data = "$colorIndex,$deckName".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data)
    }

    fun sendAudioConfig(context: Context, theme: Int, volume: Float) {
        val path = "/sys/audio_config"
        val data = "$theme,$volume".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "AUDIO SYNC")
    }

    fun sendPowerConfig(context: Context, minutes: Int) {
        val path = "/sys/pwr_config"
        val data = "$minutes".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "POWER SYNC")
    }

    fun sendProfileConfig(context: Context, profileName: String) {
        val path = "/sys/context_update"
        val data = profileName.toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data)
    }

    fun sendDeckList(context: Context) {
        val decks = CommandRepository.getDecks(context)
        val sb = StringBuilder("DEFAULT|DEFAULT|0")
        
        decks.forEach { deck ->
            sb.append(";")
            sb.append("${deck.id}|${deck.name}|${deck.colorIndex}")
        }
        
        val data = sb.toString().toByteArray(Charsets.UTF_8)
        sendMessage(context, "/sys/deck_list", data, "DECK LIST SYNC")
    }

    // --- CROWN SENSITIVITY ---
    fun sendCrownSensitivity(context: Context, sensitivityIndex: Int) {
        val path = "/sys/crown_sens"
        val data = sensitivityIndex.toString().toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "SENSITIVITY SYNC")
    }

    // --- NEW: MOTION PHYSICS CONFIG ---
    fun sendMotionConfig(context: Context, twistThreshold: Float, poseThreshold: Float) {
        val path = "/sys/motion_config"
        // Payload: "TWIST,POSE" e.g. "7.0,6.0"
        val data = "$twistThreshold,$poseThreshold".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "PHYSICS SYNC")
    }

    // --- GESTURE TRAINING MODE ---
    // mode is one of "OFF" / "PACED" / "LIVE":
    //   OFF   - normal live behavior.
    //   PACED - guided pose walkthroughs. Suppresses real output and suspends the
    //           watch's auto-timeouts so a learner has time to read each step.
    //   LIVE  - Training Ground. Suppresses real output but leaves timing alone.
    fun sendTrainingMode(context: Context, mode: String) {
        val path = "/sys/training_mode"
        val data = mode.toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "TRAINING MODE $mode")
    }

    // Helper to reduce boilerplate
    private fun sendMessage(context: Context, path: String, data: ByteArray?, logMsg: String? = null) {
        Wearable.getNodeClient(context).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> 
                Wearable.getMessageClient(context).sendMessage(node.id, path, data)
            }
            if (logMsg != null) broadcastLog(context, logMsg, "SYS")
        }
    }

    private fun broadcastLog(context: Context, msg: String, type: String) {
        val intent = Intent("ACK_LOG")
        intent.setPackage(context.packageName)
        intent.putExtra("msg", msg)
        intent.putExtra("type", type)
        context.sendBroadcast(intent)
    }
}
