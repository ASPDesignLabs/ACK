// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** What happened when a message was handed to the watch to play. */
enum class RelayResult {
    /** The watch said it is playing the message. The phone plays nothing. */
    DELIVERED,

    /** A watch was reachable and was sent the audio, but did not confirm in time. The phone plays it itself. */
    NOT_CONFIRMED,

    /** No watch was reachable. The phone plays it itself, as it always has. */
    NO_WATCH
}

/**
 * The messages the phone and the ACK Wear app exchange when OUTPUT DEVICE is set to ACK WATCH. Plain Kotlin so the exact
 * bytes are tested without a phone or a watch. The watch app is a separate module (com.example.besu.wear) with its own
 * code for the same bytes: change anything here and the watch's AudioRelay / WearConfigListenerService with it, and
 * release the phone and watch apps together.
 *
 *   /audio/relay_chunk   phone -> watch  12-byte header (see [encodeChunkHeader]) + PCM. A piece of the audio.
 *   /sys/audio_relay_ack watch -> phone  the transfer id (4 bytes, little-endian): "I am playing this".
 *   /audio/relay_cancel  phone -> watch  the transfer id (4 bytes, little-endian): "stop waiting for this one".
 *
 * Known limits (also stated in the changelog): a confirmation that arrives after the phone has given up can mean the
 * message plays on both the phone and the watch, which is better than silence. A watch app that has not been updated never
 * confirms, so every message sent while ACK WATCH is selected waits out the timeout and then plays on the phone.
 */
object WatchRelayProtocol {
    const val CHUNK_PATH = "/audio/relay_chunk"
    const val ACK_PATH = "/sys/audio_relay_ack"
    const val CANCEL_PATH = "/audio/relay_cancel"

    // header = transferId (Int) + sampleRate (Int) + chunkIndex (Short) + totalChunks (Short), all little-endian.
    const val HEADER_BYTES = 12

    // Comfortably under MessageClient's ~100 KB payload cap even after the header, and even so a chunk boundary
    // never splits a 16-bit sample across two messages.
    const val CHUNK_PAYLOAD_BYTES = 80_000

    private const val TRANSFER_ID_BYTES = 4

    /** How many chunks [pcmByteCount] bytes of audio travel in. Never less than one. */
    fun chunkCount(pcmByteCount: Int): Int =
        ((pcmByteCount.toLong() + CHUNK_PAYLOAD_BYTES - 1) / CHUNK_PAYLOAD_BYTES).toInt().coerceAtLeast(1)

    fun encodeChunkHeader(transferId: Int, sampleRate: Int, chunkIndex: Int, totalChunks: Int): ByteArray =
        ByteBuffer.allocate(HEADER_BYTES)
            .order(ByteOrder.LITTLE_ENDIAN)
            .putInt(transferId)
            .putInt(sampleRate)
            .putShort(chunkIndex.toShort())
            .putShort(totalChunks.toShort())
            .array()

    fun encodeTransferId(transferId: Int): ByteArray =
        ByteBuffer.allocate(TRANSFER_ID_BYTES).order(ByteOrder.LITTLE_ENDIAN).putInt(transferId).array()

    /** The transfer id in an ack or cancel payload, or null unless the payload is exactly 4 bytes. */
    fun decodeTransferId(payload: ByteArray): Int? =
        if (payload.size != TRANSFER_ID_BYTES) null
        else ByteBuffer.wrap(payload).order(ByteOrder.LITTLE_ENDIAN).int
}
