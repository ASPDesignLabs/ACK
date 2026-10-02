// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.RandomAccessFile

/** What a WAV file's header says, checked against how long the file really is. */
data class WavInfo(val sampleRate: Int, val frames: Long, val dataOffset: Int) {
    val seconds: Double get() = frames.toDouble() / sampleRate
}

/** A WAV file that can't be used, with a message a person can act on. */
class WavException(message: String) : Exception(message)

// 16-bit mono PCM WAV with the standard 44-byte header, which is all this feature ever writes (format document, section 3).
// Nothing here touches android.*, so the unit tests run it on an ordinary JVM.
object WavFile {
    const val HEADER_BYTES = 44
    const val MIN_RATE = 16_000
    const val MAX_RATE = 96_000

    private fun putLe32(b: ByteArray, at: Int, v: Long) {
        for (i in 0 until 4) b[at + i] = ((v shr (8 * i)) and 0xff).toByte()
    }

    private fun putLe16(b: ByteArray, at: Int, v: Int) {
        b[at] = (v and 0xff).toByte()
        b[at + 1] = ((v shr 8) and 0xff).toByte()
    }

    private fun le32(b: ByteArray, at: Int): Long {
        var v = 0L
        for (i in 0 until 4) v = v or ((b[at + i].toLong() and 0xff) shl (8 * i))
        return v
    }

    private fun le16(b: ByteArray, at: Int): Int = (b[at].toInt() and 0xff) or ((b[at + 1].toInt() and 0xff) shl 8)

    /** The standard header for [dataBytes] bytes of 16-bit mono audio at [rate]. */
    fun header(rate: Int, dataBytes: Long): ByteArray {
        require(dataBytes in 0..0xffff_ffdbL) { "audio length out of range: $dataBytes" }
        val h = ByteArray(HEADER_BYTES)
        "RIFF".toByteArray(Charsets.US_ASCII).copyInto(h, 0)
        putLe32(h, 4, 36 + dataBytes)
        "WAVEfmt ".toByteArray(Charsets.US_ASCII).copyInto(h, 8)
        putLe32(h, 16, 16)
        putLe16(h, 20, 1)                       // PCM
        putLe16(h, 22, 1)                       // mono
        putLe32(h, 24, rate.toLong())
        putLe32(h, 28, rate.toLong() * 2)       // bytes per second
        putLe16(h, 32, 2)                       // bytes per frame
        putLe16(h, 34, 16)                      // bits
        "data".toByteArray(Charsets.US_ASCII).copyInto(h, 36)
        putLe32(h, 40, dataBytes)
        return h
    }

    /** Checks a header against the format and against the file's real length, exactly as Freeform Studio's reader does. */
    fun inspect(head: ByteArray, total: Long, name: String): WavInfo {
        if (head.size < HEADER_BYTES || String(head, 0, 4, Charsets.US_ASCII) != "RIFF" || String(head, 8, 4, Charsets.US_ASCII) != "WAVE") {
            throw WavException("$name is not a WAV file.")
        }
        val riffSize = le32(head, 4)
        var pos = 12
        var fmt: IntArray? = null
        var dataAt = -1
        var dataSize = 0L
        while (pos + 8 <= head.size) {
            val id = String(head, pos, 4, Charsets.US_ASCII)
            val size = le32(head, pos + 4)
            if (id == "fmt ") {
                if (size < 16 || pos + 24 > head.size) throw WavException("$name: its audio format block is damaged.")
                fmt = intArrayOf(le16(head, pos + 8), le16(head, pos + 10), le32(head, pos + 12).toInt(), le16(head, pos + 22))
            } else if (id == "data") {
                dataAt = pos + 8
                dataSize = size
                break
            }
            pos += (8 + size + (size and 1)).toInt()
        }
        if (fmt == null || dataAt < 0) throw WavException("$name has no readable audio data (the recording may have been interrupted).")
        val (tag, channels, rate, bits) = fmt.let { listOf(it[0], it[1], it[2], it[3]) }
        if (tag != 1 || channels != 1 || bits != 16) {
            throw WavException("$name should be plain 16-bit mono audio, but this is format $tag, $channels channel(s), $bits-bit.")
        }
        if (rate < MIN_RATE || rate > MAX_RATE) throw WavException("$name: its sample rate ($rate Hz) is outside $MIN_RATE to $MAX_RATE.")
        val dataEndOk = dataAt + dataSize == total || dataAt + dataSize + (dataSize and 1) == total
        val riffOk = riffSize + 8 == total || riffSize + 9 == total
        if (!(dataEndOk && riffOk)) {
            throw WavException("$name: its header says the audio is $dataSize bytes, but the file holds ${total - dataAt}. " +
                "A recording that was interrupted looks like this; it needs repairing before it can be packaged.")
        }
        if (dataSize % 2L != 0L) throw WavException("$name: the audio length is not a whole number of samples.")
        return WavInfo(rate, dataSize / 2, dataAt)
    }

    fun inspect(file: File): WavInfo {
        if (!file.isFile) throw WavException("${file.name} is missing.")
        val total = file.length()
        val head = ByteArray(minOf(total, 4096L).toInt())
        RandomAccessFile(file, "r").use { it.readFully(head) }
        return inspect(head, total, file.name)
    }

    /**
     * Makes a recording that was cut off (the app was closed, the battery died) usable again: the header's lengths are set to what
     * the file really holds, and a stray odd byte at the end is dropped. Only for files this app wrote, with the standard header.
     * Returns the repaired file's info; throws if the file is not a recording this app could have written.
     */
    fun repair(file: File): WavInfo {
        if (!file.isFile) throw WavException("${file.name} is missing.")
        val total = file.length()
        if (total < HEADER_BYTES) throw WavException("${file.name} is too short to hold a recording.")
        RandomAccessFile(file, "rw").use { raf ->
            val head = ByteArray(HEADER_BYTES)
            raf.readFully(head)
            val standard = String(head, 0, 4, Charsets.US_ASCII) == "RIFF" && String(head, 8, 8, Charsets.US_ASCII) == "WAVEfmt " &&
                String(head, 36, 4, Charsets.US_ASCII) == "data" && le32(head, 16) == 16L && le16(head, 20) == 1 && le16(head, 22) == 1 &&
                le16(head, 34) == 16
            val rate = le32(head, 24)
            if (!standard || rate < MIN_RATE || rate > MAX_RATE) throw WavException("${file.name} is not a recording this app wrote, so it was left alone.")
            val data = (total - HEADER_BYTES) and 1L.inv()
            if (data != total - HEADER_BYTES) raf.setLength(HEADER_BYTES + data)
            raf.seek(0)
            raf.write(header(rate.toInt(), data))
            raf.fd.sync()
        }
        return inspect(file)
    }
}

/**
 * Writes a recording straight to disk as it arrives, so a long recording never has to fit in memory. The header is written first
 * with a length of zero and fixed up by [close] (and by [checkpoint], which the recorder calls now and then), so a crash leaves a file
 * that [WavFile.repair] can make whole.
 */
class WavStreamWriter(val file: File, val sampleRate: Int) : AutoCloseable {
    private val raf = RandomAccessFile(file, "rw")
    private var bytes = 0L
    private var scratch = ByteArray(0)
    private var closed = false

    init {
        require(sampleRate in WavFile.MIN_RATE..WavFile.MAX_RATE) { "sample rate out of range: $sampleRate" }
        raf.setLength(0)
        raf.write(WavFile.header(sampleRate, 0))
    }

    val framesWritten: Long get() = bytes / 2

    fun write(samples: ShortArray, offset: Int = 0, count: Int = samples.size - offset) {
        check(!closed) { "already closed" }
        if (count <= 0) return
        if (scratch.size < count * 2) scratch = ByteArray(count * 2)
        for (i in 0 until count) {
            val v = samples[offset + i].toInt()
            scratch[2 * i] = (v and 0xff).toByte()
            scratch[2 * i + 1] = ((v shr 8) and 0xff).toByte()
        }
        raf.write(scratch, 0, count * 2)
        bytes += count * 2L
    }

    /** Fixes the header's lengths for what has been written so far and asks the system to put it on disk. */
    fun checkpoint() {
        check(!closed) { "already closed" }
        val end = raf.filePointer
        raf.seek(0)
        raf.write(WavFile.header(sampleRate, bytes))
        raf.seek(end)
        raf.fd.sync()
    }

    override fun close() {
        if (closed) return
        try {
            raf.seek(0)
            raf.write(WavFile.header(sampleRate, bytes))
            raf.fd.sync()
        } finally {
            closed = true
            raf.close()
        }
    }
}
