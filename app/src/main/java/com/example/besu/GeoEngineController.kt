package com.example.besu

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import android.util.Log
// Note: Requires implementation("com.google.android.gms:play-services-location:21.0.1") in build.gradle
import com.google.android.gms.location.Geofence
import com.google.android.gms.location.GeofencingRequest
import com.google.android.gms.location.LocationServices
import kotlin.math.*

object GeoEngineController {

    private var isSovereignPolling = false
    private var locationManager: LocationManager? = null

    private var locationListener: LocationListener? = null

    // --- MAIN ROUTER ---
    fun syncEngineState(context: Context) {
        val isEnabled = GeoRepository.isGeoEnabled(context)
        val mode = GeoRepository.getEngineMode(context)
        val zones = GeoRepository.getZones(context)

        // Tear down everything first to prevent overlap
        stopSovereignEngine(context)
        stopOptimizedEngine(context)

        if (!isEnabled || zones.isEmpty()) return

        if (mode == GeoEngineMode.SOVEREIGN) {
            startSovereignEngine(context, zones)
        } else {
            startOptimizedEngine(context, zones)
        }
    }

    // ==========================================
    // ENGINE A: SOVEREIGN (Local Math Polling)
    // ==========================================
    @SuppressLint("MissingPermission")
    private fun startSovereignEngine(context: Context, zones: List<GeoZone>) {
        if (locationManager == null) {
            locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        }

        // Clean up any old listeners before starting a new one
        stopSovereignEngine(context)

        isSovereignPolling = true
        broadcastLog(context, "SOVEREIGN ENGINE: ONLINE", "GEO")

        locationListener = LocationListener { location ->
            if (!isSovereignPolling) return@LocationListener

            // HEARTBEAT LOG: This will show up in your Terminal every 15 seconds
            // so you know it's actually working. (Accuracy is in meters).
            broadcastLog(context, "PING: Acc ${location.accuracy.toInt()}m", "GEO")

            evaluateSovereignZones(context, location, zones)
        }

        try {
            // Register both providers.
            // Network works indoors (Desk), GPS works outdoors.
            val providers = locationManager?.getProviders(true) ?: emptyList()
            var registered = false

            if (providers.contains(LocationManager.GPS_PROVIDER)) {
                locationManager?.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER, 15000L, 0f, locationListener!!, Looper.getMainLooper()
                )
                registered = true
            }

            if (providers.contains(LocationManager.NETWORK_PROVIDER)) {
                locationManager?.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER, 15000L, 0f, locationListener!!, Looper.getMainLooper()
                )
                registered = true
            }

            if (!registered) {
                broadcastLog(context, "GEO ERR: No Location Providers Enabled", "ERR")
            }
        } catch (e: Exception) {
            broadcastLog(context, "SOVEREIGN ENGINE ERR: Permission Denied", "ERR")
        }
    }

    private fun stopSovereignEngine(context: Context) {
        isSovereignPolling = false
        locationListener?.let {
            locationManager?.removeUpdates(it)
        }
        locationListener = null
        broadcastLog(context, "SOVEREIGN ENGINE: OFFLINE", "GEO")
    }

    private fun evaluateSovereignZones(context: Context, loc: Location, zones: List<GeoZone>) {
        val prefs = context.getSharedPreferences("ack_geo_secure", Context.MODE_PRIVATE)
        val activeZonesStr = prefs.getString("active_sovereign_zones", "") ?: ""
        val activeZones = activeZonesStr.split(",").filter { it.isNotEmpty() }.toMutableSet()

        val currentlyInside = mutableSetOf<String>()

        zones.forEach { zone ->
            val distance = haversine(loc.latitude, loc.longitude, zone.lat, zone.lng)
            if (distance <= zone.radiusMeters) {
                currentlyInside.add(zone.id)

                // If we weren't in it before, trigger an ENTER event
                if (!activeZones.contains(zone.id)) {
                    triggerGeoPrompt(context, zone.id, isEntering = true)
                }
            }
        }

        // Check for EXITS (we were in them last time, but not anymore)
        activeZones.forEach { oldZoneId ->
            if (!currentlyInside.contains(oldZoneId)) {
                triggerGeoPrompt(context, oldZoneId, isEntering = false)
            }
        }

        // Save current state for next tick
        prefs.edit().putString("active_sovereign_zones", currentlyInside.joinToString(",")).apply()
    }

    // Mathematical boundary calculation (Privacy First - No Google API needed)
    private fun haversine(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val R = 6371e3 // Earth radius in meters
        val phi1 = lat1 * Math.PI / 180
        val phi2 = lat2 * Math.PI / 180
        val deltaPhi = (lat2 - lat1) * Math.PI / 180
        val deltaLambda = (lon2 - lon1) * Math.PI / 180

        val a = sin(deltaPhi / 2) * sin(deltaPhi / 2) +
                cos(phi1) * cos(phi2) *
                sin(deltaLambda / 2) * sin(deltaLambda / 2)
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    }

    // ==========================================
    // ENGINE B: OPTIMIZED (Google Play Services)
    // ==========================================
    @SuppressLint("MissingPermission")
    private fun startOptimizedEngine(context: Context, zones: List<GeoZone>) {
        val geofencingClient = LocationServices.getGeofencingClient(context)
        
        val geofenceList = zones.map { zone ->
            Geofence.Builder()
                .setRequestId(zone.id)
                .setCircularRegion(zone.lat, zone.lng, zone.radiusMeters)
                .setExpirationDuration(Geofence.NEVER_EXPIRE)
                .setTransitionTypes(Geofence.GEOFENCE_TRANSITION_ENTER or Geofence.GEOFENCE_TRANSITION_EXIT)
                .build()
        }

        val geofencingRequest = GeofencingRequest.Builder()
            .setInitialTrigger(GeofencingRequest.INITIAL_TRIGGER_ENTER)
            .addGeofences(geofenceList)
            .build()

        geofencingClient.addGeofences(geofencingRequest, getGeofencePendingIntent(context))
            .addOnSuccessListener { broadcastLog(context, "OPTIMIZED ENGINE: ONLINE", "GEO") }
            .addOnFailureListener { broadcastLog(context, "OPTIMIZED ENGINE: ERR", "ERR") }
    }

    private fun stopOptimizedEngine(context: Context) {
        LocationServices.getGeofencingClient(context).removeGeofences(getGeofencePendingIntent(context))
        broadcastLog(context, "OPTIMIZED ENGINE: OFFLINE", "GEO")
    }

    private fun getGeofencePendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, GeoBroadcastReceiver::class.java)
        return PendingIntent.getBroadcast(
            context, 
            0, 
            intent, 
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
        )
    }

    // --- UTILS ---
    private fun triggerGeoPrompt(context: Context, zoneId: String, isEntering: Boolean) {
        val intent = Intent(context, GeoBroadcastReceiver::class.java).apply {
            action = GeoBroadcastReceiver.ACTION_SOVEREIGN_EVENT
            putExtra("zone_id", zoneId)
            putExtra("is_entering", isEntering)
        }
        context.sendBroadcast(intent)
    }

    private fun broadcastLog(context: Context, msg: String, type: String) {
        val intent = Intent("ACK_LOG")
        intent.setPackage(context.packageName)
        intent.putExtra("msg", msg)
        intent.putExtra("type", type)
        context.sendBroadcast(intent)
    }
}
