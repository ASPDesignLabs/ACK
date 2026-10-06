<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Third-party sources and their licenses

ACK itself is licensed **GPL-3.0-or-later** (see `LICENSE` and `NOTICE`). This file lists the software, fonts and models
made by other people that ACK uses, the license each comes under, and **how that was checked**, so a claim that was only
remembered is never mistaken for one that was read from the source. Last checked: 2026-10-01.

This is a working record kept by the project, not legal advice.

How each entry was checked: **installed** = read from the license metadata of the installed package; **repo** = read from
the upstream repository's license file or source headers; **file** = read from the file itself; **POM** = read from the
published Maven metadata; **docs** = stated in the upstream project's own documentation; **not verified** = not checked here.

## 1. Files in this repository that come from someone else

| File | Source | License | Checked | Note |
|---|---|---|---|---|
| `app/src/main/jniLibs/arm64-v8a/libvtm-jni.so` | VTM (OpenScienceMap / Mapsforge) native library | LGPL (Maven POM says "GNU Lesser GPL", no version) | POM | A prebuilt binary kept in the tree. LGPL asks that recipients can get the corresponding source and replace the library: the source is the VTM project's. |
| `app/src/main/res/font/atkinson_hyperlegible_next_regular.otf` | Atkinson Hyperlegible Next 2.001, © 2020, 2024 Braille Institute of America | **Its embedded license text reads: "for use, without derivatives or alteration, to the public free of charge for all non-commercial and commercial work. No attribution required."** That is not an open-source license. | file | **Needs a decision.** The upstream open project (`googlefonts/atkinson-hyperlegible-next`) publishes the *same version number* under the **SIL Open Font License 1.1**, but as a different build (392 glyphs against this file's 375, a different character map, different outlines in 197 glyphs; same advance widths). Swapping it would change how some text renders, so it has not been swapped. |
| `gradlew`, `gradlew.bat` | Gradle wrapper scripts | Apache-2.0, "Copyright 2015 the original author or authors" | file | Unmodified header kept. |
| `app/src/main/assets/ack_theme.xml` | A Mapsforge render theme | not verified | | Appears to be written for ACK (uses the Mapsforge theme schema); authorship not confirmed. |
| `assets/**`, `app/src/main/res/mipmap-*`, `app/src/main/res/drawable` | Images, GIFs, icons | not verified | | Provenance of each image has not been checked. |

The landing page (`index.html`) and `legacy/mosaic-importer/` load nothing from other sites. Checked by listing every
script, image, stylesheet and `url()` they reference: the landing page loads 21 things, all from its own files; its only
absolute address is the `rel="canonical"` link, which is metadata and loads nothing. The legacy page loads nothing.

## 2. Fetched by whoever builds the Android app (not stored in this repository)

| Component | License | Checked | Note |
|---|---|---|---|
| sherpa-onnx Android library (`app/libs/*.aar`, gitignored) | Apache-2.0 | repo | Its build links **espeak-ng (GPL-3.0-or-later)** for Piper voices (`cmake/espeak-ng-for-piper.cmake`), which is one reason ACK is GPL. Bundles ONNX Runtime (MIT, not verified here). |
| espeak-ng phonemization data (`app/src/main/assets/espeak-ng-data`, gitignored) | GPL-3.0-or-later | not verified (stated by sherpa-onnx's and piper1-gpl's use of it) | |
| Mapsforge (`mapsforge-map-android`, `mapsforge-themes`) and VTM (`vtm-android`, `vtm-themes`) | LGPL ("GNU Lesser GPL" in the POMs) | POM | The project's landing page describes them as "LGPLv3, with a static-linking waiver" (earlier research, not re-checked). |
| AndroidX, Jetpack Compose, Material, kotlinx.serialization | Apache-2.0 | not verified | |
| Google Play Services: `play-services-location`, `play-services-wearable` | **Proprietary** (Google's terms), not open source | not verified | A strict free-software reading, and stores such as F-Droid, treat proprietary libraries as a problem for a GPL app. `play-services-location` is also a route by which location data is processed by Google's services. Replacing them is a project decision. |

The app's own manifest asks for **no network permission** and its Kotlin code opens no connections; Android cloud backup is
switched off for all app data. Both are checked by `tools/freeform_studio/tests/test_sovereignty_policy.py`. (A library's
manifest could still add a permission when the app is built; check the built APK with `aapt dump permissions`.)

## 3. Freeform Studio (Python): installed by `install.sh`

All 38 packages the installer puts in its environment were read from their installed metadata. None is GPL-only, AGPL,
proprietary or undeclared.

| License | Packages |
|---|---|
| MIT | Quart, Hypercorn, faster-whisper, CTranslate2, onnxruntime, anyio, blinker, filelock, h11, h2, hpack, hyperframe, priority, PyYAML, toml, wsproto |
| BSD-3-Clause | Flask, Werkzeug, Jinja2, MarkupSafe, click, itsdangerous, idna, httpx, httpcore, fsspec, protobuf, PyAV (`av`), numpy (also bundles 0BSD, MIT, Zlib, CC0-1.0 parts) |
| Apache-2.0 | huggingface_hub, hf-xet, tokenizers, aiofiles, flatbuffers, packaging (Apache-2.0 OR BSD-2-Clause) |
| MPL-2.0 | certifi, tqdm (MPL-2.0 AND MIT) |
| PSF-2.0 | typing_extensions |

Two things beside the packages:

* **PyAV's wheel bundles FFmpeg libraries built with `libx264` and `libx265`**, which are GPL encoders. Freeform Studio only
  decodes audio, never encodes video, and the wheel is installed by the user, not distributed by this project. (Checked by
  inspecting the installed wheel. Whether every bundled GPL component is "or later" has not been checked.)
* **`ffmpeg` and `ffprobe` (system programs)** run as separate processes. Ubuntu's build is GPL-enabled (GPLv2 or later per
  Debian's copyright file). Running a program is not linking to it, so it places no condition on ACK's code.

## 4. Speech models and the recorder

| Item | License | Checked | Note |
|---|---|---|---|
| OpenAI Whisper model weights | MIT, "Whisper's code and model weights are released under the MIT License" | repo | |
| faster-whisper conversions (`Systran/faster-whisper-*` on Hugging Face) | derived from the MIT original; the model pages themselves were not read | not verified | Hugging Face was not reachable from where this was checked. |
| piper-recording-studio (the recorder) | MIT | repo | Vendors Bootstrap 4.1.1 (MIT) and wavesurfer.js 4.2.0 (BSD-3-Clause), both from their file headers; also Font Awesome, whose license header was stripped from the vendored files. Freeform Studio only reads its output folder. |

## 5. Training (run on the user's PC, not part of ACK)

| Item | License | Checked |
|---|---|---|
| piper1-gpl (trainer), including espeak-ng built in | GPL-3.0-or-later (`setup.py`, `COPYING`); bundles g2pW-derived code under Apache-2.0 (`licenses/`) | repo |
| torch | Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT AND Apache-2.0 WITH LLVM-exception | PyPI metadata |
| lightning, tensorboard, onnx, cython | Apache-2.0 | PyPI metadata |
| tensorboardX, jsonargparse, pysilero-vad, pathvalidate, onnxruntime | MIT | PyPI metadata |
| librosa | ISC | PyPI metadata |
| torchaudio | BSD | PyPI metadata |
| SpeechMOS (the `val_mos` scorer, loaded through `torch.hub`) and its UTMOS22 weights | MIT; weights derived from the University of Tokyo's UTMOS22 (MIT); fairseq-derived code (MIT) | repo |
| Silero VAD model (inside pysilero-vad) | MIT | not verified |
| **Base voice checkpoints** (`rhasspy/piper-checkpoints`) | **Per voice, in each voice's `MODEL_CARD`.** Piper's own docs: "Some voices may have restrictive licenses, however, so please review them carefully!" | docs |

A voice you train from a base checkpoint is a derivative of it. **Read the `MODEL_CARD` of the base voice you start from
before sharing or distributing the result.** (`mike.ckpt` and the `hfc_male` base the guide suggests were not checked.)
The recordings you train on are your own voice: see `docs/DATA_SOVEREIGNTY.md` for consent and handling.

## 6. How this fits GPL-3.0-or-later

* Permissive (MIT, BSD, ISC, PSF), Apache-2.0 and MPL-2.0 code can be used in a GPLv3 program. (Apache-2.0 is compatible
  with GPLv3, not with GPLv2-only; that is why the project is not "GPLv2".) LGPL libraries can be linked.
* GPL components here (espeak-ng, piper1-gpl, FFmpeg's GPL build) are either the same family as ACK or separate programs.
* Open items, each needing a decision rather than a quiet change: **the font** (section 1), **the two Play Services libraries**
  (section 2), **the base checkpoint's license** (section 5), and the **provenance of the images** (section 1).
* **Authorship note:** Freeform Studio and most recent changes were written with an AI coding assistant. No third-party code was
  copied in on purpose, and the only known derivation is the sherpa-onnx script credited in its own header, but similarity to
  existing code cannot be ruled out by anyone, and a maintainer should know that.
* **Translations:** the Spanish, Portuguese, Hindi, Arabic and Afrikaans texts under `app/src/main/res/values-*` were written by an AI assistant
  with no native speaker involved and not copied from any other app, dictionary or translation memory on purpose. They are drafts, each file says
  so at the top, and they have not been reviewed by a native speaker or a speech-language pathologist (`docs/TRANSLATIONS.md`).
