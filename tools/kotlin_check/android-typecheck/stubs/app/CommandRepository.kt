// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.decks.EmergencyDeckConfig
import com.example.besu.decks.EmergencyInfoCard

// Stub of the Emergency and custom-context halves of data/CommandRepository.kt (it reads and writes storage and is not staged), written from its real signatures.
data class CustomContextEntry(val name: String, val basePose: String = "IDENTITY")

object CommandRepository {
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
