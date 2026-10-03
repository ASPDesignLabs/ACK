// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.wear

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log
import com.google.android.gms.wearable.Wearable
import java.nio.ByteBuffer
import java.nio.ByteOrder

// Receives chunked phrase audio relayed from the phone
// (com.example.besu.watch.WatchAudioRelay, via WearConfigListenerService's
// /audio/relay_chunk path) and plays it back locally once fully
// reassembled. The phone has already applied every effect (gain, Master
// Gain, recording loudness normalization, everything) before sending --
// this only ever plays back finished PCM bytes, no DSP of its own beyond
// scaling by TechSynth's existing WATCH AUDIO FEEDBACK master volume, so
// there's one consistent "how loud is my watch" setting rather than an
// unexplained second one just for relayed phrases.
//
// Only one transfer is tracked at a time -- ACK dispatches one phrase at
// a time in practice, so a new transfer id simply replaces whatever
// incomplete one was still in progress. Chunks are keyed by index rather
// than appended in arrival order, so a transfer still reassembles
// correctly even if MessageClient delivers its chunks out of sequence
// (which it doesn't guarantee against for separate sendMessage calls).
//
// CONFIRMATION: the phone does not play a relayed message itself (it waits
// for this app to say so). The moment playback has really started, play()
// sends /sys/audio_relay_ack, whose payload is the transfer id as 4
// little-endian bytes, back to the phone node the chunks came from. If
// playback fails, nothing is sent, so the phone plays the message itself
// after its timeout. If the phone gives up first it sends /audio/relay_cancel
// (same 4-byte id); cancel() then drops a half-received transfer so it is not
// played late as well. Byte layouts: the phone's core/WatchRelayProtocol.kt,
// which pins them with tests. Update both together, and release the phone
// and watch apps together: a watch app without this never confirms.
object AudioRelay {

    private const val TAG = "ACK_WEAR"

    // Same as WatchRelayProtocol.ACK_PATH on the phone.
    private const val ACK_PATH = "/sys/audio_relay_ack"

    // How many cancelled transfer ids are remembered, so chunks that arrive after their cancel are ignored.
    private const val MAX_REMEMBERED_CANCELS = 8

    // header = transferId (Int) + sampleRate (Int) + chunkIndex (Short) +
    // totalChunks (Short) -- must match WatchAudioRelay's layout exactly.
    private const val HEADER_BYTES = 12

    private class InFlightTransfer(
        val transferId: Int,
        val sampleRate: Int,
        val totalChunks: Int
    ) {
        val chunks = arrayOfNulls<ByteArray>(totalChunks)
        var receivedCount = 0
    }

    private var current: InFlightTransfer? = null

    private val cancelledIds = ArrayDeque<Int>()

    // Called from WearConfigListenerService.onMessageReceived, which runs
    // on the main thread -- this only ever does cheap array bookkeeping
    // itself; the actual AudioTrack playback in play() is handed off to a
    // background thread. sourceNodeId is the phone the chunks came from: the
    // confirmation goes back to it.
    @Synchronized
    fun onChunkReceived(context: Context, sourceNodeId: String, data: ByteArray) {
        if (data.size < HEADER_BYTES) {
            return
        }

        val header = ByteBuffer.wrap(data, 0, HEADER_BYTES).order(ByteOrder.LITTLE_ENDIAN)
        val transferId = header.int
        val sampleRate = header.int
        val chunkIndex = header.short.toInt()
        val totalChunks = header.short.toInt()

        if (totalChunks <= 0 || chunkIndex < 0 || chunkIndex >= totalChunks || sampleRate <= 0) {
            return
        }

        // The phone already gave up on this one and played it itself.
        if (transferId in cancelledIds) {
            return
        }

        var transfer = current
        if (transfer == null || transfer.transferId != transferId) {
            transfer = InFlightTransfer(transferId, sampleRate, totalChunks)
            current = transfer
        }

        if (transfer.chunks[chunkIndex] == null) {
            transfer.chunks[chunkIndex] = data.copyOfRange(HEADER_BYTES, data.size)
            transfer.receivedCount++
        }

        if (transfer.receivedCount == transfer.totalChunks) {
            current = null

            val pcmBytes = ByteArray(transfer.chunks.sumOf { it!!.size })
            var offset = 0
            transfer.chunks.forEach { chunk ->
                chunk!!.copyInto(pcmBytes, offset)
                offset += chunk.size
            }

            val sampleRateForTransfer = transfer.sampleRate
            val completedTransferId = transfer.transferId
            // applicationContext: the listener service that delivered the chunks may be gone by the time playback starts.
            val appContext = context.applicationContext
            Thread {
                play(appContext, sourceNodeId, completedTransferId, pcmBytes, sampleRateForTransfer)
            }.start()
        }
    }

    // The phone gave up waiting for this transfer and is playing the message itself. Drop it if it is still being
    // reassembled, and ignore any of its chunks that arrive later, so it is not played here as well. If playback had
    // already started there is nothing to take back: the message plays on both, which beats silence.
    @Synchronized
    fun cancel(transferId: Int) {
        if (current?.transferId == transferId) {
            current = null
        }
        if (transferId !in cancelledIds) {
            cancelledIds.addLast(transferId)
            while (cancelledIds.size > MAX_REMEMBERED_CANCELS) {
                cancelledIds.removeFirst()
            }
        }
    }

    private fun play(context: Context, sourceNodeId: String, transferId: Int, pcmBytes: ByteArray, sampleRate: Int) {
        if (pcmBytes.size < 2) {
            return
        }

        runCatching {
            val shortBuffer = ByteBuffer.wrap(pcmBytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
            val pcm = ShortArray(shortBuffer.remaining())
            shortBuffer.get(pcm)

            val volume = TechSynth.currentMasterVolume()
            val scaled = ShortArray(pcm.size)
            for (i in pcm.indices) {
                scaled[i] = (pcm[i] * volume)
                    .toInt()
                    .coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                    .toShort()
            }

            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(sampleRate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setBufferSizeInBytes(scaled.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()

            track.write(scaled, 0, scaled.size)
            track.play()

            // Playback has really started (nothing above threw): tell the phone it can stay quiet. If anything
            // above had thrown, nothing would be sent and the phone would play the message itself.
            sendPlayingAck(context, sourceNodeId, transferId)

            // MODE_STATIC playback runs to completion on its own -- wait
            // out its duration on this same background thread, then
            // release, rather than leaving it held indefinitely the way
            // TechSynth's reused streaming track does for short SFX bursts.
            val durationMs = scaled.size.toLong() * 1000L / sampleRate + 200
            Thread.sleep(durationMs)
            runCatching { track.stop() }
            track.release()
        }.onFailure { error ->
            error.printStackTrace()
        }
    }

    // Best effort. A failure here is logged, not fatal: the audio is already playing, and the worst case is the phone
    // also plays the message after its timeout.
    private fun sendPlayingAck(context: Context, sourceNodeId: String, transferId: Int) {
        runCatching {
            val payload = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(transferId).array()
            Wearable.getMessageClient(context)
                .sendMessage(sourceNodeId, ACK_PATH, payload)
                .addOnFailureListener { error -> Log.e(TAG, "playback confirmation was not delivered", error) }
        }.onFailure { error ->
            Log.e(TAG, "could not confirm playback to the phone", error)
        }
    }
}
