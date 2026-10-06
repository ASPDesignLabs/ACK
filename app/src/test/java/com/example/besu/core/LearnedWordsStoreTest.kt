// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** The saved word model: atomic saves, a damaged file set aside rather than overwritten, changes made behind its back noticed, forgetting that really forgets. */
class LearnedWordsStoreTest {

    private lateinit var dir: File
    private var now = 1_000L
    private fun store() = LearnedWordsStore(dir) { now }
    private val file get() = File(dir, LearnedWordsStore.FILE_NAME)

    @Before fun setUp() { dir = Files.createTempDirectory("learned_words_test").toFile().resolve(LearnedWordsStore.FOLDER) }
    @After fun tearDown() { dir.parentFile.deleteRecursively() }

    private fun predict(s: LearnedWordsStore, text: String, extra: List<String> = emptyList()) =
        s.predict(extra, text, text.length)

    // ---- learning and predicting ---------------------------------------------------------------------------------------------

    @Test
    fun aStoreWithNothingLearned_suggestsNothing_andWritesNothing() {
        val s = store()
        assertEquals(Prediction.NONE, predict(s, "hel"))
        assertFalse("reading must never create the folder or the file", dir.exists())
        assertNull(s.exportForBackup())
        assertEquals(0, s.wordCount())
    }

    @Test
    fun whatIsLearned_isSuggested_andSurvivesANewStoreOnTheSameFolder() {
        store().learn("I would like tea please")
        val p = predict(store(), "I would like te")
        assertEquals(PredictionKind.COMPLETE, p.kind)
        assertEquals(listOf("tea"), p.suggestions)
    }

    @Test
    fun theNextWordIsOfferedAfterASpace() {
        val s = store()
        s.learn("good morning")
        val p = predict(s, "good ")
        assertEquals(PredictionKind.NEXT, p.kind)
        assertEquals(listOf("morning"), p.suggestions)
    }

    @Test
    fun namesFromElsewhereAreOffered_butNeverCopiedIntoTheSavedWords() {
        val s = store()
        val p = predict(s, "Hello Sa", extra = listOf("Sarah"))
        assertEquals(listOf("Sarah"), p.suggestions)
        assertFalse("extra words must not be learned by being offered", file.exists())
        assertEquals(0, s.wordCount())
    }

    @Test
    fun learningNothing_writesNothing() {
        val s = store()
        s.learn("")
        s.learn("   ")
        s.learn("12345 [COMPUTER:HOME] {VAR:A}")
        assertFalse(dir.exists())
    }

    @Test
    fun learningTextWithNoWordInIt_doesNotRewriteTheFile() {
        val s = store()
        s.learn("alpha beta")
        assertTrue(file.setLastModified(1_000_000L))
        val before = file.readBytes()
        s.learn("")
        s.learn("   \n")
        s.learn("12345 [COMPUTER:HOME] {VAR:A}")
        assertEquals("the file must not be rewritten", 1_000_000L, file.lastModified())
        assertTrue(before.contentEquals(file.readBytes()))
    }

    @Test
    fun aSaveThatCannotWriteItsTemporaryFile_leavesTheOldFileExactlyAsItWas() {
        val s = store()
        s.learn("alpha")
        val saved = file.readBytes()
        // Make the temporary file impossible to create, as a full disk or a permission problem would.
        val temp = File(dir, LearnedWordsStore.TEMP_NAME)
        assertTrue(temp.mkdir())
        s.learn("beta")
        assertTrue("the old file must be untouched, not half-written", saved.contentEquals(file.readBytes()))
        assertEquals("the words are still in memory", setOf("alpha", "beta"), s.exportForBackup()!!.words.map { it.key }.toSet())
        // Once the problem goes away (the failed save cleans up after itself), the next save writes everything.
        temp.delete()
        s.learn("gamma")
        assertEquals(setOf("alpha", "beta", "gamma"), store().exportForBackup()!!.words.map { it.key }.toSet())
    }

    @Test
    fun learningRecordsTheTimeFromTheClock() {
        now = 5_000L
        val s = store()
        s.learn("alpha")
        now = 9_000L
        s.learn("beta")
        val saved = s.exportForBackup()!!
        assertEquals(5_000L, saved.words.first { it.key == "alpha" }.lastUsedAt)
        assertEquals(9_000L, saved.words.first { it.key == "beta" }.lastUsedAt)
    }

    // ---- the file ---------------------------------------------------------------------------------------------------------

    @Test
    fun aSaveLeavesOneFileAndNoTemporaryFile() {
        store().learn("one two three")
        assertTrue(file.isFile)
        assertEquals(listOf(LearnedWordsStore.FILE_NAME), dir.list()!!.toList())
    }

    @Test
    fun aTemporaryFileLeftByACrash_isIgnored_andReplacedByTheNextSave() {
        dir.mkdirs()
        File(dir, LearnedWordsStore.TEMP_NAME).writeText("{ half written")
        val s = store()
        assertEquals(Prediction.NONE, predict(s, "hel"))
        s.learn("hello there")
        assertEquals(listOf(LearnedWordsStore.FILE_NAME), dir.list()!!.toList())
        assertEquals(listOf("hello"), predict(store(), "hel").suggestions)
    }

    @Test
    fun theSameLearningAlwaysSavesTheSameBytes() {
        store().learn("alpha beta gamma. beta alpha")
        val first = file.readText()
        file.delete()
        store().learn("alpha beta gamma. beta alpha")
        assertEquals(first, file.readText())
    }

    // ---- a damaged file ----------------------------------------------------------------------------------------------------

    @Test
    fun aFileThatIsNotJson_isTreatedAsEmpty_andSetAsideBeforeAnythingIsSaved() {
        dir.mkdirs()
        file.writeText("this is not json")
        val s = store()
        assertEquals(Prediction.NONE, predict(s, "hel"))
        s.learn("hello world")
        val kept = dir.listFiles()!!.filter { it.name.startsWith(LearnedWordsStore.DAMAGED_PREFIX) }
        assertEquals("the damaged file must be kept, byte for byte", 1, kept.size)
        assertEquals("this is not json", kept.single().readText())
        assertEquals(listOf("hello"), predict(store(), "hel").suggestions)
    }

    @Test
    fun aFileThatParsesButFailsTheChecks_isTreatedTheSameWay() {
        dir.mkdirs()
        val twice = """{"words":[{"key":"a","form":"a","count":1,"lastUsedAt":1},{"key":"a","form":"a","count":1,"lastUsedAt":1}],"pairs":[]}"""
        file.writeText(twice)
        val s = store()
        assertEquals(0, s.wordCount())
        s.learn("fresh start")
        assertEquals(twice, dir.listFiles()!!.single { it.name.startsWith(LearnedWordsStore.DAMAGED_PREFIX) }.readText())
    }

    @Test
    fun aHugeFile_isNotReadIntoMemory_evenWhenItIsValidJson() {
        dir.mkdirs()
        // Valid, empty model padded with spaces to one byte over the ceiling: only the size check can refuse it.
        file.outputStream().buffered().use { out ->
            out.write("""{"words":[],"pairs":[]}""".toByteArray())
            val padding = ByteArray(64 * 1024) { ' '.code.toByte() }
            var written = 0L
            while (written <= LearnedWordsStore.MAX_FILE_BYTES) { out.write(padding); written += padding.size }
        }
        assertTrue(file.length() > LearnedWordsStore.MAX_FILE_BYTES)
        val s = store()
        assertEquals(0, s.wordCount())
        assertTrue(dir.listFiles()!!.any { it.name.startsWith(LearnedWordsStore.DAMAGED_PREFIX) })
    }

    @Test
    fun twoDamagedFilesDoNotOverwriteEachOther() {
        dir.mkdirs()
        file.writeText("first damage")
        val s = store()
        s.learn("alpha")
        file.writeText("second damage")
        // The clock has not moved, so both set-aside files would get the same name without the uniqueness rule.
        val again = store()
        again.learn("beta")
        val kept = dir.listFiles()!!.filter { it.name.startsWith(LearnedWordsStore.DAMAGED_PREFIX) }.map { it.readText() }.toSet()
        assertEquals(setOf("first damage", "second damage"), kept)
    }

    // ---- changes made behind the store's back (a wipe, a restore) ------------------------------------------------------------

    @Test
    fun aFileDeletedBehindItsBack_isNoticed_andTheOldWordsAreNotBroughtBack() {
        val s = store()
        s.learn("alpha beta")
        assertTrue(file.delete()) // what DELETE DATA does
        assertEquals(Prediction.NONE, predict(s, "alp"))
        s.learn("gamma")
        val saved = store().exportForBackup()!!
        assertEquals(listOf("gamma"), saved.words.map { it.key })
    }

    @Test
    fun aFileChangedByAnotherStore_isNoticed() {
        val first = store()
        first.learn("alpha")
        val second = store()
        second.learn("alphabet")
        assertEquals(setOf("alpha", "alphabet"), predict(first, "alp").suggestions.toSet())
    }

    // ---- forgetting ---------------------------------------------------------------------------------------------------------

    @Test
    fun forgettingOneWord_removesItAndItsPairs_andSavesThat() {
        val s = store()
        s.learn("good morning sunshine")
        assertTrue(s.forget("Morning"))
        assertFalse(s.forget("morning"))
        val saved = store().exportForBackup()!!
        assertEquals(setOf("good", "sunshine"), saved.words.map { it.key }.toSet())
        assertTrue(saved.pairs.none { it.prev == "morning" || it.next == "morning" })
    }

    @Test
    fun forgettingTheLastWord_leavesNoFileAtAll() {
        val s = store()
        s.learn("alpha")
        assertTrue(s.forget("alpha"))
        assertFalse(file.exists())
        assertNull(s.exportForBackup())
    }

    @Test
    fun forgetAll_removesEveryFileThisStoreMade_includingSetAsideDamagedOnes() {
        dir.mkdirs()
        file.writeText("damaged")
        val s = store()
        s.learn("alpha beta")
        assertTrue(dir.listFiles()!!.size >= 2)
        s.forgetAll()
        assertTrue("nothing may remain: ${dir.list()?.toList()}", !dir.exists() || dir.list().isNullOrEmpty())
        assertEquals(0, s.wordCount())
        assertNull(s.exportForBackup())
    }

    @Test
    fun forgetAll_leavesFilesThatAreNotItsOwn() {
        dir.mkdirs()
        val other = File(dir, "someone_elses.txt").also { it.writeText("keep me") }
        val s = store()
        s.learn("alpha")
        s.forgetAll()
        assertEquals("keep me", other.readText())
    }

    // ---- the list ------------------------------------------------------------------------------------------------------------

    @Test
    fun theListIsBestFirst_withHowOftenEachWasUsed() {
        val s = store()
        s.learn("tea tea tea coffee coffee water")
        assertEquals(listOf("tea" to 3, "coffee" to 2, "water" to 1), s.listWords().map { it.form to it.count })
    }

    // ---- backup --------------------------------------------------------------------------------------------------------------

    @Test
    fun theBackupHoldsExactlyWhatWasLearned_andNothingWhenEmpty() {
        val s = store()
        assertNull(s.exportForBackup())
        s.learn("alpha beta")
        val data = s.exportForBackup()!!
        assertEquals(2, data.words.size)
        assertEquals(1, data.pairs.size)
        assertNull("a model the store made must pass its own checks", data.validate())
    }

    @Test
    fun aRestoreAddsToWhatIsThere_neverLowersACount_andNeverRemovesAWord() {
        val s = store()
        s.learn("alpha alpha alpha beta")
        val older = WordModelData(
            words = listOf(StoredWord("alpha", "alpha", 1, 1), StoredWord("gamma", "gamma", 4, 2)),
            pairs = emptyList(),
        )
        s.mergeFromBackup(older)
        val saved = store().exportForBackup()!!.words.associateBy { it.key }
        assertEquals(3, saved.getValue("alpha").count)
        assertTrue("beta" in saved)
        assertEquals(4, saved.getValue("gamma").count)
    }

    @Test
    fun aHostileRestore_cannotBreakTheStore() {
        val s = store()
        s.learn("alpha")
        val hostile = WordModelData(
            words = listOf(
                StoredWord("", "", 1, 1), StoredWord("x".repeat(500), "x", 1, 1), StoredWord("neg", "neg", -5, 1),
                StoredWord("big", "big", Int.MAX_VALUE, 1), StoredWord("late", "late", 1, -1),
            ),
            pairs = listOf(StoredPair("big", "ghost", 1), StoredPair("big", "big", Int.MAX_VALUE)),
        )
        s.mergeFromBackup(hostile)
        val saved = store().exportForBackup()!!
        assertNull(saved.validate())
        assertEquals(setOf("alpha", "big"), saved.words.map { it.key }.toSet())
        assertTrue(saved.words.first { it.key == "big" }.count <= WordModel.MAX_COUNT)
    }

    // ---- threads --------------------------------------------------------------------------------------------------------------

    @Test
    fun learningFromTwoThreadsLosesNothing() {
        val s = store()
        val threads = (1..2).map { Thread { repeat(100) { s.learn("shared") } } }
        threads.forEach { it.start() }
        threads.forEach { it.join() }
        assertEquals(200, store().exportForBackup()!!.words.single().count)
    }
}
