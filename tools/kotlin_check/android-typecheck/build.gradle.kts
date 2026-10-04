// SPDX-License-Identifier: GPL-3.0-or-later
// Type-checks the Android-bound capture screens (app/.../voicecapture) without an Android SDK: Compose Multiplatform has the same
// androidx.compose.* API and is on Maven Central, the app's own Compose-only files are copied in as they are, and the Android classes
// the screens call are small stubs (stubs/). See ../README.md for what this can and cannot tell you.
plugins {
    kotlin("jvm") version "2.0.21"
    kotlin("plugin.serialization") version "2.0.21"
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
}
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("org.jetbrains.compose.runtime:runtime-desktop:1.7.0")
    implementation("org.jetbrains.compose.foundation:foundation-desktop:1.7.0")
    implementation("org.jetbrains.compose.material3:material3-desktop:1.7.0")
    implementation("org.jetbrains.compose.material:material-desktop:1.7.0")
    implementation("org.jetbrains.compose.ui:ui-desktop:1.7.0")
    implementation("org.jetbrains.compose.animation:animation-core-desktop:1.7.0")
}
sourceSets { main { kotlin.srcDir("build/stage") } }
