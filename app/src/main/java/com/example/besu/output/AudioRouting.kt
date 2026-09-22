package com.example.besu.output

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build

// Enumerates connected Bluetooth audio OUTPUT devices via AudioManager.getDevices()
// rather than BluetoothAdapter/BluetoothManager. This only ever returns devices
// that are actually valid audio routes right now (not, say, a paired fitness
// tracker with no audio capability), and needs no BLUETOOTH_CONNECT runtime
// permission at all -- unlike the BluetoothAdapter APIs, which would require
// prompting for it on every device this app runs on (minSdk 31). Mirrors
// exactly how OutputService's FORCE SPEAKER routing already finds the
// built-in speaker (AudioDeviceInfo.TYPE_BUILTIN_SPEAKER) via this same
// AudioManager call -- this generalizes that mechanism to Bluetooth outputs.
object AudioRouting {

    fun isBluetoothOutputType(type: Int): Boolean {
        if (type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
            type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        ) {
            return true
        }

        // BLE Audio output types were only introduced in API 33 -- a device
        // on an older OS will simply never report them, but the version
        // check keeps this consistent with how the rest of the app guards
        // newer AudioDeviceInfo/AudioTrack behavior.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (type == AudioDeviceInfo.TYPE_BLE_HEADSET ||
                type == AudioDeviceInfo.TYPE_BLE_SPEAKER
            ) {
                return true
            }
        }

        return false
    }

    // Every currently-connected Bluetooth audio output, deduplicated by
    // address -- the same physical device can sometimes surface as more than
    // one AudioDeviceInfo entry (e.g. both an A2DP and a SCO route).
    fun listConnectedBluetoothDevices(context: Context): List<AudioDeviceInfo> {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        return audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            .filter { isBluetoothOutputType(it.type) }
            .distinctBy { it.address }
    }

    // productName is usually the device's real name, but isn't guaranteed to
    // be meaningful -- falls back to a short label built from the device's
    // own address so two unnamed devices in the picker still look distinct
    // from each other rather than identical.
    fun friendlyLabel(device: AudioDeviceInfo): String {
        val name = device.productName.toString().trim()
        if (name.isNotEmpty() && !name.equals("android", ignoreCase = true)) {
            return name
        }

        val addressSuffix = device.address.takeLast(5).uppercase()
        return if (addressSuffix.isNotBlank()) {
            "BLUETOOTH DEVICE ($addressSuffix)"
        } else {
            "BLUETOOTH DEVICE"
        }
    }
}
