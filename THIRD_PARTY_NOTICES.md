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
  (section 2), **the base checkpoint's license** (section 5; the two starting voices ACK Voice Studio offers are in section 7), **NVIDIA's licence on the training environment** (section 7), and the **provenance of the images** (section 1).
* **Authorship note:** Freeform Studio and most recent changes were written with an AI coding assistant. No third-party code was
  copied in on purpose, and the only known derivation is the sherpa-onnx script credited in its own header, but similarity to
  existing code cannot be ruled out by anyone, and a maintainer should know that.
* **Translations:** the Spanish, Portuguese, Hindi, Arabic and Afrikaans texts under `app/src/main/res/values-*` were written by an AI assistant
  with no native speaker involved and not copied from any other app, dictionary or translation memory on purpose. They are drafts, each file says
  so at the top, and they have not been reviewed by a native speaker or a speech-language pathologist (`docs/TRANSLATIONS.md`).

## 7. ACK Voice Studio (`tools/voice_studio/`, being built: see `docs/VOICE_STUDIO_SETUP_PLAN.md`)

Planned dependencies of the guided setup, listed before they are used so that nothing arrives unlisted. Checked 2026-10-10. None of this
is shipped in the repository: the person's own computer installs or fetches it.

| Item | License | Checked | Note |
|---|---|---|---|
| GTK 4 and PyGObject (Ubuntu packages `gir1.2-gtk-4.0` and `python3-gi`), for the window | PyGObject: LGPL-2.1-or-later (PyPI classifier "LGPLv2+", license text is LGPL 2.1). GTK 4: LGPL-2.1-or-later | PyGObject: PyPI metadata. GTK: not verified | Installed by the person's own `apt`, not distributed by this project. LGPL libraries can be linked from GPL-3.0-or-later code. |
| segno (QR codes) | BSD (PyPI classifier "BSD License"; which BSD variant was not checked) | PyPI metadata | |
| cryptography (the phone-recording certificate authority) | Apache-2.0 OR BSD-3-Clause | PyPI metadata (license expression) | |
| sherpa-onnx (Python package, to check a finished voice on the PC with the engine the phone uses) | Apache-2.0 (PyPI: "Apache licensed, as found in the LICENSE file"; section 2 read its repository) | PyPI metadata | |
| The training stack (piper1-gpl, torch and the rest) | see section 5 and the lock's table below | PyPI metadata (training lock, 2026-10-10) | The guided setup pins exact versions; each pinned package is re-checked when the lock file is made. `studio.lock.txt` is not made yet. |

**The training environment's lock** (`tools/voice_studio/data/locks/training.lock.txt`, 91 packages, made 2026-10-11). Each package's licence was read from the package
site's own metadata for the exact pinned version (setuptools and wheel included); the licence *texts* were not read. Nothing is GPL-only or AGPL. The packages are installed by the person's own
computer from the package site; none is part of this repository.

| License (as the package states it) | Packages |
|---|---|
| MIT | attrs, audioread, charset-normalizer, coloredlogs, docstring_parser, filelock, humanfriendly, jsonargparse, onnxruntime, pathvalidate, platformdirs, pysilero_vad, PyYAML, setuptools, tensorboardX, triton, typeshed_client, urllib3 |
| MIT-0 | cffi |
| BSD-2-Clause / BSD-3-Clause / "BSD" | cloudpickle, decorator, fsspec, idna, Jinja2, joblib, Lazy-loader, Markdown, MarkupSafe, mpmath, networkx, numba, numpy, pooch, protobuf, pycparser, scikit-learn, scipy, soundfile, sympy, threadpoolctl, Werkzeug (numpy and scipy also bundle other permissive parts) |
| Apache-2.0 | absl-py, aiosignal, async-timeout, cuda-bindings, cuda-pathfinder, Cython, flatbuffers, frozenlist, grpcio, lightning, Lightning-utilities, ml_dtypes, msgpack, multidict, onnx, propcache, pytorch-lightning, requests, tensorboard, tensorboard-data-server, torchmetrics, yarl |
| Apache-2.0 AND MIT | aiohttp |
| Apache-2.0 OR BSD-2-Clause | packaging |
| BSD-2-Clause AND Apache-2.0 WITH LLVM-exception | llvmlite |
| torch's own expression | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| ISC | librosa |
| PSF-2.0 | aiohappyeyeballs, typing_extensions |
| MPL-2.0 | certifi; tqdm (MPL-2.0 AND MIT) |
| MIT-CMU | pillow |
| **GPL-3.0-or-later** | piper-tts 1.8.0, the trainer's published wheel (PyPI metadata and its `setup.py`; the wheel carries the compiled espeak-ng, also GPL-3.0-or-later, and g2pW-derived code under Apache-2.0, as section 5 says of its source) |
| **LGPL-2.1-or-later** | soxr (a dependency of librosa; the wheel carries the libsoxr library). Fine to link from GPL-3.0-or-later code; the person's computer installs it. |
| **NVIDIA proprietary, or no licence stated** | The 15 `nvidia-*` CUDA libraries (cuBLAS, cuDNN, NCCL, cuFFT, cuRAND, cuSOLVER, cuSPARSE, cuSPARSELt, NVSHMEM, NVTX, nvJitLink, cuFile, CUDA runtime, NVRTC, CUPTI) that `torch` needs, and the `cuda-toolkit` meta-package. Ten say proprietary (`LicenseRef-NVIDIA-Proprietary` or "NVIDIA Proprietary Software"); `nvidia-nvtx` says "Apache 2.0" but carries the proprietary classifier; `nvidia-cuda-runtime`, `nvidia-cudnn-cu13`, `nvidia-nccl-cu13`, `nvidia-nvshmem-cu13` and `cuda-toolkit` state nothing. **NVIDIA's licence text was not read** (not reachable from where this was checked). |

**One file of someone else's code is in this repository** (`tools/voice_studio/data/native/monotonic_align_core.pyx`, 1148 bytes, SHA-256 `8640b303683823a4a1259179547ef476999b1cbb2e46ff656b970763cfbc1157`). It is the
alignment code the trainer imports as `monotonic_align.core`, which the published wheel neither compiles nor ships. It is byte for byte `src/piper/train/vits/monotonic_align/core.pyx` of piper1-gpl at commit
`5b355b1` (checked by size and checksum on the developer's computer), so it is under that project's licence, GPL-3.0-or-later. The file carries no notice of its own; the algorithm comes from the VITS
project, which I believe is MIT-licensed (**not checked**: no way to reach it from where this was written). The tool compiles it on the person's computer (Cython and the computer's C compiler) and never changes it.

**Open item (a decision, not a quiet change):** the setup screen's agreement for the training environment does not yet say that it includes NVIDIA's CUDA libraries under NVIDIA's own licence
(plan: "NVIDIA's licence on the training environment"). The trainer's own source, `piper1-gpl`, is GPL-3.0-or-later (section 5) and is installed from its pinned archive, not from this lock.

**The two starting voices** (`rhasspy/piper-checkpoints`, `en/en_US`, medium quality, 22,050 Hz, 846 MB each). Fetched by the person after
a screen that shows this chain and asks; the project hosts, mirrors and sublicenses none of it (plan decision D27). This is not legal advice.

| Item | License | Checked | Note |
|---|---|---|---|
| `mike` | Its model card (read from the developer's screenshot, 2026-10-10): dataset OHF-Voice/voice-datasets, **CC0**. Fine-tuned from the lessac voice. | model card (screenshot) | The lessac chain below applies. |
| `amy` | Its model card: dataset MycroftAI/mimic3-voices, license listed only as "See URL". Fine-tuned from the lessac voice. | model card (screenshot); the linked license **not read** | The lessac chain below applies. |
| The lessac voice, and the Blizzard 2013 Lessac data behind it | **Not read here.** A separate review of the data's license, summarised by another session and **not verified**, reports: use limited to research and exploration, commercial use excluded, no redistribution, personal to the registered person and not sublicensable, revocable on written notice, Massachusetts law. Whether any of that reaches a model trained from the data is unsettled. | not verified | A voice trained from `mike` or `amy` carries this chain. A person using ACK to speak every day should decide for themselves whether their use is covered. |
