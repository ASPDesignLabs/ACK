# ACK Voice Studio: where we are (note for the next agent)

Written 2026-10-14 by the agent that built the installation flow, for whoever picks the work up next. `main` was at `a36f862` (PRs #64 and #65 merged).
Read this first, then `docs/VOICE_STUDIO_SETUP_PLAN.md` (the plan, every decision D1 to D40, every finding F1 to F34, every task VS-x.y with an "As built" note).
Everything under `tools/voice_studio/` is the tool; `tools/freeform_studio/` is the older server it reuses for processing recordings.

> **Update 2026-10-15 (the next agent's first session).** The preview is **built and tested in the sandbox, not yet heard on a real computer**: `python3 -m voice_studio.voicefile listen`,
> plan task VS-5.4, evidence F35, choices P15, checklist section I8 (part B decides how it plays). The studio environment's lock gained sherpa-onnx, so the studio programs build again beside
> the old ones. **Refresh is defined** (D41, task VS-6.6): a reinstall that does not wipe data, with a check way and a full-rebuild way; it is not built. The window does not offer to listen
> yet (a button on the Voice file page, and listening to a round without writing a zip, are the next slice). The four open questions about the preview are in the plan's "Still open".
> A test-hygiene fix (F36) made the whole suite green under `-W error`; one Freeform Studio test still fails on Python 3.13 for an unrelated reason (also F36).
>
> **Update 2026-10-15 (second slice, after the developer's answers).** `listen` now also (a) **writes down what the computer heard** in each sound and shows it under the sentence, as a hint and never a
> verdict (task VS-5.5; `hear_runner.py`, `core/heardcheck.py`; English voices only; needs the listening model that `recordings model` fetches, and says so and goes on when it is missing), and (b) can
> **listen straight to a round with no zip file** (`--round chosen` or a number): it makes the voice in the new listening folder with the same three steps as `make`, then asks whether to remove the
> large voice copy (only a yes removes it, only by exact names). The developer's answers are recorded as D42 (three sentences kept; show what was heard; no offer at the end of `make`). **Checklist
> I8 parts D and E are new and not yet run on a real computer**; the real listening model heard the sandbox's real clips word for word, offline.

**What the developer wants next (two things; the first is now built, see the update above):**

1. **Preview voices on the PC before exporting.** Hear the trained voice say test sentences on the computer, so a round can be judged (and the voice file checked by ear)
   before it is sent to the phone.
2. **A full GUI flow for install, update, refresh and uninstall, on Windows and on Ubuntu.** Today these are commands and guides, not screens.

Details, what already exists to build on, and the open questions for each are in sections 3 and 4.

---

## 1. Who you are working with, and the rules they hold

The developer is autistic, uses the tools they are building every day, and builds them to close accessibility gaps. Their standing preference is
**"Backups should be encouraged, edits need to be confirmed."** In practice that has meant:

- **Ask before changing anything of theirs, and before any download.** Every flow shows what it will do, asks once, and does nothing on "no", on Enter, or when nobody can be asked.
  Uninstall and delete ask twice and name a backup first. Restore and copy-in only ever add.
- **Plain words.** Nothing a person reads is jargon. Every sentence a person sees is in the text catalog (`data/text/en.json`) or, for the two install scripts, in the script itself;
  none is built from pieces in code. A language pass was done with the developer; new wording is shown to them before it is applied.
- **Give them one command block at a time, to run in their own terminal, and ask for the output pasted as text.** They run it, paste what happened, and you go from there.
- **Say exactly what was and was not seen.** The sandbox you work in has no Windows, no WSL, no GPU, no phone and no display. The plan and the checklist keep "built and tested in the
  sandbox" and "seen on a real computer" apart on purpose; keep doing that. Three bugs found on 2026-10-12 (F31, F33, F34) were invisible to every sandbox test.
- **No pull request unless they ask.** They merge themselves. After a merge, restart your branch from the new `main`.

## 2. Where the install flow stands

**Proved on a real computer (the developer's own: Windows build 26200, Windows PowerShell 5.1, WSL 2 with Ubuntu 24.04 already installed, RTX 4060, 2026-10-12):**

- `irm <address of install.ps1> | iex` in an ordinary PowerShell looks at the computer, finds Ubuntu, hands over to Ubuntu (password prompt and questions appear in the PowerShell window),
  does the Ubuntu steps, and **opens the Voice Studio window on its own**. PowerShell stays busy while the window is open. **Closing only the PowerShell window closes the Voice Studio window at once**,
  so PowerShell must stay attached (this is the design, not a bug).
- `get.sh` reuses a copy already at `~/ack-tools`. Since F34 it compares that copy with the release asked for and **asks** before running `git pull --ff-only`.
- The tool itself (recordings, rounds, voice file, free-up-space, display) has run on the developer's Ubuntu 22.04 and 24.04 under WSL. The window was run on WSLg (checklist I5).

**Built and tested only in the sandbox, never run on a real computer:**

- The `wsl --install` path (a Windows with no WSL), the restart it needs, and Ubuntu's first-run user creation. (Checklist I7 section A.)
- Native Ubuntu 22.04 and 24.04 desktops, Orca, and any screen reader under WSLg. (I7 section C; plan VS-0.1.)
- The no-`sudo` Windows Start-menu shortcut (F27) and whether it behaves like the install flow when closed.
- Timings of every step. Whether closing PowerShell also closes the window on a clean Windows.

**The pieces, in the order a person meets them:**

| Piece | File | What it does |
|---|---|---|
| Windows helper | `tools/voice_studio/install.ps1` | Looks (Windows build, Nvidia driver, free room), finds or offers Ubuntu, hands over, opens the window. Exit codes 0 done, 1 could not, 2 nothing done, 3 "a step is left for you, then run the same command again". |
| Ubuntu entry | `tools/voice_studio/get.sh` | Fetches ACK with `git clone --depth 1 --branch <release>` into `~/ack-tools` (asks before installing `git`), offers an update to an existing copy, hands over to `setup.sh`. |
| Guided setup | `core/guided_flow.py`, `core/setup_flow.py`, `core/buildenv_flow.py` | `python3 -m voice_studio`: Ubuntu packages, then the studio programs, then the training programs, then the window. Each is asked first, skippable, and safe to repeat. `--no-window` is what `install.ps1` passes. |
| The window | `window/` (GTK edge), `core/windowmodel.py`, `core/windowio.py` (plain Python) | Pages today: Projects, Recordings, Rounds, Voice file, Free up space, Display. It runs the same flows as the terminal through `windowio.ChannelIO` and `Services.run`. |
| Launcher | `core/launcher.py`, `core/winshortcut.py`, `core/windowcli.py` | `python3 -m voice_studio.window --install-launcher / --remove-launcher`: a menu entry on the Linux side and a Start-menu shortcut on the Windows side. |
| Guides | `docs/ACK_Voice_Studio_Installation_Guide.MD` (Windows), `..._Ubuntu.MD` | Standalone; **held to the code by tests** (see section 5). |
| Checklist | `docs/VOICE_STUDIO_DEVICE_TEST.md` section I7 | What to run on a clean Windows and a native Ubuntu, and what to write down. |

Where things live on the person's computer: `~/ack-voice-studio/` holds `projects/` (precious), `tool/` (downloads and the two Python environments: rebuildable), `state/` (consent record, settings),
`backups/`. The code is the git copy at `~/ack-tools`. The two must never be treated as one (see 4B).

## 3. Preview voices on the PC before export

**What exists.** The chain up to a finished file is built and tested: `core/commands.py` has `export_command` (checkpoint to `.onnx`, through the training environment's launcher so the
`dynamo=False` workaround applies), `copy_config` (the settings file placed as `<model>.onnx.json`, never replacing a file) and `patch_command` (the repository's own
`tools/patch_voice_for_sherpa_onnx.py`). `python3 -m voice_studio.voicefile make` runs all of it, then `core/voicezip.py` checks the voice against **ACK's import rules on the PC** and writes
`my_voice_backup.zip`. That check reads the model's metadata without running it. **No audio is ever produced on the PC.** A voice that passes can still fail on the phone.

**What is missing, all of it:**

- **A speech engine on the PC.** The plan (VS-2.7) says: synthesize three test sentences with sherpa-onnx and play them, "what you hear is what the phone will say". **sherpa-onnx is in no lock file**;
  where it lives (the training environment, the studio environment, or one of its own) is an **open decision** noted under VS-0.2 and VS-5.2. Adding it means a new pinned, hashed lock entry,
  a line in `THIRD_PARTY_NOTICES.md` saying how its license was checked (a test fails otherwise), and the size in the setup plan the person agrees to.
- **Playing a sound.** "Playing a `.wav` from WSLg" is an unchecked item on the VS-0.1 findings list. Nobody has heard anything from the window yet. Decide whether to play from the Linux side
  (WSLg's audio) or hand the file to Windows, and test it on the real computer before building on it.
- **The screens.** D12 says a round "makes a short test clip from the latest checkpoint; the helper chooses *sounds good*, *another round* or *go back to the previous round*". The Rounds page
  lets a person choose a round, go back to an earlier one and start another, but has nothing to listen to. The Voice file page should offer to listen before it writes the zip.

**Rules that make a preview honest (from `CLAUDE.md`, "The CUSTOM TRAINED VOICE system" at the repository root; read that section before writing any synthesis code):**

- The phone's engine is sherpa-onnx with a `tokens.txt` it generates from the config's `phoneme_id_map`, **dropping the `"\n"` symbol and every symbol that is not exactly one Unicode codepoint**.
  A PC preview that tokenizes any other way would say something different from the phone. Reuse the same rule, and add a test that reads the Kotlin (`PiperVoiceEngine.generateTokensFile`) the way
  `tests/test_vs_voicezip_contract.py` already reads ACK's other limits.
- The `.onnx` must be the **patched** one, and it must be the very file that goes into the zip.
- **Never send speech markup (SSML) to the custom voice.** It does not parse it.
- The phone ships the `espeak-ng-data` phonemization folder as a separate asset. Check whether the PC package carries it or needs it supplied, and account for its license (GPL-3.0-or-later) in the notices.
- Nothing leaves the computer: no network, no upload, no "share" step. The sentences are fixed by the tool; a person's own sentence is shown exactly as typed and never logged.

**Open questions for the developer** (do not decide these for them): *answered 2026-10-15 (D42):* the three sentences stay, the preview does not play at the end of `make`, and the visual aid is the words the
computer heard. *Still open:* where the test clips are kept and how long (they are small, rebuildable and disposable; today they stay under the project's scratch place and the tool never deletes them), and the
round-mode voice copy is the one large thing the tool now offers to delete on a yes.

## 4. A full GUI flow for install, update, refresh and uninstall

**What exists today, by action:**

| Action | Today | Planned (the plan already says how) |
|---|---|---|
| Install | The two scripts and the guided setup above. Terminal and PowerShell text, no screens. | Plan D40, VS-7.x. |
| Update | By hand: `cd ~/ack-tools && git pull`, then `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio` (Ubuntu guide section 8, Windows guide section 9). `get.sh` offers the pull when it is re-run. | **VS-6.2:** a button that asks before contacting the internet, fetches a tagged release, **shows what changes**, builds the new environments beside the old ones and **switches only after the self-test passes**. Never automatic (P4, D11). |
| Refresh | Not defined anywhere. The nearest things: re-running the guided setup (it finds what is done and carries on), and the environment builder, which finds broken links, replaces only those and keeps installed packages. | **Ask the developer what "refresh" means before building it.** My reading is "check everything and repair what is wrong, without a full update", but it is a guess. |
| Uninstall | By hand, and dangerous as written: the guides say to delete `ack-tools` and `ack-voice-studio`, and the second holds the person's projects and recordings. | **VS-6.3, P5:** removes the tool and its environments only; **a project is never deleted by it**. Deleting a person's data is a separate action that asks twice, names a backup first, and is driven by a storage catalogue with a test that fails if a new folder is in no area (the Android app's `StorageCatalogue` idea). Each area is marked precious, rebuildable or disposable (P11). |

Stage 6 (backup, update, uninstall, delete) is **Not started** in the plan's progress table, and VS-6.1 (a checked backup before changes, outside OneDrive and Documents) should come first:
every other action in this section asks the person to back up first.

**The structural problem to put to the developer before building anything:** the window is a GTK program that runs *inside* Ubuntu. It cannot be the screen for the *first* install on a computer
that has no Ubuntu, no Python GTK bindings, or no copy of the tool. So "a full GUI flow" is really two different things:

- **(a) Everything after the first install, inside the window** (a Tool or Maintenance page: install what is missing, update, refresh, uninstall, with the same ask-first, show-what-changes,
  back-up-first pattern as the other pages). The window already runs the terminal flows through `windowio`, so this is the lower-risk part and testable in the sandbox as plain Python.
- **(b) The very first install as a screen on Windows**, before Ubuntu exists. Windows PowerShell 5.1 can show Windows Forms dialogs, but that is a separate accessibility surface from the GTK
  window, with its own screen-reader behaviour to test, and `install.ps1` is built around a script that works when piped into `iex`. On native Ubuntu the first install happens in a terminal,
  or from a desktop launcher that calls the same command.

My suggestion, to be confirmed with the developer: build (a) first; keep the first install as the guided, ask-first text flow (it just worked end to end); decide on (b) once (a) exists and the
developer has said how much they want a Windows-native screen. Do not assume either.

**Windows specifics to respect:**

- The tool runs in Ubuntu under WSL; "uninstall on Windows" means the tool and its Start-menu shortcut, not Ubuntu or WSL. **Never call `wsl --unregister`**, which destroys a whole Ubuntu and
  everything in it; if the person wants Ubuntu gone, say how and let them do it.
- `install.ps1` must stay valid **Windows PowerShell 5.1** (the developer runs 5.1.26100): ASCII only, no newer syntax, no `exit` when piped into `iex`, options through `ACK_VOICE_*` settings.
  **A native program called inside a PowerShell function has its output captured into the function's result and gets no console** (this was F33): start it with
  `Start-Process -NoNewWindow -Wait -PassThru` as `Invoke-AckVsWslLive` does.
- WSL stops an Ubuntu that has no Windows-attached session about a minute after the last one ends, and the window dies with the session that opened it. Anything that starts the window must
  keep a session attached (`install.ps1` does; whether the Start-menu shortcut does has not been checked on a real computer).

## 5. Rules in the code that tests enforce

You will meet these as failing tests; knowing them saves time.

- **`core/` is plain Python: no GUI toolkit, no network, no program started** (`test_vs_package_rules.py`). Only `core/system.py`, `core/fetch.py`, `core/jobs.py` and `core/jobrunner.py` may start
  programs; only `core/fetch.py` may touch the network, and only after the person agrees; web addresses are allowed only in `data/sources.json` and `get.sh` (`test_vs_network_rules.py`;
  `install.ps1` has its own tests). The GTK edge in `window/` stays thin: decisions go in `core/`, tested without a display. **GTK 4.6 is the floor** (Ubuntu 22.04): no `Gtk.FileDialog`.
- **Words:** sentences come from the catalog by key; a sentence never ends in a space, and the catalog lints for shouted words. The two scripts keep their sentences in the script.
- **The guides are held to the code.** `test_vs_install_guides.py` checks that every command a guide shows is real, every option exists, every quoted sentence or button name is one the tool says
  (the catalog, `install.ps1`'s text table, and the `say`/`ask`/`ask_person` lines of `get.sh` and `setup.sh`), and every number matches. `test_vs_device_test_doc.py` runs the checklist's snippets.
  **Changing a sentence in code means changing the guide, the checklist and the test that pins it, together.**
- **License:** every source file (`.py .sh .ps1 .kt ...`) starts with `SPDX-License-Identifier: GPL-3.0-or-later`; every outside source goes in `THIRD_PARTY_NOTICES.md` with how its license was
  checked ("not verified" is stated, never guessed). The project is GPL-3.0-or-later.
- **Data sovereignty:** recordings, transcripts, models and previews stay on the person's computer. See `docs/DATA_SOVEREIGNTY.md` and the "DATA SOVEREIGNTY and LICENSING" section of `CLAUDE.md`.

## 6. How to run and prove things

- Tests: `cd tools && ACK_VS_PWSH=<path to pwsh> PYTHONPATH=. python3 -m pytest voice_studio/tests -q -W error` (or `voice_studio/run_tests.sh`). The tests for `install.ps1` call real PowerShell and are
  **skipped without it**; install `pwsh` (or point `ACK_VS_PWSH` at one) or you are not testing the Windows helper at all. The window's GTK tour needs GTK 4.6 typelibs and Xvfb
  (`window/selftest.py`, see "How the GTK edge is tested" in the plan).
- **Test the real function, not only a stand-in for it.** F33 slipped through 168 tests because every test replaced the function that starts `wsl.exe`. Every function that talks to the outside
  (starts a program, reads the machine) now has at least one test that runs it for real against a stub program on the path (`with_stub_wsl` in `test_vs_install_ps1.py`, the git stand-ins in `test_vs_scripts.py`).
- **Break your own code on purpose** (mutation testing). The earlier work did this for every real rule: copy the tree, change one comparison or drop one check, and confirm a test fails. The ones
  that survive show a missing test. The scripts used in this session lived in a scratch folder and are not in the repository; the idea is a loop over (name, old text, new text) edits.
- Sandbox notes: no Windows, WSL, GPU, phone, display or Android SDK. In the sandbox this was written in, a regular file stood where `/dev/null` should be and a stray `/abs.wav` existed: sandbox-only oddities, not tool bugs. Check yours.

## 7. Git and the current state of the branch

- `claude/voice-studio-guided-setup` is the development branch for this work. PRs #64 and #65 from it are merged, so **restart it from the latest `main`**
  (`git fetch origin main && git checkout -B claude/voice-studio-guided-setup origin/main`) before adding anything. Do not stack commits on merged history.
- The one-command installers fetch **`main`** by default. A fix reaches a user only after it is merged; to try an unmerged branch on a real computer, set `ACK_VOICE_TAG` to the branch name and
  fetch `install.ps1` from that branch's address (the developer did this twice on 2026-10-12; the introduction to checklist section I7 says how, and the block is simple: set `ACK_VOICE_TAG`, run the `irm ... | iex` line with the branch name in the address, remove the setting).
- Commit messages in this work are plain prose describing the cause, the change and what was proved; the session trailers are added by whatever instructions the session was given.

## 8. Where to read next

| Question | Read |
|---|---|
| Why is it built this way? | `docs/VOICE_STUDIO_SETUP_PLAN.md`: section 6 (decisions D1 to D40), the proposed defaults P1 to P14, the findings F1 to F34 |
| What is built, what is tested, what is not | the plan's Progress table and each task's "As built" note |
| What an IT person needs to approve | `docs/VOICE_STUDIO_IT_GUIDE.md` |
| What the developer has to run and write down | `docs/VOICE_STUDIO_DEVICE_TEST.md` (section I7 is the install; J is the voice file; I5 is the window) |
| What a person following the guide sees | the two `docs/ACK_Voice_Studio_Installation_Guide*.MD` |
| Rules for the Android side that the voice file must satisfy | `CLAUDE.md` at the repository root, "The CUSTOM TRAINED VOICE system" and "DATA SOVEREIGNTY and LICENSING" |
