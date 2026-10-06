// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** The four ways a Terminal message can be asked to go out differently. Each has a typed form (`/q /n /s /e`) and, with PLAIN WORDS on, a switch. */
enum class SendFlag { QUIET, SKIP_LOG, STICKY, EMERGENCY }

/**
 * How one message leaves the Terminal. Plain Kotlin, so the decisions are tested (SendFlagsTest) without the screen.
 *
 * - [quiet]: no sound (`/q`). [skipLog]: not written to the history (`/n`). [sticky]: stays on the screen until it is cleared (`/s`).
 * - [emergency]: the Emergency deck's settings (`/e`). It is never asked to confirm, typed or switched: that is a recorded decision, not an oversight.
 */
data class SendFlags(
    val quiet: Boolean = false,
    val skipLog: Boolean = false,
    val sticky: Boolean = false,
    val emergency: Boolean = false
) {
    val anyOn: Boolean get() = quiet || skipLog || sticky || emergency

    fun isOn(flag: SendFlag): Boolean = when (flag) {
        SendFlag.QUIET -> quiet
        SendFlag.SKIP_LOG -> skipLog
        SendFlag.STICKY -> sticky
        SendFlag.EMERGENCY -> emergency
    }

    fun with(flag: SendFlag, on: Boolean): SendFlags = when (flag) {
        SendFlag.QUIET -> copy(quiet = on)
        SendFlag.SKIP_LOG -> copy(skipLog = on)
        SendFlag.STICKY -> copy(sticky = on)
        SendFlag.EMERGENCY -> copy(emergency = on)
    }

    /** The flags that are on, in the fixed order of [SendFlag] (so a summary always reads the same way). */
    fun onFlags(): List<SendFlag> = SendFlag.values().filter { isOn(it) }

    /** A flag is on if either side asks for it; nothing a person typed is ever turned off by a switch, and no switch is turned off by what they typed. */
    fun or(other: SendFlags): SendFlags = SendFlags(
        quiet = quiet || other.quiet,
        skipLog = skipLog || other.skipLog,
        sticky = sticky || other.sticky,
        emergency = emergency || other.emergency
    )
}

/** What a send uses, given the typed flags and the switches. */
object SendSwitchPolicy {
    /**
     * The switches count only while PLAIN WORDS is on, because that is the only time they can be seen. A switch left on while it is hidden would make a
     * message silent, unsaved or loud by accident, which is the one thing a communication app must not do. (Turning PLAIN WORDS off also sets them off.)
     */
    fun effective(typed: SendFlags, switches: SendFlags, plainWordsOn: Boolean): SendFlags =
        if (plainWordsOn) typed.or(switches) else typed
}
