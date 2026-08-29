package com.example.besu

import android.Manifest
import android.annotation.SuppressLint
import android.app.Application
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.RequiresApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asComposeRenderEffect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority

// Mapsforge 2D Imports
import org.mapsforge.core.graphics.Style
import org.mapsforge.core.model.LatLong
import org.mapsforge.map.android.graphics.AndroidGraphicFactory
import org.mapsforge.map.android.util.AndroidUtil
import org.mapsforge.map.android.view.MapView as MapsforgeMapView
import org.mapsforge.map.datastore.MapDataStore
import org.mapsforge.map.layer.cache.TileCache
import org.mapsforge.map.layer.overlay.Circle
import org.mapsforge.map.layer.renderer.TileRendererLayer
import org.mapsforge.map.reader.MapFile
import org.mapsforge.map.rendertheme.InternalRenderTheme
import java.io.File
import java.io.FileOutputStream

@RequiresApi(Build.VERSION_CODES.TIRAMISU)
val MAP_3D_SHADER = """
    uniform shader composable;
    uniform float time;

    half4 main(float2 fragCoord) {
        half4 center = composable.eval(fragCoord);
        
        // Isolate elements based on your 2D theme colors
        float isBuilding = step(0.5, center.r) * (1.0 - step(0.5, center.g)); 
        float isRoad = step(0.4, center.b) * (1.0 - step(0.5, center.r));
        
        // EXTRUSION: Draw downwards in 2D. 
        // When Compose tilts the map back 55 degrees, these will stand straight up!
        // ISOMETRIC EXTRUSION: Draw diagonally down and right!
        vec2 extrudeDir = normalize(vec2(0.6, 1.0)); 
        float fakeHeight = 25.0; // Shorter loop = faster GPU performance
        
        bool isWall = false;
        float wallGradient = 0.0;
        
        // Raymarch Fake 3D Walls
        if (isBuilding < 0.5) {
            for(int i = 1; i <= 35; i++) {
                float fi = float(i);
                vec2 samplePos = fragCoord - (extrudeDir * fi);
                half4 sampleColor = composable.eval(samplePos);
                float sampleVal = step(0.5, sampleColor.r) * (1.0 - step(0.5, sampleColor.g));
                
                if (sampleVal > 0.5) {
                    isWall = true;
                    wallGradient = fi / fakeHeight; 
                    break;
                }
            }
        }
        
        // Color Compositing
        half3 finalColor = center.rgb;
        
        if (isBuilding > 0.5) {
            // ROOFS
            finalColor = finalColor * 1.5;
            float wave = (fragCoord.y + (time * 35.0)) * 0.5;
            finalColor = mix(finalColor, half3(0.05, 0.0, 0.0), ((sin(wave) + 1.0) * 0.5) * 0.45);
        } else if (isWall) {
            // FAKE WALLS
            finalColor = finalColor * 0.45;
            finalColor -= (wallGradient * 0.2);
            if (wallGradient < 0.15) {
                finalColor += half3(0.0, 0.2, 0.3);
            }
        } else if (isRoad > 0.5 && !isWall) {
            // ROADS
            float wave = (fragCoord.y + (time * -50.0)) * 0.8;
            finalColor = mix(finalColor, half3(1.5, 3.0, 3.0), ((sin(wave) + 1.0) * 0.5) * 0.65);
        }
        
        return half4(finalColor, center.a);
    }
""".trimIndent()

@Composable
fun GeoProtocolView(context: Context, primaryColor: Color) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var showPermissionModal by remember { mutableStateOf(false) }

    var isMapFullscreen by remember { mutableStateOf(false) }
    var crosshairLat by remember { mutableDoubleStateOf(0.0) }
    var crosshairLng by remember { mutableDoubleStateOf(0.0) }
    var editingZoneId by remember { mutableStateOf<String?>(null) }
    var isTracking by remember { mutableStateOf(true) }

    val isMasterEnabled = remember(refreshKey) { GeoRepository.isGeoEnabled(context) }
    val currentEngine = remember(refreshKey) { GeoRepository.getEngineMode(context) }
    val zones = remember(refreshKey) { GeoRepository.getZones(context) }
    val availableDecks = remember { CommandRepository.getDecks(context) }

    val fusedLocationClient = remember { LocationServices.getFusedLocationProviderClient(context) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        if (permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true) refreshKey++
    }

    DisposableEffect(isMapFullscreen, isTracking) {
        var locationCallback: LocationCallback? = null
        if (isMapFullscreen && isTracking) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 2000L).setMinUpdateDistanceMeters(2f).build()
                locationCallback = object : LocationCallback() {
                    override fun onLocationResult(result: LocationResult) {
                        result.lastLocation?.let { location ->
                            crosshairLat = location.latitude
                            crosshairLng = location.longitude
                        }
                    }
                }
                fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper())
            }
        }
        onDispose { locationCallback?.let { fusedLocationClient.removeLocationUpdates(it) } }
    }

    @SuppressLint("MissingPermission")
    fun openMapAtCurrentLocation() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            fusedLocationClient.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null).addOnSuccessListener { location ->
                if (location != null) {
                    crosshairLat = location.latitude
                    crosshairLng = location.longitude
                }
                editingZoneId = null
                isTracking = true
                isMapFullscreen = true
            }
        } else {
            showPermissionModal = true
        }
    }

    if (isMapFullscreen) {
        Dialog(onDismissRequest = { isMapFullscreen = false; editingZoneId = null }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
            Box(modifier = Modifier.fillMaxSize().background(VoidBlack)) {

                // MODE 7 TACTICAL MAP
                TacticalMapView(
                    currentLat = if (crosshairLat == 0.0) 40.7128 else crosshairLat,
                    currentLng = if (crosshairLng == 0.0) -74.0060 else crosshairLng,
                    isTracking = isTracking,
                    zones = zones,
                    onMapPan = { lat, lng -> crosshairLat = lat; crosshairLng = lng; isTracking = false },
                    modifier = Modifier.fillMaxSize()
                )

                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("+", color = NeonPalette.SWATCHES[1], fontSize = 32.sp, fontFamily = FontFamily.Monospace)
                }

                Row(modifier = Modifier.fillMaxWidth().background(VoidBlack.copy(alpha = 0.85f)).windowInsetsPadding(WindowInsets.statusBars).padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(if (editingZoneId != null) "EDIT SECURE NODE" else "DEPLOY NEW NODE", color = primaryColor, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(if (isTracking) "[TRACKING: ON]" else "[TRACKING: OFF]", color = if (isTracking) primaryColor else Color.Gray, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.clickable { isTracking = !isTracking }.padding(end = 16.dp))
                        Text("[ABORT]", color = Color.Red, fontFamily = FontFamily.Monospace, modifier = Modifier.clickable { isMapFullscreen = false; editingZoneId = null })
                    }
                }

                Column(modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().background(VoidBlack.copy(alpha = 0.9f)).windowInsetsPadding(WindowInsets.navigationBars).padding(48.dp)) {
                    Text("TARGET: ${String.format("%.4f, %.4f", crosshairLat, crosshairLng)}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                        if (editingZoneId != null) {
                            NeonButton("PURGE", Modifier.weight(1f), mainColor = Color.Red) {
                                GeoRepository.deleteZone(context, editingZoneId!!)
                                GeoEngineController.syncEngineState(context)
                                isMapFullscreen = false; editingZoneId = null; refreshKey++
                            }
                        }
                        HeroButton("LOCK COORDINATE", modifier = Modifier.weight(2f), mainColor = primaryColor) {
                            if (editingZoneId != null) {
                                val existing = zones.find { it.id == editingZoneId }
                                if (existing != null) GeoRepository.saveZone(context, existing.copy(lat = crosshairLat, lng = crosshairLng))
                            } else {
                                GeoRepository.saveZone(context, GeoZone(java.util.UUID.randomUUID().toString(), "NODE ${zones.size + 1}", crosshairLat, crosshairLng))
                            }
                            GeoEngineController.syncEngineState(context)
                            isMapFullscreen = false; editingZoneId = null; refreshKey++
                        }
                    }
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Text("GEO-PROTOCOL", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            NeonButton(if (isMasterEnabled) "SYSTEM: ON" else "SYSTEM: OFF", isActive = isMasterEnabled, mainColor = primaryColor) {
                GeoRepository.setGeoEnabled(context, !isMasterEnabled); GeoEngineController.syncEngineState(context); refreshKey++
            }
        }
        Spacer(modifier = Modifier.height(16.dp))

        Text("COMPUTE ENGINE", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GeoEngineMode.entries.forEachIndexed { index, mode ->
                ThemeOption(index, mode.name, if (currentEngine == mode) index else -1, primaryColor) {
                    GeoRepository.setEngineMode(context, mode); GeoEngineController.syncEngineState(context); refreshKey++
                }
            }
        }
        Spacer(modifier = Modifier.height(24.dp))
        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
        Spacer(modifier = Modifier.height(24.dp))

        Text("SECURE NODES [${zones.size}]", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
        Spacer(modifier = Modifier.height(12.dp))

        LazyColumn(modifier = Modifier.weight(1f)) {
            items(zones) { zone ->
                GeoZoneCard(zone = zone, primaryColor = primaryColor, availableDecks = availableDecks,
                    onUpdate = { updatedZone -> GeoRepository.saveZone(context, updatedZone); GeoEngineController.syncEngineState(context); refreshKey++ },
                    onDelete = { GeoRepository.deleteZone(context, zone.id); GeoEngineController.syncEngineState(context); refreshKey++ },
                    onEdit = { crosshairLat = zone.lat; crosshairLng = zone.lng; editingZoneId = zone.id; isMapFullscreen = true }
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        HeroButton("OPEN TACTICAL GRID", modifier = Modifier.fillMaxWidth().tutorialTarget("MARK_GEO_BTN",), mainColor = primaryColor) {
            openMapAtCurrentLocation()
        }
    }

    if (showPermissionModal) GeoPermissionModal(context, primaryColor, permissionLauncher, onDismiss = { showPermissionModal = false })
}

// --- 2D MAPSFORGE RENDERER WITH COMPOSE MODE-7 TILT ---
@Composable
fun TacticalMapView(
    modifier: Modifier = Modifier,
    currentLat: Double,
    currentLng: Double,
    isTracking: Boolean,
    zones: List<GeoZone>,
    onMapPan: (Double, Double) -> Unit
) {
    val context = LocalContext.current
    val density = LocalDensity.current.density
    LaunchedEffect(Unit) { AndroidGraphicFactory.createInstance(context.applicationContext as Application) }

    var time by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        val startTime = withFrameMillis { it }
        while (true) {
            withFrameMillis { frameTime -> time = (frameTime - startTime) / 1000f }
        }
    }

    val mapView = remember {
        MapsforgeMapView(context).apply {
            layoutParams = android.view.ViewGroup.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.MATCH_PARENT
            )
            isClickable = true
            setBuiltInZoomControls(false)
            mapScaleBar.isVisible = false
            setCenter(LatLong(currentLat, currentLng))
            setZoomLevel(17.toByte())
            model.displayModel.setBackgroundColor(android.graphics.Color.parseColor("#050505"))

            try {
                val mapFile = File(context.cacheDir, "tactical_grid.map")
                if (!mapFile.exists()) {
                    context.assets.open("tactical_grid.map").use { input -> FileOutputStream(mapFile).use { output -> input.copyTo(output) } }
                }

                // Make sure your OLD 2D Mapsforge XML theme is restored to ack_theme.xml in assets
                val themeFile = File(context.cacheDir, "ack_theme.xml")
                context.assets.open("ack_theme.xml").use { input -> FileOutputStream(themeFile).use { output -> input.copyTo(output) } }

                // Using 3.0 and 2.0 (Doubles) instead of 3f and 2f
                val tileCache: TileCache = AndroidUtil.createTileCache(
                    context,
                    "mapcache",
                    model.displayModel.tileSize,
                    3f,
                    2.0
                )
                val mapDataStore: MapDataStore = MapFile(mapFile)
                val tileRendererLayer = TileRendererLayer(tileCache, mapDataStore, model.mapViewPosition, AndroidGraphicFactory.INSTANCE)

                try {
                    tileRendererLayer.setXmlRenderTheme(org.mapsforge.map.rendertheme.ExternalRenderTheme(themeFile))
                } catch (e: Exception) {
                    tileRendererLayer.setXmlRenderTheme(InternalRenderTheme.OSMARENDER)
                }
                layerManager.layers.add(tileRendererLayer)
            } catch (e: Exception) {}

            val paintFill = AndroidGraphicFactory.INSTANCE.createPaint().apply { setColor(android.graphics.Color.parseColor("#3300F3FF")); setStyle(Style.FILL) }
            val paintStroke = AndroidGraphicFactory.INSTANCE.createPaint().apply { setColor(android.graphics.Color.parseColor("#FF00F3FF")); setStrokeWidth(3f); setStyle(Style.STROKE) }
            zones.forEach { zone -> layerManager.layers.add(Circle(LatLong(zone.lat, zone.lng), zone.radiusMeters, paintFill, paintStroke)) }

            model.mapViewPosition.addObserver {
                val center = model.mapViewPosition.center
                if (Math.abs(center.latitude - currentLat) > 0.0001 || Math.abs(center.longitude - currentLng) > 0.0001) {
                    onMapPan(center.latitude, center.longitude)
                }
            }
        }
    }

    LaunchedEffect(currentLat, currentLng) {
        if (isTracking) mapView.model.mapViewPosition.animateTo(LatLong(currentLat, currentLng))
    }

    DisposableEffect(Unit) { onDispose { mapView.destroyAll() } }

    val mapShader = remember {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) android.graphics.RuntimeShader(MAP_3D_SHADER) else null
    }

    // THE MODE 7 TRICK
    AndroidView(
        factory = { mapView },
        modifier = modifier
            .fillMaxSize() // Normal screen size, no more 1.5x inflation!
            .graphicsLayer {
                // REMOVED rotationX = 55f
                // REMOVED cameraDistance = 12f * density

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && mapShader != null) {
                    mapShader.setFloatUniform("time", time)
                    renderEffect = android.graphics.RenderEffect.createRuntimeShaderEffect(
                        mapShader, "composable"
                    ).asComposeRenderEffect()
                }
            }
    )
}

@Composable
fun GeoZoneCard(zone: GeoZone, primaryColor: Color, availableDecks: List<DeckMeta>, onUpdate: (GeoZone) -> Unit, onDelete: () -> Unit, onEdit: () -> Unit) {
    var enterExpanded by remember { mutableStateOf(false) }
    var exitExpanded by remember { mutableStateOf(false) }
    val enterOptions = listOf("DEFAULT" to "SYSTEM DEFAULT") + availableDecks.map { it.id to it.name }
    val exitOptions = listOf("NONE" to "DO NOTHING", "PREVIOUS" to "REVERT TO PREVIOUS", "DEFAULT" to "SYSTEM DEFAULT") + availableDecks.map { it.id to it.name }
    val enterLabel = enterOptions.find { it.first == zone.enterDeckId }?.second ?: zone.enterDeckId
    val exitLabel = exitOptions.find { it.first == zone.exitDeckId }?.second ?: zone.exitDeckId
    val allowedRadii = listOf(10f, 20f, 30f, 50f, 100f, 200f, 300f, 400f, 500f, 600f, 700f, 800f)
    val currentIndex = allowedRadii.indexOf(zone.radiusMeters).let { if (it == -1) 4 else it }.toFloat()

    Column(modifier = Modifier.fillMaxWidth().border(1.dp, primaryColor.copy(alpha = 0.5f), CutCornerShape(8.dp)).background(Graphite, CutCornerShape(8.dp)).padding(12.dp)) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(value = zone.name, onValueChange = { onUpdate(zone.copy(name = it.uppercase())) }, modifier = Modifier.weight(1f).height(50.dp), colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent), textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 14.sp, fontWeight = FontWeight.Bold))
            Row {
                Text(" [EDIT]", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.clickable { onEdit() }.padding(8.dp))
                Text(" [PURGE]", color = Color.Red, fontSize = 10.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.clickable { onDelete() }.padding(8.dp))
            }
        }
        Spacer(modifier = Modifier.height(12.dp))
        Text("RADIUS: ${zone.radiusMeters.toInt()}m", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Slider(value = currentIndex, onValueChange = { indexFloat -> onUpdate(zone.copy(radiusMeters = allowedRadii[indexFloat.toInt()])) }, valueRange = 0f..(allowedRadii.size - 1).toFloat(), steps = allowedRadii.size - 2, colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray))
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp), modifier = Modifier.fillMaxWidth()) {
            Box(modifier = Modifier.weight(1f)) {
                Column(modifier = Modifier.clickable { enterExpanded = true }) { Text("ENTER DECK:", color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace); Text(enterLabel, color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace) }
                DropdownMenu(expanded = enterExpanded, onDismissRequest = { enterExpanded = false }, modifier = Modifier.background(Graphite)) { enterOptions.forEach { (id, name) -> DropdownMenuItem(text = { Text(name, color = primaryColor, fontFamily = FontFamily.Monospace) }, onClick = { onUpdate(zone.copy(enterDeckId = id)); enterExpanded = false }) } }
            }
            Box(modifier = Modifier.weight(1f)) {
                Column(modifier = Modifier.clickable { exitExpanded = true }) { Text("EXIT DECK:", color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace); Text(exitLabel, color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace) }
                DropdownMenu(expanded = exitExpanded, onDismissRequest = { exitExpanded = false }, modifier = Modifier.background(Graphite)) { exitOptions.forEach { (id, name) -> DropdownMenuItem(text = { Text(name, color = primaryColor, fontFamily = FontFamily.Monospace) }, onClick = { onUpdate(zone.copy(exitDeckId = id)); exitExpanded = false }) } }
            }
        }
    }
}