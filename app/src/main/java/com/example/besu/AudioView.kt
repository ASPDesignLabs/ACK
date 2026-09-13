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
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.besu.ui.theme.ErrorRed
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

// Small enough that the profile chip row never has to wrap onto a second
// line on a phone-width screen -- well under the 20-profile cap the backup
// importer enforces (TransferManager.kt).
private const val MAX_CUSTOM_PROFILES = 8

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
    var masterGain by remember { mutableFloatStateOf(prefs.getFloat("MASTER_GAIN", 1.0f)) }

    // A SnapshotStateList so mutating an entry in place (rename, DSP edits)
    // is itself observable -- a plain MutableList behind mutableStateOf only
    // notifies Compose when the whole list reference is reassigned, not when
    // an element inside it changes.
    val customVoices = remember {
        mutableStateListOf<VoiceProfile>().apply {
            try {
                val json = prefs.getString("CUSTOM_VOICES", "[]") ?: "[]"
                addAll(Json.decodeFromString<List<VoiceProfile>>(json))
            } catch (e: Exception) { /* start empty */ }
        }
    }

    var showVoicePicker by remember { mutableStateOf(false) }
    var showManageProfiles by remember { mutableStateOf(false) }
    var showRoboticEditor by remember { mutableStateOf(false) }
    var deleteTargetId by remember { mutableStateOf<String?>(null) }

    val activeIdx = customVoices.indexOfFirst { it.id == userProfile }
    var editingProfile by remember(userProfile) {
        mutableStateOf(if (activeIdx != -1) customVoices[activeIdx] else null)
    }

    fun syncDsp() {
        prefs.edit()
            .putString("USER_VOX_PROFILE", userProfile)
            .putFloat("VOX_CADENCE", cadenceAmount)
            .putFloat("MASTER_GAIN", masterGain)
            .putString("CUSTOM_VOICES", Json.encodeToString(customVoices.toList()))
            .apply()

        val intent = Intent(context, OutputService::class.java).apply {
            action = "UPDATE_DSP"
            putExtra("user_profile", userProfile)
            putExtra("cadence", cadenceAmount)
            putExtra("master_gain", masterGain)
            putExtra("custom_voices_json", Json.encodeToString(customVoices.toList()))
        }
        context.startService(intent)
    }

    fun saveEditingProfile() {
        if (activeIdx != -1 && editingProfile != null) {
            customVoices[activeIdx] = editingProfile!!
            syncDsp()
        }
    }

    fun discardEditingProfile() {
        editingProfile = customVoices.getOrNull(activeIdx)
        // PREVIEW pushes uncommitted values straight to the live service;
        // re-sync the committed truth so a discard after a preview doesn't
        // leave the service holding the discarded values.
        syncDsp()
    }

    fun createProfile() {
        if (customVoices.size >= MAX_CUSTOM_PROFILES) return
        val newId = "USER_" + UUID.randomUUID().toString().take(8).uppercase()
        val newLabel = "CUSTOM ${'A' + customVoices.size}"
        // Flat/neutral starting point -- a new profile shouldn't surprise
        // the user with an effect they didn't choose.
        customVoices.add(VoiceProfile(newId, newLabel, 1.0f, 1.0f, 0f, 0f, 0f))
        userProfile = newId
        syncDsp()
    }

    fun renameProfile(id: String, newLabel: String) {
        val idx = customVoices.indexOfFirst { it.id == id }
        val trimmed = newLabel.trim().take(20)
        if (idx == -1 || trimmed.isEmpty()) return
        customVoices[idx] = customVoices[idx].copy(label = trimmed)
        if (userProfile == id) {
            editingProfile = editingProfile?.copy(label = trimmed)
        }
        syncDsp()
    }

    fun deleteProfile(id: String) {
        val idx = customVoices.indexOfFirst { it.id == id }
        if (idx == -1) return
        customVoices.removeAt(idx)
        if (userProfile == id) {
            userProfile = "CYBER"
        }
        syncDsp()
    }

    fun previewCurrentEdit() {
        val current = editingProfile ?: return
        val previewList = customVoices.toMutableList().apply {
            if (activeIdx != -1) set(activeIdx, current) else add(current)
        }
        val intent = Intent(context, OutputService::class.java).apply {
            action = "UPDATE_DSP"
            putExtra("user_profile", userProfile)
            putExtra("custom_voices_json", Json.encodeToString(previewList.toList()))
        }
        context.startService(intent)
        val playIntent = Intent(context, OutputService::class.java)
        playIntent.action = "TEST_SIGNAL"
        context.startService(playIntent)
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("AUDIO ARCHITECT", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
        Spacer(modifier = Modifier.height(10.dp))

        // --- GLOBAL OUTPUT ---
        Text("MASTER GAIN: ${(masterGain * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Slider(
            value = masterGain,
            valueRange = 0f..2f,
            onValueChange = { masterGain = it },
            onValueChangeFinished = {
                syncDsp()
                reportHelpInteraction(AckTags.AUDIO_MASTER_GAIN)
            },
            modifier = Modifier.helpTarget(AckTags.AUDIO_MASTER_GAIN, primaryColor),
            colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray)
        )

        Text("GLOBAL CADENCE: ${(cadenceAmount * 100).toInt()}%", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Slider(
            value = cadenceAmount,
            onValueChange = { cadenceAmount = it },
            onValueChangeFinished = {
                syncDsp()
                reportHelpInteraction(AckTags.AUDIO_MASTER_GAIN)
            },
            modifier = Modifier.helpTarget(AckTags.AUDIO_MASTER_GAIN, primaryColor),
            colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray)
        )

        Spacer(modifier = Modifier.height(10.dp))

        // --- VOICE PROFILE SELECTOR ---
        Text("VOICE PROFILE", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Spacer(modifier = Modifier.height(8.dp))
        FlowRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            listOf("CYBER", "MECH", "ORGANIC").forEach { name ->
                AudioProfileChip(name, userProfile == name, primaryColor) {
                    userProfile = name
                    syncDsp()
                }
            }
            for (i in customVoices.indices) {
                val profile = customVoices[i]
                AudioProfileChip(
                    profile.label,
                    userProfile == profile.id,
                    primaryColor,
                    modifier = Modifier
                        .testTag(AckTags.AUDIO_PROFILE_SELECT)
                        .helpTarget(AckTags.AUDIO_PROFILE_SELECT, primaryColor)
                ) {
                    userProfile = profile.id
                    syncDsp()
                    reportHelpInteraction(AckTags.AUDIO_PROFILE_SELECT)
                }
            }
            if (customVoices.size < MAX_CUSTOM_PROFILES) {
                AudioProfileChip("+ NEW", false, primaryColor) { createProfile() }
            }
        }
        Spacer(modifier = Modifier.height(10.dp))
        NeonButton(
            "MANAGE PROFILES",
            Modifier.fillMaxWidth().helpTarget(AckTags.AUDIO_PROFILE_MANAGE, primaryColor),
            mainColor = primaryColor
        ) {
            showManageProfiles = true
            reportHelpInteraction(AckTags.AUDIO_PROFILE_MANAGE)
        }

        Spacer(modifier = Modifier.height(10.dp))

        // --- DSP CHAIN (fills remaining space, no internal page scroll) ---
        if (editingProfile != null) {
            val p = editingProfile!!
            val voiceName = if (p.systemVoiceName.isNotEmpty()) p.systemVoiceName.takeLast(15) else "DEFAULT"
            val isRobotic = p.modDepth > 0.05f

            Column(modifier = Modifier.weight(1f).fillMaxWidth().border(1.dp, primaryColor, CutCornerShape(12.dp)).background(VoidBlack).padding(12.dp)) {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text("DSP CHAIN // ${p.label}", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                    Text("UNSAVED*", color = if (customVoices[activeIdx] != p) NeonPalette.SWATCHES[3] else Color.Transparent, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                }
                Spacer(modifier = Modifier.height(8.dp))

                NeonButton(
                    "BASE VOICE: $voiceName",
                    Modifier.fillMaxWidth().helpTarget(AckTags.AUDIO_VOICE_PICKER, primaryColor),
                    mainColor = primaryColor
                ) {
                    showVoicePicker = true
                }

                Spacer(modifier = Modifier.height(8.dp))

                Column(modifier = Modifier.helpTarget(AckTags.AUDIO_PITCH_SPEED, primaryColor)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(modifier = Modifier.weight(1f)) {
                            DspSlider("PITCH", p.pitch, 0.5f..2.0f, primaryColor) {
                                editingProfile = p.copy(pitch = it)
                                reportHelpInteraction(AckTags.AUDIO_PITCH_SPEED)
                            }
                        }
                        Box(modifier = Modifier.weight(1f)) {
                            DspSlider("SPEED", p.speed, 0.5f..2.0f, primaryColor) {
                                editingProfile = p.copy(speed = it)
                                reportHelpInteraction(AckTags.AUDIO_PITCH_SPEED)
                            }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                        Text(
                            "RESET TO HUMAN",
                            color = primaryColor,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.clickable {
                                editingProfile = p.copy(pitch = 1.0f, speed = 1.0f, modDepth = 0f)
                            }.padding(4.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column {
                        Text("ROBOTIC OVERLAY", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                        if (isRobotic) {
                            Text(
                                "${p.modFreq.toInt()}Hz / ${(p.modDepth * 100).toInt()}%",
                                color = primaryColor,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NeonButton(if (isRobotic) "ON" else "OFF", Modifier.width(60.dp), isActive = isRobotic, mainColor = primaryColor) {
                            editingProfile = if (isRobotic) {
                                p.copy(modDepth = 0f)
                            } else {
                                p.copy(modDepth = 0.5f, modFreq = 50f)
                            }
                        }
                        NeonButton(
                            "EDIT",
                            Modifier.width(70.dp).helpTarget(AckTags.AUDIO_ROBOTIC_OVERLAY, primaryColor),
                            isActive = isRobotic,
                            mainColor = primaryColor
                        ) {
                            if (isRobotic) {
                                showRoboticEditor = true
                                reportHelpInteraction(AckTags.AUDIO_ROBOTIC_OVERLAY)
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))

                Box(modifier = Modifier.helpTarget(AckTags.AUDIO_BITCRUSH, primaryColor)) {
                    DspSlider("BITCRUSH (%)", p.crush, 0f..1f, primaryColor) {
                        editingProfile = p.copy(crush = it)
                        reportHelpInteraction(AckTags.AUDIO_BITCRUSH)
                    }
                }

                Spacer(modifier = Modifier.weight(1f))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NeonButton("PREVIEW", Modifier.weight(1f), mainColor = primaryColor) {
                        previewCurrentEdit()
                    }
                    NeonButton("DISCARD", Modifier.weight(1f), mainColor = Color.Gray) {
                        discardEditingProfile()
                    }
                    HeroButton(
                        "COMMIT",
                        Modifier.weight(1f).testTag(AckTags.AUDIO_SAVE).helpTarget(AckTags.AUDIO_SAVE, primaryColor),
                        mainColor = NeonPalette.SWATCHES[2]
                    ) {
                        saveEditingProfile()
                        reportTextCommit(AckTags.AUDIO_SAVE)
                    }
                }
            }
        } else {
            Box(modifier = Modifier.weight(1f).fillMaxWidth().border(1.dp, Color.Gray, CutCornerShape(12.dp)).padding(24.dp), contentAlignment = Alignment.Center) {
                Text("FACTORY PRESET LOCKED\nSELECT OR CREATE A CUSTOM SLOT TO EDIT", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, textAlign = TextAlign.Center)
            }
        }
    }

    if (showVoicePicker) {
        AudioDialogFrame(onDismissRequest = { showVoicePicker = false }, primaryColor = primaryColor, title = "SELECT SYSTEM VOICE") {
            LazyColumn(modifier = Modifier.heightIn(max = 300.dp)) {
                items(systemVoices) { voice ->
                    val isSelected = editingProfile?.systemVoiceName == voice.name
                    Row(modifier = Modifier.fillMaxWidth().background(if (isSelected) primaryColor.copy(alpha = 0.2f) else Color.Transparent).clickable {
                        editingProfile = editingProfile?.copy(systemVoiceName = voice.name)
                        showVoicePicker = false
                        reportHelpInteraction(AckTags.AUDIO_VOICE_PICKER)
                    }.padding(12.dp)) {
                        Text(voice.name, color = if (isSelected) primaryColor else Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                    }
                    Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
                }
            }
            Spacer(modifier = Modifier.height(14.dp))
            Text("CANCEL", color = Color.Red, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { showVoicePicker = false }.padding(8.dp))
        }
    }

    if (showRoboticEditor && editingProfile != null) {
        val p = editingProfile!!
        AudioDialogFrame(onDismissRequest = { showRoboticEditor = false }, primaryColor = primaryColor, title = "ROBOTIC OVERLAY") {
            Text(
                "Ring-modulates the base voice for a mechanical character. Frequency sets the modulation rate, Depth blends between the clean and modulated signal.",
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(8.dp))
            DspSlider("FREQUENCY (HZ)", p.modFreq, 0f..100f, primaryColor) { editingProfile = p.copy(modFreq = it) }
            DspSlider("DEPTH (%)", p.modDepth, 0f..1f, primaryColor) { editingProfile = p.copy(modDepth = it) }
            Spacer(modifier = Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                NeonButton("TEST", Modifier.weight(1f), mainColor = primaryColor) { previewCurrentEdit() }
                Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    Text("DONE", color = primaryColor, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { showRoboticEditor = false }.padding(8.dp))
                }
            }
        }
    }

    if (showManageProfiles) {
        AudioDialogFrame(onDismissRequest = { showManageProfiles = false }, primaryColor = primaryColor, title = "MANAGE CUSTOM PROFILES") {
            if (customVoices.isEmpty()) {
                Text("NO CUSTOM PROFILES YET.", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
            }
            LazyColumn(modifier = Modifier.heightIn(max = 280.dp)) {
                items(customVoices, key = { it.id }) { profile ->
                    var renaming by remember(profile.id) { mutableStateOf(false) }
                    var draftLabel by remember(profile.id) { mutableStateOf(profile.label) }

                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                        if (renaming) {
                            AckInlineTextField(
                                value = draftLabel,
                                primaryColor = primaryColor,
                                onValueChange = { draftLabel = it },
                                modifier = Modifier.weight(1f)
                            )
                            Text(
                                "SAVE",
                                color = primaryColor,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.clickable {
                                    renameProfile(profile.id, draftLabel)
                                    renaming = false
                                }.padding(8.dp)
                            )
                        } else {
                            Text(
                                profile.label,
                                color = if (profile.id == userProfile) primaryColor else Color.White,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.weight(1f)
                            )
                            Text(
                                "RENAME",
                                color = Color.Gray,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.clickable {
                                    draftLabel = profile.label
                                    renaming = true
                                }.padding(6.dp)
                            )
                        }
                        Text(
                            "DELETE",
                            color = ErrorRed,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.clickable { deleteTargetId = profile.id }.padding(6.dp)
                        )
                    }
                    Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            if (customVoices.size < MAX_CUSTOM_PROFILES) {
                Text(
                    "+ NEW SLOT",
                    color = primaryColor,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                    modifier = Modifier.clickable { createProfile() }.padding(8.dp)
                )
            } else {
                Text("SLOT LIMIT REACHED ($MAX_CUSTOM_PROFILES)", color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text("CLOSE", color = primaryColor, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { showManageProfiles = false }.padding(8.dp))
        }
    }

    if (deleteTargetId != null) {
        val target = customVoices.find { it.id == deleteTargetId }
        AudioDialogFrame(onDismissRequest = { deleteTargetId = null }, primaryColor = ErrorRed, title = "DELETE PROFILE?") {
            Text(
                "Delete \"${target?.label ?: ""}\" permanently? This cannot be undone.",
                color = Color.White,
                fontFamily = FontFamily.Monospace,
                fontSize = 11.sp
            )
            Spacer(modifier = Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    Text("CANCEL", color = Color.Gray, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { deleteTargetId = null }.padding(8.dp))
                }
                Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    Text(
                        "DELETE",
                        color = ErrorRed,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable {
                            deleteTargetId?.let { deleteProfile(it) }
                            deleteTargetId = null
                        }.padding(8.dp)
                    )
                }
            }
        }
    }
}

// The app's own modal chrome (cut-corner border/background, matching
// CreateDeckDialog.kt) instead of Material3 AlertDialog's fixed rounded
// shape, which clashes with the cut-corner look used everywhere else.
@Composable
private fun AudioDialogFrame(
    onDismissRequest: () -> Unit,
    primaryColor: Color,
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    val shape = CutCornerShape(topStart = 16.dp, bottomEnd = 16.dp)

    Dialog(onDismissRequest = onDismissRequest) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Graphite, shape)
                .border(1.dp, primaryColor, shape)
                .padding(18.dp)
        ) {
            Text(
                title,
                color = primaryColor,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.height(14.dp))
            content()
        }
    }
}

@Composable
private fun AckInlineTextField(
    value: String,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onValueChange: (String) -> Unit
) {
    val shape = CutCornerShape(4.dp)

    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = TextStyle(
            color = primaryColor,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        ),
        modifier = modifier
            .background(VoidBlack, shape)
            .border(1.dp, primaryColor.copy(alpha = 0.75f), shape)
            .padding(horizontal = 10.dp, vertical = 8.dp)
    )
}

// Bigger and more legible than the shared ThemeOption chip (which is fixed
// at 60x40dp for compact settings toggles) -- profile names here need to
// stay readable at a glance, so this gets its own sizing.
@Composable
private fun AudioProfileChip(
    label: String,
    isActive: Boolean,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val shape = CutCornerShape(8.dp)

    Box(
        modifier = modifier
            .defaultMinSize(minWidth = 92.dp, minHeight = 52.dp)
            .background(if (isActive) primaryColor.copy(alpha = 0.16f) else VoidBlack, shape)
            .border(if (isActive) 2.dp else 1.dp, if (isActive) primaryColor else Color.DarkGray, shape)
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            label,
            color = if (isActive) primaryColor else Color.White,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2
        )
    }
}
