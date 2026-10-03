// SPDX-License-Identifier: GPL-3.0-or-later
package android.media
object AudioFormat { const val CHANNEL_IN_MONO = 16; const val ENCODING_PCM_16BIT = 2 }
object MediaRecorder { object AudioSource { const val UNPROCESSED = 9; const val VOICE_RECOGNITION = 6 } }
class AudioRecord(source: Int, rate: Int, channels: Int, format: Int, bufferBytes: Int) {
    val state: Int get() = STATE_INITIALIZED
    fun startRecording() {}
    fun stop() {}
    fun release() {}
    fun read(buf: ShortArray, offset: Int, size: Int): Int = 0
    companion object {
        const val STATE_INITIALIZED = 1
        fun getMinBufferSize(rate: Int, channels: Int, format: Int): Int = 0
    }
}
