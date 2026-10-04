// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.decks.EmergencyDeckConfig
import com.example.besu.decks.EmergencyInfoCard

// Stub of the Emergency half of data/CommandRepository.kt (it reads and writes storage and is not staged), written from its real signatures.
object CommandRepository {
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
