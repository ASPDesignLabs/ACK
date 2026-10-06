# Clinical use (Section 5): checking it on a real phone

This list grows with each task in `docs/CLINICAL_USE_PLAN.md`. Today it holds one part: **A. The limits statement (C4)**.

The limits statement was built and tested **without an Android SDK or a phone**. What is tested is the plain-Kotlin part: the words in all six
languages, that the first two sentences match the website, and where the banner may and may not appear (`tools/kotlin_check/run_unit_tests.sh`
passes). The Android files were type-checked and syntax-checked (`run_typecheck.sh`, `run_syntax_check.sh`). **What was never run is the Android
part**: the build, how the banner and the section look and behave, and what a real phone does at a large font. This list is for you to work through
once. Each line is *do this → expect that*. If something does not match, say which line and what you saw.

Use a debug build with sample data. Make a backup first anyway (PROTOCOL → DATA PORT → EXPORT .JSON). Nothing here is timed; stop whenever you like.

## A. The limits statement (ABOUT ACK and the one-time banner)

- [ ] Build `:app` in Android Studio and run `./gradlew :app:testDebugUnitTest`. → Both succeed. If the build fails, copy the first red error: the Kotlin
  for `ui/LimitsNoticeBanner.kt`, `settings/AboutSection.kt` and the two edits in `MainActivity.kt` and `SettingsView.kt` was never compiled against the
  real Android libraries.
- [ ] `git diff` the manifests. → No permission was added.
- [ ] Start from a state where the banner has not been dismissed (a new install, or PROTOCOL → DATA PORT → DELETE DATA → SETTINGS). Open ACK. → It opens
  on the TERMINAL. A bordered banner sits above the header with three sentences (NOT A SUBSTITUTE FOR PROFESSIONAL AAC EVALUATION OR SPEECH-LANGUAGE
  THERAPY. / BUILT BY ONE PERSON AS A PERSONAL TOOL, SHARED AS-IS. / KEEP ANOTHER WAY TO COMMUNICATE AVAILABLE AT ALL TIMES.), a grey line saying where to
  read it again, and a **GOT IT** button.
- [ ] Look at the grey line. → It names the SETTINGS button the way the header does (PROTOCOL; SETTINGS once PLAIN WORDS is on) and says ABOUT ACK.
- [ ] Set the phone's font size and display size to the largest. → All the banner's text can be read and GOT IT can be reached. **Write down if the banner
  leaves too little room for the Terminal below it**; that is a layout question this plan has not answered.
- [ ] Open a deck (Matrix), then Quick Actions, then Emergency, then TYPE, AUDIO and TARGETS. → **No banner on any of them.** Open SETTINGS again. → It is there.
- [ ] With the banner showing, send a message from the Terminal prompt and from a deck button. → It speaks and shows as usual. The banner changes nothing about it.
- [ ] Tap **GOT IT**. → The banner goes. Nothing else changes (no toast, no screen change, no new Terminal line). Close ACK completely and reopen it. → The
  banner stays gone.
- [ ] PROTOCOL → scroll to the very end. → **ABOUT ACK** with the same three sentences and no buttons or switches.
- [ ] Turn PLAIN WORDS on and off. → Nothing in ABOUT ACK changes (it has no labels). The banner's grey line, if you bring the banner back, follows the button name.
- [ ] PROTOCOL → DATA PORT → DELETE DATA → SETTINGS (confirm it). → After ACK restarts, the banner shows once more, and GOT IT hides it again.
- [ ] Choose Spanish, then Arabic, in the LANGUAGE control (and bring the banner back as above). → The three sentences and GOT IT are in that language, in
  capitals for Spanish. In Arabic the layout is mirrored and nothing is clipped. **These are drafts no native speaker has read.** Say what reads wrongly.
- [ ] Lock the phone and play a message with the watch or a widget. → Nothing about the lock-screen or watch behaviour is different.

### Optional: look at the stored note (debug build only; these adb lines were written from the code and have not been run)

- [ ] `adb shell run-as com.example.besu cat shared_prefs/ack_assist_prefs.xml` before tapping GOT IT. → No `limits_notice_seen` line.
- [ ] The same after tapping GOT IT. → `<boolean name="limits_notice_seen" value="true" />`.
- [ ] `adb shell run-as com.example.besu cat shared_prefs/ack_assist_prefs.xml` on a freshly installed build. → The note is not there (nothing seeds it).
