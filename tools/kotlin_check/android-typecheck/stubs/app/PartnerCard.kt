// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.core.PartnerCardBackup
import com.example.besu.core.PartnerCardSettings

// Stub of data/PartnerCardRepository.kt (it reads and writes storage and is not staged), written from its real signatures.
object PartnerCardRepository {
    fun load(context: Context): PartnerCardSettings = PartnerCardSettings.DEFAULT
    fun save(context: Context, settings: PartnerCardSettings): Boolean = true
    fun exportForBackup(context: Context): PartnerCardBackup? = null
    fun mergeFromBackup(context: Context, backup: PartnerCardBackup) {}
}
