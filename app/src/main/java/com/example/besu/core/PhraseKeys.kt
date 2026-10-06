// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Where a Matrix phrase is stored in the `ack_matrix_config` preference file. Plain Kotlin (no `android.*`).
 *
 * This used to be a private function inside CommandRepository. It lives here so that the repository (which reads and writes a
 * person's phrases) and the starter seed (which must write to exactly the same keys) use ONE recipe and cannot disagree.
 * CommandRepository.generateStorageKey now just calls it; a test (PhraseKeysTest) fails if that stops being true.
 *
 * The recipe: the DEFAULT deck and the DEFAULT profile add no prefix, so the default deck's default phrase for `/std/id/0` is
 * stored under the key `/std/id/0` itself. Any other deck adds `<deckId>_` and any other profile `<profile>_`, deck first.
 */
object PhraseKeys {
    fun storageKey(deckId: String, profile: String, path: String): String {
        val deckPrefix = if (deckId == "DEFAULT") "" else "${deckId}_"
        val profilePrefix = if (profile == "DEFAULT") "" else "${profile}_"
        return "$deckPrefix$profilePrefix$path"
    }
}
