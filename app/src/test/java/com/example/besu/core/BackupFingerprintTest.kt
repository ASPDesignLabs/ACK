// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BackupFingerprintTest {
    private fun fp(json: String) = BackupFingerprint.fingerprint(json)

    // --- the algorithm is pinned to values computed independently (Python hashlib) ---

    @Test
    fun anEmptyObjectHasTheKnownHash() {
        assertEquals("44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a", fp("{}"))
    }

    @Test
    fun theCanonicalFormIsCompactSortedUtf8() {
        assertEquals("8baa73198470c7bb4c3ce142a8fd651affc0310d878bb9bd159e37a573fb4874", fp("""{ "b": [1, 2],  "a": 1 }"""))
    }

    @Test
    fun unicodeSurvivesAndIsHashedAsUtf8() {
        assertEquals("56805bf23c53dd8d42920e4525cc4263377496ef37dfcb3bbb6d0fb116094cc8", fp("""{"p":"café ❤"}"""))
        // A composed and a decomposed e are different text, so they must be different fingerprints.
        assertNotEquals(fp("""{"p":"café"}"""), fp("""{"p":"café"}"""))
    }

    @Test
    fun theResultIsLowerCaseHexOfTheRightLength() {
        val h = fp("""{"x":1}""")
        assertEquals(64, h.length)
        assertTrue(h.all { it in '0'..'9' || it in 'a'..'f' })
    }

    // --- order and whitespace ---

    @Test
    fun theSameDataInADifferentKeyOrderGivesTheSameResult() {
        // matrixData comes from SharedPreferences.getAll(), whose order is not guaranteed.
        val a = """{"matrixData":{"deck1/a":"hello","deck1/b":"bye","DEFAULT/c":"x"},"quickPhrases":[1,2]}"""
        val b = """{"quickPhrases":[1,2],"matrixData":{"DEFAULT/c":"x","deck1/b":"bye","deck1/a":"hello"}}"""
        assertEquals(fp(a), fp(b))
    }

    @Test
    fun keysAreSortedAtEveryDepth() {
        assertEquals(fp("""{"a":{"y":1,"x":{"q":1,"p":2}}}"""), fp("""{"a":{"x":{"p":2,"q":1},"y":1}}"""))
    }

    @Test
    fun whitespaceDoesNotMatter() {
        assertEquals(fp("""{"a":1,"b":"x y"}"""), fp("{\n  \"a\": 1,\n  \"b\": \"x y\"\n}"))
        // ...but whitespace inside a text value is data.
        assertNotEquals(fp("""{"b":"x y"}"""), fp("""{"b":"x  y"}"""))
    }

    @Test
    fun arrayOrderMatters() {
        assertNotEquals(fp("""{"decks":["a","b"]}"""), fp("""{"decks":["b","a"]}"""))
        assertNotEquals(fp("""{"o":[{"k":1},{"k":2}]}"""), fp("""{"o":[{"k":2},{"k":1}]}"""))
    }

    // --- what is ignored: things that change all the time without the person adding anything ---

    @Test
    fun eachIgnoredFieldChangingLeavesTheResultUnchanged() {
        val base = """{"phrase":"hello","timestamp":1,"activeDeckId":"A","activeDeckColorIndex":1,"activeProfile":"P","activeCategoryFocus":"IDENTITY","autocompleteHistory":{"k":1},"rootOverrideCollapsed":{"IDENTITY":true}}"""
        val reference = fp(base)
        assertEquals(BackupFingerprint.IGNORED_FIELDS.size, 7)
        for (field in BackupFingerprint.IGNORED_FIELDS) {
            val changed = changeTopLevelValue(base, field)
            assertNotEquals("the test must really change $field", base, changed)
            assertEquals("$field must be ignored", reference, fp(changed))
        }
    }

    @Test
    fun anIgnoredFieldBeingAbsentOrPresentIsTheSame() {
        assertEquals(fp("""{"phrase":"hello"}"""), fp("""{"phrase":"hello","timestamp":99,"autocompleteHistory":{}}"""))
    }

    @Test
    fun theSameNameNestedInsideSomethingElseStillCounts() {
        // Only TOP-LEVEL fields are ignored: a deck or recording with a "timestamp" of its own is real data.
        assertNotEquals(fp("""{"decks":[{"timestamp":1}]}"""), fp("""{"decks":[{"timestamp":2}]}"""))
        assertNotEquals(fp("""{"x":{"activeDeckId":"A"}}"""), fp("""{"x":{"activeDeckId":"B"}}"""))
    }

    // --- what is not ignored: real changes ---

    @Test
    fun changingOnePhraseChangesIt() {
        assertNotEquals(fp("""{"matrixData":{"k":"hello"}}"""), fp("""{"matrixData":{"k":"hello!"}}"""))
    }

    @Test
    fun addingADeckChangesIt() {
        assertNotEquals(fp("""{"decks":[{"id":"1"}]}"""), fp("""{"decks":[{"id":"1"},{"id":"2"}]}"""))
    }

    @Test
    fun changingARecordingsMetadataChangesIt() {
        val a = """{"voiceRecordings":[{"recording":{"id":"r1","durationMs":1200,"createdAt":5},"sampleRate":0,"audioBase64":""}]}"""
        val b = """{"voiceRecordings":[{"recording":{"id":"r1","durationMs":1300,"createdAt":5},"sampleRate":0,"audioBase64":""}]}"""
        assertNotEquals(fp(a), fp(b))
    }

    @Test
    fun addingOrRemovingAnEntryChangesIt() {
        assertNotEquals(fp("""{"targets":[]}"""), fp("""{"targets":[{"index":0}]}"""))
        assertNotEquals(fp("""{"a":1}"""), fp("""{"a":1,"b":null}"""))
    }

    @Test
    fun aValueThatIsTextIsNotTheSameAsTheNumber() {
        assertNotEquals(fp("""{"n":1}"""), fp("""{"n":"1"}"""))
        assertNotEquals(fp("""{"b":true}"""), fp("""{"b":"true"}"""))
    }

    // --- bad input ---

    @Test(expected = IllegalArgumentException::class)
    fun aBackupThatIsNotAnObjectIsRefused() {
        fp("[1,2,3]")
    }

    @Test(expected = Exception::class)
    fun textThatIsNotJsonIsRefused() {
        fp("not json")
    }

    // Replaces a top-level field's value (a string, number, object or boolean) with a different one.
    private fun changeTopLevelValue(json: String, field: String): String {
        val key = "\"$field\":"
        val start = json.indexOf(key) + key.length
        require(start >= key.length) { "$field not in the sample" }
        val end = when (json[start]) {
            '{' -> json.indexOf('}', start) + 1
            '"' -> json.indexOf('"', start + 1) + 1
            else -> start + json.substring(start).takeWhile { it != ',' && it != '}' }.length
        }
        val replacement = when (json[start]) {
            '{' -> """{"changed":true}"""
            '"' -> "\"CHANGED\""
            else -> "424242"
        }
        return json.substring(0, start) + replacement + json.substring(end)
    }
}
