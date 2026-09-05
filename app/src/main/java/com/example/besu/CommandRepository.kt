package com.example.besu

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import com.example.besu.ui.theme.NeonPalette

// --- DATA CLASSES ---

@Serializable
data class QuickPhrase(
    val id: Long = System.currentTimeMillis(),
    val text: String,
    val tag: String
)


@Serializable
enum class DeckType {
    MATRIX,
    QUICK_ACTIONS,
    EMERGENCY,
    EMOJI,
    GIF
}

@Serializable
data class DeckMeta(
    val id: String,
    val name: String,
    val colorIndex: Int,
    val created: Long = System.currentTimeMillis(),

    // Backward-compatible default:
    // all existing stored decks remain Matrix decks.
    val type: DeckType = DeckType.MATRIX
)
val defaultDeckMeta = DeckMeta(
    id = "DEFAULT",
    name = "DEFAULT",
    colorIndex = 0,
    type = DeckType.MATRIX
)
data class MatrixNode(
    val path: String,       // Unique storage key
    val triggerPath: String, // The WATCH signal that triggers this
    val label: String,
    val defaultPhrase: String,
    val category: String
)

object CommandRepository {
    private const val PREFS_NAME = "ack_matrix_config"
    
    // --- STORAGE KEYS ---
    private const val QUICK_PHRASES_KEY = "saved_quick_phrases"
    private const val DECKS_KEY = "custom_decks_meta"
    private const val ACTIVE_DECK_ID = "active_deck_id"
    private const val ACTIVE_DECK_COLOR = "active_deck_color_idx"
    private const val QUICK_ACTIONS_PREFIX = "quick_actions_"
    private const val QUICK_ACTIONS_SUFFIX = "_config"

    private const val EMOJI_DECK_PREFIX = "emoji_deck_"
    private const val EMOJI_DECK_SUFFIX = "_config"
    
    // Legacy Keys
    private const val CUSTOM_CATS_KEY = "custom_categories"
    private const val ACTIVE_CAT_KEY = "active_category_focus"
    private const val ACTIVE_PROFILE_KEY = "ACTIVE_PROFILE"

    private const val EMERGENCY_PREFIX = "emergency_"
    private const val EMERGENCY_SUFFIX = "_config"

    // Standard Profiles
    val PROFILES = listOf("DEFAULT", "WORK", "HIGH_STRESS", "SOCIAL", "BUILDER")

    // --- BASE 3x4 MATRIX TEMPLATE (NOW PUBLIC FOR EXPORT OPTIMIZATION) ---
    val BASE_TEMPLATE = listOf(
        // === ROOT 1: IDENTITY (Arm Up) ===
        MatrixNode("/std/id/0", "/gesture/thumbsup", "Twist 0 (Default)", "Acknowledged.", "IDENTITY"),
        MatrixNode("/std/id/1", "/gesture/wave", "Twist 1", "Systems Online.", "IDENTITY"),
        MatrixNode("/std/id/2", "/gesture/ask_name", "Twist 2", "Identify yourself.", "IDENTITY"),
        MatrixNode("/std/id/3", "/gesture/name", "Twist 3", "Handle is Snakesan.", "IDENTITY"),
        
        // === ROOT 2: DEFEND (Arm Flat) ===
        MatrixNode("/std/def/0", "/gesture/stop", "Twist 0 (Default)", "Stop.", "DEFEND"),
        MatrixNode("/std/def/1", "/gesture/wait", "Twist 1", "Please wait.", "DEFEND"),
        MatrixNode("/std/def/2", "/gesture/break", "Twist 2", "I need a break.", "DEFEND"),
        MatrixNode("/std/def/3", "/gesture/leave_alone", "Twist 3", "Leave me alone.", "DEFEND"),
        
        // === ROOT 3: CONNECT (Handshake) ===
        MatrixNode("/std/con/0", "/gesture/nice", "Twist 0 (Default)", "Greetings.", "CONNECT"),
        MatrixNode("/std/con/1", "/gesture/same", "Twist 1", "Me too.", "CONNECT"),
        MatrixNode("/std/con/2", "/gesture/sorry_wait", "Twist 2", "Sorry.", "CONNECT"),
        MatrixNode("/std/con/3", "/gesture/meet_pleasure", "Twist 3", "Pleasure meeting you.", "CONNECT")
    )
    
    private var cachedNodes: MutableList<MatrixNode> = BASE_TEMPLATE.toMutableList()

    // --- MULTI-DECK MANAGEMENT ---


    private fun emojiDeckKey(deckId: String): String {
        return "$EMOJI_DECK_PREFIX$deckId$EMOJI_DECK_SUFFIX"
    }

    private fun quickActionsKey(deckId: String): String {
        return "$QUICK_ACTIONS_PREFIX$deckId$QUICK_ACTIONS_SUFFIX"
    }

    private fun emergencyKey(deckId: String): String {
        return "$EMERGENCY_PREFIX$deckId$EMERGENCY_SUFFIX"
    }

    fun getQuickActionsConfig(
        context: Context,
        deckId: String = getActiveDeckId(context)
    ): QuickActionsDeckConfig {
        val fallback = QuickActionsDeckConfig(deckId = deckId)

        if (deckId == "DEFAULT") {
            return fallback
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(quickActionsKey(deckId), null) ?: return fallback

        return try {
            normalizeQuickActionsConfig(
                Json.decodeFromString<QuickActionsDeckConfig>(raw)
            )
        } catch (_: Exception) {
            fallback
        }
    }

    fun saveQuickActionsConfig(
        context: Context,
        config: QuickActionsDeckConfig
    ) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        prefs.edit()
            .putString(
                quickActionsKey(config.deckId),
                Json.encodeToString(normalizeQuickActionsConfig(config))
            )
            .apply()
    }

    fun updateQuickActionSlot(
        context: Context,
        deckId: String,
        groupIndex: Int,
        slotIndex: Int,
        label: String,
        template: String,
        localValues: List<String>
    ) {
        val current = getQuickActionsConfig(context, deckId)

        val updatedGroups = current.groups.map { group ->
            if (group.groupIndex != groupIndex) {
                group
            } else {
                group.copy(
                    slots = group.slots.map { slot ->
                        if (slot.slotIndex != slotIndex) {
                            slot
                        } else {
                            slot.copy(
                                label = label.trim().ifBlank {
                                    "ACTION ${slotIndex + 1}"
                                },
                                template = template,
                                localValues = localValues
                            )
                        }
                    }
                )
            }
        }

        saveQuickActionsConfig(
            context = context,
            config = current.copy(groups = updatedGroups)
        )
    }

    fun updateQuickActionGroup(
        context: Context,
        deckId: String,
        groupIndex: Int,
        label: String,
        rootCategory: String,
        boundPose: String
    ) {
        val current = getQuickActionsConfig(context, deckId)

        val safeCategory = rootCategory.takeIf { it in POSE_CATEGORIES } ?: "IDENTITY"
        val safePose = boundPose.takeIf { it in POSE_CATEGORIES } ?: "IDENTITY"

        // Keep the three groups' poses a permutation: if another group already
        // owns the pose being assigned here, hand it this group's old pose
        // rather than leaving two groups pointing at the same gesture.
        val targetGroup = current.groups.find { it.groupIndex == groupIndex }
        val previousPose = targetGroup?.boundPose
        val conflictingGroupIndex = current.groups.find {
            it.groupIndex != groupIndex && it.boundPose == safePose
        }?.groupIndex

        val updatedGroups = current.groups.map { group ->
            when (group.groupIndex) {
                groupIndex -> group.copy(
                    label = label.trim().ifBlank {
                        "GROUP ${groupIndex + 1}"
                    },
                    rootCategory = safeCategory,
                    boundPose = safePose
                )
                conflictingGroupIndex -> group.copy(
                    boundPose = previousPose ?: group.boundPose
                )
                else -> group
            }
        }

        saveQuickActionsConfig(
            context = context,
            config = current.copy(groups = updatedGroups)
        )
    }

    fun resolveQuickAction(
        context: Context,
        deckId: String,
        groupIndex: Int,
        slotIndex: Int
    ): String {
        val config = getQuickActionsConfig(context, deckId)

        val group = config.groups.find {
            it.groupIndex == groupIndex
        } ?: return ""

        val slot = group.slots.find {
            it.slotIndex == slotIndex
        } ?: return ""

        if (slot.template.isBlank()) {
            return ""
        }

        val rootConfig = RootOverrideRepository.getConfig(
            context = context,
            category = group.rootCategory
        )

        return TemplateEngine.resolve(
            template = slot.template,
            localValues = slot.localValues,
            overrides = rootConfig.slots
        )
    }

    private fun normalizeQuickActionsConfig(
        config: QuickActionsDeckConfig
    ): QuickActionsDeckConfig {
        val normalizedGroups = (0..2).map { groupIndex ->
            val existingGroup = config.groups.find {
                it.groupIndex == groupIndex
            } ?: QuickActionGroup(groupIndex = groupIndex)

            existingGroup.copy(
                groupIndex = groupIndex,
                boundPose = existingGroup.boundPose.takeIf { it in POSE_CATEGORIES }
                    ?: defaultBoundPose(groupIndex),
                slots = (0..3).map { slotIndex ->
                    val existingSlot = existingGroup.slots.find {
                        it.slotIndex == slotIndex
                    }

                    existingSlot?.copy(slotIndex = slotIndex)
                        ?: QuickActionSlot(slotIndex = slotIndex)
                }
            )
        }

        // Guard against corrupt or hand-edited data leaving two groups bound to
        // the same pose (or a gap) -- fall back to the canonical
        // IDENTITY/DEFEND/CONNECT-by-index assignment if it's not a clean
        // permutation across the three groups.
        val posesAreUnique = normalizedGroups.map { it.boundPose }.toSet().size ==
            POSE_CATEGORIES.size

        val finalGroups = if (posesAreUnique) {
            normalizedGroups
        } else {
            normalizedGroups.map { group ->
                group.copy(boundPose = defaultBoundPose(group.groupIndex))
            }
        }

        return config.copy(groups = finalGroups)
    }

    fun getEmergencyConfig(
        context: Context,
        deckId: String = getActiveDeckId(context)
    ): EmergencyDeckConfig {
        val fallback = EmergencyDeckConfig(deckId = deckId)

        if (deckId == "DEFAULT") {
            return fallback
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(emergencyKey(deckId), null) ?: return fallback

        return try {
            normalizeEmergencyConfig(
                Json.decodeFromString<EmergencyDeckConfig>(raw)
            )
        } catch (_: Exception) {
            fallback
        }
    }

    fun saveEmergencyConfig(
        context: Context,
        config: EmergencyDeckConfig
    ) {
        if (config.deckId == "DEFAULT") {
            return
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        prefs.edit()
            .putString(
                emergencyKey(config.deckId),
                Json.encodeToString(normalizeEmergencyConfig(config))
            )
            .apply()
    }

    fun updateEmergencySlot(
        context: Context,
        deckId: String,
        slotIndex: Int,
        label: String,
        template: String,
        localValues: List<String>
    ) {
        val current = getEmergencyConfig(
            context = context,
            deckId = deckId
        )

        val updatedSlots = current.slots.map { slot ->
            if (slot.slotIndex != slotIndex) {
                slot
            } else {
                slot.copy(
                    label = label.trim().ifBlank {
                        "EMERGENCY ${slotIndex + 1}"
                    },
                    template = template.trim(),
                    localValues = localValues
                )
            }
        }

        saveEmergencyConfig(
            context = context,
            config = current.copy(slots = updatedSlots)
        )
    }

    fun updateRelatedEmojiSlot(
        context: Context,
        deckId: String,
        pageId: String,
        parentSlotIndex: Int,
        childSlotIndex: Int,
        emoji: String,
        label: String,
        displayText: String
    ) {
        val current = getEmojiDeckConfig(
            context = context,
            deckId = deckId
        )

        val updatedPages = current.pages.map { page ->
            if (page.pageId != pageId) {
                page
            } else {
                page.copy(
                    slots = page.slots.map { parentSlot ->
                        if (parentSlot.slotIndex != parentSlotIndex) {
                            parentSlot
                        } else {
                            val existingChildren = parentSlot.relatedPanel

                            val updatedChildren = (0 until current.gridSize.slotCount)
                                .map { slotIndex ->
                                    val existing = existingChildren.find {
                                        it.slotIndex == slotIndex
                                    } ?: EmojiSlot(slotIndex = slotIndex)

                                    if (slotIndex != childSlotIndex) {
                                        existing.copy(
                                            opensRelatedPanel = false,
                                            relatedPanel = emptyList()
                                        )
                                    } else {
                                        existing.copy(
                                            emoji = emoji,
                                            label = label,
                                            displayText = displayText,
                                            opensRelatedPanel = false,
                                            relatedPanel = emptyList()
                                        )
                                    }
                                }

                            parentSlot.copy(
                                relatedPanel = updatedChildren
                            )
                        }
                    }
                )
            }
        }

        saveEmojiDeckConfig(
            context = context,
            config = current.copy(pages = updatedPages)
        )
    }

    fun resolveEmergencyPrompt(
        context: Context,
        deckId: String,
        slotIndex: Int
    ): String {
        val config = getEmergencyConfig(
            context = context,
            deckId = deckId
        )

        val slot = config.slots.find {
            it.slotIndex == slotIndex
        } ?: return ""

        if (slot.template.isBlank()) {
            return ""
        }

        /*
         * Emergency slots intentionally resolve only their own local variables.
         * They are independent from Matrix profiles, root category focus, and
         * root-override configuration.
         */
        return TemplateEngine.resolve(
            template = slot.template,
            localValues = slot.localValues,
            overrides = emptyMap()
        )
    }

    private fun normalizeEmergencyConfig(
        config: EmergencyDeckConfig
    ): EmergencyDeckConfig {
        val normalizedSlots = (0..3).map { slotIndex ->
            val existing = config.slots.find {
                it.slotIndex == slotIndex
            }

            existing?.copy(slotIndex = slotIndex)
                ?: EmergencyPromptSlot(slotIndex = slotIndex)
        }

        return config.copy(slots = normalizedSlots)
    }

    fun getEmojiDeckConfig(
        context: Context,
        deckId: String = getActiveDeckId(context)
    ): EmojiDeckConfig {
        val fallback = normalizeEmojiDeckConfig(
            EmojiDeckConfig(deckId = deckId)
        )

        if (deckId == "DEFAULT") {
            return fallback
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(emojiDeckKey(deckId), null) ?: return fallback

        return try {
            normalizeEmojiDeckConfig(
                Json.decodeFromString<EmojiDeckConfig>(raw)
            )
        } catch (_: Exception) {
            fallback
        }
    }

    fun saveEmojiDeckConfig(
        context: Context,
        config: EmojiDeckConfig
    ) {
        if (config.deckId == "DEFAULT") {
            return
        }

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        prefs.edit()
            .putString(
                emojiDeckKey(config.deckId),
                Json.encodeToString(normalizeEmojiDeckConfig(config))
            )
            .apply()
    }

    fun updateEmojiSlot(
        context: Context,
        deckId: String,
        pageId: String,
        slotIndex: Int,
        emoji: String,
        label: String,
        displayText: String,
        opensRelatedPanel: Boolean
    ) {
        val current = getEmojiDeckConfig(
            context = context,
            deckId = deckId
        )

        val updatedPages = current.pages.map { page ->
            if (page.pageId != pageId) {
                page
            } else {
                page.copy(
                    slots = page.slots.map { slot ->
                        if (slot.slotIndex != slotIndex) {
                            slot
                        } else {
                            slot.copy(
                                emoji = emoji,
                                label = label,
                                displayText = displayText,
                                opensRelatedPanel = opensRelatedPanel
                            )
                        }
                    }
                )
            }
        }

        saveEmojiDeckConfig(
            context = context,
            config = current.copy(pages = updatedPages)
        )
    }

    private fun normalizeEmojiDeckConfig(
        config: EmojiDeckConfig
    ): EmojiDeckConfig {
        val safePages = config.pages
            .ifEmpty {
                listOf(
                    EmojiPage(
                        pageId = "page_1",
                        name = "PAGE 1"
                    )
                )
            }
            .mapIndexed { pageIndex, page ->
                page.copy(
                    pageId = page.pageId.ifBlank {
                        "page_${pageIndex + 1}"
                    },
                    name = page.name.trim().ifBlank {
                        "PAGE ${pageIndex + 1}"
                    },
                    slots = (0 until config.gridSize.slotCount).map { slotIndex ->
                        val existing = page.slots.find { it.slotIndex == slotIndex }

                        existing?.copy(
                            slotIndex = slotIndex,
                            relatedPanel = normalizeRelatedEmojiPanel(
                                slots = existing.relatedPanel,
                                gridSize = config.gridSize
                            )
                        ) ?: EmojiSlot(
                            slotIndex = slotIndex,
                            relatedPanel = normalizeRelatedEmojiPanel(
                                slots = emptyList(),
                                gridSize = config.gridSize
                            )
                        )
                    }
                )
            }

        return config.copy(pages = safePages)
    }

    fun updateEmojiSlotRelatedPanelEnabled(
        context: Context,
        deckId: String,
        pageId: String,
        slotIndex: Int,
        enabled: Boolean
    ) {
        val current = getEmojiDeckConfig(
            context = context,
            deckId = deckId
        )

        val updatedPages = current.pages.map { page ->
            if (page.pageId != pageId) {
                page
            } else {
                page.copy(
                    slots = page.slots.map { slot ->
                        if (slot.slotIndex != slotIndex) {
                            slot
                        } else {
                            slot.copy(
                                opensRelatedPanel = enabled
                            )
                        }
                    }
                )
            }
        }

        saveEmojiDeckConfig(
            context = context,
            config = current.copy(pages = updatedPages)
        )
    }


    private fun normalizeRelatedEmojiPanel(
        slots: List<EmojiSlot>,
        gridSize: EmojiGridSize
    ): List<EmojiSlot> {
        return (0 until gridSize.slotCount).map { slotIndex ->
            val existing = slots.find { it.slotIndex == slotIndex }

            /*
             * Child slots are intentionally terminal. Even malformed or old
             * imported data cannot create a nested Emoji-panel chain.
             */
            existing?.copy(
                slotIndex = slotIndex,
                opensRelatedPanel = false,
                relatedPanel = emptyList()
            ) ?: EmojiSlot(slotIndex = slotIndex)
        }
    }

    fun getDecks(context: Context): List<DeckMeta> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val jsonString = prefs.getString(DECKS_KEY, "[]") ?: "[]"
        return try {
            Json.decodeFromString(jsonString)
        } catch (e: Exception) {
            emptyList()
        }
    }
    
    fun getActiveDeckId(context: Context): String {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(ACTIVE_DECK_ID, "DEFAULT") ?: "DEFAULT"
    }

    fun getActiveColorIndex(context: Context): Int {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getInt(ACTIVE_DECK_COLOR, 0) // 0 is Default Cyan
    }

    fun getDeckType(
        context: Context,
        deckId: String = getActiveDeckId(context)
    ): DeckType {
        // DEFAULT is never persisted as DeckMeta. It is permanently Matrix.
        if (deckId == "DEFAULT") {
            return DeckType.MATRIX
        }

        return getDecks(context)
            .find { it.id == deckId }
            ?.type
            ?: DeckType.MATRIX
    }

    fun getDeckName(
        context: Context,
        deckId: String = getActiveDeckId(context)
    ): String {
        if (deckId == "DEFAULT") {
            return "DEFAULT"
        }

        return getDecks(context)
            .find { it.id == deckId }
            ?.name
            ?: "UNKNOWN"
    }


    /**
     * Saves a new Deck.
     * Sanitizes incoming keys to prevent "Deck Inception" (nested prefixes).
     */
    fun saveDeck(
        context: Context,
        name: String,
        colorIndex: Int,
        matrixData: Map<String, String>
    ) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val currentDecks = getDecks(context).toMutableList()
        
        // Generate Unique ID
        val newId = "DECK_${System.currentTimeMillis()}"
        
        // 1. Save Meta
        currentDecks.add(
            DeckMeta(
                id = newId,
                name = name,
                colorIndex = colorIndex,
                type = DeckType.MATRIX
            )
        )
        prefs.edit().putString(DECKS_KEY, Json.encodeToString(currentDecks)).apply()
        
        // 2. Save Matrix Data
        val editor = prefs.edit()
        
        matrixData.forEach { (key, phrase) ->
            // 1. Find the path (starts with /std/ or /custom/)
            val pathIndex = key.indexOf("/std/")
            val customIndex = key.indexOf("/custom/")
            
            // Whichever comes first (or exists)
            val validIndex = if (pathIndex != -1) pathIndex else customIndex
            
            if (validIndex != -1) {
                val pathPart = key.substring(validIndex) // e.g., "/std/id/0"
                val prefixPart = key.substring(0, validIndex) // e.g., "DECK_OLD_WORK_"
                
                // 2. Extract Profile from the dirty prefix
                var profileTag = ""
                for (prof in PROFILES) {
                    // Check if prefix ENDS with known profile (e.g. "WORK_")
                    if (prefixPart.endsWith("${prof}_") && prof != "DEFAULT") {
                        profileTag = "${prof}_"
                        break
                    }
                }
                
                // 3. Construct Clean Key: DECK_NEW_ + PROFILE_ + PATH
                val cleanKey = "${newId}_${profileTag}${pathPart}"
                editor.putString(cleanKey, phrase)
            }
        }
        editor.apply()
    }

    fun createDeck(
        context: Context,
        name: String,
        colorIndex: Int,
        type: DeckType
    ): DeckMeta {
        /*
         * DEFAULT is the permanent Matrix deck. New Matrix decks are no longer
         * supported, even if an old UI route accidentally attempts creation.
         *
         * Existing legacy Matrix decks remain readable and deletable.
         */
        require(type != DeckType.MATRIX) {
            "New MATRIX decks are not supported. Use the DEFAULT Matrix deck."
        }

        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val currentDecks = getDecks(context).toMutableList()

        val cleanName = name
            .trim()
            .uppercase()
            .take(40)
            .ifBlank {
                when (type) {
                    DeckType.MATRIX -> "DEFAULT"
                    DeckType.QUICK_ACTIONS -> "QUICK ACTIONS"
                    DeckType.EMERGENCY -> "EMERGENCY"
                    DeckType.EMOJI -> "EMOJI"
                    DeckType.GIF -> "GIF"
                }
            }

        val newDeck = DeckMeta(
            id = "DECK_${System.currentTimeMillis()}",
            name = cleanName,
            colorIndex = colorIndex.coerceIn(
                0,
                NeonPalette.SWATCHES.lastIndex
            ),
            type = type
        )

        currentDecks.add(newDeck)

        prefs.edit()
            .putString(
                DECKS_KEY,
                Json.encodeToString(currentDecks)
            )
            .apply()

        return newDeck
    }

    fun updateDeckMeta(
        context: Context,
        deckId: String,
        name: String,
        colorIndex: Int
    ): DeckMeta? {
        /*
         * DEFAULT is the permanent system Matrix deck. It is intentionally not
         * editable from deck management.
         */
        if (deckId == "DEFAULT") {
            return null
        }

        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val currentDecks = getDecks(context)
        val existingDeck = currentDecks.find { deck ->
            deck.id == deckId
        } ?: return null

        val updatedDeck = existingDeck.copy(
            name = name
                .trim()
                .uppercase()
                .take(40)
                .ifBlank { "UNTITLED DECK" },
            colorIndex = colorIndex.coerceIn(
                0,
                NeonPalette.SWATCHES.lastIndex
            )
        )

        val updatedDecks = currentDecks.map { deck ->
            if (deck.id == deckId) {
                updatedDeck
            } else {
                deck
            }
        }

        prefs.edit()
            .putString(
                DECKS_KEY,
                Json.encodeToString(updatedDecks)
            )
            .apply()

        /*
         * Persist the edited color to the active-deck state and sync the
         * renamed deck to the watch when this deck is currently active.
         */
        if (getActiveDeckId(context) == deckId) {
            activateDeck(
                context = context,
                deckId = updatedDeck.id,
                colorIndex = updatedDeck.colorIndex
            )
        }

        return updatedDeck
    }

    fun activateDeck(context: Context, deckId: String, colorIndex: Int) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(ACTIVE_DECK_ID, deckId)
            .putInt(ACTIVE_DECK_COLOR, colorIndex)
            .apply()

        val name = if(deckId == "DEFAULT") "DEFAULT" else {
            getDecks(context).find { it.id == deckId }?.name ?: "UNKNOWN"
        }
        WatchSync.sendDeckConfig(context, colorIndex, name)
    }

    fun deleteDeck(
        context: Context,
        deckId: String
    ): Boolean {
        /*
         * DEFAULT is the one permanent Matrix deck.
         *
         * It is not stored in custom_decks_meta, cannot be deleted, and is the
         * fallback target whenever an active custom deck is removed.
         */
        if (deckId == "DEFAULT") {
            return false
        }

        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val currentDecks = getDecks(context)
        val deletedDeck = currentDecks.find { deck ->
            deck.id == deckId
        } ?: return false

        /*
         * Capture these before removing metadata. Calling getDeckType() after
         * removing it would fall back to MATRIX and skip GIF file cleanup.
         */
        val deletedDeckType = deletedDeck.type
        val wasActiveDeck = getActiveDeckId(context) == deckId

        val updatedDecks = currentDecks.filterNot { deck ->
            deck.id == deckId
        }

        val editor = prefs.edit()

        /*
         * Remove deck metadata first.
         */
        editor.putString(
            DECKS_KEY,
            Json.encodeToString(updatedDecks)
        )

        /*
         * Remove all Matrix phrase, variable, visual override, and
         * profile-specific storage belonging to this deck.
         */
        prefs.all.keys.forEach { key ->
            if (key.startsWith("${deckId}_")) {
                editor.remove(key)
            }
        }

        /*
         * Remove non-Matrix deck configuration.
         */
        editor.remove(quickActionsKey(deckId))
        editor.remove(emergencyKey(deckId))
        editor.remove(emojiDeckKey(deckId))

        /*
         * An active deleted deck must immediately return to DEFAULT.
         */
        if (wasActiveDeck) {
            editor.putString(ACTIVE_DECK_ID, "DEFAULT")
            editor.putInt(ACTIVE_DECK_COLOR, 0)
        }

        editor.apply()

        /*
         * GIF media is deliberately stored outside ack_matrix_config so that it
         * never participates in TransferManager backup or restore behavior.
         */
        if (deletedDeckType == DeckType.GIF) {
            GifRepository.deleteDeckGifs(
                context = context,
                deckId = deckId
            )
        }

        /*
         * Send the fallback deck configuration to the watch after preferences
         * have been committed.
         */
        if (wasActiveDeck) {
            activateDeck(
                context = context,
                deckId = "DEFAULT",
                colorIndex = 0
            )
        }

        return true
    }

    // --- QUICK PHRASES ---
    fun saveQuickPhrase(context: Context, text: String, tag: String) {
        val currentList = getQuickPhrases(context).toMutableList()
        currentList.add(0, QuickPhrase(text = text, tag = tag.uppercase()))
        saveList(context, currentList)
    }

    fun deleteQuickPhrase(context: Context, phrase: QuickPhrase) {
        val currentList = getQuickPhrases(context).toMutableList()
        currentList.removeAll { it.id == phrase.id }
        saveList(context, currentList)
    }

    fun getQuickPhrases(context: Context): List<QuickPhrase> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val jsonString = prefs.getString(QUICK_PHRASES_KEY, "[]") ?: "[]"
        return try {
            Json.decodeFromString(jsonString)
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun saveList(context: Context, list: List<QuickPhrase>) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val jsonString = Json.encodeToString(list)
        prefs.edit().putString(QUICK_PHRASES_KEY, jsonString).apply()
    }

    // --- PROFILE STATE MANAGEMENT ---

    fun getActiveProfile(context: Context): String {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(ACTIVE_PROFILE_KEY, "DEFAULT") ?: "DEFAULT"
    }

    fun setActiveProfile(context: Context, profile: String) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().putString(ACTIVE_PROFILE_KEY, profile).apply()
    }
    
    fun getActiveCategoryFocus(context: Context): String {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(ACTIVE_CAT_KEY, "IDENTITY") ?: "IDENTITY"
    }
    
    fun setActiveCategoryFocus(context: Context, category: String) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().putString(ACTIVE_CAT_KEY, category).apply()
    }

    // Decodes a fired gesture path (e.g. "/gesture/ask_name") back to which
    // pose and twist index produced it. BackgroundSensorService.fireCommand()
    // sends one of exactly 12 fixed paths -- 3 poses x 4 twists -- regardless
    // of which deck is active on the phone, and BASE_TEMPLATE already lists
    // that same fixed mapping (category + the /0../3 suffix on path) for the
    // default Matrix deck, so it doubles as the canonical decode table here
    // rather than duplicating it.
    private fun decodeGestureSignal(signalPath: String): Pair<String, Int>? {
        val node = BASE_TEMPLATE.find { it.triggerPath == signalPath } ?: return null
        val twistIndex = node.path.substringAfterLast("/").toIntOrNull() ?: return null
        return node.category to twistIndex
    }

    // --- SIGNAL RESOLUTION ---
    fun resolveSignalToPhrase(
        context: Context,
        signalPath: String
    ): String {
        val deckType = getDeckType(context)

        // A Quick Actions deck overrides normal Matrix routing entirely: each
        // of its three groups is bound to one root pose, and the fired twist
        // index selects the slot within that group.
        if (deckType == DeckType.QUICK_ACTIONS) {
            val (pose, twistIndex) = decodeGestureSignal(signalPath) ?: return ""
            val deckId = getActiveDeckId(context)
            val config = getQuickActionsConfig(context, deckId)
            val group = config.groups.find { it.boundPose == pose } ?: return ""
            return resolveQuickAction(context, deckId, group.groupIndex, twistIndex)
        }

        // Normal watch gesture paths are Matrix routines. Any other deck type
        // must never accidentally execute a phrase from the last Matrix
        // deck/profile.
        if (deckType != DeckType.MATRIX) {
            return ""
        }

        refreshCache(context)

        val focusedCategory = getActiveCategoryFocus(context)

        // 1. The currently focused root gets first priority.
        val focusedNode = cachedNodes.find { node ->
            node.category == focusedCategory &&
                    node.triggerPath == signalPath
        }

        if (focusedNode != null) {
            return getResolvedPhrase(context, focusedNode.path)
        }

        // 2. DEFEND and CONNECT remain globally available.
        val fixedNode = cachedNodes.find { node ->
            node.triggerPath == signalPath &&
                    (node.category == "DEFEND" || node.category == "CONNECT")
        }

        if (fixedNode != null) {
            return getResolvedPhrase(context, fixedNode.path)
        }

        // 3. Last fallback is the default identity mapping.
        val identityNode = cachedNodes.find { node ->
            node.category == "IDENTITY" &&
                    node.triggerPath == signalPath
        }

        return identityNode?.let { node ->
            getResolvedPhrase(context, node.path)
        }.orEmpty()
    }

    // --- UNIVERSAL KEY GENERATOR ---
    private fun generateStorageKey(deckId: String, profile: String, path: String): String {
        val deckPrefix = if (deckId == "DEFAULT") "" else "${deckId}_"
        val profilePrefix = if (profile == "DEFAULT") "" else "${profile}_"
        return "$deckPrefix$profilePrefix$path"
    }

    fun getPhrase(context: Context, storagePath: String): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val activeDeckId = getActiveDeckId(context)
        val activeProfile = getActiveProfile(context)

        // 1. Deck + profile-specific value.
        //
        // Use contains() rather than isNullOrEmpty(): an intentionally blank
        // saved prompt is still a valid prompt and must override the default.
        val specificKey = generateStorageKey(
            activeDeckId,
            activeProfile,
            storagePath
        )

        if (prefs.contains(specificKey)) {
            return prefs.getString(specificKey, "").orEmpty()
        }

        // 2. Default profile fallback for the active deck.
        if (activeProfile != "DEFAULT") {
            val defaultProfileKey = generateStorageKey(
                activeDeckId,
                "DEFAULT",
                storagePath
            )

            if (prefs.contains(defaultProfileKey)) {
                return prefs.getString(defaultProfileKey, "").orEmpty()
            }
        }

        // 3. Built-in phrase only when no saved value exists at all.
        val node = cachedNodes.find { it.path == storagePath }

        return node?.defaultPhrase.orEmpty()
    }

    fun setPhrase(context: Context, storagePath: String, phrase: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val activeDeckId = getActiveDeckId(context)
        val activeProfile = getActiveProfile(context)

        val key = generateStorageKey(activeDeckId, activeProfile, storagePath)
        prefs.edit().putString(key, phrase).apply()
    }

    fun getVisualOverride(context: Context, storagePath: String): String {
                val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                val activeDeckId = getActiveDeckId(context)
                val activeProfile = getActiveProfile(context)

                val key = generateStorageKey(activeDeckId, activeProfile, storagePath) + "_visual"
                return prefs.getString(key, null) ?: ""
            }

        fun setVisualOverride(context: Context, storagePath: String, overrideText: String) {
                val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                val activeDeckId = getActiveDeckId(context)
                val activeProfile = getActiveProfile(context)

                val key = generateStorageKey(activeDeckId, activeProfile, storagePath) + "_visual"
                prefs.edit().putString(key, overrideText).apply()
            }

    // --- VARIABLES ---
    fun getVariableValues(context: Context, storagePath: String): List<String> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val key = generateStorageKey(getActiveDeckId(context), getActiveProfile(context), storagePath) + "_vars"
        val raw = prefs.getString(key, "[]") ?: "[]"
        return try { Json.decodeFromString(raw) } catch(e: Exception) { emptyList() }
    }

    fun setVariableValues(context: Context, storagePath: String, values: List<String>) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val key = generateStorageKey(getActiveDeckId(context), getActiveProfile(context), storagePath) + "_vars"
        prefs.edit().putString(key, Json.encodeToString(values)).apply()
    }

    fun debugResolvedPhrase(
        context: Context,
        storagePath: String
    ): String {
        refreshCache(context)

        val template = getPhrase(context, storagePath)
        val localValues = getVariableValues(context, storagePath)

        val category = cachedNodes
            .find { node ->
                node.path == storagePath
            }
            ?.category
            ?: "IDENTITY"

        val rootConfig = RootOverrideRepository.getConfig(
            context = context,
            category = category
        )

        val variableTags = TemplateEngine.getVariableTags(template)

        val variableTrace = variableTags.mapIndexed { index, tag ->
            val localValue = localValues.getOrNull(index).orEmpty()

            val rootValue = tag?.let { rootConfig.slots[it] }

            val usesRootOverride = rootValue?.enabled == true &&
                    rootValue.value.isNotBlank()

            val token = if (tag == null) {
                "{VAR}"
            } else {
                "{VAR:$tag}"
            }

            val source = if (usesRootOverride) {
                "ROOT $tag"
            } else {
                "LOCAL"
            }

            val resolvedValue = if (usesRootOverride) {
                rootValue.value
            } else {
                localValue
            }

            "$token=$source[${resolvedValue.ifBlank { "EMPTY" }}]"
        }

        val resolved = TemplateEngine.resolve(
            template = template,
            localValues = localValues,
            overrides = rootConfig.slots
        )

        val trace = if (variableTrace.isEmpty()) {
            "NO VARIABLES"
        } else {
            variableTrace.joinToString(separator = " | ")
        }

        return "RESOLVE ${category}/${storagePath} :: $trace :: OUT=$resolved"
    }

    fun getResolvedPhrase(
        context: Context,
        storagePath: String
    ): String {
        refreshCache(context)

        val template = getPhrase(context, storagePath)
        val localValues = getVariableValues(context, storagePath)

        val category = cachedNodes
            .find { node ->
                node.path == storagePath
            }
            ?.category
            ?: "IDENTITY"

        val rootConfig = RootOverrideRepository.getConfig(
            context = context,
            category = category
        )

        return TemplateEngine.resolve(
            template = template,
            localValues = localValues,
            overrides = rootConfig.slots
        )
    }

    // Header Shortcut Handlers

    @Serializable
    data class HeaderShortcut(val label: String, val phrase: String)

    fun getHeaderShortcuts(context: Context): List<HeaderShortcut> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString("header_shortcuts", "[]") ?: "[]"

        val list = try {
            Json.decodeFromString<List<HeaderShortcut>>(raw)
        } catch(e: Exception) {
            emptyList()
        }

        // Enforce exactly 3 slots at all times
        return (0..2).map { i ->
            list.getOrNull(i) ?: HeaderShortcut("M${i + 1}", "")
        }
    }

    fun saveHeaderShortcuts(context: Context, shortcuts: List<HeaderShortcut>) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString("header_shortcuts", Json.encodeToString(shortcuts)).apply()
    }

    // --- CACHE & HELPERS ---
    fun createCustomCategory(context: Context, catName: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existingSet = prefs.getStringSet(CUSTOM_CATS_KEY, mutableSetOf()) ?: mutableSetOf()
        
        if (!existingSet.contains(catName)) {
            existingSet.add(catName)
            prefs.edit().putStringSet(CUSTOM_CATS_KEY, existingSet).apply()
            refreshCache(context)
        }
    }

    private fun refreshCache(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val customCats = prefs.getStringSet(CUSTOM_CATS_KEY, emptySet()) ?: emptySet()
        
        cachedNodes = BASE_TEMPLATE.toMutableList()
        
        customCats.forEach { cat ->
            cachedNodes.add(MatrixNode("/custom/$cat/1", "/gesture/thumbsup", "Twist 0 (Mapped)", "Yes.", cat))
            cachedNodes.add(MatrixNode("/custom/$cat/2", "/gesture/wave", "Twist 1 (Mapped)", "No.", cat))
            cachedNodes.add(MatrixNode("/custom/$cat/3", "/gesture/ask_name", "Twist 2 (Mapped)", "Maybe.", cat))
            cachedNodes.add(MatrixNode("/custom/$cat/4", "/gesture/name", "Twist 3 (Mapped)", "Explain.", cat))
        }
    }

    fun getMatrix(context: Context): List<Triple<MatrixNode, String, String>> {
        refreshCache(context)
        return cachedNodes.map { node ->
            val raw = getPhrase(context, node.path)
            val resolved = getResolvedPhrase(context, node.path)
            Triple(node, raw, resolved)
        }
    }
}
