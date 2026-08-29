package com.example.besu

import android.content.Context
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

object TargetRepository {
    private const val PREFS_NAME = "ack_targets"
    private const val KEY_TARGETS = "saved_targets"
    private const val KEY_SYNTAX = "saved_syntax_rules"
    
    // Runtime State (Reset on app restart)
    private var activeSlotIndex: Int = -1 // -1 = No Target Selected (Cleared)
    
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    // --- STATE MANAGEMENT ---

    fun setActiveTarget(index: Int) {
        // Bounds check: 0 to 7, or -1 to clear
        activeSlotIndex = if (index in 0..7) index else -1
    }

    fun getActiveTargetIndex(): Int = activeSlotIndex

    fun getActiveTarget(context: Context): TargetSlot? {
        if (activeSlotIndex == -1) return null
        return getTargets(context).find { it.index == activeSlotIndex }
    }

    // --- NEW: CYCLING LOGIC (For Watch Face Control) ---
    /**
     * Cycles through valid targets.
     * Includes -1 (CLEARED) in the rotation.
     * direction: 1 (Next) or -1 (Prev)
     */
    fun cycleTarget(context: Context, direction: Int) {
        val allTargets = getTargets(context).sortedBy { it.index }
        
        // Build list of valid indices: [-1, targetIdx1, targetIdx2...]
        val validIndices = mutableListOf(-1)
        validIndices.addAll(allTargets.map { it.index })
        
        // Find current position. If activeSlotIndex isn't in list (deleted), default to 0 (cleared)
        val currentPos = validIndices.indexOf(activeSlotIndex).let { if (it == -1) 0 else it }
        
        // Calculate next position with wrapping
        var nextPos = (currentPos + direction) % validIndices.size
        if (nextPos < 0) nextPos += validIndices.size
        
        activeSlotIndex = validIndices[nextPos]
    }

    // --- THE CORE LOGIC: SYNTAX RESOLVER ---

    fun processPhrase(context: Context, rawPhrase: String, matrixPath: String): String {
        // 1. Check if a target is even active
        val target = getActiveTarget(context) ?: return rawPhrase
        
        // 2. Load Syntax Rules
        val rules = getSyntaxRules(context)
        
        // 3. Determine Strategy (Specific Rule -> Target Default -> Heuristic Fallback)
        val strategy = rules[matrixPath] 
            ?: target.defaultStrategy.takeIf { it.isNotEmpty() } 
            ?: "POST" // Default to Append ("Hello, Sarah")

        return applyInjection(rawPhrase, target.label, strategy)
    }

    private fun applyInjection(phrase: String, name: String, strategy: String): String {
        val cleanPhrase = phrase.trim()
        
        // Safety: Don't double inject if the user manually typed the name
        if (cleanPhrase.contains(name, ignoreCase = true)) return cleanPhrase

        return if (strategy == "PRE") {
            // PREPEND: "Sarah, Systems online."
            "$name, $cleanPhrase" 
        } else {
            // APPEND: "Systems online, Sarah."
            // Handle punctuation cleanly to keep it grammatical
            if (cleanPhrase.endsWith(".") || cleanPhrase.endsWith("!") || cleanPhrase.endsWith("?")) {
                val punctuation = cleanPhrase.last()
                val textWithoutPunctuation = cleanPhrase.dropLast(1)
                "$textWithoutPunctuation, $name$punctuation"
            } else {
                "$cleanPhrase, $name"
            }
        }
    }

    // --- STORAGE (CRUD) ---

    fun getTargets(context: Context): List<TargetSlot> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_TARGETS, "[]") ?: "[]"
        return try { json.decodeFromString(raw) } catch(e: Exception) { emptyList() }
    }

    fun saveTarget(context: Context, slot: TargetSlot) {
        val list = getTargets(context).toMutableList()
        // Remove existing slot at this index if any to overwrite
        list.removeAll { it.index == slot.index }
        list.add(slot)
        list.sortBy { it.index }
        
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_TARGETS, json.encodeToString(list)).apply()
    }
    
    fun clearTarget(context: Context, index: Int) {
        val list = getTargets(context).toMutableList()
        list.removeAll { it.index == index }
        
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_TARGETS, json.encodeToString(list)).apply()
        
        // If we deleted the active target, switch to cleared
        if (activeSlotIndex == index) activeSlotIndex = -1
    }

    fun getSyntaxRules(context: Context): Map<String, String> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_SYNTAX, "{}") ?: "{}"
        return try { json.decodeFromString(raw) } catch(e: Exception) { emptyMap() }
    }

    fun setSyntaxRule(context: Context, path: String, strategy: String) {
        val map = getSyntaxRules(context).toMutableMap()
        if (strategy == "AUTO") {
            map.remove(path) // Remove override to use default
        } else {
            map[path] = strategy
        }
        
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_SYNTAX, json.encodeToString(map)).apply()
    }
}
