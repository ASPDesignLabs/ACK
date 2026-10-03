// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertTrue

/**
 * Finds and reads the shared test cases (tools/freeform_studio/tests/data/ack_capture/) and the format document, which live at the
 * top of the repository, above this module. The Python side is held to the very same files, so a rule can't differ between the phone
 * and the PC without a test failing on one of them.
 */
object Vectors {
    private const val DATA_DIR = "tools/freeform_studio/tests/data/ack_capture"

    val root: File by lazy {
        var d: File? = File(System.getProperty("user.dir")).absoluteFile
        while (d != null && !File(d, DATA_DIR).isDirectory) d = d.parentFile
        d ?: error("can't find $DATA_DIR above ${System.getProperty("user.dir")}")
    }

    fun load(name: String): JsonElement = Json.parseToJsonElement(File(root, "$DATA_DIR/$name").readText(Charsets.UTF_8))

    fun formatDocument(): String = File(root, "docs/ACK_TRAINING_CAPTURE_FORMAT.md").readText(Charsets.UTF_8)

    /** Seconds to whole hops, rounding half to even like the reference code's round(). */
    fun hops(seconds: Double): Int = Math.rint(seconds / CaptureConstants.HOP_S).toInt()

    /** `[[seconds, level_dbfs], ...]` to one level per hop. */
    fun levelsFromRuns(runs: JsonArray): DoubleArray {
        val out = ArrayList<Double>()
        for (run in runs) {
            val pair = run.jsonArray
            val n = hops(pair[0].jsonPrimitive.double)
            val db = pair[1].jsonPrimitive.double
            repeat(n) { out.add(db) }
        }
        return out.toDoubleArray()
    }

    /** Exact integer samples: +amp / -amp alternating every [half] samples, restarting for every part (silence when amp is 0). */
    fun square(parts: List<Triple<Double, Int, Int>>, rate: Int): ShortArray {
        val out = ArrayList<Short>()
        for ((seconds, amp, half) in parts) {
            val n = Math.rint(seconds * rate).toInt()
            for (k in 0 until n) {
                val sign = if ((k / half) % 2 == 0) 1 else -1
                out.add((sign * amp).coerceIn(-32768, 32767).toShort())
            }
        }
        return out.toShortArray()
    }

    fun square(parts: JsonArray, rate: Int): ShortArray = square(
        parts.map { p ->
            val o = p.jsonObject
            Triple(o["seconds"]!!.jsonPrimitive.double, o["amp"]!!.jsonPrimitive.double.toInt(), o["half_period"]?.jsonPrimitive?.double?.toInt() ?: 24)
        },
        rate,
    )

    fun JsonObject.d(key: String): Double = this[key]!!.jsonPrimitive.double

    fun JsonObject.s(key: String): String = this[key]!!.jsonPrimitive.content

    fun JsonElement.isNull(): Boolean = this is JsonNull
}

/** Collects every difference in a test, so one run shows all of them rather than just the first. */
class Differences {
    private val list = mutableListOf<String>()
    fun add(case: String, expected: Any?, got: Any?) { list.add("$case\n    expected: $expected\n    got:      $got") }
    fun <T> expect(case: String, expected: T, got: T) { if (expected != got) add(case, expected, got) }
    fun assertNone() {
        assertTrue("${list.size} difference(s):\n" + list.take(6).joinToString("\n") + if (list.size > 6) "\n..." else "", list.isEmpty())
    }
}
