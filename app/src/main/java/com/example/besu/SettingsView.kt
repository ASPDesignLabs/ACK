package com.example.besu

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack




@Composable
fun SettingsView(context: Context, primaryColor: Color, onUploadClick: () -> Unit) {
    val prefs = context.getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)

    val helpManager = LocalHelpManager.current

    var toneTheme by remember { mutableIntStateOf(prefs.getInt("TONE_THEME", 1)) }
    var toneVolume by remember { mutableFloatStateOf(prefs.getFloat("TONE_VOLUME", 0.8f)) }
    var autoCryo by remember { mutableFloatStateOf(prefs.getInt("AUTO_CRYO", 10).toFloat()) }
    var crownSens by remember { mutableFloatStateOf(prefs.getInt("CROWN_SENS", 2).toFloat()) }
    var motTwist by remember { mutableFloatStateOf(prefs.getFloat("MOT_TWIST", 7.0f)) }
    var motPose by remember { mutableFloatStateOf(prefs.getFloat("MOT_POSE", 6.0f)) }
    var headerShortcuts by remember { mutableStateOf(CommandRepository.getHeaderShortcuts(context)) }






    fun syncAll() {
        prefs.edit().putInt("TONE_THEME", toneTheme).putFloat("TONE_VOLUME", toneVolume)
            .putInt("AUTO_CRYO", autoCryo.toInt()).putInt("CROWN_SENS", crownSens.toInt())
            .putFloat("MOT_TWIST", motTwist).putFloat("MOT_POSE", motPose).apply()

        WatchSync.sendAudioConfig(context, toneTheme, toneVolume)
        WatchSync.sendPowerConfig(context, autoCryo.toInt())
        WatchSync.sendCrownSensitivity(context, crownSens.toInt())
        WatchSync.sendMotionConfig(context, motTwist, motPose)
    }

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(
            HelpEvent.Interacted(tag)
        )
    }

    var showImportDialog by remember { mutableStateOf(false) }
    var importedBackup by remember { mutableStateOf<AckBackup?>(null) }
    var newDeckName by remember { mutableStateOf("") }
    var selectedColorIdx by remember { mutableIntStateOf(0) }

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let {
            try {
                val jsonStr = TransferManager.readTextFromUri(context, it)
                val backup = TransferManager.parseQrPayload(jsonStr)
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

    val customScannerLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        WatchSync.sendDeckList(context)
    }

    fun launchQrScanner() {
        val intent = Intent(context, MosaicScannerActivity::class.java)
        customScannerLauncher.launch(intent)
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
                Text("WATCH AUDIO FEEDBACK", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ThemeOption(0, "SHARP", if(toneTheme == 0) 0 else -1, primaryColor) { toneTheme = 0; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                    ThemeOption(1, "CLEAN", if(toneTheme == 1) 1 else -1, primaryColor) { toneTheme = 1; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                    ThemeOption(2, "SOFT", if(toneTheme == 2) 2 else -1, primaryColor) { toneTheme = 2; syncAll()
                        reportHelpInteraction(AckTags.SETTINGS_WATCH_AUDIO)}
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text("WATCH VOLUME: ${(toneVolume * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = toneVolume, onValueChange = { toneVolume = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray))
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

                Text("AUTO-CRYO: ${autoCryo.toInt()} MIN", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = autoCryo, onValueChange = { autoCryo = it }, onValueChangeFinished = { syncAll()
                    reportHelpInteraction(AckTags.SETTINGS_WATCH_CONFIG)}, valueRange = 1f..10f, steps = 8, colors = SliderDefaults.colors(thumbColor = NeonPalette.SWATCHES[3], activeTrackColor = NeonPalette.SWATCHES[3], inactiveTrackColor = Color.DarkGray),
                    modifier = Modifier.helpTarget(
                        AckTags.SETTINGS_WATCH_CONFIG,
                        primaryColor
                    ))
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
                    Row(modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = shortcut.label,
                            onValueChange = { newLabel ->
                                val updated = headerShortcuts.toMutableList(); updated[i] = shortcut.copy(label = newLabel.take(4).uppercase()); headerShortcuts = updated
                                reportHelpInteraction(AckTags.SETTINGS_SHORTCUTS)
                                CommandRepository.saveHeaderShortcuts(context, updated)
                            },
                            modifier = Modifier.weight(0.3f).helpTarget(AckTags.SETTINGS_SHORTCUTS, primaryColor),
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
                            modifier = Modifier.weight(0.7f),
                            colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor, unfocusedIndicatorColor = Color.DarkGray),
                            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 10.sp),
                            placeholder = { Text("TARGET PHRASE") }
                        )
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(24.dp)); Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray)); Spacer(modifier = Modifier.height(24.dp)) }

            item {
                Text("DATA PORT", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                Spacer(modifier = Modifier.height(12.dp))
                NeonButton(
                    "OPTICAL SYNC [QR]",
                    Modifier
                        .fillMaxWidth()
                        .helpTarget(AckTags.SETTINGS_DATA_PORT, primaryColor),
                    mainColor = primaryColor
                ) {
                    launchQrScanner()
                    reportHelpInteraction(AckTags.SETTINGS_DATA_PORT)
                }
                Spacer(modifier = Modifier.height(8.dp))
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
                    NeonButton("IMPORT .JSON", Modifier.weight(1f), mainColor = primaryColor) { importLauncher.launch(arrayOf("application/json")) }
                }
            }
        }
        HeroButton("UPLOAD PROTOCOL", Modifier.fillMaxWidth().tutorialTarget(AckTags.UPLOAD_BTN), mainColor = primaryColor) { syncAll(); onUploadClick() }
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
                    }
                }
            },
            dismissButton = { Text("CANCEL", color = Color.Red, modifier = Modifier.clickable { showImportDialog = false }.padding(8.dp)) }
        )
    }
}