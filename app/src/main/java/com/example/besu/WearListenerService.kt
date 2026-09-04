package com.example.besu

import android.content.Intent
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService

class WearListenerService : WearableListenerService() {

    override fun onMessageReceived(messageEvent: MessageEvent) {
        val path = messageEvent.path
        
        // 1. GESTURE TRIGGER (Now with Target Injection)
        if (path.startsWith("/gesture/")) {
            broadcastLog("RX: $path", "DATA")
            
            // A. Resolve Base Phrase from Matrix (e.g. "Systems Online")
            val basePhrase = CommandRepository.resolveSignalToPhrase(this, path)
            
            if (basePhrase.isNotEmpty()) {
                // B. INJECT TARGET NAME
                // Checks if a Target is active. Checks Training Rules.
                // Result: "Systems Online, Sarah."
                val finalPhrase = TargetRepository.processPhrase(this, basePhrase, path)
                
                triggerVoice(finalPhrase)
            }
        } 
        
        // 2. WATCH TELEMETRY (Visuals for Overseer/Phone UI)
        else if (path == "/sys/status_update") {
            try {
                val data = String(messageEvent.data, Charsets.UTF_8).split(",")
                if (data.size >= 3) {
                    val intent = Intent("ACK_WATCH_STATUS")
                    intent.setPackage(packageName)
                    intent.putExtra("state", data[0])
                    intent.putExtra("pose", data[1])
                    intent.putExtra("twist", data[2].toIntOrNull() ?: 0)
                    sendBroadcast(intent)
                }
            } catch (e: Exception) { }
        }
        
        // 3. HELP / TUTORIAL EVENT (Gesture Calibration practice steps)
        else if (path == "/sys/help_event") {
            val eventType = String(messageEvent.data, Charsets.US_ASCII)
            val intent = Intent("ACK_HELP_EVENT")
            intent.setPackage(packageName)
            intent.putExtra("type", eventType)
            sendBroadcast(intent)
        }

        // 4. DECK CHANGE REQUEST
        else if (path == "/sys/req_deck_change") {
            val deckId = String(messageEvent.data, Charsets.UTF_8)
            broadcastLog("REMOTE DECK SWAP: $deckId", "SYS")
            
            val colorIdx = if (deckId == "DEFAULT") 0 else {
                CommandRepository.getDecks(this).find { it.id == deckId }?.colorIndex ?: 0
            }
            
            CommandRepository.activateDeck(this, deckId, colorIdx)
            
            val uiIntent = Intent("ACK_DECK_CHANGE")
            uiIntent.setPackage(packageName)
            uiIntent.putExtra("deckId", deckId)
            uiIntent.putExtra("colorIdx", colorIdx)
            sendBroadcast(uiIntent)
        }

        // 5. NEW: TARGET SELECTION REQUEST
        else if (path == "/sys/req_target") {
            try {
                // Payload is index "0" to "7", or "-1" to clear
                val indexStr = String(messageEvent.data, Charsets.UTF_8)
                val index = indexStr.toIntOrNull() ?: -1
                
                TargetRepository.setActiveTarget(index)
                
                val targetName = TargetRepository.getActiveTarget(this)?.label ?: "CLEARED"
                broadcastLog("TARGET LOCKED: $targetName", "SYS")
                
                // --- AUDIO FEEDBACK DISABLED (Too Chatty) ---
                // triggerVoice("Target locked: $targetName")
                
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    private fun triggerVoice(text: String) {
        val intent = Intent(this, OutputService::class.java)
        intent.putExtra("phrase", text)
        intent.putExtra("robotic", false)
        intent.putExtra("source", "HW/WATCH") // Source tag for logs
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun broadcastLog(msg: String, type: String) {
        val intent = Intent("ACK_LOG")
        intent.setPackage(packageName)
        intent.putExtra("msg", msg)
        intent.putExtra("type", type)
        sendBroadcast(intent)
    }
}
