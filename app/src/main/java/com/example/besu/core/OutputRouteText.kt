// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words SETTINGS > AUDIO OUTPUT ROUTING shows for where speech goes: the summary under OUTPUT DEVICE, and the hint on the ACK WATCH and Bluetooth rows. Plain Kotlin, read through a
 * [TextSource], tested in every language.
 *
 * The route itself is stored as the exact strings [AUTO], [BLUETOOTH] and [WATCH] (`OUTPUT_ROUTE_MODE`, read by OutputService and checked by the backup): they are logic and never
 * translated. A Bluetooth device's own name is shown exactly as the phone reports it.
 */
object OutputRouteText {
    const val AUTO = "AUTO"
    const val BLUETOOTH = "BLUETOOTH"
    const val WATCH = "WATCH"

    /**
     * One line under OUTPUT DEVICE. FORCE SPEAKER beats every route, so while it is on the line says so, naming the switch by [forceSpeakerName] (the same label the switch above it shows,
     * which follows PLAIN WORDS). Otherwise it names the chosen route.
     */
    fun summary(text: TextSource, forceSpeaker: Boolean, mode: String, bluetoothLabel: String?, forceSpeakerName: String): String = when {
        forceSpeaker -> text.get("settings_route_overridden", forceSpeakerName)
        mode == BLUETOOTH -> bluetoothName(text, bluetoothLabel)
        mode == WATCH -> text.get("settings_route_watch")
        else -> text.get("settings_route_auto")
    }

    /** A saved Bluetooth pick's cached name, or a plain word for it when the phone never gave one. */
    fun bluetoothName(text: TextSource, cachedLabel: String?): String = cachedLabel ?: text.get("settings_route_bt_device")

    /** The hint on the ACK WATCH row: whether the watch is reachable right now. */
    fun watchHint(text: TextSource, connected: Boolean): String = text.get(if (connected) "settings_route_connected" else "settings_route_not_connected")
}
