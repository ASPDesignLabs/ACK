// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import com.example.besu.core.LabelKey
import com.example.besu.*
import com.example.besu.backup.*
import com.example.besu.core.SpeechLanguage
import com.example.besu.core.SpeechLanguageText
import com.example.besu.core.VoiceListing
import com.example.besu.core.defaultsOffer
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import com.example.besu.ui.theme.*
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.speech.tts.Voice
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
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
import com.example.besu.core.CustomVoiceRemoval
import com.example.besu.ui.theme.ErrorRed
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import com.example.besu.voicecapture.TrainingCaptureHome
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

// Small enough that the profile chip row never has to wrap onto a second
// line on a phone-width screen -- well under the 20-profile cap the backup
// importer enforces (TransferManager.kt).
private const val MAX_CUSTOM_PROFILES = 8

@OptIn(ExperimentalLayoutApi::class)
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
    // SPEECH LANGUAGE (data/AssistPrefs.kt, rules in core/SpeechLanguage.kt): the language a profile with no voice of its own speaks in.
    var speechLanguage by remember { mutableStateOf(AssistPrefs.speechLanguage(context)) }
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
    var showDspChainEditor by remember { mutableStateOf(false) }
    var deleteTargetId by remember { mutableStateOf<String?>(null) }

    // One-time offer of the newer defaults, for an install that already existed (core/DefaultsOffer.kt decides what to
    // offer, data/InstallState.kt remembers it was dismissed). Nothing is changed until the person confirms in the review.
    var defaultsPromptRefresh by remember { mutableIntStateOf(0) }
    var showDefaultsReview by remember { mutableStateOf(false) }
    var defaultsBackupStatus by remember { mutableStateOf<String?>(null) }
    val defaultsOfferNow = remember(userProfile, defaultsPromptRefresh) {
        defaultsOffer(
            isExistingInstall = !InstallState.isFreshInstall(context),
            dismissed = InstallState.isDefaultsPromptDismissed(context),
            voiceIsCyber = userProfile == "CYBER",
            presetTruncates = !VisualPresetRepository.getActivePreset(context).bypassTruncation
        )
    }

    // BACK UP FIRST: the same file as EXPORT .JSON in SETTINGS. Unlike that button, this one says whether it worked,
    // because the whole point of backing up before a change is knowing there is a copy.
    val defaultsBackupLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri != null) {
            try {
                val json = TransferManager.generateBackupJson(context)
                val out = context.contentResolver.openOutputStream(uri) ?: throw java.io.IOException("could not open the file")
                out.use { it.write(json.toByteArray()) }
                defaultsBackupStatus = "BACKUP SAVED. NOTHING HAS BEEN CHANGED YET."
            } catch (e: Exception) {
                Log.e("ACK_BACKUP", "backup before applying the newer defaults failed", e)
                defaultsBackupStatus = "BACKUP FAILED. NOTHING WAS CHANGED."
            }
        }
    }

    val activeIdx = customVoices.indexOfFirst { it.id == userProfile }
    var editingProfile by remember(userProfile) {
        mutableStateOf(if (activeIdx != -1) customVoices[activeIdx] else null)
    }

    fun syncDsp() {
        prefs.edit()
            .putString("USER_VOX_PROFILE", userProfile)
            .putFloat("MASTER_GAIN", masterGain)
            .putString("CUSTOM_VOICES", Json.encodeToString(customVoices.toList()))
            .apply()

        val intent = Intent(context, OutputService::class.java).apply {
            action = "UPDATE_DSP"
            putExtra("user_profile", userProfile)
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
            // Deleting the active custom voice falls back to the unprocessed voice, not the robot one.
            userProfile = "ORGANIC"
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

    // --- CUSTOM TRAINED VOICE ---
    // hasCustomVoice is judged straight from disk (CustomVoiceRepository has
    // no separate flag to fall out of sync with) rather than cached forever,
    // so re-entering this screen after an import always reflects reality.
    var hasCustomVoice by remember { mutableStateOf(CustomVoiceRepository.hasCustomVoice(context)) }
    var pendingCustomVoiceRestart by remember { mutableStateOf(false) }
    // DELETE CUSTOM VOICE: two confirmations, and the result of a voice backup tried from the first one.
    var showDeleteVoiceFirst by remember { mutableStateOf(false) }
    var showDeleteVoiceSecond by remember { mutableStateOf(false) }
    var voiceBackupStatus by remember { mutableStateOf<String?>(null) }
    val uiScope = rememberCoroutineScope()
    // RECORD TRAINING DATA is its own set of screens (voicecapture/); while it is open it takes the whole area in place of this one.
    var showTrainingCapture by remember { mutableStateOf(false) }

    // A new/replaced voice changes what OutputService's PiperVoiceEngine
    // singleton has loaded -- the app-restart pattern (see MainActivity.kt's
    // restartApp, already used by GIF deck import/FULL RESTORE) is the
    // simplest way to guarantee a clean reload rather than trying to patch
    // live service state from here.
    LaunchedEffect(pendingCustomVoiceRestart) {
        if (pendingCustomVoiceRestart) {
            delay(1500)
            restartApp(context)
        }
    }

    val importVoiceLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments()
    ) { uris: List<Uri> ->
        if (uris.isNotEmpty()) {
            if (CustomVoiceRepository.importVoice(context, uris)) {
                hasCustomVoice = true
                Toast.makeText(context, "VOICE IMPORTED -- RESTARTING", Toast.LENGTH_LONG).show()
                pendingCustomVoiceRestart = true
            } else {
                Toast.makeText(context, "IMPORT FAILED -- SELECT BOTH .ONNX AND .ONNX.JSON", Toast.LENGTH_LONG).show()
            }
        }
    }

    val exportVoiceBackupLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/zip")
    ) { uri: Uri? ->
        if (uri != null) {
            val success = CustomVoiceBackupManager.exportVoice(context, uri)
            voiceBackupStatus = if (success) "VOICE BACKUP SAVED." else "VOICE BACKUP FAILED. NOTHING WAS DELETED."
            Toast.makeText(
                context,
                if (success) "VOICE BACKUP EXPORTED" else "EXPORT FAILED",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    val importVoiceBackupLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            if (CustomVoiceBackupManager.importBackup(context, uri)) {
                hasCustomVoice = true
                Toast.makeText(context, "VOICE BACKUP RESTORED -- RESTARTING", Toast.LENGTH_LONG).show()
                pendingCustomVoiceRestart = true
            } else {
                Toast.makeText(context, "RESTORE FAILED -- INTEGRITY CHECK", Toast.LENGTH_SHORT).show()
            }
        }
    }

    // What deleting the voice does to the profiles (core/CustomVoiceRemoval.kt). The first confirmation lists it and
    // deleteCustomVoice() applies the very same result, so what the person is told is what happens.
    fun removalImpact() = CustomVoiceRemoval.impact(
        userProfile,
        customVoices.map { CustomVoiceRemoval.Profile(it.id, it.label, it.useCustomVoice) }
    )

    // Runs the delete off the main thread (releasing the native session can wait for a model that is still loading),
    // then moves any profile that used the voice onto a normal one. Profiles are only changed once the voice can no longer
    // be used; if the delete failed and the voice still works, nothing else is touched. No restart is needed: the engine
    // is released and the MY VOICE chip is simply no longer shown.
    fun deleteCustomVoice() {
        uiScope.launch {
            val allGone = withContext(Dispatchers.IO) { CustomVoiceRepository.deleteVoice(context) }
            val stillUsable = CustomVoiceRepository.hasCustomVoice(context)
            hasCustomVoice = stillUsable
            if (!stillUsable) {
                val impact = removalImpact()
                for (id in impact.profileIdsToClear) {
                    val idx = customVoices.indexOfFirst { it.id == id }
                    if (idx != -1) customVoices[idx] = customVoices[idx].copy(useCustomVoice = false)
                }
                editingProfile = editingProfile?.let {
                    if (it.id in impact.profileIdsToClear) it.copy(useCustomVoice = false) else it
                }
                userProfile = impact.newActiveProfileId
                syncDsp()
            }
            Toast.makeText(
                context,
                when {
                    allGone -> "CUSTOM VOICE DELETED"
                    !stillUsable -> "VOICE REMOVED, BUT SOME FILES COULD NOT BE DELETED"
                    else -> "COULD NOT DELETE THE VOICE"
                },
                Toast.LENGTH_LONG
            ).show()
        }
    }

    if (showDeleteVoiceFirst) {
        DeleteVoiceFirstDialog(
            primaryColor = primaryColor,
            impact = removalImpact(),
            backupStatus = voiceBackupStatus,
            onExportBackupFirst = { exportVoiceBackupLauncher.launch("my_voice_backup.zip") },
            onContinue = {
                showDeleteVoiceFirst = false
                showDeleteVoiceSecond = true
            },
            onCancel = { showDeleteVoiceFirst = false }
        )
    }
    if (showDeleteVoiceSecond) {
        DeleteVoiceSecondDialog(
            primaryColor = primaryColor,
            onDelete = {
                showDeleteVoiceSecond = false
                deleteCustomVoice()
            },
            onCancel = { showDeleteVoiceSecond = false }
        )
    }

    if (showTrainingCapture) {
        TrainingCaptureHome(context, primaryColor) { showTrainingCapture = false }
    } else Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text(labelFor(LabelKey.AUDIO_ARCHITECT), color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = looseSpacing(2.sp))
        Spacer(modifier = Modifier.height(10.dp))

        if (defaultsOfferNow.any) {
            DefaultsPromptBanner(
                offer = defaultsOfferNow,
                primaryColor = primaryColor,
                onReview = {
                    defaultsBackupStatus = null
                    showDefaultsReview = true
                },
                // Only hides it for good. Changes no setting.
                onNotNow = {
                    InstallState.dismissDefaultsPrompt(context)
                    defaultsPromptRefresh++
                }
            )
            Spacer(modifier = Modifier.height(10.dp))
        }

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

        Spacer(modifier = Modifier.height(10.dp))

        // --- VOICE PROFILE SELECTOR ---
        Text(labelFor(LabelKey.VOICE_PROFILE), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
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
            // Only appears once a voice is actually imported -- same "hide
            // rather than show disabled" convention as the "+ NEW" chip
            // below, which only appears while under the profile cap.
            if (hasCustomVoice) {
                AudioProfileChip("MY VOICE", userProfile == "MY_VOICE", primaryColor) {
                    userProfile = "MY_VOICE"
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
                    showDspChainEditor = true
                    reportHelpInteraction(AckTags.AUDIO_PROFILE_SELECT)
                }
            }
            if (customVoices.size < MAX_CUSTOM_PROFILES) {
                AudioProfileChip("+ NEW", false, primaryColor) {
                    createProfile()
                    showDspChainEditor = true
                }
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

        // --- SPEECH LANGUAGE ---
        // Said in words, changeable at any time, and used from the very next message (OutputService re-reads it). Choosing a voice in a profile,
        // or MY VOICE, is separate and is not affected.
        NeonButton(
            SpeechLanguageText.label(speechLanguage),
            Modifier.fillMaxWidth(),
            mainColor = primaryColor
        ) {
            speechLanguage = if (speechLanguage == SpeechLanguage.DEVICE) SpeechLanguage.ENGLISH_US else SpeechLanguage.DEVICE
            AssistPrefs.setSpeechLanguage(context, speechLanguage)
        }
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            SpeechLanguageText.EXPLANATION,
            color = Color.Gray,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(10.dp))

        // --- CUSTOM TRAINED VOICE ---
        Text(labelFor(LabelKey.CUSTOM_VOICE), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            if (hasCustomVoice) "STATUS: INSTALLED" else "STATUS: NOT IMPORTED",
            color = if (hasCustomVoice) primaryColor else Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )
        Spacer(modifier = Modifier.height(6.dp))
        NeonButton(
            if (hasCustomVoice) labelFor(LabelKey.REIMPORT_CUSTOM_VOICE) else labelFor(LabelKey.IMPORT_CUSTOM_VOICE),
            Modifier.fillMaxWidth(),
            mainColor = primaryColor
        ) {
            // No reliable MIME type for .onnx/.onnx.json -- CustomVoiceRepository
            // identifies which is which by filename suffix, same tolerance
            // GifRepository.importGif already applies to a null/unknown MIME.
            importVoiceLauncher.launch(arrayOf("*/*"))
        }
        Spacer(modifier = Modifier.height(6.dp))
        NeonButton(
            labelFor(LabelKey.RECORD_TRAINING),
            Modifier.fillMaxWidth().testTag(AckTags.TRAIN_ENTRY_BTN).helpTarget(AckTags.TRAIN_ENTRY_BTN, primaryColor),
            mainColor = primaryColor
        ) {
            showTrainingCapture = true
            reportHelpInteraction(AckTags.TRAIN_ENTRY_BTN)
        }
        if (hasCustomVoice) {
            Spacer(modifier = Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                NeonButton("EXPORT VOICE BACKUP", Modifier.weight(1f), mainColor = primaryColor) {
                    exportVoiceBackupLauncher.launch("my_voice_backup.zip")
                }
                NeonButton("IMPORT VOICE BACKUP", Modifier.weight(1f), mainColor = primaryColor) {
                    importVoiceBackupLauncher.launch(arrayOf("application/zip"))
                }
            }
            Spacer(modifier = Modifier.height(6.dp))
            // The trained voice is made from the person's own recordings: the backup file is as private as a recording
            // would be, and is not encrypted.
            Text(
                "THE VOICE BACKUP IS AS PRIVATE AS A RECORDING OF YOU, AND IS NOT ENCRYPTED. SAVE IT WHERE YOU CONTROL WHO CAN SEE IT.",
                color = Color.Gray,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(10.dp))
            // Opens two confirmations; nothing is removed by this tap.
            NeonButton(labelFor(LabelKey.DELETE_CUSTOM_VOICE), Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                voiceBackupStatus = null
                showDeleteVoiceFirst = true
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // --- DSP CHAIN (opens as its own popup -- see AudioDialogFrame below) ---
        if (editingProfile != null) {
            val p = editingProfile!!
            val isUnsaved = customVoices.getOrNull(activeIdx) != p

            NeonButton(
                "${labelFor(LabelKey.DSP_EDIT)} // ${p.label}${if (isUnsaved) " *" else ""}",
                Modifier.fillMaxWidth(),
                mainColor = primaryColor
            ) {
                showDspChainEditor = true
            }
        } else {
            Box(modifier = Modifier.fillMaxWidth().border(1.dp, Color.Gray, CutCornerShape(12.dp)).padding(24.dp), contentAlignment = Alignment.Center) {
                Text(
                    if (userProfile == "MY_VOICE") {
                        "MY VOICE ACTIVE\nTHIS ENGINE HAS NO DSP CONTROLS OF ITS OWN"
                    } else {
                        "FACTORY PRESET LOCKED\nSELECT OR CREATE A CUSTOM SLOT TO EDIT"
                    },
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.Center
                )
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
                        Column {
                            Text(voice.name, color = if (isSelected) primaryColor else Color.White, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            // The language by name ("German (Germany)"), so a person can find theirs; the list is sorted by it.
                            Text(VoiceListing.languageLine(voice.toVoiceInfo()), color = Color.Gray, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                        }
                    }
                    Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(Color.DarkGray))
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(VoiceListing.LIST_NOTE, color = Color.Gray, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
            Spacer(modifier = Modifier.height(14.dp))
            Text("CANCEL", color = Color.Red, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { showVoicePicker = false }.padding(8.dp))
        }
    }

    if (showDspChainEditor && editingProfile != null) {
        val p = editingProfile!!
        val voiceName = if (p.systemVoiceName.isNotEmpty()) p.systemVoiceName.takeLast(15) else "DEFAULT"
        val isRobotic = p.modDepth > 0.05f
        val isUnsaved = customVoices.getOrNull(activeIdx) != p

        AudioDialogFrame(onDismissRequest = { showDspChainEditor = false }, primaryColor = primaryColor, title = "${labelFor(LabelKey.DSP_CHAIN)} // ${p.label}") {
            Text(
                if (isUnsaved) "UNSAVED CHANGES*" else "UP TO DATE",
                color = if (isUnsaved) NeonPalette.SWATCHES[3] else Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(10.dp))

            Column(modifier = Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState())) {
                if (!p.useCustomVoice) {
                    NeonButton(
                        "BASE VOICE: $voiceName",
                        Modifier.fillMaxWidth().helpTarget(AckTags.AUDIO_VOICE_PICKER, primaryColor),
                        mainColor = primaryColor
                    ) {
                        showVoicePicker = true
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column {
                        Text("USE MY VOICE", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                        if (!hasCustomVoice) {
                            Text(
                                "NO VOICE IMPORTED",
                                color = Color.DarkGray,
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                    NeonButton(
                        if (p.useCustomVoice) "ON" else "OFF",
                        Modifier.width(60.dp),
                        isActive = p.useCustomVoice,
                        mainColor = if (hasCustomVoice) primaryColor else Color.DarkGray
                    ) {
                        if (hasCustomVoice) {
                            editingProfile = p.copy(useCustomVoice = !p.useCustomVoice)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

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

                // A cloned voice ignores the robotic/bitcrush character
                // effects entirely (see OutputService's custom-voice branch,
                // which always zeroes them) -- hidden here rather than shown
                // uselessly.
                if (!p.useCustomVoice) {
                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                        modifier = Modifier.fillMaxWidth().helpTarget(AckTags.AUDIO_ROBOTIC_OVERLAY, primaryColor)
                    ) {
                        Text(labelFor(LabelKey.ROBOTIC_OVERLAY), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                        NeonButton(if (isRobotic) "ON" else "OFF", Modifier.width(60.dp), isActive = isRobotic, mainColor = primaryColor) {
                            editingProfile = if (isRobotic) {
                                p.copy(modDepth = 0f)
                            } else {
                                p.copy(modDepth = 0.5f, modFreq = 50f)
                            }
                        }
                    }
                    if (isRobotic) {
                        Spacer(modifier = Modifier.height(4.dp))
                        DspSlider("ROBOTIC FREQ (HZ)", p.modFreq, 0f..100f, primaryColor) {
                            editingProfile = p.copy(modFreq = it)
                            reportHelpInteraction(AckTags.AUDIO_ROBOTIC_OVERLAY)
                        }
                        DspSlider("ROBOTIC DEPTH (%)", p.modDepth, 0f..1f, primaryColor) {
                            editingProfile = p.copy(modDepth = it)
                            reportHelpInteraction(AckTags.AUDIO_ROBOTIC_OVERLAY)
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    Box(modifier = Modifier.helpTarget(AckTags.AUDIO_BITCRUSH, primaryColor)) {
                        DspSlider("${labelFor(LabelKey.BITCRUSH)} (%)", p.crush, 0f..1f, primaryColor) {
                            editingProfile = p.copy(crush = it)
                            reportHelpInteraction(AckTags.AUDIO_BITCRUSH)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

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

            Spacer(modifier = Modifier.height(10.dp))

            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text("CLOSE", color = primaryColor, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { showDspChainEditor = false }.padding(8.dp))
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

    if (showDefaultsReview) {
        DefaultsReviewDialog(
            offer = defaultsOfferNow,
            primaryColor = primaryColor,
            backupStatus = defaultsBackupStatus,
            onBackUpFirst = { defaultsBackupLauncher.launch("ack_backup_${System.currentTimeMillis()}.json") },
            onApply = { useUnprocessedVoice, useFullMessage ->
                // Only what was switched on. The voice goes through the same path as tapping the ORGANIC chip.
                if (useUnprocessedVoice) {
                    userProfile = "ORGANIC"
                    syncDsp()
                }
                if (useFullMessage) {
                    addFullTextPreset(context)
                }
                // Seen and decided: do not offer again, even for a part that was left off.
                InstallState.dismissDefaultsPrompt(context)
                showDefaultsReview = false
                defaultsPromptRefresh++
                Toast.makeText(context, "SETTINGS UPDATED", Toast.LENGTH_SHORT).show()
            },
            onDismiss = { showDefaultsReview = false }
        )
    }
}

// The app's own modal chrome (cut-corner border/background, matching
// CreateDeckDialog.kt) instead of Material3 AlertDialog's fixed rounded
// shape, which clashes with the cut-corner look used everywhere else.
@Composable
internal fun AudioDialogFrame(
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
                letterSpacing = looseSpacing(1.sp)
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
