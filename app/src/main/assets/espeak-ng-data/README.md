# espeak-ng phonemization data (manual download required)

This folder needs to hold sherpa-onnx's `espeak-ng-data` directory -- the
phonemization data every Piper/VITS voice needs (language rules, not
anything specific to your own trained voice). It's shared and fixed
regardless of which voice is installed, so it ships once as a bundled app
asset rather than something the voice-import flow copies in per voice.

## Steps

1. Download any one of sherpa-onnx's released Piper voice packages -- it
   doesn't matter which language/voice, since `espeak-ng-data` inside it is
   the same shared bundle every one of their Piper packages ships. A
   small one is enough, e.g.:
   `https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2`
2. Extract it (`tar xjf vits-piper-en_US-amy-low.tar.bz2`), and find the
   `espeak-ng-data/` folder inside.
3. Copy the **contents** of that `espeak-ng-data/` folder directly into
   this folder (`app/src/main/assets/espeak-ng-data/`), so this README
   ends up sitting next to files like `en_dict`, `phontab`, `phonindex`,
   etc. -- not nested inside another `espeak-ng-data` subfolder.
4. You can discard the rest of that downloaded voice package (its `.onnx`/
   `.onnx.json` are not used -- your own trained voice, imported through
   ACK's Settings > Audio Architect screen, is what actually gets used).
5. This folder's contents (aside from this README) are intentionally
   excluded from git (`.gitignore`) -- it's third-party data, not source
   code, and every machine building ACK needs to repeat this one-time step
   rather than it living in the repo's history forever.

After copying the files in, rebuild in Android Studio.
