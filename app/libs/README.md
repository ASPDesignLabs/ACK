# sherpa-onnx native library (manual download required)

ACK's custom trained voice feature (`output/PiperVoiceEngine.kt`) runs on
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), an on-device neural
TTS engine. It isn't published to Maven Central, so it can't be pulled in
as a normal Gradle dependency -- it has to be downloaded once and placed
in this folder.

## Steps

1. Download the current release AAR:
   `https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar`
   (as of writing this, the latest release is v1.13.8, ~48MB -- if a newer
   version has since been released, use that one instead; check
   `https://github.com/k2-fsa/sherpa-onnx/releases` for the current tag).
   **Do not download `sherpa-onnx-<version>-rknn.aar`** -- that variant is
   for Rockchip NPU hardware, not a phone's regular CPU.
2. Place the downloaded `.aar` file directly in this folder
   (`app/libs/`). The Gradle build (`app/build.gradle.kts`) already picks
   up any `*.aar` file here automatically.
3. This file is intentionally excluded from git (`.gitignore`) -- it's a
   large third-party binary, not source code, so every machine that builds
   ACK needs to repeat this one-time download rather than it living in the
   repo's history forever.

After placing the file, sync/rebuild in Android Studio.
