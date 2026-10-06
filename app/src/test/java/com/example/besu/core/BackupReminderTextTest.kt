// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackupReminderTextTest {

    @Test
    fun theMessageAfterARealBackupSaysHowLongAgo() {
        assertEquals(
            "BACKUP DUE: YOUR LAST BACKUP WAS 7 DAYS AGO, AND SETTINGS OR DECKS HAVE CHANGED SINCE.",
            BackupReminderText.message(EnglishText, daysSince = 7, neverBackedUp = false),
        )
        assertEquals(
            "BACKUP DUE: YOUR LAST BACKUP WAS 30 DAYS AGO, AND SETTINGS OR DECKS HAVE CHANGED SINCE.",
            BackupReminderText.message(EnglishText, daysSince = 30, neverBackedUp = false),
        )
    }

    @Test
    fun oneDayIsSingular() {
        assertTrue(BackupReminderText.message(EnglishText, 1, false).contains("WAS 1 DAY AGO"))
        assertFalse(BackupReminderText.message(EnglishText, 1, false).contains("DAYS"))
    }

    @Test
    fun theMessageWhenThereHasNeverBeenABackupDoesNotMentionDays() {
        val text = BackupReminderText.message(EnglishText, daysSince = 12, neverBackedUp = true)
        assertEquals("YOU HAVE NOT MADE A BACKUP YET, AND THINGS HAVE CHANGED.", text)
        assertFalse(text.contains("DAYS"))
    }

    @Test
    fun theButtonsAndSwitchUseThePlainWordsTheyWereAskedFor() {
        assertEquals("BACK UP NOW", EnglishText.get(BackupReminderText.BACK_UP_NOW))
        assertEquals("NOT NOW", EnglishText.get(BackupReminderText.NOT_NOW))
        assertEquals("BACKUP REMINDER: ON", BackupReminderText.switchLabel(EnglishText, true))
        assertEquals("BACKUP REMINDER: OFF", BackupReminderText.switchLabel(EnglishText, false))
    }

    @Test
    fun theSwitchExplainsItIsInAppOnlyAndWritesNoFile() {
        val e = EnglishText.get(BackupReminderText.SWITCH_EXPLANATION)
        assertTrue(e.contains("7 DAYS"))
        assertTrue(e.contains("IN ACK ONLY"))
        assertTrue(e.contains("NO FILE"))
    }

    @Test
    fun everythingIsCapitalsLikeTheRestOfTheApp() {
        val all = listOf(
            BackupReminderText.message(EnglishText, 7, false), BackupReminderText.message(EnglishText, 7, true),
            EnglishText.get(BackupReminderText.BACK_UP_NOW), EnglishText.get(BackupReminderText.NOT_NOW),
            BackupReminderText.switchLabel(EnglishText, true), BackupReminderText.switchLabel(EnglishText, false),
            EnglishText.get(BackupReminderText.SWITCH_EXPLANATION), EnglishText.get(BackupReminderText.ICON_DESCRIPTION), EnglishText.get(BackupReminderText.DIALOG_TITLE),
        )
        for (s in all) assertEquals(s.uppercase(), s)
    }

    @Test
    fun theIconAndTheDialogHaveTheSameWords_soAScreenReaderSaysWhatTheDialogIsCalled() {
        assertEquals(BackupReminderText.DIALOG_TITLE, BackupReminderText.ICON_DESCRIPTION)
    }

    @Test
    fun theWordsNeverClaimABackupWasMadeAutomatically() {
        val all = (listOf(true, false).map { BackupReminderText.message(EnglishText, 9, it) } + EnglishText.get(BackupReminderText.SWITCH_EXPLANATION)).joinToString(" ")
        assertFalse(all.contains("AUTOMATIC BACKUP"))
        assertFalse(all.contains("BACKED UP FOR YOU"))
    }
}
