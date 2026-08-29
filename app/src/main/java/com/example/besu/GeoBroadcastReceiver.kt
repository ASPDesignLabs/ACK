package com.example.besu

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.Geofence
import com.google.android.gms.location.GeofencingEvent

class GeoBroadcastReceiver : BroadcastReceiver() {

    companion object {
        const val ACTION_GEO_ENGAGE = "com.example.besu.GEO_ENGAGE"
        const val ACTION_GEO_ABORT = "com.example.besu.GEO_ABORT"
        const val ACTION_SOVEREIGN_EVENT = "com.example.besu.SOVEREIGN_EVENT"

        const val EXTRA_DECK_ID = "extra_deck_id"
        const val EXTRA_ZONE_NAME = "extra_zone_name"
        const val EXTRA_NOTIF_ID = "extra_notif_id"
        const val EXTRA_IS_ENTERING = "extra_is_entering"
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            ACTION_GEO_ENGAGE -> handleEngage(context, intent)
            ACTION_GEO_ABORT -> handleAbort(context, intent)
            ACTION_SOVEREIGN_EVENT -> handleSovereignEvent(context, intent)
            else -> handleGoogleGeofenceEvent(context, intent) // OS Optimized Engine trigger
        }
    }

    private fun handleGoogleGeofenceEvent(context: Context, intent: Intent) {
        val geofencingEvent = GeofencingEvent.fromIntent(intent)
        if (geofencingEvent == null || geofencingEvent.hasError()) return

        val transition = geofencingEvent.geofenceTransition
        val triggerZones = geofencingEvent.triggeringGeofences ?: return

        val isEntering = transition == Geofence.GEOFENCE_TRANSITION_ENTER
        val isExiting = transition == Geofence.GEOFENCE_TRANSITION_EXIT

        if (!isEntering && !isExiting) return

        val zones = GeoRepository.getZones(context)

        triggerZones.forEach { trigger ->
            val zone = zones.find { it.id == trigger.requestId }
            if (zone != null) {
                processTransition(context, zone, isEntering)
            }
        }
    }

    private fun handleSovereignEvent(context: Context, intent: Intent) {
        val zoneId = intent.getStringExtra("zone_id") ?: return
        val isEntering = intent.getBooleanExtra("is_entering", true)

        val zone = GeoRepository.getZones(context).find { it.id == zoneId }
        if (zone != null) {
            processTransition(context, zone, isEntering)
        }
    }

    private fun processTransition(context: Context, zone: GeoZone, isEntering: Boolean) {
        val targetDeckId = if (isEntering) zone.enterDeckId else zone.exitDeckId

        if (targetDeckId == "NONE") return

        val decks = CommandRepository.getDecks(context)
        val deckName = when (targetDeckId) {
            "DEFAULT" -> "SYSTEM DEFAULT"
            "PREVIOUS" -> "PREVIOUS DECK"
            else -> decks.find { it.id == targetDeckId }?.name ?: "UNKNOWN"
        }

        val actionText = if (isEntering) "Entering" else "Exiting"
        broadcastLog(context, "$actionText ${zone.name}. Awaiting User Ack.", "GEO")

        showNotification(context, zone, targetDeckId, deckName, isEntering)
    }

    private fun showNotification(context: Context, zone: GeoZone, targetDeckId: String, deckName: String, isEntering: Boolean) {
        val notifManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channelId = "geo_protocol_alerts"

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId, "Geo-Protocol Alerts", NotificationManager.IMPORTANCE_HIGH
            )
            notifManager.createNotificationChannel(channel)
        }

        val notifId = zone.id.hashCode()

        // Engage Intent
        val engageIntent = Intent(context, GeoBroadcastReceiver::class.java).apply {
            action = ACTION_GEO_ENGAGE
            putExtra(EXTRA_DECK_ID, targetDeckId)
            putExtra(EXTRA_ZONE_NAME, zone.name)
            putExtra(EXTRA_NOTIF_ID, notifId)
            putExtra(EXTRA_IS_ENTERING, isEntering)
        }
        val engagePending = PendingIntent.getBroadcast(
            context, notifId, engageIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Abort Intent
        val abortIntent = Intent(context, GeoBroadcastReceiver::class.java).apply {
            action = ACTION_GEO_ABORT
            putExtra(EXTRA_ZONE_NAME, zone.name)
            putExtra(EXTRA_NOTIF_ID, notifId)
        }
        val abortPending = PendingIntent.getBroadcast(
            context, notifId + 1, abortIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_map)
            .setContentTitle("GEO-NODE: ${zone.name}")
            .setContentText("Switch layout to [$deckName]?")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setVibrate(longArrayOf(0, 250, 250, 250)) // Haptic attention
            .addAction(0, "ENGAGE", engagePending)
            .addAction(0, "ABORT", abortPending)
            .setAutoCancel(true)

        notifManager.notify(notifId, builder.build())
    }

    private fun handleEngage(context: Context, intent: Intent) {
        var deckId = intent.getStringExtra(EXTRA_DECK_ID) ?: return
        val zoneName = intent.getStringExtra(EXTRA_ZONE_NAME) ?: "ZONE"
        val notifId = intent.getIntExtra(EXTRA_NOTIF_ID, -1)
        val isEntering = intent.getBooleanExtra(EXTRA_IS_ENTERING, true)

        // 1. Logic for Return to Previous
        if (isEntering) {
            // Save the current deck before we change it so we can return to it later
            val currentDeck = CommandRepository.getActiveDeckId(context)
            GeoRepository.setLastPreGeoDeck(context, currentDeck)
        } else {
            // If exiting and set to PREVIOUS, fetch what we saved
            if (deckId == "PREVIOUS") {
                deckId = GeoRepository.getLastPreGeoDeck(context)
            }
        }

        // 2. Find Color & Name for Watch Sync and UI
        val decks = CommandRepository.getDecks(context)
        val targetDeck = decks.find { it.id == deckId }
        val colorIdx = targetDeck?.colorIndex ?: 0
        val deckName = if (deckId == "DEFAULT") "DEFAULT" else targetDeck?.name ?: "UNKNOWN"

        // 3. Execute Core State Change
        CommandRepository.activateDeck(context, deckId, colorIdx)

        // 4. Notify UI and Watch (WatchSync is handled inside activateDeck, but we broadcast for UI refresh)
        val uiIntent = Intent("ACK_DECK_CHANGE")
        uiIntent.setPackage(context.packageName)
        uiIntent.putExtra("deckId", deckId)
        uiIntent.putExtra("colorIdx", colorIdx)
        context.sendBroadcast(uiIntent)

        broadcastLog(context, "PROTOCOL ENGAGED: $zoneName -> $deckName", "GEO")

        // 5. Cleanup Notification
        if (notifId != -1) {
            val notifManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notifManager.cancel(notifId)
        }
    }

    private fun handleAbort(context: Context, intent: Intent) {
        val zoneName = intent.getStringExtra(EXTRA_ZONE_NAME) ?: "ZONE"
        val notifId = intent.getIntExtra(EXTRA_NOTIF_ID, -1)

        broadcastLog(context, "PROTOCOL ABORTED: $zoneName", "GEO")

        if (notifId != -1) {
            val notifManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notifManager.cancel(notifId)
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