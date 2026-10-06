// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.File
import java.io.IOException
import java.nio.file.Files

class VerifiedFileReplaceTest {
    private lateinit var dir: File

    @Before
    fun setUp() { dir = Files.createTempDirectory("ack-replace-test").toFile() }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private val good = "GIF89a-the-good-one".toByteArray()
    private val replacement = "GIF89a-the-new-one-from-the-backup".toByteArray()
    private val junk = ByteArray(300) { (it * 7).toByte() }

    private fun names(): List<String> = dir.list()!!.sorted()

    private fun startsWithGif(f: File): Boolean = f.readBytes().decodeToString().startsWith("GIF8")

    // --- the promise: a refused picture never touches the file that is already there ----------------------------------------

    @Test
    fun refusedBytesLeaveAnExistingFileExactlyAsItWas() {
        val target = File(dir, "GIF_1.gif").also { it.writeBytes(good) }
        val modified = target.lastModified()

        val replaced = VerifiedFileReplace.replaceIfValid(target, junk, ::startsWithGif)

        assertFalse(replaced)
        assertArrayEquals(good, target.readBytes())
        assertEquals(modified, target.lastModified())
        assertEquals("no scratch file is left", listOf("GIF_1.gif"), names())
    }

    @Test
    fun refusedBytesForAFileThatIsNotThereLeaveNothing() {
        val target = File(dir, "GIF_2.gif")

        assertFalse(VerifiedFileReplace.replaceIfValid(target, junk, ::startsWithGif))

        assertFalse(target.exists())
        assertEquals(emptyList<String>(), names())
    }

    @Test
    fun acceptedBytesReplaceAnExistingFileCompletely() {
        val target = File(dir, "GIF_3.gif").also { it.writeBytes(ByteArray(5_000) { 1 }) }

        assertTrue(VerifiedFileReplace.replaceIfValid(target, replacement, ::startsWithGif))

        assertArrayEquals("exactly the new bytes, none of the old tail", replacement, target.readBytes())
        assertEquals(listOf("GIF_3.gif"), names())
    }

    @Test
    fun acceptedBytesCreateAFileThatWasNotThere() {
        val target = File(dir, "GIF_4.gif")

        assertTrue(VerifiedFileReplace.replaceIfValid(target, replacement, ::startsWithGif))

        assertArrayEquals(replacement, target.readBytes())
        assertEquals(listOf("GIF_4.gif"), names())
    }

    // --- what the check is shown ---------------------------------------------------------------------------------------------

    @Test
    fun theCheckSeesTheNewBytesInAScratchFileWhileTheTargetStillHoldsTheOldOnes() {
        val target = File(dir, "GIF_5.gif").also { it.writeBytes(good) }
        var seen: File? = null
        var seenBytes: ByteArray? = null
        var targetDuringCheck: ByteArray? = null

        VerifiedFileReplace.replaceIfValid(target, replacement) { staged ->
            seen = staged
            seenBytes = staged.readBytes()
            targetDuringCheck = target.readBytes()
            true
        }

        assertEquals("GIF_5.gif.restoring", seen!!.name)
        assertEquals(dir, seen!!.parentFile)
        assertFalse("the scratch name must not end in .gif", seen!!.name.endsWith(".gif"))
        assertArrayEquals(replacement, seenBytes)
        assertArrayEquals(good, targetDuringCheck)
    }

    // --- failures --------------------------------------------------------------------------------------------------------------

    @Test
    fun aCheckThatThrowsLeavesTheTargetAndRethrowsTheSameException() {
        val target = File(dir, "GIF_6.gif").also { it.writeBytes(good) }
        val boom = IllegalStateException("check blew up")

        try {
            VerifiedFileReplace.replaceIfValid(target, replacement) { throw boom }
            fail("expected the exception")
        } catch (e: IllegalStateException) {
            assertSame(boom, e)
        }

        assertArrayEquals(good, target.readBytes())
        assertEquals(listOf("GIF_6.gif"), names())
    }

    @Test
    fun aRefusedMoveLeavesTheTargetAloneAndCleansUp() {
        // A non-empty folder where the file should go: the move cannot succeed, whatever the platform.
        val target = File(dir, "GIF_7.gif").also { it.mkdir(); File(it, "keep.txt").writeText("keep") }

        try {
            VerifiedFileReplace.replaceIfValid(target, replacement) { true }
            fail("expected the move to fail")
        } catch (e: IOException) {
            // expected: java.nio.file.FileSystemException is an IOException
        }

        assertTrue(target.isDirectory)
        assertEquals("keep", File(target, "keep.txt").readText())
        assertEquals("the scratch file was removed", listOf("GIF_7.gif"), names())
    }

    @Test
    fun aScratchFileLeftByACrashIsOverwrittenNotAppendedTo() {
        val target = File(dir, "GIF_8.gif").also { it.writeBytes(good) }
        VerifiedFileReplace.stagingFileFor(target).writeBytes(ByteArray(10_000) { 9 })

        assertTrue(VerifiedFileReplace.replaceIfValid(target, replacement, ::startsWithGif))

        assertArrayEquals(replacement, target.readBytes())
        assertEquals(listOf("GIF_8.gif"), names())
    }

    @Test
    fun aStaleScratchFileIsAlsoCleanedWhenTheNewBytesAreRefused() {
        val target = File(dir, "GIF_9.gif").also { it.writeBytes(good) }
        VerifiedFileReplace.stagingFileFor(target).writeBytes(ByteArray(10) { 9 })

        assertFalse(VerifiedFileReplace.replaceIfValid(target, junk, ::startsWithGif))

        assertArrayEquals(good, target.readBytes())
        assertEquals(listOf("GIF_9.gif"), names())
    }

    @Test
    fun otherFilesInTheFolderAreNeverTouched() {
        val neighbour = File(dir, "GIF_other.gif").also { it.writeBytes(good) }
        val target = File(dir, "GIF_10.gif")

        VerifiedFileReplace.replaceIfValid(target, junk, ::startsWithGif)
        VerifiedFileReplace.replaceIfValid(target, replacement, ::startsWithGif)

        assertArrayEquals(good, neighbour.readBytes())
        assertEquals(listOf("GIF_10.gif", "GIF_other.gif"), names())
    }

    @Test
    fun theHelperNeverOpensOrDeletesTheTargetItselfAndMovesInOneStep() {
        // Running it cannot show a delete-then-move (a crash between the two would lose the file), so read the source.
        val body = RepoFiles.declarationOf(RepoFiles.read("app/src/main/java/com/example/besu/core/VerifiedFileReplace.kt"), "replaceIfValid")
        for (forbidden in listOf("target.delete", "target.outputStream", "target.writeBytes", "target.writeText", "target.appendBytes", "target.renameTo")) {
            assertFalse("replaceIfValid must not use \"$forbidden\"", body.contains(forbidden))
        }
        assertTrue("the only delete is of the scratch file", Regex("(\\w+)\\.delete\\(\\)").findAll(body).all { it.groupValues[1] == "staging" })
        assertTrue(body.contains("StandardCopyOption.ATOMIC_MOVE"))
        assertFalse("a move that can copy-then-delete is not one step", body.contains("REPLACE_EXISTING"))
        // The check runs on the scratch file, before the move.
        assertTrue(body.indexOf("isValid(staging)") in 0 until body.indexOf("Files.move("))
    }

    @Test
    fun theScratchNameIsTheTargetNamePlusTheSuffixInTheSameFolder() {
        val staged = VerifiedFileReplace.stagingFileFor(File(dir, "GIF_x.gif"))
        assertEquals(File(dir, "GIF_x.gif.restoring"), staged)
        assertEquals(".restoring", VerifiedFileReplace.STAGING_SUFFIX)
    }
}
