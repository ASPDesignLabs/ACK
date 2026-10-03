// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CaptureConstantsTest {
    @Test
    fun theConstantsAreTheOnesTheDocumentSays() {
        val section = Vectors.formatDocument().substringAfter("## 11. Constants")
        val block = section.substringAfter("```json\n").substringBefore("\n```")
        val fromDocument = Json.parseToJsonElement(block).jsonObject.mapValues { it.value.jsonPrimitive.double }
        assertEquals("names in the document and in CaptureConstants.asMap()", fromDocument.keys, CaptureConstants.asMap().keys)
        val diffs = Differences()
        for ((name, value) in fromDocument) diffs.expect(name, value, CaptureConstants.asMap()[name])
        diffs.assertNone()
    }

    @Test
    fun theWholeHopFormsAreTheLengthsInSeconds() {
        assertEquals(Vectors.hops(CaptureConstants.REGION_MIN_SILENCE_S), CaptureConstants.REGION_MIN_SILENCE_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.REGION_MIN_LEN_S), CaptureConstants.REGION_MIN_LEN_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.CUT_AFTER_S), CaptureConstants.CUT_AFTER_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.FORCE_AT_S), CaptureConstants.FORCE_AT_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.FORCE_WINDOW_S), CaptureConstants.FORCE_WINDOW_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.MIN_SEG_S), CaptureConstants.MIN_SEG_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.PAD_LEAD_S), CaptureConstants.PAD_LEAD_HOPS)
        assertEquals(Vectors.hops(CaptureConstants.PAD_TAIL_S), CaptureConstants.PAD_TAIL_HOPS)
    }

    @Test
    fun theLimitsStayInsideWhatAZipWithoutZip64CanHold() {
        // Format document, section 2: one package stays under 2^31 bytes so no ZIP64 is needed.
        assertTrue(CaptureConstants.MAX_PACKAGE_BYTES < Int.MAX_VALUE.toLong())
        assertTrue(CaptureConstants.MAX_ENTRIES < 65_535)
    }
}
