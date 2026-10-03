// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Random

// The watch app (a separate module, com.example.besu.wear) builds and reads these same bytes with its own code, so the exact
// layout is pinned here: a change on one side without the other must fail a test, not a watch.
class WatchRelayProtocolTest {
    @Test
    fun thePathsAreExactlyWhatBothSidesAreBuiltAround() {
        assertEquals("/audio/relay_chunk", WatchRelayProtocol.CHUNK_PATH)
        assertEquals("/sys/audio_relay_ack", WatchRelayProtocol.ACK_PATH)
        assertEquals("/audio/relay_cancel", WatchRelayProtocol.CANCEL_PATH)
    }

    @Test
    fun theAckPathIsUnderSys_whichIsWhatThePhonesManifestFilterAlreadyAccepts() {
        assertTrue(WatchRelayProtocol.ACK_PATH.startsWith("/sys"))
    }

    @Test
    fun noRelayPathIsAPrefixOfAnother_soAManifestPathPrefixCannotMatchTheWrongOne() {
        val paths = listOf(WatchRelayProtocol.CHUNK_PATH, WatchRelayProtocol.ACK_PATH, WatchRelayProtocol.CANCEL_PATH)
        for (a in paths) for (b in paths) if (a != b) assertFalse("$a vs $b", a.startsWith(b))
    }

    @Test
    fun chunkCountIsTheNumberOf80000ByteChunksNeeded_andNeverLessThanOne() {
        assertEquals(1, WatchRelayProtocol.chunkCount(0))
        assertEquals(1, WatchRelayProtocol.chunkCount(1))
        assertEquals(1, WatchRelayProtocol.chunkCount(80_000))
        assertEquals(2, WatchRelayProtocol.chunkCount(80_001))
        assertEquals(2, WatchRelayProtocol.chunkCount(160_000))
        assertEquals(3, WatchRelayProtocol.chunkCount(160_001))
    }

    @Test
    fun chunkCountMatchesTheFormulaTheRelayUsedBefore() {
        val random = Random(20261003L)
        repeat(2_000) {
            val size = random.nextInt(2_000_000)
            val old = ((size + 80_000 - 1) / 80_000).coerceAtLeast(1)
            assertEquals("size=$size", old, WatchRelayProtocol.chunkCount(size))
        }
    }

    @Test
    fun aTransferIdIsFourLittleEndianBytes() {
        assertArrayEquals(byteArrayOf(1, 2, 3, 4), WatchRelayProtocol.encodeTransferId(0x04030201))
        assertArrayEquals(byteArrayOf(0, 0, 0, 0), WatchRelayProtocol.encodeTransferId(0))
        assertArrayEquals(byteArrayOf(-1, -1, -1, -1), WatchRelayProtocol.encodeTransferId(-1))
    }

    @Test
    fun aTransferIdRoundTripsIncludingTheExtremes() {
        val random = Random(1L)
        val ids = listOf(0, 1, -1, Int.MAX_VALUE, Int.MIN_VALUE) + List(500) { random.nextInt() }
        for (id in ids) assertEquals(id, WatchRelayProtocol.decodeTransferId(WatchRelayProtocol.encodeTransferId(id)))
    }

    @Test
    fun anAckPayloadThatIsNotExactlyFourBytesIsRejected() {
        for (size in listOf(0, 1, 2, 3, 5, 8, 12)) assertNull("size $size", WatchRelayProtocol.decodeTransferId(ByteArray(size)))
        assertEquals(0, WatchRelayProtocol.decodeTransferId(ByteArray(4)))
    }

    @Test
    fun theChunkHeaderIsTwelveBytes_idThenRateThenIndexThenTotal_allLittleEndian() {
        val header = WatchRelayProtocol.encodeChunkHeader(transferId = 0x04030201, sampleRate = 0x00005622 /* 22050 */, chunkIndex = 2, totalChunks = 5)
        assertEquals(12, WatchRelayProtocol.HEADER_BYTES)
        assertArrayEquals(byteArrayOf(1, 2, 3, 4, 0x22, 0x56, 0, 0, 2, 0, 5, 0), header)
    }
}
