package com.example.besu.wear

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
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
object AudioRelay {

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

    // Called from WearConfigListenerService.onMessageReceived, which runs
    // on the main thread -- this only ever does cheap array bookkeeping
    // itself; the actual AudioTrack playback in play() is handed off to a
    // background thread.
    fun onChunkReceived(data: ByteArray) {
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
            Thread { play(pcmBytes, sampleRateForTransfer) }.start()
        }
    }

    private fun play(pcmBytes: ByteArray, sampleRate: Int) {
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
}
