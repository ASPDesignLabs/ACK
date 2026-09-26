package com.example.besu.watch

import com.example.besu.computer.*
import com.example.besu.data.*
import android.content.Context
import android.content.Intent
import com.google.android.gms.wearable.Wearable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

object WatchSync {

    private val json = Json { encodeDefaults = true }

    // Hard ceiling on how many nodes of one category get synced to the
    // watch -- a defensive cap against a pathological tree blowing past the
    // Wearable MessageClient payload limit, not a "your tree shouldn't be
    // this big" opinion. Silent truncation is acceptable here (unlike
    // TransferManager's validated import path) because this is a live,
    // repeatedly-resent cache, not a one-shot user action that could lose
    // data -- the watch just won't offer every entry until the tree's
    // trimmed down, same as any other sync lag.
    private const val MAX_SYNCED_NODES_PER_CATEGORY = 400
    
    // --- EXISTING FUNCTIONS ---

    // --- NEW: TARGET LIST SYNC ---
    fun sendTargetList(context: Context) {
        // 1. Get List from Repository
        val targets = TargetRepository.getTargets(context)

        // 2. Format: "0:LABEL|1:LABEL"
        val sb = StringBuilder()
        targets.forEachIndexed { i, slot ->
            if (i > 0) sb.append("|")
            sb.append("${slot.index}:${slot.label}")
        }

        val payload = sb.toString().toByteArray(Charsets.UTF_8)

        // 3. Send
        sendMessage(context, "/sys/target_list", payload, "TARGET LIST SYNC")
    }

    fun sendDeckConfig(context: Context, colorIndex: Int, deckName: String, deckType: String) {
        val path = "/sys/deck_update"
        val data = "$colorIndex,$deckName,$deckType".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data)
    }

    fun sendAudioConfig(context: Context, theme: Int, volume: Float) {
        val path = "/sys/audio_config"
        val data = "$theme,$volume".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "AUDIO SYNC")
    }

    fun sendPowerConfig(context: Context, minutes: Int) {
        val path = "/sys/pwr_config"
        val data = "$minutes".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "POWER SYNC")
    }

    fun sendProfileConfig(context: Context, profileName: String) {
        val path = "/sys/context_update"
        val data = profileName.toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data)
    }

    fun sendDeckList(context: Context) {
        val decks = CommandRepository.getDecks(context)
        val sb = StringBuilder("DEFAULT|DEFAULT|0|MATRIX")

        decks.forEach { deck ->
            sb.append(";")
            sb.append("${deck.id}|${deck.name}|${deck.colorIndex}|${deck.type.name}")
        }

        val data = sb.toString().toByteArray(Charsets.UTF_8)
        sendMessage(context, "/sys/deck_list", data, "DECK LIST SYNC")
    }

    // --- NEW: TARGET COMPUTER CATEGORY SYNC ---
    // Sends the watch a compact copy of every Target Computer category
    // referenced by [COMPUTER:X] tags anywhere in the given Quick Actions
    // deck's slots, so its tap-tap-hold flyout can offer a pick without a
    // round trip. Always sent (even empty) on every deck activation --
    // CommandRepository.activateDeck calls this unconditionally -- so a
    // switch away from a tagged Quick Actions deck clears the watch's
    // cache instead of leaving the previous deck's categories selectable.
    fun sendComputerCategoriesForDeck(context: Context, deckId: String) {
        val categoryIds = CommandRepository.computerCategoryIdsForQuickActionsDeck(context, deckId)

        val payload = if (categoryIds.isEmpty()) {
            "[]"
        } else {
            val allCategories = ComputerRepository.getCategories(context)
            val synced = categoryIds.mapNotNull { categoryId ->
                val category = allCategories.find { it.id == categoryId } ?: return@mapNotNull null
                val nodes = mutableListOf<SyncedComputerNode>()
                flattenComputerNodes(category.root.children, parentId = "", into = nodes)
                SyncedComputerCategory(
                    id = category.id,
                    label = category.label,
                    nodes = nodes,
                    activeNodeId = category.activeNodeId
                )
            }
            json.encodeToString(synced)
        }

        sendMessage(context, "/sys/computer_categories", payload.toByteArray(Charsets.UTF_8), "TARGET COMPUTER SYNC")
    }

    // --- NEW: UNSCOPED TARGET COMPUTER SYNC (ALL CATEGORIES) ---
    // Sends every Target Computer category on the phone, regardless of which
    // deck (if any) references it -- unlike sendComputerCategoriesForDeck,
    // this ignores deck scoping entirely. Feeds OVERSEER's "ALL TARGETS"
    // browser (relayed onward by ACK Wear); ACK Wear's own UI has no use for
    // this and doesn't cache it locally, only relays it through. Sent
    // alongside the deck-scoped resync on every pick/clear (see
    // ComputerRepository.setActiveEntry/clearActiveEntry) so it's never
    // staler than any pick made anywhere.
    fun sendAllComputerCategories(context: Context) {
        val allCategories = ComputerRepository.getCategories(context)
        val synced = allCategories.map { category ->
            val nodes = mutableListOf<SyncedComputerNode>()
            flattenComputerNodes(category.root.children, parentId = "", into = nodes)
            SyncedComputerCategory(
                id = category.id,
                label = category.label,
                nodes = nodes,
                activeNodeId = category.activeNodeId
            )
        }

        val payload = json.encodeToString(synced)
        sendMessage(context, "/sys/computer_categories_all", payload.toByteArray(Charsets.UTF_8), "ALL TARGET COMPUTER SYNC")
    }

    private fun flattenComputerNodes(
        children: List<ComputerNode>,
        parentId: String,
        into: MutableList<SyncedComputerNode>
    ) {
        for (child in children) {
            if (into.size >= MAX_SYNCED_NODES_PER_CATEGORY) return

            into.add(
                SyncedComputerNode(
                    id = child.id,
                    label = child.label,
                    isCategory = child.type == ComputerNodeType.CATEGORY,
                    parentId = parentId
                )
            )
            flattenComputerNodes(child.children, child.id, into)
        }
    }

    // --- CROWN SENSITIVITY ---
    fun sendCrownSensitivity(context: Context, sensitivityIndex: Int) {
        val path = "/sys/crown_sens"
        val data = sensitivityIndex.toString().toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "SENSITIVITY SYNC")
    }

    // --- NEW: MOTION PHYSICS CONFIG ---
    fun sendMotionConfig(context: Context, twistThreshold: Float, poseThreshold: Float) {
        val path = "/sys/motion_config"
        // Payload: "TWIST,POSE" e.g. "7.0,6.0"
        val data = "$twistThreshold,$poseThreshold".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "PHYSICS SYNC")
    }

    // How long, after a pose locks and goes quiet, the watch waits past its
    // warning buzz before actually firing -- a tap on the watch face any
    // time before then cancels instead. 250-1000ms.
    fun sendFireGraceConfig(context: Context, graceMs: Int) {
        val path = "/sys/fire_grace_config"
        val data = "$graceMs".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "FIRE GRACE SYNC")
    }

    // How much time is allowed between consecutive twists of the 3-twist
    // wake gesture before the count resets to zero. 800-3000ms.
    fun sendWakeWindowConfig(context: Context, windowMs: Int) {
        val path = "/sys/wake_window_config"
        val data = "$windowMs".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "WAKE WINDOW SYNC")
    }

    // How long the Target Computer flyout (ComputerTargetFlyout, watch-
    // side) waits with no interaction before auto-dismissing. 5-30s.
    fun sendComputerFlyoutTimeout(context: Context, seconds: Int) {
        val path = "/sys/computer_flyout_timeout"
        val data = "$seconds".toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "FLYOUT TIMEOUT SYNC")
    }

    // --- GESTURE TRAINING MODE ---
    // mode is one of "OFF" / "PACED" / "LIVE":
    //   OFF   - normal live behavior.
    //   PACED - guided pose walkthroughs. Suppresses real output, suspends the
    //           watch's auto-timeouts, and firing waits on sendTrainingFireReady
    //           instead of a timer.
    //   LIVE  - Training Ground. Suppresses real output but leaves timing alone.
    fun sendTrainingMode(context: Context, mode: String) {
        val path = "/sys/training_mode"
        val data = mode.toByteArray(Charsets.UTF_8)
        sendMessage(context, path, data, "TRAINING MODE $mode")
    }

    // Tells the watch it's safe to complete the held pose -- sent the instant the
    // coach panel actually reaches its FIRE step during PACED training, so the
    // watch never fires before the learner has been shown that step.
    fun sendTrainingFireReady(context: Context) {
        sendMessage(context, "/sys/training_fire_ready", null)
    }

    // Tells the watch to discard any pose/twist it may have picked up
    // incidentally during the previous transition and start listening fresh for
    // a deliberate one. target is "POSE" (coach panel reached the pose-entry
    // step) or "MODIFIER" (reached the twist step).
    fun sendTrainingResetListen(context: Context, target: String) {
        val data = target.toByteArray(Charsets.UTF_8)
        sendMessage(context, "/sys/training_reset_listen", data, "TRAINING RESET: $target")
    }

    // Helper to reduce boilerplate
    private fun sendMessage(context: Context, path: String, data: ByteArray?, logMsg: String? = null) {
        Wearable.getNodeClient(context).connectedNodes.addOnSuccessListener { nodes ->
            nodes.forEach { node -> 
                Wearable.getMessageClient(context).sendMessage(node.id, path, data)
            }
            if (logMsg != null) broadcastLog(context, logMsg, "SYS")
        }
    }

    private fun broadcastLog(context: Context, msg: String, type: String) {
        val intent = Intent("ACK_LOG")
        intent.setPackage(context.packageName)
        intent.putExtra("msg", msg)
        intent.putExtra("type", type)
        context.sendBroadcast(intent)
    }
}
