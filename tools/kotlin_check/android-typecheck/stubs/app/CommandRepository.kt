// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.decks.EmergencyDeckConfig
import com.example.besu.decks.EmergencyInfoCard
import com.example.besu.decks.QuickActionsDeckConfig

// Stub of the Emergency, custom-context, autocomplete-tree and recordings halves of data/CommandRepository.kt (it reads and writes storage and is not staged), written from its real signatures.
data class CustomContextEntry(val name: String, val basePose: String = "IDENTITY")

data class MatrixNode(val path: String, val triggerPath: String, val label: String, val defaultPhrase: String, val category: String)

object CommandRepository {
    data class HeaderShortcut(val label: String, val phrase: String)
    fun getHeaderShortcuts(context: Context): List<HeaderShortcut> = emptyList()
    fun resolveQuickAction(context: Context, deckId: String, groupIndex: Int, slotIndex: Int): String = ""
    fun getVisualOverride(context: Context, storagePath: String, deckId: String = "DEFAULT", profile: String = "DEFAULT"): String = ""
    fun getResolvedPhrase(context: Context, storagePath: String, deckId: String = "DEFAULT", profile: String = "DEFAULT"): String = ""
    fun setQuickActionSlotRecording(context: Context, deckId: String, groupIndex: Int, slotIndex: Int, recordingId: String?) {}
    fun getDeckName(context: Context, deckId: String = "DEFAULT"): String = deckId
    fun findMatrixNode(context: Context, path: String): MatrixNode? = null
    fun getPhrase(context: Context, storagePath: String, deckId: String = "DEFAULT", profile: String = "DEFAULT"): String = ""
    fun getQuickActionsConfig(context: Context, deckId: String = "DEFAULT"): QuickActionsDeckConfig = QuickActionsDeckConfig(deckId)
    fun getCustomContextEntries(context: Context): List<CustomContextEntry> = emptyList()
    fun addCustomContextEntry(context: Context, name: String, basePose: String): Boolean = false
    fun renameCustomContextEntry(context: Context, oldName: String, newName: String): Boolean = false
    fun reassignCustomContextPose(context: Context, name: String, basePose: String): Boolean = false
    fun removeCustomContextEntry(context: Context, name: String) {}
    fun moveCustomContextEntry(context: Context, name: String, offset: Int) {}
    fun getEmergencyConfig(context: Context, deckId: String = ""): EmergencyDeckConfig = EmergencyDeckConfig(deckId = deckId)
    fun saveEmergencyConfig(context: Context, config: EmergencyDeckConfig) {}
    fun getEmergencyInfoCard(context: Context): EmergencyInfoCard = EmergencyInfoCard()
    fun saveEmergencyInfoCard(context: Context, card: EmergencyInfoCard) {}
    fun updateEmergencySlot(context: Context, deckId: String, slotIndex: Int, label: String, template: String, localValues: List<String>) {}
    fun resolveEmergencyPrompt(context: Context, deckId: String, slotIndex: Int): String = ""
}

object TemplateEngine {
    fun getVariableTags(template: String): List<String?> = emptyList()
}
