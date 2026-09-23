package com.example.besu.settings

import com.example.besu.*
import com.example.besu.backup.*
import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import com.example.besu.ui.theme.*
import com.example.besu.watch.*
import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import android.widget.Toast
import com.google.android.gms.wearable.Wearable
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.delay
import kotlin.math.roundToInt




@Composable
private fun SettingsToggleRow(
    title: String,
    description: String,
    checked: Boolean,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                title,
                color = if (checked) primaryColor else Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Text(
                description,
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        Spacer(modifier = Modifier.width(12.dp))

        NeonToggle(
            checked = checked,
            onCheckedChange = onCheckedChange,
            activeColor = primaryColor
        )
    }
}

// One selectable row inside the OUTPUT DEVICE picker -- AUTO, ACK WATCH, or
// a connected Bluetooth device. enabled=false renders the row (so a
// currently-selected-but-disconnected device still shows, using its cached
// label) without letting it be tapped -- there's nothing useful to select
// it INTO, it's just context for why routing fell back to AUTO.
@Composable
private fun OutputRouteRow(
    label: String,
    hint: String,
    isSelected: Boolean,
    primaryColor: Color,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    val rowShape = CutCornerShape(topStart = 8.dp, bottomEnd = 8.dp)
    val borderColor = if (isSelected) primaryColor else Color.DarkGray

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, borderColor.copy(alpha = if (enabled) 1f else 0.5f), rowShape)
            .background(
                if (isSelected) primaryColor.copy(alpha = 0.12f) else Color.Transparent,
                rowShape
            )
            .then(if (enabled) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = label,
                color = if (!enabled) Color.DarkGray else if (isSelected) primaryColor else Color.White,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = hint,
                color = Color.Gray,
                fontSize = 8.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        if (isSelected) {
            Text(
                text = "[X]",
                color = if (enabled) primaryColor else Color.DarkGray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Composable
fun SettingsView(
    context: Context,
    primaryColor: Color,
    logs: androidx.compose.runtime.snapshots.SnapshotStateList<LogEntry>,
    onUploadClick: () -> Unit
) {
    val prefs = context.getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)

    val helpManager = LocalHelpManager.current

    var hideSystemMessages by remember { mutableStateOf(TerminalLogStore.getHideSystemMessages(context)) }
    var hidePathTrace by remember { mutableStateOf(TerminalLogStore.getHidePathTrace(context)) }
    var monospaceTerminal by remember { mutableStateOf(TerminalLogStore.getMonospaceEnabled(context)) }
    var statusboxColorIdx by remember { mutableIntStateOf(TerminalLogStore.getStatusboxColorIndex(context)) }
    var retentionDays by remember { mutableFloatStateOf(TerminalLogStore.getRetentionDays(context).toFloat()) }

    var toneTheme by remember { mutableIntStateOf(prefs.getInt("TONE_THEME", 1)) }
    var toneVolume by remember { mutableFloatStateOf(prefs.getFloat("TONE_VOLUME", 0.8f)) }
    var autoCryo by remember { mutableFloatStateOf(prefs.getInt("AUTO_CRYO", 10).toFloat()) }
    var crownSens by remember { mutableFloatStateOf(prefs.getInt("CROWN_SENS", 2).toFloat()) }
    var motTwist by remember { mutableFloatStateOf(prefs.getFloat("MOT_TWIST", 7.0f)) }
    var motPose by remember { mutableFloatStateOf(prefs.getFloat("MOT_POSE", 6.0f)) }
    var fireGraceMs by remember { mutableFloatStateOf(prefs.getInt("FIRE_GRACE_MS", 500).toFloat()) }
    var wakeWindowMs by remember { mutableFloatStateOf(prefs.getInt("WAKE_WINDOW_MS", 1800).toFloat()) }
    var computerFlyoutTimeoutSec by remember { mutableFloatStateOf(prefs.getInt("COMPUTER_FLYOUT_TIMEOUT_SEC", 10).toFloat()) }
    var shakeThreshold by remember {
        mutableFloatStateOf(
            prefs.getFloat("SHAKE_THRESHOLD", AccelerometerTapService.DEFAULT_SHAKE_THRESHOLD)
        )
    }
    var isShakeTestActive by remember { mutableStateOf(false) }
    var shakeDetectedCount by remember { mutableIntStateOf(0) }
    var isShakeDetectedFlash by remember { mutableStateOf(false) }
    var headerShortcuts by remember { mutableStateOf(CommandRepository.getHeaderShortcuts(context)) }
    var recordingKeyIndex by remember { mutableStateOf<Int?>(null) }
    var recordingRefreshKey by remember { mutableIntStateOf(0) }
    var forceDeviceRotation by remember {
        mutableStateOf(OverlayDisplayPrefs.isDeviceRotationEnabled(context))
    }

    var forceSpeaker by remember { mutableStateOf(prefs.getBoolean("FORCE_SPEAKER", false)) }
    var silentOutput by remember { mutableStateOf(prefs.getBoolean("SILENT_OUTPUT", false)) }
    var guideVoxEnabled by remember { mutableStateOf(prefs.getBoolean("TUTORIAL_VOX", true)) }

    // Where non-forced output goes when it isn't routed to the built-in
    // speaker -- "AUTO" (today's existing behavior: whatever the OS's
    // current default route is), "BLUETOOTH" (a specific paired device, by
    // address -- outputRouteBtLabel is a cached display name so a
    // temporarily-disconnected device still shows correctly instead of
    // vanishing from the picker), or "WATCH" (relayed to the paired ACK
    // Wear app). FORCE SPEAKER always wins over all three.
    var outputRouteMode by remember { mutableStateOf(prefs.getString("OUTPUT_ROUTE_MODE", "AUTO") ?: "AUTO") }
    var outputRouteBtAddress by remember { mutableStateOf(prefs.getString("OUTPUT_ROUTE_BT_ADDRESS", null)) }
    var outputRouteBtLabel by remember { mutableStateOf(prefs.getString("OUTPUT_ROUTE_BT_LABEL", null)) }

    fun syncPhoneAudio() {
        prefs.edit()
            .putBoolean("FORCE_SPEAKER", forceSpeaker)
            .putBoolean("SILENT_OUTPUT", silentOutput)
            .putBoolean("TUTORIAL_VOX", guideVoxEnabled)
            .putString("OUTPUT_ROUTE_MODE", outputRouteMode)
            .putString("OUTPUT_ROUTE_BT_ADDRESS", outputRouteBtAddress)
            .putString("OUTPUT_ROUTE_BT_LABEL", outputRouteBtLabel)
            .apply()

        val intent = Intent(context, OutputService::class.java).apply {
            action = "UPDATE_DSP"
            putExtra("speaker", forceSpeaker)
            putExtra("silent_output", silentOutput)
            putExtra("guide_vox", guideVoxEnabled)
            // Always included together, even when unchanged -- this is how
            // OutputService tells "this UPDATE_DSP call concerns output
            // routing" (and should apply outputRouteBtAddress, including
            // clearing it to null for AUTO) apart from an unrelated DSP
            // sync (e.g. AudioView's voice-profile changes) that doesn't
            // carry these extras at all and should leave routing untouched.
            putExtra("output_route_mode", outputRouteMode)
            putExtra("output_route_bt_address", outputRouteBtAddress)
        }
        context.startService(intent)
    }

    // Collapsed by default, same as the Matrix editor's DESTRUCTIVE
    // CONTROLS section.
    var outputDeviceExpanded by remember { mutableStateOf(false) }

    var connectedBtDevices by remember {
        mutableStateOf(AudioRouting.listConnectedBluetoothDevices(context))
    }

    // Live-refreshes while PROTOCOL is open, so pairing/unpairing a device
    // updates the picker without needing to back out and reopen it.
    DisposableEffect(Unit) {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val callback = object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>) {
                connectedBtDevices = AudioRouting.listConnectedBluetoothDevices(context)
            }

            override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>) {
                connectedBtDevices = AudioRouting.listConnectedBluetoothDevices(context)
            }
        }
        audioManager.registerAudioDeviceCallback(callback, null)
        onDispose { audioManager.unregisterAudioDeviceCallback(callback) }
    }

    // A one-shot, informational check -- not gating whether WATCH can be
    // selected (it can, same as picking a currently-disconnected Bluetooth
    // device), just letting the picker show whether it's actually reachable
    // right now.
    var isWatchConnected by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        Wearable.getNodeClient(context).connectedNodes
            .addOnSuccessListener { nodes -> isWatchConnected = nodes.isNotEmpty() }
            .addOnFailureListener { isWatchConnected = false }
    }



    fun syncAll() {
        prefs.edit().putInt("TONE_THEME", toneTheme).putFloat("TONE_VOLUME", toneVolume)
            .putInt("AUTO_CRYO", autoCryo.toInt()).putInt("CROWN_SENS", crownSens.toInt())
            .putFloat("MOT_TWIST", motTwist).putFloat("MOT_POSE", motPose)
            .putInt("FIRE_GRACE_MS", fireGraceMs.toInt())
            .putInt("WAKE_WINDOW_MS", wakeWindowMs.toInt())
            .putInt("COMPUTER_FLYOUT_TIMEOUT_SEC", computerFlyoutTimeoutSec.toInt()).apply()

        WatchSync.sendAudioConfig(context, toneTheme, toneVolume)
        WatchSync.sendPowerConfig(context, autoCryo.toInt())
        WatchSync.sendCrownSensitivity(context, crownSens.toInt())
        WatchSync.sendMotionConfig(context, motTwist, motPose)
        WatchSync.sendFireGraceConfig(context, fireGraceMs.toInt())
        WatchSync.sendWakeWindowConfig(context, wakeWindowMs.toInt())
        WatchSync.sendComputerFlyoutTimeout(context, computerFlyoutTimeoutSec.toInt())
    }

    fun updateShakeThreshold() {
        prefs.edit().putFloat("SHAKE_THRESHOLD", shakeThreshold).apply()
        context.startService(
            Intent(context, AccelerometerTapService::class.java).setAction("UPDATE_CONFIG")
        )
    }

    // Listens for the real shake detector's broadcast while the test panel
    // is open, so calibrating the slider reflects the actual detector
    // rather than a separate simulated one.
    DisposableEffect(isShakeTestActive) {
        if (!isShakeTestActive) {
            return@DisposableEffect onDispose {}
        }

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context?, intent: Intent?) {
                shakeDetectedCount++
            }
        }
        val filter = IntentFilter(AccelerometerTapService.ACTION_SHAKE_DETECTED)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            context.registerReceiver(receiver, filter)
        }

        onDispose { context.unregisterReceiver(receiver) }
    }

    LaunchedEffect(shakeDetectedCount) {
        if (shakeDetectedCount > 0) {
            isShakeDetectedFlash = true
            delay(1500)
            isShakeDetectedFlash = false
        }
    }

    // Set true right after a successful IMPORT MATRIX AS NEW DECK or FULL
    // RESTORE FROM JSON -- gives the confirmation toast a moment on
    // screen, then restarts the app so the newly-written data actually
    // shows up (see restartApp above). Declared at this top level, not
    // inside either action's own dialog, so it keeps running even after
    // that dialog closes.
    var pendingRestart by remember { mutableStateOf(false) }
    LaunchedEffect(pendingRestart) {
        if (pendingRestart) {
            delay(1500)
            restartApp(context)
        }
    }

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(
            HelpEvent.Interacted(tag)
        )
    }

    var showImportDialog by remember { mutableStateOf(false) }
    var showManageAutocomplete by remember { mutableStateOf(false) }
    var showManageRecordings by remember { mutableStateOf(false) }
    var showFullRestoreConfirm by remember { mutableStateOf(false) }
    var pendingFullRestoreJson by remember { mutableStateOf<String?>(null) }
    var recordingGainPercent by remember {
        mutableFloatStateOf(VoiceRecordingRepository.getPlaybackGainPercent(context).toFloat())
    }
    var importedBackup by remember { mutableStateOf<AckBackup?>(null) }
    var newDeckName by remember { mutableStateOf("") }
    var selectedColorIdx by remember { mutableIntStateOf(0) }

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let {
            try {
                val jsonStr = TransferManager.readTextFromUri(context, it)
                val backup = TransferManager.parseBackupJson(jsonStr)
                if (backup != null) { importedBackup = backup; showImportDialog = true }
            } catch (e: Exception) { }
        }
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        uri?.let {
            try {
                val jsonStr = TransferManager.generateBackupJson(context)
                context.contentResolver.openOutputStream(it)?.use { os -> os.write(jsonStr.toByteArray()) }
            } catch (e: Exception) { }
        }
    }

    // Whole-protocol restore -- unlike importLauncher above (which only ever
    // imports matrix phrases into a new deck), this overwrites the entire
    // current configuration. Reads the file, then holds the raw JSON in
    // pendingFullRestoreJson until the confirm dialog below approves it --
    // never applied straight from the picker.
    val fullRestoreLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let {
            try {
                pendingFullRestoreJson = TransferManager.readTextFromUri(context, it)
                showFullRestoreConfirm = true
            } catch (e: Exception) { }
        }
    }

    // --- DB METER STATE ---
    var hasMicPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
        hasMicPermission = isGranted
    }

    var currentDb by remember { mutableFloatStateOf(0f) }
    val analyzer = remember { AmbientAudioAnalyzer() }
    var isMonitoringActive by remember { mutableStateOf(false) }

    DisposableEffect(isMonitoringActive, hasMicPermission) {
        if (isMonitoringActive && hasMicPermission) {
            analyzer.start(context)
        }
        onDispose {
            analyzer.stop()
        }
    }

    LaunchedEffect(isMonitoringActive, hasMicPermission) {
        if (isMonitoringActive && hasMicPermission) {
            analyzer.collectDbLevels { level -> currentDb = level }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        LazyColumn(modifier = Modifier.weight(1f)) {
            item {
                Text("AUDIO OUTPUT ROUTING", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))

                SettingsToggleRow(
                    title = "FORCE SPEAKER",
                    description = "Routes speech to the device's built-in speaker instead of the current audio route.",
                    checked = forceSpeaker,
                    primaryColor = primaryColor,
                    modifier = Modifier.testTag(AckTags.SETTINGS_AUDIO_ROUTING).helpTarget(AckTags.SETTINGS_AUDIO_ROUTING, primaryColor)
                ) { enabled ->
                    forceSpeaker = enabled
                    syncPhoneAudio()
                    reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .helpTarget(AckTags.SETTINGS_AUDIO_ROUTING, primaryColor)
                        .clickable(enabled = !forceSpeaker) {
                            outputDeviceExpanded = !outputDeviceExpanded
                        },
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = if (outputDeviceExpanded) "▾ " else "▸ ",
                        color = if (forceSpeaker) Color.DarkGray else primaryColor,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "OUTPUT DEVICE",
                            color = if (forceSpeaker) Color.DarkGray else Color.White,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = when {
                                forceSpeaker -> "OVERRIDDEN BY FORCE SPEAKER ABOVE"
                                outputRouteMode == "BLUETOOTH" -> outputRouteBtLabel ?: "BLUETOOTH DEVICE"
                                outputRouteMode == "WATCH" -> "ACK WATCH"
                                else -> "AUTO (SYSTEM DEFAULT)"
                            },
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }

                if (outputDeviceExpanded && !forceSpeaker) {
                    Spacer(modifier = Modifier.height(8.dp))

                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        OutputRouteRow(
                            label = "AUTO (SYSTEM DEFAULT)",
                            hint = "WHATEVER THE PHONE'S CURRENT AUDIO ROUTE IS",
                            isSelected = outputRouteMode == "AUTO",
                            primaryColor = primaryColor
                        ) {
                            outputRouteMode = "AUTO"
                            outputRouteBtAddress = null
                            outputRouteBtLabel = null
                            syncPhoneAudio()
                            reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                        }

                        OutputRouteRow(
                            label = "ACK WATCH",
                            hint = if (isWatchConnected) {
                                "CONNECTED"
                            } else {
                                "NOT CURRENTLY CONNECTED -- FALLS BACK TO AUTO WHEN UNREACHABLE"
                            },
                            isSelected = outputRouteMode == "WATCH",
                            primaryColor = primaryColor
                        ) {
                            outputRouteMode = "WATCH"
                            outputRouteBtAddress = null
                            outputRouteBtLabel = null
                            syncPhoneAudio()
                            reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                        }

                        connectedBtDevices.forEach { device ->
                            val deviceLabel = AudioRouting.friendlyLabel(device)
                            OutputRouteRow(
                                label = deviceLabel,
                                hint = "CONNECTED",
                                isSelected = outputRouteMode == "BLUETOOTH" &&
                                    outputRouteBtAddress == device.address,
                                primaryColor = primaryColor
                            ) {
                                outputRouteMode = "BLUETOOTH"
                                outputRouteBtAddress = device.address
                                outputRouteBtLabel = deviceLabel
                                syncPhoneAudio()
                                reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                            }
                        }

                        // The saved Bluetooth pick isn't in the live
                        // connected list right now -- still show it (its
                        // cached label) so picking AUTO or another device
                        // is the only way to change it, rather than it
                        // just silently disappearing from the picker.
                        val selectedBtMissing = outputRouteMode == "BLUETOOTH" &&
                            outputRouteBtAddress != null &&
                            connectedBtDevices.none { it.address == outputRouteBtAddress }
                        if (selectedBtMissing) {
                            OutputRouteRow(
                                label = outputRouteBtLabel ?: "BLUETOOTH DEVICE",
                                hint = "NOT CURRENTLY CONNECTED -- FALLS BACK TO AUTO WHEN UNREACHABLE",
                                isSelected = true,
                                primaryColor = primaryColor,
                                enabled = false,
                                onClick = {}
                            )
                        }

                        if (connectedBtDevices.isEmpty() && !selectedBtMissing) {
                            Text(
                                text = "NO BLUETOOTH DEVICES CURRENTLY CONNECTED",
                                color = Color.DarkGray,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                SettingsToggleRow(
                    title = "GUIDE VOX",
                    description = "Controls whether tutorial and guide narration is spoken aloud.",
                    checked = guideVoxEnabled,
                    primaryColor = primaryColor,
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_AUDIO_ROUTING, primaryColor)
                ) { enabled ->
                    guideVoxEnabled = enabled
                    syncPhoneAudio()
                    reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                }

                Spacer(modifier = Modifier.height(16.dp))

                SettingsToggleRow(
                    title = "SILENT MODE",
                    description = "Shows prompts as normal but never speaks them out loud -- for places where sound itself is the problem. Emergency messages and tutorial narration are never silenced.",
                    checked = silentOutput,
                    primaryColor = primaryColor,
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_AUDIO_ROUTING, primaryColor)
                ) { enabled ->
                    silentOutput = enabled
                    syncPhoneAudio()
                    reportHelpInteraction(AckTags.SETTINGS_AUDIO_ROUTING)
                }
            }
            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("WATCH AUDIO FEEDBACK", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ThemeOption(0, "SHARP", if(toneTheme == 0) 0 else -1, primaryColor, modifier = Modifier.testTag(AckTags.SETTINGS_WATCH_AUDIO).helpTarget(AckTags.SETTINGS_WATCH_AUDIO, primaryColor)) { toneTheme = 0; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                    ThemeOption(1, "CLEAN", if(toneTheme == 1) 1 else -1, primaryColor, modifier = Modifier.testTag(AckTags.SETTINGS_WATCH_AUDIO).helpTarget(AckTags.SETTINGS_WATCH_AUDIO, primaryColor)) { toneTheme = 1; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                    ThemeOption(2, "SOFT", if(toneTheme == 2) 2 else -1, primaryColor, modifier = Modifier.testTag(AckTags.SETTINGS_WATCH_AUDIO).helpTarget(AckTags.SETTINGS_WATCH_AUDIO, primaryColor)) { toneTheme = 2; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text("WATCH VOLUME: ${(toneVolume * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = toneVolume, onValueChange = { toneVolume = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray))
            }
            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("VISUAL PROMPT DISPLAY", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    "Text/emoji/GIF prompts fill the screen and rotate their content in place so words display large without wrapping.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            "FORCE DEVICE ROTATION",
                            color = if (forceDeviceRotation) primaryColor else Color.White,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            "OFF: rotate the prompt only. ON: rotate the whole screen (old behavior).",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    NeonToggle(
                        checked = forceDeviceRotation,
                        onCheckedChange = { enabled ->
                            forceDeviceRotation = enabled
                            OverlayDisplayPrefs.setDeviceRotationEnabled(context, enabled)
                        },
                        activeColor = primaryColor
                    )
                }
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("HARDWARE CONFIG", color = NeonPalette.SWATCHES[5], fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))

                Text("CROWN RESISTANCE: LEVEL ${crownSens.toInt()}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = crownSens, onValueChange = { crownSens = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 1f..5f, steps = 3, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("TWIST SENSITIVITY: ${String.format("%.1f", motTwist)}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = motTwist, onValueChange = { motTwist = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 2.0f..12.0f, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("GRAVITY LOCK: ${String.format("%.1f", motPose)}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = motPose, onValueChange = { motPose = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 2.0f..9.0f, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("FIRE GRACE WINDOW: ${fireGraceMs.toInt()}ms", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Text(
                    "Extra time after a pose locks and goes quiet before it fires. Tap the watch face anytime before then to cancel instead.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Slider(value = fireGraceMs, onValueChange = { fireGraceMs = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 250f..1000f, steps = 14, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("WAKE GESTURE WINDOW: ${wakeWindowMs.toInt()}ms", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Text(
                    "How much time is allowed between each of the 3 wake twists. Higher gives more room if your hand isn't perfectly steady.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Slider(value = wakeWindowMs, onValueChange = { wakeWindowMs = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 800f..3000f, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("TARGET FLYOUT TIMEOUT: ${computerFlyoutTimeoutSec.toInt()}s", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Text(
                    "How long the watch's Target Computer flyout (tap-tap-hold on a Quick Actions deck) waits with no interaction before closing itself.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Slider(value = computerFlyoutTimeoutSec, onValueChange = { computerFlyoutTimeoutSec = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 5f..30f, steps = 4, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[5], activeTrackColor = NeonPalette.SWATCHES[5], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))

                Text("AUTO-CRYO: ${autoCryo.toInt()} MIN", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = autoCryo, onValueChange = { autoCryo = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 1f..10f, steps = 8, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[3], activeTrackColor = NeonPalette.SWATCHES[3], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))
            }

            // --- PHONE SHAKE KILL SWITCH ---
            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("SHAKE KILL SWITCH", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    "Shake the phone to immediately stop whatever it's currently saying or showing -- a backstop for a mistaken watch fire or a wrong tap.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(12.dp))

                Text("SENSITIVITY: ${String.format("%.1f", shakeThreshold)} (lower = easier to trigger)", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = shakeThreshold, onValueChange = { shakeThreshold = it }, onValueChangeFinished = { updateShakeThreshold() },
                    valueRange = 8f..25f, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[3], activeTrackColor = NeonPalette.SWATCHES[3], inactiveTrackColor = Color.DarkGray))

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("TRAIN / TEST", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 1.sp)
                    Text(
                        text = if (isShakeTestActive) "[STOP]" else "[TEST]",
                        color = if (isShakeTestActive) Color.Red else primaryColor,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable { isShakeTestActive = !isShakeTestActive }
                    )
                }

                if (isShakeTestActive) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 56.dp)
                            .border(1.dp, if (isShakeDetectedFlash) BioGreen else Color.DarkGray, CutCornerShape(4.dp))
                            .background(if (isShakeDetectedFlash) BioGreen.copy(alpha = 0.15f) else Graphite),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (isShakeDetectedFlash) "DETECTED ✓  ($shakeDetectedCount)" else "ARMED -- SHAKE THE PHONE",
                            color = if (isShakeDetectedFlash) BioGreen else Color.Gray,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Text(
                        "This uses the real detector at the sensitivity above -- shake exactly as hard as you would to actually cut off output, and adjust the slider until that feels right.",
                        color = Color.Gray,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            // --- NEW ENVIRONMENTAL SENSOR SECTION ---
            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("ENVIRONMENT SENSOR", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                    if (hasMicPermission) {
                        Text(
                            text = if (isMonitoringActive) "[STOP]" else "[SCAN]",
                            color = if (isMonitoringActive) Color.Red else primaryColor,

                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier
                                .helpTarget(AckTags.SETTINGS_ENV_SENSOR, primaryColor)
                                .clickable {
                                    isMonitoringActive = !isMonitoringActive
                                    reportHelpInteraction(AckTags.SETTINGS_ENV_SENSOR)
                                }
                        )
                    }
                }
                Spacer(modifier = Modifier.height(12.dp))

                if (!hasMicPermission) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NeonButton(
                            "AUTHORIZE MIC SCAN",
                            Modifier
                                .weight(1f)
                                .helpTarget(AckTags.SETTINGS_ENV_SENSOR, primaryColor),
                            mainColor = primaryColor
                        ) {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                            reportHelpInteraction(AckTags.SETTINGS_ENV_SENSOR)
                        }
                        // Fallback button to manually open App Settings if the system prompt is blocked
                        NeonButton("OPEN SETTINGS", Modifier.weight(1f), mainColor = Color.DarkGray) {
                            val intent = Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                                data = android.net.Uri.fromParts("package", context.packageName, null)
                            }
                            context.startActivity(intent)
                        }
                    }
                } else if (isMonitoringActive) {
                    val maxDb = 95f
                    val fillRatio = (currentDb / maxDb).coerceIn(0f, 1f)

                    val levelColor = when {
                        currentDb > 80f -> Color(0xFFFF0055)
                        currentDb > 65f -> Color(0xFFFF9900)
                        else -> primaryColor
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "${currentDb.toInt()} dB",
                            color = levelColor,
                            fontSize = 24.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Black,
                            modifier = Modifier.width(80.dp)
                        )
                        Box(
                            modifier = Modifier.weight(1f).height(20.dp).background(VoidBlack).border(1.dp, Color.DarkGray, CutCornerShape(4.dp)).padding(2.dp)
                        ) {
                            Box(modifier = Modifier.fillMaxHeight().fillMaxWidth(fillRatio).background(levelColor, CutCornerShape(2.dp)))
                        }
                    }
                    Spacer(modifier = Modifier.height(4.dp))

                    val statusText = when {
                        currentDb > 80f -> "CRITICAL: A.S.R. INTERFERENCE HIGH"
                        currentDb > 65f -> "WARNING: MODERATE NOISE LEVEL"
                        else -> "OPTIMAL: ENVIRONMENT CLEAR"
                    }

                    Text(text = statusText, color = levelColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                } else {
                    Text("MONITOR OFFLINE", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                }
            }

            item {
                Text("QUICK-ACCESS KEYS", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))

                for (i in 0..2) {
                    val shortcut = headerShortcuts.getOrNull(i) ?: CommandRepository.HeaderShortcut("M${i+1}", "")
                    val hasRecording = remember(i, recordingRefreshKey) {
                        VoiceRecordingRepository.getForQuickAccessKey(context, i) != null
                    }
                    Row(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = shortcut.label,
                            onValueChange = { newLabel ->
                                val updated = headerShortcuts.toMutableList(); updated[i] = shortcut.copy(label = newLabel.take(4).uppercase()); headerShortcuts = updated
                                reportHelpInteraction(AckTags.SETTINGS_SHORTCUTS)
                                CommandRepository.saveHeaderShortcuts(context, updated)
                            },
                            modifier = Modifier.weight(0.25f).helpTarget(AckTags.SETTINGS_SHORTCUTS, primaryColor),
                            colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor, unfocusedIndicatorColor = Color.DarkGray),
                            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 10.sp),
                            placeholder = { Text("LBL") }
                        )
                        OutlinedTextField(
                            value = shortcut.phrase,
                            onValueChange = { newPhrase ->
                                val updated = headerShortcuts.toMutableList(); updated[i] = shortcut.copy(phrase = newPhrase); headerShortcuts = updated
                                CommandRepository.saveHeaderShortcuts(context, updated)
                            },
                            modifier = Modifier.weight(0.6f),
                            colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor, unfocusedIndicatorColor = Color.DarkGray),
                            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 10.sp),
                            placeholder = { Text("TARGET PHRASE") }
                        )
                        Box(
                            modifier = Modifier
                                .weight(0.15f)
                                .heightIn(min = 56.dp)
                                .border(1.dp, if (hasRecording) primaryColor else Color.DarkGray, CutCornerShape(4.dp))
                                .background((if (hasRecording) primaryColor else Color.DarkGray).copy(alpha = 0.12f), CutCornerShape(4.dp))
                                .clickable { recordingKeyIndex = i },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = if (hasRecording) "REC" else "+REC",
                                color = if (hasRecording) primaryColor else Color.Gray,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("TERMINAL LOG", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))

                SettingsToggleRow(
                    title = "HIDE SYSTEM MESSAGES",
                    description = "Filters boot, status, and error lines out of the Terminal view. The underlying log is untouched -- switch off to see them again.",
                    checked = hideSystemMessages,
                    primaryColor = primaryColor,
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_TERMINAL_LOG, primaryColor)
                ) { enabled ->
                    hideSystemMessages = enabled
                    TerminalLogStore.setHideSystemMessages(context, enabled)
                    reportHelpInteraction(AckTags.SETTINGS_TERMINAL_LOG)
                }

                Spacer(modifier = Modifier.height(16.dp))

                SettingsToggleRow(
                    title = "HIDE PATH RESOLUTION",
                    description = "Filters out the verbose per-tag RESOLVE trace logged every time a Matrix phrase plays, independent of the toggle above.",
                    checked = hidePathTrace,
                    primaryColor = primaryColor,
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_TERMINAL_LOG, primaryColor)
                ) { enabled ->
                    hidePathTrace = enabled
                    TerminalLogStore.setHidePathTrace(context, enabled)
                    reportHelpInteraction(AckTags.SETTINGS_TERMINAL_LOG)
                }

                Spacer(modifier = Modifier.height(16.dp))

                SettingsToggleRow(
                    title = "MONOSPACE TERMINAL",
                    description = "Renders the Terminal screen -- log rows, the prompt line, command output -- in a true monospace font so columns line up like a real terminal. Off by default to keep the existing look.",
                    checked = monospaceTerminal,
                    primaryColor = primaryColor,
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_TERMINAL_LOG, primaryColor)
                ) { enabled ->
                    monospaceTerminal = enabled
                    TerminalLogStore.setMonospaceEnabled(context, enabled)
                    reportHelpInteraction(AckTags.SETTINGS_TERMINAL_LOG)
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    "STATUSBOX TEXT COLOR",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    "Color of the live TYPING / shared root variable strip above the Terminal prompt.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier
                        .horizontalScroll(rememberScrollState())
                        .helpTarget(AckTags.SETTINGS_TERMINAL_LOG, primaryColor)
                ) {
                    NeonPalette.SWATCHES.forEachIndexed { index, color ->
                        Box(
                            modifier = Modifier
                                .padding(4.dp)
                                .size(36.dp)
                                .background(color, CutCornerShape(4.dp))
                                .border(2.dp, if (statusboxColorIdx == index) Color.White else Color.Transparent, CutCornerShape(4.dp))
                                .clickable {
                                    statusboxColorIdx = index
                                    TerminalLogStore.setStatusboxColorIndex(context, index)
                                    reportHelpInteraction(AckTags.SETTINGS_TERMINAL_LOG)
                                }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    "LOG RETENTION: ${retentionDays.toInt()} DAY${if (retentionDays.toInt() == 1) "" else "S"} (ROLLING)",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    "Entries older than this roll off on a continuous window, not a calendar day -- up to ${TerminalLogStore.MAX_ENTRIES} kept either way.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Slider(
                    value = retentionDays,
                    onValueChange = { retentionDays = it },
                    onValueChangeFinished = {
                        TerminalLogStore.applyRetention(context, logs, retentionDays.toInt())
                        reportHelpInteraction(AckTags.SETTINGS_TERMINAL_LOG)
                    },
                    valueRange = TerminalLogStore.MIN_RETENTION_DAYS.toFloat()..TerminalLogStore.MAX_RETENTION_DAYS.toFloat(),
                    steps = TerminalLogStore.MAX_RETENTION_DAYS - TerminalLogStore.MIN_RETENTION_DAYS - 1,
                    colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(AckTags.SETTINGS_TERMINAL_LOG, primaryColor)
                )
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("DATA PORT", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NeonButton(
                        "EXPORT .JSON",
                        Modifier
                            .weight(1f)
                            .helpTarget(AckTags.SETTINGS_DATA_PORT, primaryColor),
                        mainColor = primaryColor
                    ) {
                        exportLauncher.launch(
                            "ack_backup_${System.currentTimeMillis()}.json"
                        )

                        reportHelpInteraction(AckTags.SETTINGS_DATA_PORT)
                    }
                    NeonButton("IMPORT MATRIX AS NEW DECK", Modifier.weight(1f), mainColor = primaryColor) { importLauncher.launch(arrayOf("application/json")) }
                }
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    "IMPORT MATRIX AS NEW DECK brings in a backup's matrix phrases as a brand new deck, without touching anything else. FULL RESTORE below applies everything else a backup carries -- overwriting or adding to your current setup, never deleting what it doesn't mention.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(8.dp))
                NeonButton(
                    "FULL RESTORE FROM JSON",
                    Modifier
                        .fillMaxWidth()
                        .testTag(AckTags.SETTINGS_FULL_RESTORE_BTN)
                        .helpTarget(AckTags.SETTINGS_FULL_RESTORE_BTN, primaryColor),
                    mainColor = primaryColor
                ) {
                    fullRestoreLauncher.launch(arrayOf("application/json"))
                    reportHelpInteraction(AckTags.SETTINGS_FULL_RESTORE_BTN)
                }
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("VOICE RECORDINGS", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    "Manage voice clips recorded for Quick Actions prompts.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(12.dp))
                NeonButton(
                    "MANAGE RECORDINGS",
                    Modifier
                        .fillMaxWidth()
                        .testTag(AckTags.VOICE_REC_MANAGE_BTN)
                        .helpTarget(AckTags.VOICE_REC_MANAGE_BTN, primaryColor),
                    mainColor = primaryColor
                ) {
                    showManageRecordings = true
                    reportHelpInteraction(AckTags.VOICE_REC_MANAGE_BTN)
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    "RECORDING PLAYBACK GAIN: ${recordingGainPercent.toInt()}%",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    "Trims volume for recorded voice prompts only, on top of the master gain above -- everything else (synthesized speech) is unaffected.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Slider(
                    value = recordingGainPercent,
                    onValueChange = { recordingGainPercent = (it / 5f).roundToInt() * 5f },
                    onValueChangeFinished = {
                        VoiceRecordingRepository.setPlaybackGainPercent(context, recordingGainPercent.toInt())
                    },
                    valueRange = 0f..VoiceRecordingRepository.MAX_PLAYBACK_GAIN_PERCENT.toFloat(),
                    steps = (VoiceRecordingRepository.MAX_PLAYBACK_GAIN_PERCENT / 5) - 1,
                    colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray)
                )
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("AUTOCOMPLETE", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    "ACK remembers what you've typed into Matrix and Quick Actions variable fields and Shared Root Variables, offering your most-used past values back as tappable chips. Local to this device, and included in EXPORT .JSON backups.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(12.dp))
                NeonButton(
                    "MANAGE AUTOCOMPLETE",
                    Modifier
                        .fillMaxWidth()
                        .testTag(AckTags.AUTOCOMPLETE_MANAGE_BTN)
                        .helpTarget(AckTags.AUTOCOMPLETE_MANAGE_BTN, primaryColor),
                    mainColor = primaryColor
                ) {
                    showManageAutocomplete = true
                    reportHelpInteraction(AckTags.AUTOCOMPLETE_MANAGE_BTN)
                }
            }
        }
        HeroButton("UPLOAD PROTOCOL", Modifier.fillMaxWidth().testTag(AckTags.UPLOAD_BTN), mainColor = primaryColor) { syncAll(); onUploadClick() }
    }

    if (showImportDialog && importedBackup != null) {
        AlertDialog(
            onDismissRequest = { showImportDialog = false }, containerColor = Graphite,
            title = { Text("IMPORT CONFIGURATION", color = primaryColor, fontFamily = FontFamily.Monospace) },
            text = { Column {
                Text("Import as new Deck? Select identity color:", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(value = newDeckName, onValueChange = { newDeckName = it.uppercase() }, placeholder = { Text("DECK NAME") }, colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor, unfocusedIndicatorColor = Color.Gray))
                Spacer(modifier = Modifier.height(12.dp))
                Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                    NeonPalette.SWATCHES.forEachIndexed { index, color -> Box(modifier = Modifier.padding(4.dp).size(36.dp).background(color, CutCornerShape(4.dp)).border(2.dp, if(selectedColorIdx == index) Color.White else Color.Transparent, CutCornerShape(4.dp)).clickable { selectedColorIdx = index }) }
                }
            }},
            confirmButton = {
                NeonButton("CREATE DECK", isActive = true, mainColor = primaryColor) {
                    if(newDeckName.isNotEmpty()) {
                        CommandRepository.saveDeck(context, newDeckName, selectedColorIdx, importedBackup!!.matrixData)
                        showImportDialog = false; newDeckName = ""; WatchSync.sendDeckList(context)
                        Toast.makeText(context, "DECK CREATED -- RESTARTING", Toast.LENGTH_SHORT).show()
                        pendingRestart = true
                    }
                }
            },
            dismissButton = { Text("CANCEL", color = Color.Red, modifier = Modifier.clickable { showImportDialog = false }.padding(8.dp)) }
        )
    }

    if (showManageRecordings) {
        ManageRecordingsDialog(
            context = context,
            primaryColor = primaryColor,
            onDismiss = { showManageRecordings = false }
        )
    }

    if (showManageAutocomplete) {
        ManageAutocompleteDialog(
            context = context,
            primaryColor = primaryColor,
            onDismiss = { showManageAutocomplete = false }
        )
    }

    if (showFullRestoreConfirm) {
        TightDialogSurface(
            onDismiss = {
                showFullRestoreConfirm = false
                pendingFullRestoreJson = null
            },
            primaryColor = primaryColor,
            title = "FULL RESTORE FROM JSON",
            dismissLabel = "CANCEL"
        ) {
            Text(
                "This applies whatever the selected file contains -- decks, quick actions, root overrides, target computer entries, emergency prompts, voice recordings, autocomplete history, Geo-Protocol zones, visual presets, output routing, and more -- overwriting a matching entry by its id, or adding it if you don't already have one. Nothing on this device that the file doesn't mention is touched or removed. To clear something instead, use that feature's own dedicated clear/delete action.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("RESTORE", Modifier.weight(1f), mainColor = primaryColor) {
                    val rawJson = pendingFullRestoreJson
                    if (rawJson != null) {
                        val success = TransferManager.restoreBackup(context, rawJson)
                        if (success) {
                            WatchSync.sendDeckList(context)
                            Toast.makeText(context, "PROTOCOL RESTORED -- RESTARTING", Toast.LENGTH_SHORT).show()
                            pendingRestart = true
                        } else {
                            Toast.makeText(context, "INTEGRITY CHECK FAILED", Toast.LENGTH_SHORT).show()
                        }
                    }
                    showFullRestoreConfirm = false
                    pendingFullRestoreJson = null
                }
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    showFullRestoreConfirm = false
                    pendingFullRestoreJson = null
                }
            }
        }
    }

    val keyIndex = recordingKeyIndex
    if (keyIndex != null) {
        val keyLabel = headerShortcuts.getOrNull(keyIndex)?.label ?: "M${keyIndex + 1}"
        TightDialogSurface(
            onDismiss = { recordingKeyIndex = null },
            primaryColor = primaryColor,
            title = "$keyLabel RECORDING"
        ) {
            VoiceRecordingPanel(
                context = context,
                primaryColor = primaryColor,
                panelKey = "qk_$keyIndex",
                existingRecording = VoiceRecordingRepository.getForQuickAccessKey(context, keyIndex),
                description = "WHEN SET, THIS PLAYS INSTEAD OF THE KEY'S TARGET PHRASE.",
                onAccept = { pcm, sampleRate ->
                    VoiceRecordingRepository.saveForQuickAccessKey(context, keyIndex, pcm, sampleRate)
                    recordingRefreshKey++
                },
                onRemove = {
                    VoiceRecordingRepository.deleteForQuickAccessKey(context, keyIndex)
                    recordingRefreshKey++
                }
            )
        }
    }
}