// SPDX-License-Identifier: GPL-3.0-or-later
// Compiles the app's plain-Kotlin `capture` package and runs its JUnit tests, with no Android SDK: only Maven Central is needed.
// See ../README.md. The versions match gradle/libs.versions.toml and app/build.gradle.kts.
plugins {
    kotlin("jvm") version "2.0.21"
    kotlin("plugin.serialization") version "2.0.21"
}
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    testImplementation("junit:junit:4.13.2")
}
val repo = rootDir.resolve("../../..").canonicalFile
sourceSets {
    main { kotlin.srcDir(repo.resolve("app/src/main/java/com/example/besu/capture")) }
    test { kotlin.srcDir(repo.resolve("app/src/test/java/com/example/besu/capture")) }
}
tasks.test {
    workingDir = repo.resolve("app")              // what Android's unit tests use too; the tests find the repository root from here
    testLogging { events("failed"); showStandardStreams = true; exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL }
}
