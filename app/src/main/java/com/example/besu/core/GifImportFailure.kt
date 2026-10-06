// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Why importing one GIF file failed, carried as an id and not as a sentence, so the screen can say it in the chosen language without comparing words
 * (a result is carried by id, never by a label). Plain Kotlin (no `android.*`).
 *
 * [englishMessage] is exactly the text the repository's failure has always carried (`Throwable.message`, so a log or a caller that reads it sees no change);
 * [resource] names the string resource the screen shows instead.
 */
enum class GifImportFailure(val englishMessage: String, val resource: String) {
    NOT_A_GIF("Selected file is not a GIF.", "gif_err_not_gif"),
    TOO_BIG("GIF exceeds the 20 MB safety limit.", "gif_err_too_big"),
    UNREADABLE("Unable to read selected file.", "gif_err_unreadable"),
    INVALID("Selected file is not a valid GIF.", "gif_err_invalid"),
}

/** An [IllegalStateException] (what `error(...)` threw before) that also says which of the four reasons it was. */
class GifImportException(val failure: GifImportFailure) : IllegalStateException(failure.englishMessage)
