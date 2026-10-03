// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu

import android.app.Application
import com.example.besu.data.InstallState

/**
 * Runs before any activity, service or receiver, so the install is classified before any screen writes to storage.
 * It does that one thing and nothing else. See data/InstallState.kt.
 */
class AckApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        InstallState.ensureRecorded(this)
    }
}
