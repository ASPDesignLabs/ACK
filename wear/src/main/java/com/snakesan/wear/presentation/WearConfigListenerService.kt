package com.example.besu.wear

import android.content.Context
import android.content.Intent
import com.example.besu.wear.theme.NeonPalette
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService
import androidx.compose.ui.graphics.toArgb
import android.util.Log

class WearConfigListenerService : WearableListenerService() {

    override fun onMessageReceived(messageEvent: MessageEvent) {
        val prefs = getSharedPreferences("AckPrefs", Context.MODE_PRIVATE)

        when (messageEvent.path) {
            // 1. DECK UPDATE (Contains Name + Color Index)
            // Payload: "0,NETRUNNER"
            "/sys/deck_update" -> {
                try {
                    val dataStr = String(messageEvent.data, Charsets.UTF_8)
                    val parts = dataStr.split(",")
                    
                    if (parts.size >= 2) {
                        val idx = parts[0].toInt()
                        val deckName = parts[1]

                        // A. Save locally to ACK App
                        prefs.edit()
                            .putInt("active_color_idx", idx)
                            .putString("active_deck_name", deckName)
                            .apply()

                        // B. Calculate Color Integer
                        val colorInt = NeonPalette.getColor(idx).toArgb()

                        // C. Get Context (Profile) to ensure payload is complete
                        val currentContext = prefs.getString("active_profile_name", "DEFAULT") ?: "DEFAULT"

                        // D. BROADCAST TO OVERSEER
                        broadcastToOverseer(deckName, currentContext, colorInt)
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }

            // 2. CONTEXT UPDATE (Contains Profile Name only)
            // Payload: "WORK"
            "/sys/context_update" -> {
                val contextName = String(messageEvent.data, Charsets.UTF_8)
                
                // A. Save locally
                prefs.edit().putString("active_profile_name", contextName).apply()

                // B. Retrieve existing Deck info to complete the payload
                val deckName = prefs.getString("active_deck_name", "DEFAULT") ?: "DEFAULT"
                val colorIdx = prefs.getInt("active_color_idx", 0)
                val colorInt = NeonPalette.getColor(colorIdx).toArgb()

                // C. BROADCAST TO OVERSEER
                broadcastToOverseer(deckName, contextName, colorInt)
            }

            // 3. TRAINING MODE (Phone toggles this while a gesture-training
            // HelpModule is active). Payload: "1" or "0"
            "/sys/training_mode" -> {
                val enabled = String(messageEvent.data, Charsets.UTF_8) == "1"

                val serviceIntent = Intent(this, BackgroundSensorService::class.java).apply {
                    action = PoseActions.ACTION_SET_TRAINING_MODE
                    putExtra(PoseActions.EXTRA_TRAINING_MODE, enabled)
                }

                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    startForegroundService(serviceIntent)
                } else {
                    startService(serviceIntent)
                }
            }

            // 4. NEW: TARGET LIST SYNC (Full list of slot names)
            // Payload: "0:SARAH|1:BOSS|2:TEAM"
            "/sys/target_list" -> {
                try {
                    val rawData = String(messageEvent.data, Charsets.UTF_8)

                    // A. Update ACK Wear's Internal Cache (so the list works in the Wear App too)
                    TargetCache.update(rawData)
                    
                    // B. Cache Raw String for persistent storage
                    prefs.edit().putString("cached_target_list_raw", rawData).apply()

                    // C. BROADCAST TO OVERSEER
                    // This tells the Watch Face exactly what names go with which slots
                    val intent = Intent("com.snakesan.overseer.SYNC_TARGETS")
                    intent.setPackage("com.snakesan.overseer") // Explicitly target the Face
                    intent.putExtra("source_app", "ACK_LIST_SYNC")
                    intent.putExtra("raw_targets", rawData)
                    sendBroadcast(intent)
                    
                    Log.d("ACK_WEAR", "Target list synced to Overseer: $rawData")

                } catch (e: Exception) {
                    Log.e("ACK_WEAR", "Failed to sync target list", e)
                }
            }
        }
    }

    private fun broadcastToOverseer(deckName: String, contextName: String, color: Int) {
        val intent = Intent("com.snakesan.overseer.UPDATE_STATUS")
        intent.setPackage("com.snakesan.overseer") // Explicitly target the Face
        
        intent.putExtra("source_app", "ACK")
        intent.putExtra("active_deck", deckName.uppercase())
        intent.putExtra("active_context", contextName.uppercase())
        
        // Overseer expects "deck_color" as an Int
        intent.putExtra("deck_color", color) 

        sendBroadcast(intent)
    }
}
