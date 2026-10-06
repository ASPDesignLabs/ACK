// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * Puts new bytes at a file without ever damaging what is already there. Used by GIF restore: a backup is merged by id, so the
 * file it names is often one a saved entry on this phone already points at, and a bad picture in the backup must not be able to
 * overwrite and then delete that good one.
 *
 * The bytes go to a scratch file next to the target and are flushed to disk; the caller's check runs on the scratch file; only if
 * it passes is the scratch file moved over the target in one step. The target itself is never opened for writing and never deleted
 * here, so whatever happens (a refused picture, a full disk, a crash between the steps) it is either exactly as it was or fully
 * the new bytes.
 */
object VerifiedFileReplace {
    /**
     * Ends in something other than the target's own extension, so nothing that looks for `.gif` files can mistake it for a
     * picture. A file left behind by a crash is overwritten the next time the same target is restored.
     */
    const val STAGING_SUFFIX = ".restoring"

    fun stagingFileFor(target: File): File = target.resolveSibling(target.name + STAGING_SUFFIX)

    /**
     * Returns true when [target] now holds [bytes]. Returns false when [isValid] refused the scratch file, in which case [target]
     * is exactly as it was (still there, or still not there). An exception (from [isValid], the disk, or the move) also leaves
     * [target] untouched and is rethrown as it was. The scratch file is removed in every case.
     */
    fun replaceIfValid(target: File, bytes: ByteArray, isValid: (File) -> Boolean): Boolean {
        val staging = stagingFileFor(target)

        try {
            staging.outputStream().use { out ->
                out.write(bytes)
                out.fd.sync()
            }

            if (!isValid(staging)) {
                return false
            }

            Files.move(staging.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
            return true
        } finally {
            staging.delete()
        }
    }
}
