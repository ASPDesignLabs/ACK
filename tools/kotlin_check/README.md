# Kotlin checks without the Android SDK

Two small Gradle projects for working on the training-data capture feature where there is no Android SDK (a cloud session, a
plain Linux box, CI). Neither replaces building the app in Android Studio; they catch most mistakes before that.

You need a JDK 17+ and Gradle 8+ and a connection to Maven Central (they download Kotlin, kotlinx-serialization, JUnit and Compose
Multiplatform; nothing else, and nothing from Google's Maven).

## `./run_unit_tests.sh`: the portable logic, tested

Compiles `app/src/main/java/com/example/besu/capture/` and `app/src/main/java/com/example/besu/core/` (both plain Kotlin: no
`android.*` anywhere in them, on purpose) with Kotlin 2.0.21 and runs the matching folders under `app/src/test/java/com/example/besu/`
with JUnit. These are the same tests Android Studio's unit-test run uses (`./gradlew :app:testDebugUnitTest`).

`core/` holds small decisions that are not about recording, kept in plain Kotlin so they can be tested here (for example, whether an
install is new). The Android code that uses them stays thin.

They hold the Kotlin to the shared test cases in `tools/freeform_studio/tests/data/ack_capture/`, the very files the Python side
is held to, so the phone and the computer cannot quietly disagree about a rule.

`ACK_KOTLIN_PACKAGES=/tmp/ack-packages ./run_unit_tests.sh` also makes `PackageWriterTest` write three sample packages there;
`ACK_KOTLIN_PACKAGES=/tmp/ack-packages python -m pytest tools/freeform_studio/tests/test_kotlin_package_contract.py` then opens
them with Freeform Studio's real reader and importer.

**Keep `capture/` and `core/` free of Android classes.** The harness compiles those folders and everything under them; one
`import android.*` there and it stops compiling here. Anything that needs the phone goes in `voicecapture/` (for capture) or next to
the code that uses it (for `core/`).

## `./run_typecheck.sh`: the Android screens, type-checked

Compiles `app/.../voicecapture/` (the screens, microphone and glue) against Compose Multiplatform, which has the same
`androidx.compose.*` API, together with the app's own Compose-only files (the shared buttons, HELP, tags, colours) copied in as
they are, and small **stubs** of the few Android classes the screens call (`stubs/`).

It also compiles the plain-words Terminal controls, the INTERFACE LANGUAGE section, the backup screens (the export warning and the reminder banner; `stubs/app/Backup.kt` stands in for the exporter and the reminder state, which read storage) the People and places category, tree, wizard, quick-insert and contact card screens (`stubs/app/Computer.kt` stands in for the repository and `stubs/app/Output.kt` for the visual editor), the Emergency deck screen (`stubs/app/CommandRepository.kt` stands in for its storage, and `material` is on the classpath because that screen uses it) the DELETE DATA dialogs (all of `core/`, which is plain Kotlin, is staged with them; `stubs/app/DataWipe.kt` stands in for the wipe) the MANAGE RECORDINGS dialog and the voice recording panel (the recorder and the recordings store are stubbed in `stubs/app/Recordings.kt`; the real `AudioDsp` is staged), the MANAGE AUTOCOMPLETE dialog (the history repository, the Quick Actions models and the deck, node and phrase lookups are stubbed in `stubs/app/Autocomplete.kt`, `QuickActionsModels.kt` and `CommandRepository.kt`), the MANAGE CONTEXT dialogs (`stubs/app/CommandRepository.kt` stands in for the custom context functions), the WORD SUGGESTIONS section and FORGET WORDS (`LearnedWordsRepository` and `AssistPrefs` are stubbed in `stubs/app/AudioData.kt`) the profile-change warning's dialog (its words come from `core/`, which is staged with the rest), the HELP menu, coach panel and chooser dialogs (`stubs/app/HelpModules.kt` stands in for the walkthrough modules whose option types the choosers draw, and `helpText` is stubbed in `stubs/app/AppUi.kt`) and the AUDIO ARCHITECT screen with its defaults offer (the voice stores, the visual preset store, `AssistPrefs`, `InstallState`, the backup manager and the shared slider and button are stubbed from their real signatures in `stubs/app/Audio*.kt`; the real `VoiceProfile` and `VoiceInfoMapping` are staged against a stub of Android's `Voice`).

It finds Kotlin and Compose mistakes: a misspelled function, a wrong type, a missing import, a lambda in the wrong place. It
**cannot** find a wrong Android signature (the stubs are written from how the real code is used), a runtime problem, a layout problem,
or anything about the microphone. Check that it still catches errors after you change it: put a typo in a copy of a screen and
watch it fail. If you use a new Android class or function in `voicecapture/`, add the few lines it needs to `stubs/`.

## Why this exists

The feature is a lot of code that decides what is recorded and kept. The decisions are in plain Kotlin so they can be tested; the
Android edges are kept thin. This is how that split is checked when there is no phone and no SDK to hand. Nothing in here is part of
the app.

## `./run_syntax_check.sh File.kt ...`: a parse-only check for the Android-only files

Some screens (SettingsView.kt, the display-permission banner and the shared components) use the Android SDK, so they are not staged for the type-check above. This compiles them
with no classpath and reports only **syntax** errors, which finds a missing parenthesis or brace from a wording edit; it cannot find a wrong name or type (the unit tests that read
the source and the strings file do that). It was proved by breaking a copy on purpose.
