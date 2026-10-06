// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.util.Locale
import java.util.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * SAVE MESSAGE LOG TO A FILE (core/LogExport.kt): which log lines are messages, in what order they are written, how a message is made safe for a line of
 * tab-separated text, and exactly what the file looks like, in every language and on a phone set to any language or time zone.
 */
class LogExportTest {

    private fun millis(iso: String) = Instant.parse(iso).toEpochMilli()
    private fun line(ms: Long, type: String, msg: String, replay: String?) = LogLine(ms, type, msg, replay)
    private fun out(ms: Long, source: String, text: String) = line(ms, "OUT", "$source > \"$text\"", text)

    // ---- which lines are messages ----------------------------------------------------------------------------------------------------

    @Test
    fun anOutOrEmergencyLineWithReplayTextIsAMessage() {
        assertTrue(LogExport.isMessage(line(1, "OUT", "MTX/IDENTITY > \"Hello.\"", "Hello.")))
        assertTrue(LogExport.isMessage(line(1, "EMERGENCY", "EMERGENCY > \"Help.\"", "Help.")))
    }

    @Test
    fun anOutLineWithNoReplayText_isNotAMessage_becauseOnlyARealCommunicatedPhraseHasIt() {
        assertFalse(LogExport.isMessage(line(1, "OUT", "HELP/intro > \"narration\"", null)))
        assertFalse(LogExport.isMessage(line(1, "EMERGENCY", "x", null)))
    }

    @Test
    fun noOtherKindOfLineIsEverAMessage_evenIfItCarriesReplayText() {
        for (type in listOf("SYS", "CMD", "CMD_WARN", "CMD_ERR", "PATH", "GEO", "WATCH", "out", "Out", "EMERGENCY ", "", "OUTX")) {
            assertFalse("'$type'", LogExport.isMessage(line(1, type, "m", "text")))
        }
    }

    // ---- where it was sent from ---------------------------------------------------------------------------------------------------------

    @Test
    fun theSourceIsTheTagTheLogWroteBeforeTheMessage() {
        assertEquals("MTX/IDENTITY", LogExport.fromOf("MTX/IDENTITY > \"Hello.\""))
        assertEquals("QUICK_ACTION", LogExport.fromOf("QUICK_ACTION > \"Yes.\""))
        assertEquals("HW/WATCH", LogExport.fromOf("HW/WATCH > \"Stop.\""))
        assertEquals("EMERGENCY", LogExport.fromOf("EMERGENCY > \"Help.\""))
    }

    @Test
    fun aLineTypedAtTheTerminalPromptIsFromTheTerminal_withTheModifiersItCarried() {
        assertEquals("TERMINAL", LogExport.fromOf("$ hello"))
        assertEquals("TERMINAL [Q]", LogExport.fromOf("$ [Q] hello"))
        assertEquals("TERMINAL [Q][S]", LogExport.fromOf("$ [Q][S] hello"))
        assertEquals("TERMINAL [E]", LogExport.fromOf("$ [E] help"))
    }

    @Test
    fun aLineThatIsNotInEitherShapeIsFromUnknown_andNeverCrashes() {
        assertEquals("UNKNOWN", LogExport.fromOf(""))
        assertEquals("UNKNOWN", LogExport.fromOf("no source here"))
        assertEquals("UNKNOWN", LogExport.fromOf(" > \"starts with the separator\""))
        assertEquals("UNKNOWN", LogExport.fromOf("\$5 is not the prompt"))
    }

    @Test
    fun theSourceEndsAtTheFirstSeparator_evenIfTheMessageHasAnother() {
        assertEquals("MTX/A", LogExport.fromOf("MTX/A > \"say > \"quoted\" please\""))
    }

    // ---- which messages, in what order ------------------------------------------------------------------------------------------------------

    @Test
    fun theMessagesComeOutOldestFirst_fromTheTerminalsNewestFirstOrder() {
        val newestFirst = listOf(out(300, "B", "third"), out(200, "B", "second"), out(100, "B", "first"))
        assertEquals(listOf("first", "second", "third"), LogExport.messages(newestFirst).map { it.text })
    }

    @Test
    fun messagesWithTheSameTimeKeepTheOrderTheyWereWritten() {
        // The Terminal keeps the newest first, so the one written last is first in the list.
        val newestFirst = listOf(out(100, "B", "written third"), out(100, "B", "written second"), out(100, "B", "written first"))
        assertEquals(listOf("written first", "written second", "written third"), LogExport.messages(newestFirst).map { it.text })
    }

    @Test
    fun onlyMessagesAreKept_andTheWordsComeFromTheReplayTextNeverFromTheLogLine() {
        val lines = listOf(
            line(500, "CMD", "BACKUP EXPORTED", null),
            line(400, "SYS", "geofence entered", "never"),
            out(300, "MTX/X", "kept 1"),
            line(200, "OUT", "MTX/X > \"line text differs\"", "replay text wins"),
            line(100, "CMD_ERR", "x", null),
        )
        assertEquals(listOf("replay text wins", "kept 1"), LogExport.messages(lines).map { it.text })
    }

    @Test
    fun aMessageOlderThanTheRetentionWindowIsLeftOut_andOneExactlyOnTheEdgeIsKept() {
        val now = millis("2026-10-06T12:00:00Z")
        val cutoff = LogExport.keptSince(now, 7)
        assertEquals(now - 7L * 24 * 60 * 60 * 1000, cutoff)
        val lines = listOf(out(cutoff + 1, "B", "one ms inside"), out(cutoff, "B", "exactly on the edge"), out(cutoff - 1, "B", "one ms outside"))
        assertEquals(listOf("exactly on the edge", "one ms inside"), LogExport.messages(lines, cutoff).map { it.text })
    }

    @Test
    fun withoutACutoffEveryMessageIsKept_andAnEmptyLogGivesNone() {
        assertEquals(2, LogExport.messages(listOf(out(Long.MIN_VALUE + 5, "B", "ancient"), out(5, "B", "now"))).size)
        assertEquals(emptyList<LoggedMessage>(), LogExport.messages(emptyList()))
    }

    @Test
    fun theTypeAndSourceAreCarriedForEachMessage() {
        val m = LogExport.messages(listOf(line(1, "EMERGENCY", "EMERGENCY > \"Help.\"", "Help."))).single()
        assertEquals(LoggedMessage(1, "EMERGENCY", "EMERGENCY", "Help."), m)
    }

    // ---- making a field safe -------------------------------------------------------------------------------------------------------------

    @Test
    fun aLineBreakOfAnyKindBecomesTheTwoCharactersBackslashN_andACrLfIsOne() {
        assertEquals("a\\nb", LogExport.escape("a\nb"))
        assertEquals("a\\nb", LogExport.escape("a\r\nb"))
        assertEquals("a\\nb", LogExport.escape("a\rb"))
        assertEquals("a\\nb", LogExport.escape("a\u0085b"))
        assertEquals("a\\nb", LogExport.escape("a b"))
        assertEquals("a\\nb", LogExport.escape("a b"))
        assertEquals("\\n\\n", LogExport.escape("\n\n"))
        assertEquals("\\n\\n", LogExport.escape("\r\n\r\n"))
    }

    @Test
    fun aTabAndABackslashAreEscaped_soTheColumnsAndTheEscapesCannotBeConfused() {
        assertEquals("a\\tb", LogExport.escape("a\tb"))
        assertEquals("a\\\\b", LogExport.escape("a\\b"))
        // A message that really contains a backslash and an n is not a line break.
        assertEquals("a\\\\nb", LogExport.escape("a\\nb"))
    }

    @Test
    fun anyOtherControlCharacterIsWrittenAsItsFourDigitCode() {
        assertEquals("\\u0001", LogExport.escape("\u0001"))
        assertEquals("\\u000b", LogExport.escape("\u000b"))
        assertEquals("\\u000c", LogExport.escape("\u000c"))
        assertEquals("\\u001f", LogExport.escape("\u001f"))
        assertEquals("\\u007f", LogExport.escape("\u007f"))
        assertEquals("\\u0000", LogExport.escape("\u0000"))
    }

    @Test
    fun theCharacterJustBesideEachLimitIsLeftAlone() {
        // 0x1f is the last C0 control and is escaped; a space (0x20) is the first printable one and is not. 0x7e is printable, 0x7f is not.
        assertEquals(" ", LogExport.escape(" "))
        assertEquals("~", LogExport.escape("~"))
        assertEquals(" ", LogExport.escape(" "))
        assertEquals("\u0086", LogExport.escape("\u0086")) // NEL is U+0085 only; its neighbours are ordinary
    }

    @Test
    fun everythingElseIsKeptExactly_emojiArabicHindiAndFormatCharacters() {
        for (s in listOf("Hello, world.", "مرحبا بالعالم", "नमस्ते", "I need 100% of $1 and %s", "😀 smile", "👍🏽 ok", "Ça va? ñ ü ß", "quote \" and ' marks", "", " lead and trail ")) {
            assertEquals(s, LogExport.escape(s))
        }
    }

    @Test
    fun aSurrogatePairIsNeverSplit() {
        assertEquals("😀\\n😀", LogExport.escape("😀\n😀"))
    }

    /** Reads an escaped field back (test only), to show the escaping loses nothing except that every kind of line break reads back as one line feed. */
    private fun unescape(s: String): String {
        val out = StringBuilder()
        var i = 0
        while (i < s.length) {
            val c = s[i]
            if (c != '\\') { out.append(c); i++; continue }
            when (val n = s[i + 1]) {
                'n' -> { out.append('\n'); i += 2 }
                't' -> { out.append('\t'); i += 2 }
                '\\' -> { out.append('\\'); i += 2 }
                'u' -> { out.append(s.substring(i + 2, i + 6).toInt(16).toChar()); i += 6 }
                else -> error("unexpected escape \\$n")
            }
        }
        return out.toString()
    }

    private fun normalised(s: String) = s.replace("\r\n", "\n").replace('\r', '\n').replace('\u0085', '\n').replace(' ', '\n').replace(' ', '\n')

    @Test
    fun randomTextIsAlwaysOneSafeLine_andReadsBackAsItWas() {
        val alphabet = listOf("a", "Z", " ", "\n", "\r", "\r\n", "\t", "\\", "\\n", "\\t", "\\\\", "\u0085", " ", " ", "\u0000", "\u001f", "\u007f", "%", "$", "|", "#", "\"", "'",
            "é", "م", "न", "😀", "‏", "‮", "0", "\\u0041")
        val rnd = Random(20261006)
        repeat(3000) {
            val s = (0 until rnd.nextInt(24)).joinToString("") { alphabet[rnd.nextInt(alphabet.size)] }
            val e = LogExport.escape(s)
            for (bad in listOf('\n', '\r', '\t', '\u0085', ' ', ' ')) assertFalse("escape left a $bad in '$e' (from '$s')", e.contains(bad))
            assertTrue("a control character is left in '$e'", e.none { it < ' ' || it == '\u007f' })
            assertEquals("round trip of '$s'", normalised(s), unescape(e))
        }
    }

    // ---- the file --------------------------------------------------------------------------------------------------------------------------

    private val berlin = ZoneId.of("Europe/Berlin")

    @Test
    fun theFileIsExactlyThisForTwoMessages_inEnglish() {
        val saved = millis("2026-10-06T12:10:02Z")
        val messages = listOf(
            LoggedMessage(millis("2026-10-06T12:03:22Z"), "OUT", "MTX/IDENTITY", "Hello."),
            LoggedMessage(millis("2026-10-06T12:05:00Z"), "EMERGENCY", "EMERGENCY", "I need help."),
        )
        val expected = listOf(
            "# ACK MESSAGE LOG",
            "# SAVED: 2026-10-06 14:10:02 +02:00",
            "# MESSAGES: 2. FIRST: 2026-10-06 14:03:22 +02:00. LAST: 2026-10-06 14:05:00 +02:00.",
            "# THIS FILE IS NOT ENCRYPTED AND HAS NO PASSWORD. IT HOLDS WHAT WAS SAID.",
            "# IN A MESSAGE, \\n MEANS A LINE BREAK, \\t A TAB AND \\\\ A BACKSLASH; ANY OTHER CONTROL CHARACTER IS WRITTEN \\uXXXX. THE FOUR COLUMNS ARE SEPARATED BY TABS.",
            "# DATE AND TIME\tTYPE\tFROM\tMESSAGE",
            "2026-10-06 14:03:22 +02:00\tOUT\tMTX/IDENTITY\tHello.",
            "2026-10-06 14:05:00 +02:00\tEMERGENCY\tEMERGENCY\tI need help.",
        ).joinToString("\n", postfix = "\n")
        assertEquals(expected, LogExport.render(messages, EnglishText, berlin, saved))
    }

    @Test
    fun anEmptyLogGivesOnlyTheHeader_andTheRangeIsADash() {
        val text = LogExport.render(emptyList(), EnglishText, ZoneOffset.UTC, millis("2026-01-01T00:00:00Z"))
        val lines = text.trimEnd('\n').split("\n")
        assertEquals(6, lines.size)
        assertTrue(lines.all { it.startsWith(LogExport.HEADER_MARK) })
        assertEquals("# MESSAGES: 0. FIRST: -. LAST: -.", lines[2])
        assertTrue(text.endsWith("\n"))
    }

    @Test
    fun aMessageCannotForgeARecord_aLineBreakAndATabInItStayOnItsOwnLine() {
        val forged = "yes\n2026-10-06 14:00:00 +02:00\tOUT\tFAKE\tI never said this\t\r\n# a header"
        val text = LogExport.render(
            listOf(LoggedMessage(millis("2026-10-06T12:00:00Z"), "OUT", "MTX/A\nB", forged), LoggedMessage(millis("2026-10-06T12:01:00Z"), "OUT", "B", "ok")),
            EnglishText, berlin, millis("2026-10-06T12:02:00Z")
        )
        val lines = text.trimEnd('\n').split("\n")
        assertEquals("six header lines and one line per message", 6 + 2, lines.size)
        val records = lines.drop(6)
        for (r in records) {
            assertEquals("a record has exactly four columns: '$r'", 4, r.split("\t").size)
            assertTrue(r[0].isDigit())
        }
        assertTrue(records[0].contains("\\n2026-10-06 14:00:00 +02:00\\tOUT\\tFAKE\\tI never said this\\t\\n# a header"))
        assertTrue("the source is escaped too", records[0].contains("\tMTX/A\\nB\t"))
    }

    @Test
    fun everyHeaderLineStartsWithTheMark_andEveryRecordWithADigit_inEveryLanguage() {
        val messages = listOf(LoggedMessage(millis("2026-10-06T12:00:00Z"), "OUT", "MTX/A", "Hello."))
        for (tag in StringsXml.translations().keys) {
            val text = LogExport.render(messages, FileText(tag), berlin, millis("2026-10-06T12:02:00Z"))
            val lines = text.trimEnd('\n').split("\n")
            assertEquals("$tag: six header lines and one record", 7, lines.size)
            assertTrue("$tag: a header line without the mark", lines.take(6).all { it.startsWith("# ") })
            assertTrue("$tag: the record", lines[6].first().isDigit() && lines[6].split("\t").size == 4)
            assertEquals("$tag: the column line has four columns", 4, lines[5].removePrefix("# ").split("\t").size)
            assertFalse("$tag: a resource name leaked", text.contains("log_export_"))
        }
    }

    @Test
    fun theEscapeExplanationKeepsTheTokensItExplainsInEveryLanguage() {
        for (tag in listOf("en") + StringsXml.translations().keys) {
            val explanation = (if (tag == "en") EnglishText else FileText(tag)).get(LogExport.ESCAPES)
            for (token in listOf("\\n", "\\t", "\\\\", "\\uXXXX")) assertTrue("$tag is missing $token in: $explanation", explanation.contains(token))
        }
    }

    @Test
    fun theHeaderIsTranslated_notEnglish_inEveryLanguage() {
        val english = LogExport.render(emptyList(), EnglishText, ZoneOffset.UTC, 0).lines().take(6)
        for (tag in StringsXml.translations().keys) {
            val other = LogExport.render(emptyList(), FileText(tag), ZoneOffset.UTC, 0).lines().take(6)
            assertEquals("$tag", english.size, other.size)
            for (i in english.indices) assertNotEquals("$tag line $i is still English", english[i], other[i])
        }
    }

    @Test
    fun aTranslationWithALineBreakInItCannotStartALineThatIsNotAHeader() {
        val breaking = object : TextSource {
            override fun get(name: String, vararg args: Any) = "first\nsecond\r\nthird fourth"
            override fun count(name: String, quantity: Int) = name
        }
        val text = LogExport.render(emptyList(), breaking, ZoneOffset.UTC, 0)
        assertEquals(6, text.trimEnd('\n').split("\n").size)
        assertTrue(text.trimEnd('\n').split("\n").all { it.startsWith("# ") })
    }

    // ---- times: Latin digits and an explicit offset, whatever the phone ---------------------------------------------------------------

    private fun firstRecord(ms: Long, zone: ZoneId): String =
        LogExport.render(listOf(LoggedMessage(ms, "OUT", "B", "x")), EnglishText, zone, ms).trimEnd('\n').split("\n").last()

    @Test
    fun theOffsetIsWrittenOnEveryLine_includingHalfHourZonesAndUtc() {
        val ms = millis("2026-10-06T12:00:00Z")
        assertEquals("2026-10-06 12:00:00 +00:00\tOUT\tB\tx", firstRecord(ms, ZoneOffset.UTC))
        assertEquals("2026-10-06 17:30:00 +05:30\tOUT\tB\tx", firstRecord(ms, ZoneId.of("Asia/Kolkata")))
        assertEquals("2026-10-06 14:00:00 +02:00\tOUT\tB\tx", firstRecord(ms, berlin))
        assertEquals("2026-10-06 09:30:00 -02:30\tOUT\tB\tx", firstRecord(ms, ZoneId.of("America/St_Johns")))
        assertEquals("2026-10-07 02:00:00 +14:00\tOUT\tB\tx", firstRecord(ms, ZoneId.of("Pacific/Kiritimati")))
    }

    @Test
    fun theTwoSidesOfADaylightSavingChangeAreNotAmbiguous() {
        // Berlin moved its clocks forward at 01:00 UTC on 2026-03-29: 01:59:59 +01:00 is followed by 03:00:00 +02:00.
        assertEquals("2026-03-29 01:59:59 +01:00", firstRecord(millis("2026-03-29T00:59:59Z"), berlin).substringBefore("\t"))
        assertEquals("2026-03-29 03:00:00 +02:00", firstRecord(millis("2026-03-29T01:00:00Z"), berlin).substringBefore("\t"))
        // And back, when one wall-clock hour happens twice: 02:30 +02:00 and then 02:30 +01:00.
        assertEquals("2026-10-25 02:30:00 +02:00", firstRecord(millis("2026-10-25T00:30:00Z"), berlin).substringBefore("\t"))
        assertEquals("2026-10-25 02:30:00 +01:00", firstRecord(millis("2026-10-25T01:30:00Z"), berlin).substringBefore("\t"))
    }

    @Test
    fun midnightAndTheEdgesOfTheYearAndALeapDayAreWrittenCorrectly() {
        assertEquals("2026-12-31 23:59:59 +00:00", firstRecord(millis("2026-12-31T23:59:59Z"), ZoneOffset.UTC).substringBefore("\t"))
        assertEquals("2027-01-01 00:00:00 +00:00", firstRecord(millis("2027-01-01T00:00:00Z"), ZoneOffset.UTC).substringBefore("\t"))
        assertEquals("2028-02-29 12:00:00 +00:00", firstRecord(millis("2028-02-29T12:00:00Z"), ZoneOffset.UTC).substringBefore("\t"))
        assertEquals("1970-01-01 00:00:00 +00:00", firstRecord(0, ZoneOffset.UTC).substringBefore("\t"))
    }

    @Test
    fun aPhoneSetToArabicOrHindiStillWritesLatinDigits_inTheTimesTheCountAndTheFileName() {
        val saved = Locale.getDefault()
        try {
            for (locale in listOf(Locale("ar", "SA"), Locale("ar", "EG"), Locale("hi", "IN"), Locale("fa", "IR"), Locale("bn", "BD"))) {
                Locale.setDefault(locale)
                val ms = millis("2026-10-06T12:03:22Z")
                val text = LogExport.render(listOf(LoggedMessage(ms, "OUT", "B", "x")), EnglishText, berlin, ms)
                assertTrue("$locale: ${text.lines().take(3)}", text.lines().take(3).joinToString().all { it.code < 128 })
                assertTrue("$locale: a record is not Latin digits", text.trimEnd('\n').split("\n").last().startsWith("2026-10-06 14:03:22 +02:00"))
                assertEquals("ack_messages_2026-10-06_140322.txt", LogExport.fileName(ms, berlin))
            }
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun theFileNameIsPlainAndSafe() {
        val name = LogExport.fileName(millis("2026-10-06T12:03:22Z"), berlin)
        assertEquals("ack_messages_2026-10-06_140322.txt", name)
        assertTrue(Regex("""[A-Za-z0-9_.\-]+""").matches(name))
        assertEquals("ack_messages_2026-10-06_120322.txt", LogExport.fileName(millis("2026-10-06T12:03:22Z"), ZoneOffset.UTC))
    }

    // ---- size ----------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theWholeLogAtItsCapIsWrittenInOrder_oneRecordEach() {
        val newestFirst = (400 downTo 1).map { out(1_000_000L + it, "B", "message $it") }
        val messages = LogExport.messages(newestFirst)
        assertEquals(400, messages.size)
        val lines = LogExport.render(messages, EnglishText, ZoneOffset.UTC, 0).trimEnd('\n').split("\n")
        assertEquals(6 + 400, lines.size)
        assertTrue(lines[6].endsWith("message 1"))
        assertTrue(lines.last().endsWith("message 400"))
    }

    @Test
    fun aVeryLongMessageIsWrittenInFullOnOneLine() {
        val long = "word ".repeat(2000).trim() // 9,999 characters, far past any real phrase
        val record = firstRecordText(long)
        assertTrue(record.endsWith(long))
        assertEquals(1, record.lines().size)
    }

    private fun firstRecordText(text: String): String =
        LogExport.render(listOf(LoggedMessage(0, "OUT", "B", text)), EnglishText, ZoneOffset.UTC, 0).trimEnd('\n').split("\n").last()

    @Test
    fun aCountOfWhatWouldBeSavedIsJustTheSizeOfTheMessageList() {
        val lines = listOf(out(1, "B", "a"), line(2, "SYS", "s", null), out(3, "B", "b"))
        assertEquals(2, LogExport.messages(lines).size)
    }
}
