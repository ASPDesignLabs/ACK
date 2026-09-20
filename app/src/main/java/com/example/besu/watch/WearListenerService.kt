package com.example.besu.watch

import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.output.*
import android.content.Intent
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService

class WearListenerService : WearableListenerService() {

    override fun onMessageReceived(messageEvent: MessageEvent) {
        val path = messageEvent.path
        
        // 1. GESTURE TRIGGER (Now with Target Injection)
        if (path.startsWith("/gesture/")) {
            broadcastLog("RX: $path", "DATA")

            // A Matrix node with an enabled voice recording bound to it
            // plays that recording verbatim instead of resolving the
            // template -- variables are deliberately inert while a
            // recording is active (see MatrixEditor), so no target
            // injection or single-use [COMPUTER:X] consumption happens
            // on this path either.
            val node = CommandRepository.resolveSignalToNode(this, path)
            val recording = node?.let {
                VoiceRecordingRepository.getForMatrixNode(
                    this,
                    CommandRepository.getActiveDeckId(this),
                    CommandRepository.getActiveProfile(this),
                    it.path
                )
            }

            if (node != null && recording != null && recording.enabled) {
                // The visual override (if set while recording this entry)
                // is the log line/on-screen prompt text -- otherwise this
                // falls back to the normal resolved phrase (read-only,
                // consumeSingleUse=false -- the audio doesn't reflect it,
                // so nothing here should actually consume a single-use
                // pick), matching exactly what the MATRIX list itself
                // shows for this node.
                val displayText = CommandRepository.getVisualOverride(this, node.path)
                    .ifBlank { CommandRepository.getResolvedPhrase(this, node.path) }
                triggerVoice(displayText, recording.id)
            } else {
                // A. Resolve Base Phrase from Matrix (e.g. "Systems Online")
                // This is a genuine dispatch (about to become real spoken output),
                // so single-use [COMPUTER:X] picks are allowed to clear here.
                val basePhrase = CommandRepository.resolveSignalToPhrase(this, path, consumeSingleUse = true)

                if (basePhrase.isNotEmpty()) {
                    // B. INJECT TARGET NAME
                    // Checks if a Target is active. Checks Training Rules.
                    // Result: "Systems Online, Sarah."
                    val finalPhrase = TargetRepository.processPhrase(this, basePhrase, path)

                    triggerVoice(finalPhrase)
                }
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
        
        // 3. DECK CHANGE REQUEST
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

        // 4. NEW: TARGET SELECTION REQUEST
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

    private fun triggerVoice(text: String, recordingId: String? = null) {
        val intent = Intent(this, OutputService::class.java)
        intent.putExtra("phrase", text)
        intent.putExtra("robotic", false)
        intent.putExtra("source", "HW/WATCH") // Source tag for logs
        // OutputService tries this recording first and falls back to the
        // phrase above if it can't load it, same fallback contract as
        // every other recording-aware dispatch in the app.
        if (recordingId != null) {
            intent.putExtra("recording_id", recordingId)
        }
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
