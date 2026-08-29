package com.example.besu.wear

import androidx.compose.runtime.mutableStateMapOf

object TargetCache {
    // Key: Index (0-7), Value: Label ("SARAH")
    val slots = mutableStateMapOf<Int, String>()

    fun update(rawString: String) {
        // Expected Format: "0:SARAH|1:BOSS|2:TEAM"
        slots.clear()
        try {
            if (rawString.isEmpty()) return
            
            rawString.split("|").forEach { entry ->
                val parts = entry.split(":")
                if (parts.size == 2) {
                    val index = parts[0].toIntOrNull()
                    val label = parts[1]
                    if (index != null) slots[index] = label
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
    
    fun getLabel(index: Int): String {
        return slots[index] ?: "SLOT ${index + 1}"
    }
}
