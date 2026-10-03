// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.watch

import android.content.Context
import android.util.Log
import com.example.besu.core.RelayAckTracker
import com.example.besu.core.RelayResult
import com.example.besu.core.WatchRelayProtocol
import com.example.besu.core.relayTimeoutMs
import com.google.android.gms.wearable.Node
import com.google.android.gms.wearable.Wearable
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.random.Random

// Relays a fully-processed prompt (gain, effects, everything already
// baked in -- the watch only ever plays back finished bytes, it does no
// DSP of its own) to the paired ACK Wear app for local playback, when
// OUTPUT DEVICE in PROTOCOL is set to ACK WATCH.
//
// Chunked over the existing MessageClient background-delivery path
// (WearConfigListenerService's manifest path filters) rather than
// ChannelClient. A single MessageClient payload caps out around 100KB --
// well under a full 15-second recording (~469KB of 16kHz/16-bit PCM) or
// an uncapped TTS phrase -- but this app has no existing use of
// ChannelClient to lean on for its background-wake reliability, while
// chunked MessageClient reuses a mechanism every other phone -> watch
// feature here already depends on.
//
// Delivery is CONFIRMED, not assumed. This used to be fire-and-forget: the
// phone sent the chunks, skipped its own playback because the watch node was
// reachable, and if one chunk was lost (or the watch app was not running) the
// message was never heard anywhere, with nothing to say so. Now the watch
// sends /sys/audio_relay_ack once it is really playing, and sendAndAwait waits
// for it; if none arrives in time it says so and the caller plays the message
// on the phone instead. The byte layout of every message is in
// core/WatchRelayProtocol.kt (plain Kotlin, tested).
//
// Known limits: a confirmation that arrives after the phone has given up can
// mean the message plays on both the phone and the watch, which is better
// than silence. A watch app that has not been updated never confirms, so each
// message sent with ACK WATCH selected waits out the timeout and then plays on
// the phone: release the phone and watch apps together.
object WatchAudioRelay {
    private const val TAG = "ACK_WATCH_RELAY"

    // Shared with WearListenerService (same process), which feeds it the watch's confirmations.
    val ackTracker = RelayAckTracker()

    /**
     * Sends [pcm] to every node in [nodes] and waits for one of them to confirm it is playing. Blocks for up to
     * relayTimeoutMs(chunks), so it must run off the main thread (playPcm already does).
     *
     * DELIVERED: a watch confirmed, the phone plays nothing. NOT_CONFIRMED: no confirmation in time (or sending failed);
     * a cancel is sent to the nodes, best effort, and the caller plays the message itself. NO_WATCH: [nodes] is empty.
     */
    fun sendAndAwait(
        context: Context,
        nodes: List<Node>,
        pcm: ShortArray,
        sampleRate: Int
    ): RelayResult {
        // Nothing to play. Same as before: neither the watch nor the phone is asked, because the phone's own
        // player refuses a zero-length buffer.
        if (pcm.isEmpty()) {
            return RelayResult.DELIVERED
        }
        if (nodes.isEmpty()) {
            return RelayResult.NO_WATCH
        }

        val bytes = ByteBuffer.allocate(pcm.size * 2)
            .order(ByteOrder.LITTLE_ENDIAN)
            .apply { pcm.forEach { putShort(it) } }
            .array()

        val totalChunks = WatchRelayProtocol.chunkCount(bytes.size)

        // Distinguishes this dispatch from a previous one that might still
        // be mid-transfer on the watch's reassembly buffer -- doesn't need
        // to be globally unique, just different from the last one used.
        val transferId = Random.nextInt()

        val messageClient = Wearable.getMessageClient(context)

        // Registered BEFORE the first chunk is sent: the watch's confirmation can arrive before this
        // thread has started waiting.
        ackTracker.expect(transferId)

        val confirmed = try {
            for (chunkIndex in 0 until totalChunks) {
                val start = chunkIndex * WatchRelayProtocol.CHUNK_PAYLOAD_BYTES
                val end = (start + WatchRelayProtocol.CHUNK_PAYLOAD_BYTES).coerceAtMost(bytes.size)

                val header = WatchRelayProtocol.encodeChunkHeader(transferId, sampleRate, chunkIndex, totalChunks)
                val payload = header + bytes.copyOfRange(start, end)

                nodes.forEach { node ->
                    messageClient.sendMessage(node.id, WatchRelayProtocol.CHUNK_PATH, payload)
                }
            }

            ackTracker.await(transferId, relayTimeoutMs(totalChunks))
        } catch (e: Exception) {
            // Could not even hand the audio over. Treated like a missing confirmation, so the phone plays it.
            Log.e(TAG, "sending the audio to the watch failed", e)
            ackTracker.forget(transferId)
            false
        }

        if (confirmed) {
            return RelayResult.DELIVERED
        }

        // Tell the watch to stop waiting for the rest of this one, so it is not played late as well. Best effort.
        try {
            val cancel = WatchRelayProtocol.encodeTransferId(transferId)
            nodes.forEach { node ->
                messageClient.sendMessage(node.id, WatchRelayProtocol.CANCEL_PATH, cancel)
            }
        } catch (e: Exception) {
            Log.e(TAG, "could not tell the watch to cancel", e)
        }

        return RelayResult.NOT_CONFIRMED
    }
}
