# What ACK asks Android for, and why

Written 2026-10-03 by reading the code. It lists every permission declared in the phone app's manifest
(`app/src/main/AndroidManifest.xml`) and the watch app's (`wear/src/main/AndroidManifest.xml`), what needs it, where the code asks for it
on the phone at run time, and whether it could be removed. **Neither app declares a network permission** (no `INTERNET`, no `ACCESS_NETWORK_STATE`).
`tools/freeform_studio/tests/test_sovereignty_policy.py` fails if one is added to the **phone** app's manifest. It does **not** look at the
watch's manifest, which is clean today (it was read in full) but has nothing guarding it.

File paths below are relative to `app/src/main/java/com/example/besu/` unless they start with `wear/`. Line numbers were right when this was
written. "Install time" means Android grants it when the app is installed, with no question asked.

## The phone app

| Permission | What needs it | Asked for at run time | Could it be removed? |
|---|---|---|---|
| `FOREGROUND_SERVICE` | the speech service and the shake-to-stop service run as foreground services (`output/OutputService.kt:178`, `output/AccelerometerTapService.kt:51`) | install time | No: Android requires it for any foreground service |
| `FOREGROUND_SERVICE_MEDIA_PLAYBACK` | the speech service's type, `mediaPlayback` (manifest, `OutputService`) | install time | No: required with that service type |
| `FOREGROUND_SERVICE_SPECIAL_USE` | the shake-to-stop service's type, `specialUse` (manifest, `AccelerometerTapService`) | install time | No: required with that service type |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | keeping shake-to-stop working with the phone in a pocket | `MainActivity.kt:167` opens Android's own "don't optimise battery" dialog at launch, until it is allowed | No, while that feature stays |
| `VIBRATE` | the shake-to-stop confirmation buzz (`output/AccelerometerTapService.kt:55`, `:124`). Button feedback elsewhere uses Compose's haptics, which need no permission | install time | No, while the buzz stays |
| **`WAKE_LOCK`** | **nothing found.** No code in either app acquires a wake lock (no `newWakeLock`, `setWakeMode`, `WorkManager` or `AlarmManager`). Screens that stay on use a window flag, which needs no permission. It arrived with the project's first import, with no reason recorded | install time | **Probably yes.** Not removed: asking first (see below) |
| **`POST_NOTIFICATIONS`** | the notifications of the two foreground services | **never.** Nothing asks for it and nothing checks whether notifications are allowed | See "Questions" below. Not changed |
| `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION` | Geo-Protocol only (off by default): `geo/GeoEngineController.kt:105`, `:112` (own polling) and `:198` (Google geofencing) | when Geo-Protocol is turned on: `geo/PermissionModal.kt:63`, launcher in `geo/GeoProtocolView.kt:160` | Only by dropping Geo-Protocol |
| `ACCESS_BACKGROUND_LOCATION` | Geo-Protocol watching for boundaries while the phone is locked | `geo/PermissionModal.kt:66`, a second question after the first | Only by dropping Geo-Protocol (see "Background location") |
| `RECORD_AUDIO` | recording voice clips, RECORD TRAINING DATA, the decibel meter (`output/VoiceRecorder.kt:105`, `voicecapture/TrainingCapture.kt:139`, `output/DBMediaRecorder.kt:49`) | on first use: `settings/SettingsView.kt:862`, `output/VoiceRecordingPanel.kt:253`, `output/DBMonitorView.kt:85`, `voicecapture/CaptureSessionScreen.kt:283` | No |
| `SYSTEM_ALERT_WINDOW` ("Display over other apps") | full-screen messages (`output/VisualPromptService.kt:843`) | not a pop-up question: Android keeps this on a Settings page. A red banner with **ALLOW** opens it (`ui/OverlayPermissionBanner.kt:110`) and stays until it is on; the speech service logs when a message is spoken but not shown | No |

The manifest also declares `uses-feature microphone required=false`: the app installs on a device without one.

**The phone's own speech engine.** ACK speaks through Android's text-to-speech engine, which is a separate app (the phone maker's or Google's) and needs no
permission from ACK. ACK has no network permission and no network code, and its voice list (AUDIO ARCHITECT, BASE VOICE) leaves out every voice the engine says
needs the internet or is not installed, and says so under the list. What the engine does with text on its own is the engine's behaviour, not ACK's, and ACK
cannot see it; to be sure, use only voices you have downloaded and turn off the engine's own online options in the phone's settings.

## The watch app

| Permission | What needs it | Could it be removed? |
|---|---|---|
| `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_SPECIAL_USE` | the background sensor service (`wear/.../presentation/BackgroundSensorService.kt:241`) | No |
| `VIBRATE` | the watch's haptic feedback (`BackgroundSensorService.kt:259`, `:778`, `:881`, and its main screen) | No |
| **`WAKE_LOCK`** | **nothing found**: no wake lock is acquired in the watch code either | **Probably yes**, same as the phone's |

## Questions for the developer (nothing below has been changed)

1. **`WAKE_LOCK` (phone and watch).** Nothing in either app uses it. Remove it from both manifests? Removing an unused permission cannot
   take a feature away from ACK's own code, but a library could need it, and only the merged manifest of a real build can say (below).
   The decision, and the removal, are the developer's. After any manifest change, run `test_sovereignty_policy.py`.
2. **`POST_NOTIFICATIONS`.** Declared, never requested. On Android 13 and later, per Android's documented behaviour (not tried here), a foreground service
   still runs without it, but its notification is kept out of the notification shade, so the person never sees the two ongoing notices
   that say the speech and shake-to-stop services are running. Options: **leave as is** (no prompt, nothing changes); **remove** the
   declaration (changes nothing visible); or **add a proper request**, which is a new permission prompt, so it needs a decision and its own
   screen. Reported only.
3. **Background location.** It is declared in the manifest but only asked for when Geo-Protocol (off by default) is turned on. Options: **keep
   it and document it** (this file); or **make a second build without Geo-Protocol**, with its location permissions removed by a manifest
   overlay (Gradle product flavours) and the Geo screens hidden. The second is a larger change and has not been started.

## The merged manifest: what was and was not checked

The manifests above are the **source** manifests. A built app's manifest is the source one **plus whatever its libraries declare**, and a
library can add a permission the source does not mention. That is the check the project's notes still list as open. Result so far:

* **Checked (2026-10-03, against Maven Central):** the mapping libraries cannot add anything. `org.mapsforge:mapsforge-map-android:0.20.0`,
  `mapsforge-themes:0.20.0`, `vtm-android:0.25.0` and `vtm-themes:0.25.0`, and their direct dependencies (`mapsforge-map-reader`, `vtm`,
  `com.caverock:androidsvg:1.4`), are published as plain JARs. A JAR has no `AndroidManifest.xml`, so it takes no part in manifest merging.
* **Not checked:** Google's libraries (`play-services-wearable:18.1.0`, `play-services-location:21.0.1`, what they pull in, AndroidX, Material,
  Compose), whose manifests are on Google's Maven server, which the session that wrote this could not reach; and the vendored
  `app/libs/*.aar` sherpa-onnx library, which is not in the repository. **So the merged manifest of a real build is unchecked.**
  AndroidX normally adds one signature-level permission of its own, named after the package (`...DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`); that is
  from memory, not verified here.

To finish the check on a machine with the Android SDK:

```
./gradlew :app:processDebugMainManifest :wear:processDebugMainManifest
find app/build/intermediates wear/build/intermediates -name AndroidManifest.xml -path "*merged_manifest*"
grep -h "uses-permission" <each file found>
# or, from a built APK, with the SDK's command-line tools on your path:
apkanalyzer manifest permissions app/build/outputs/apk/debug/app-debug.apk
```

Compare with the tables above. **Anything the source does not declare, above all `INTERNET` or `ACCESS_NETWORK_STATE`, should be reported at
once.** Record the result here (date, and what was found) when it has been run.
