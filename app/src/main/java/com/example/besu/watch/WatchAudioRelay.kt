package com.example.besu.watch

import android.content.Context
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
// Fire-and-forget, same as every other WatchSync message -- no
// acknowledgement, no retry. OutputService has already decided to skip
// local phone playback by the time this is called, based on the watch
// node being reachable at all, not on delivery confirmation of any
// individual chunk -- if one is dropped in transit, the watch's transfer
// simply never completes and that prompt silently doesn't play there.
object WatchAudioRelay {
    private const val PATH = "/audio/relay_chunk"

    // header = transferId (Int) + sampleRate (Int) + chunkIndex (Short) +
    // totalChunks (Short).
    private const val HEADER_BYTES = 12

    // Comfortably under MessageClient's ~100KB payload cap even after the
    // header -- kept sample-aligned (even) so a chunk boundary never
    // splits a single 16-bit PCM sample across two messages.
    private const val CHUNK_PAYLOAD_BYTES = 80_000

    fun send(
        context: Context,
        nodes: List<Node>,
        pcm: ShortArray,
        sampleRate: Int
    ) {
        if (pcm.isEmpty() || nodes.isEmpty()) {
            return
        }

        val bytes = ByteBuffer.allocate(pcm.size * 2)
            .order(ByteOrder.LITTLE_ENDIAN)
            .apply { pcm.forEach { putShort(it) } }
            .array()

        val totalChunks = ((bytes.size + CHUNK_PAYLOAD_BYTES - 1) / CHUNK_PAYLOAD_BYTES)
            .coerceAtLeast(1)

        // Distinguishes this dispatch from a previous one that might still
        // be mid-transfer on the watch's reassembly buffer -- doesn't need
        // to be globally unique, just different from the last one used.
        val transferId = Random.nextInt()

        val messageClient = Wearable.getMessageClient(context)

        for (chunkIndex in 0 until totalChunks) {
            val start = chunkIndex * CHUNK_PAYLOAD_BYTES
            val end = (start + CHUNK_PAYLOAD_BYTES).coerceAtMost(bytes.size)

            val header = ByteBuffer.allocate(HEADER_BYTES)
                .order(ByteOrder.LITTLE_ENDIAN)
                .apply {
                    putInt(transferId)
                    putInt(sampleRate)
                    putShort(chunkIndex.toShort())
                    putShort(totalChunks.toShort())
                }
                .array()

            val payload = header + bytes.copyOfRange(start, end)

            nodes.forEach { node ->
                messageClient.sendMessage(node.id, PATH, payload)
            }
        }
    }
}
