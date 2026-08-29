package com.example.besu

import android.content.Context
import android.content.Intent
import android.speech.tts.Voice
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.verticalScroll
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
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Composable
fun AudioArchitectView(context: Context, primaryColor: Color, systemVoices: List<Voice>) {
    val prefs = context.getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)
    val helpManager = LocalHelpManager.current

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(
            HelpEvent.Interacted(tag)
        )
    }

    fun reportTextCommit(tag: String) {
        helpManager?.onEvent(
            HelpEvent.TextCommitted(tag)
        )
    }
    
    var userProfile by remember { mutableStateOf(prefs.getString("USER_VOX_PROFILE", "CYBER") ?: "CYBER") }
    var cadenceAmount by remember { mutableFloatStateOf(prefs.getFloat("VOX_CADENCE", 0.0f)) }
    var forceSpeaker by remember { mutableStateOf(prefs.getBoolean("FORCE_SPEAKER", false)) }
    var isVoxEnabled by remember { mutableStateOf(prefs.getBoolean("TUTORIAL_VOX", true)) }
    var masterGain by remember { mutableFloatStateOf(prefs.getFloat("MASTER_GAIN", 1.0f)) }

    var customVoices by remember {
        mutableStateOf<MutableList<VoiceProfile>>(
            try {
                val json = prefs.getString("CUSTOM_VOICES", "[]") ?: "[]"
                Json.decodeFromString<List<VoiceProfile>>(json).toMutableList()
            } catch (e: Exception) { mutableListOf() }
        )
    }
    
    var showVoicePicker by remember { mutableStateOf(false) }
    
    val activeIdx = customVoices.indexOfFirst { it.id == userProfile }
    var editingProfile by remember(userProfile) { 
        mutableStateOf(if (activeIdx != -1) customVoices[activeIdx] else null) 
    }

    fun syncDsp() {
        prefs.edit()
            .putString("USER_VOX_PROFILE", userProfile)
            .putFloat("VOX_CADENCE", cadenceAmount)
            .putBoolean("FORCE_SPEAKER", forceSpeaker)
            .putBoolean("TUTORIAL_VOX", isVoxEnabled)
            .putFloat("MASTER_GAIN", masterGain)
            .putString("CUSTOM_VOICES", Json.encodeToString(customVoices))
            .apply()
            
        val intent = Intent(context, OutputService::class.java).apply { 
            action = "UPDATE_DSP"
            putExtra("user_profile", userProfile)
            putExtra("cadence", cadenceAmount)
            putExtra("speaker", forceSpeaker)
            putExtra("master_gain", masterGain)
            putExtra("custom_voices_json", Json.encodeToString(customVoices))
        }
        context.startService(intent)
    }

    fun saveEditingProfile() {
        if (activeIdx != -1 && editingProfile != null) {
            customVoices[activeIdx] = editingProfile!!
            syncDsp()
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("AUDIO ARCHITECT", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
        Spacer(modifier = Modifier.height(16.dp))
        
        LazyColumn(modifier = Modifier.weight(0.4f)) {
            item {
                Text("GLOBAL OUTPUT", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(8.dp))
                
                Text("MASTER GAIN: ${(masterGain * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(
                    value = masterGain,
                    valueRange = 0f..2f,
                    onValueChange = {
                        masterGain = it
                    },
                    onValueChangeFinished = {
                        syncDsp()
                        reportHelpInteraction(AckTags.AUDIO_MASTER_GAIN)
                    },
                    modifier = Modifier.helpTarget(
                        AckTags.AUDIO_MASTER_GAIN,
                        primaryColor
                    ),
                    colors = SliderDefaults.colors(
                        thumbColor = primaryColor,
                        activeTrackColor = primaryColor,
                        inactiveTrackColor = Color.DarkGray
                    )
                )

                Text("GLOBAL CADENCE: ${(cadenceAmount * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = cadenceAmount, onValueChange = { cadenceAmount = it }, onValueChangeFinished = { syncDsp()
                    reportHelpInteraction(AckTags.AUDIO_MASTER_GAIN)},
                    modifier = Modifier.helpTarget(
                        AckTags.AUDIO_MASTER_GAIN,
                        primaryColor
                    ),
                    colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray))
                
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NeonButton(
                        "FORCE SPKR: ${if (forceSpeaker) "ON" else "OFF"}",
                        Modifier
                            .weight(1f)
                            .helpTarget(AckTags.AUDIO_OUTPUT_ROUTING, primaryColor),
                        isActive = forceSpeaker,
                        mainColor = primaryColor
                    ) {
                        forceSpeaker = !forceSpeaker
                        syncDsp()
                        reportHelpInteraction(AckTags.AUDIO_OUTPUT_ROUTING)
                    }
                    NeonButton(
                        "GUIDE VOX: ${if (isVoxEnabled) "ON" else "OFF"}", Modifier.weight(1f)
                            .helpTarget(AckTags.AUDIO_OUTPUT_ROUTING, primaryColor),
                        isActive = isVoxEnabled,
                        mainColor = primaryColor
                    ) {
                        isVoxEnabled = !isVoxEnabled;
                        syncDsp()
                        reportHelpInteraction(AckTags.AUDIO_OUTPUT_ROUTING)
                    }
                }
                Spacer(modifier = Modifier.height(12.dp))
                Text("VOICE PROFILE", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("CYBER", "MECH", "ORGANIC").forEach { name -> ThemeOption(0, name, if(userProfile == name) 0 else -1, primaryColor) { userProfile = name; syncDsp() } }
                }
                Spacer(modifier = Modifier.height(8.dp))
                if (customVoices.isNotEmpty()) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (i in customVoices.indices) {
                            val profile = customVoices[i]
                            ThemeOption(
                                0,
                                profile.label,
                                if (userProfile == profile.id) 0 else -1,
                                primaryColor
                            ) {
                                userProfile = profile.id
                                syncDsp()

                                reportHelpInteraction(AckTags.AUDIO_PROFILE_SELECT)
                            }
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        if (editingProfile != null) {
            val p = editingProfile!!
            val voiceName = if(p.systemVoiceName.isNotEmpty()) p.systemVoiceName.takeLast(15) else "DEFAULT"
            val isRobotic = p.modDepth > 0.05f

            Column(modifier = Modifier.weight(0.6f).fillMaxWidth().border(1.dp, primaryColor, CutCornerShape(12.dp)).background(VoidBlack).padding(12.dp)) {
                
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text("DSP CHAIN // ${p.label}", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                    Text("UNSAVED*", color = if(customVoices[activeIdx] != p) NeonPalette.SWATCHES[3] else Color.Transparent, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                }
                Spacer(modifier = Modifier.height(12.dp))

                Column(modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    Text("--- BASE SIGNAL ---", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Spacer(modifier = Modifier.height(4.dp))
                    NeonButton(
                        "BASE VOICE: $voiceName",
                        Modifier
                            .fillMaxWidth()
                            .helpTarget(AckTags.AUDIO_VOICE_PICKER, primaryColor),
                        mainColor = primaryColor
                    ) {
                        showVoicePicker = true
                    }
                    
                    Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                        Text("RESET TO HUMAN", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { 
                             editingProfile = p.copy(pitch = 1.0f, speed = 1.0f, modDepth = 0f) 
                        }.padding(4.dp))
                    }
                    
                    Spacer(modifier = Modifier.height(4.dp))
                    DspSlider("PITCH SHIFT", p.pitch, 0.5f..2.0f, primaryColor) { editingProfile = p.copy(pitch = it) }
                    DspSlider("SPEED", p.speed, 0.5f..2.0f, primaryColor) { editingProfile = p.copy(speed = it) }
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                        Text("--- ROBOTIC OVERLAY ---", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                        NeonButton(if(isRobotic) "ON" else "OFF", Modifier.width(60.dp), isActive = isRobotic, mainColor = primaryColor) {
                            if (isRobotic) {
                                editingProfile = p.copy(modDepth = 0f)
                            } else {
                                editingProfile = p.copy(modDepth = 0.5f, modFreq = 50f)
                            }
                        }
                    }
                    
                    if (isRobotic) {
                        Spacer(modifier = Modifier.height(4.dp))
                        DspSlider("ROBOTIC FREQ (HZ)", p.modFreq, 0f..100f, primaryColor) { editingProfile = p.copy(modFreq = it) }
                        DspSlider("ROBOTIC DEPTH (%)", p.modDepth, 0f..1f, primaryColor) { editingProfile = p.copy(modDepth = it) }
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Text("--- TEXTURE ---", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Spacer(modifier = Modifier.height(4.dp))
                    DspSlider("BITCRUSH (%)", p.crush, 0f..1f, primaryColor) { editingProfile = p.copy(crush = it) }
                }

                Spacer(modifier = Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NeonButton("PREVIEW", Modifier.weight(1f), mainColor = primaryColor) {
                        val intent = Intent(context, OutputService::class.java).apply { 
                            action = "UPDATE_DSP"
                            putExtra("user_profile", userProfile)
                            putExtra("custom_voices_json", Json.encodeToString(customVoices.toMutableList().apply { set(activeIdx, editingProfile!!) }))
                        }
                        context.startService(intent)
                        val playIntent = Intent(context, OutputService::class.java); playIntent.action = "TEST_SIGNAL"; context.startService(playIntent)
                    }
                    HeroButton(
                        "COMMIT",
                        Modifier
                            .weight(1f)
                            .testTag(AckTags.AUDIO_SAVE)
                            .helpTarget(AckTags.AUDIO_SAVE, primaryColor),
                        mainColor = NeonPalette.SWATCHES[2]
                    ) {
                        saveEditingProfile()
                        reportTextCommit(AckTags.AUDIO_SAVE)
                    }
                }
            }
        } else {
            Box(modifier = Modifier.weight(0.6f).fillMaxWidth().border(1.dp, Color.Gray, CutCornerShape(12.dp)).padding(24.dp), contentAlignment = Alignment.Center) {
                Text("FACTORY PRESET LOCKED\nSELECT A CUSTOM SLOT TO EDIT", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
            }
        }
    }
    
    if (showVoicePicker) {
        AlertDialog(
            onDismissRequest = { showVoicePicker = false },
            containerColor = Graphite,
            title = { Text("SELECT SYSTEM VOICE", color = primaryColor, fontFamily = FontFamily.Monospace) },
            text = {
                LazyColumn(modifier = Modifier.height(300.dp)) {
                    items(systemVoices) { voice ->
                        val isSelected = editingProfile?.systemVoiceName == voice.name
                        Row(modifier = Modifier.fillMaxWidth().background(if(isSelected) primaryColor.copy(alpha=0.2f) else Color.Transparent).clickable { 
                            editingProfile = editingProfile?.copy(systemVoiceName = voice.name)
                            showVoicePicker = false

                            reportHelpInteraction(AckTags.AUDIO_VOICE_PICKER)
                        }.padding(12.dp)) {
                            Text(voice.name, color = if(isSelected) primaryColor else Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                        }
                        Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
                    }
                }
            },
            confirmButton = {},
            dismissButton = { Text("CANCEL", color = Color.Red, modifier = Modifier.clickable { showVoicePicker = false }.padding(8.dp)) }
        )
    }
}
