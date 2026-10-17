# ACK Voice Studio: where we are (note for the next agent)

Written 2026-10-14 by the agent that built the installation flow, for whoever picks the work up next. `main` was at `a36f862` (PRs #64 and #65 merged).
Read this first, then `docs/VOICE_STUDIO_SETUP_PLAN.md` (the plan, every decision D1 to D40, every finding F1 to F34, every task VS-x.y with an "As built" note).
Everything under `tools/voice_studio/` is the tool; `tools/freeform_studio/` is the older server it reuses for processing recordings.

> **Update 2026-10-15 (the next agent's first session).** The preview is **built and tested in the sandbox, not yet heard on a real computer**: `python3 -m voice_studio.voicefile listen`,
> plan task VS-5.4, evidence F35, choices P15, checklist section I8 (part B decides how it plays). The studio environment's lock gained sherpa-onnx, so the studio programs build again beside
> the old ones. **Refresh is defined** (D41, task VS-6.6): a reinstall that does not wipe data, with a check way and a full-rebuild way; it is not built. The window did not offer to listen
> then (it does now: the Hear the voice page, see the last update below). The four open questions about the preview are in the plan's "Still open".
> A test-hygiene fix (F36) made the whole suite green under `-W error`; one Freeform Studio test still fails on Python 3.13 for an unrelated reason (also F36).
>
> **Update 2026-10-15 (second slice, after the developer's answers).** `listen` now also (a) **writes down what the computer heard** in each sound and shows it under the sentence, as a hint and never a
> verdict (task VS-5.5; `hear_runner.py`, `core/heardcheck.py`; English voices only; needs the listening model that `recordings model` fetches, and says so and goes on when it is missing), and (b) can
> **listen straight to a round with no zip file** (`--round chosen` or a number): it makes the voice in the new listening folder with the same three steps as `make`, then asks whether to remove the
> large voice copy (only a yes removes it, only by exact names). The developer's answers are recorded as D42 (three sentences kept; show what was heard; no offer at the end of `make`). **Checklist
> I8 parts D and E are new and not yet run on a real computer**; the real listening model heard the sandbox's real clips word for word, offline.
>
> **Then (third slice, D43, task VS-5.6):** the test clips moved out of scratch into the project's own `listening` folder (grouped by the round or voice file they came from), and Free up space (terminal and
> window) now offers them and the `--round` voice copies: `rounds free --clips N` / `--copies N` / `--all`. The end-of-run question about the voice copy stays. A listening 30 days old or older gets a notice
> (in `rounds free`, before `listen`'s plan, and at the top of the window page) and `rounds free --old` takes them all after asking; nothing is ever removed on its own.
>
> **Then (Stage 6 begins, 2026-10-16; task VS-6.1, decision P17):** **Backup now is built and tested in the sandbox, never run on a real computer**: `python3 -m voice_studio.backup now | list | verify | restore`,
> checklist section I9. `core/areas.py` is the first piece of the storage catalogue (VS-6.3): every folder the tool makes is in an area with a kind (precious, rebuildable, disposable, the tool's own) and whether a
> backup holds it; a test fails when a path the tool names is in no area. `core/projectbackup.py` writes one plain `.tar` of the precious part of one project (never scratch, the test sounds, older saved points or the
> tool's programs), reads it back in full before it counts, and never replaces or removes an earlier backup; restore only adds what is missing. A one-line reminder is printed by `rounds start` and after
> `recordings import`. The window can run the command by name (`windowmodel.TOOLS`) and, since the update at the end of this block, has a Backup page. Everything about it that was decided without asking is in P17 ("veto any"). **Next in
> Stage 6:** VS-6.2 Update, VS-6.3 Uninstall and delete (the delete questions should name a backup first, now that one exists), VS-6.4 problem report, VS-6.5 move scratch, VS-6.6 Refresh (needs VS-6.1, now there).
>
> **Then (2026-10-16; task VS-6.6, decision P18):** **Refresh is built and tested in the sandbox, never run on a real computer**: `python3 -m voice_studio.refresh check | repair | rebuild | older`, checklist section I10. `check` looks at the programs (their record, and their own self-test run again without writing anything), the downloaded files byte for byte, and four small notes; `repair` mends only what it found; `rebuild` builds a second whole copy of a set of programs beside the one in use. That needed one change in the builder: a **generation number** (`core/envgen.py`, `state/environments.json`) that goes into an environment folder's name, so the same inputs can have a second folder; generation 0 adds nothing, so no existing folder is renamed, and the number is only raised after the new copy passes its self-test. `older` lists and removes the copies no longer in use (a typed yes; never while a task runs). The window can run the command by name (it has a Check the tool page since the last update below); the menu entry and the system packages are not covered (the first setup step and `--install-launcher` already show and ask). **Next in Stage 6:** the rest of VS-6.3 (uninstall, delete the whole data folder), VS-6.5 move scratch, VS-6.2 Update (which would end in a refresh), VS-6.4 problem report.
>
> **Then (2026-10-16; task VS-6.3, decision P19):** **Uninstall is built and tested in the sandbox, never run on a real computer**: `python3 -m voice_studio.uninstall show | remove`, checklist section I11. `show` lists the programs and downloaded files an uninstall would remove, and what it keeps (the projects, the backups, the starting voices, the small notes), and changes nothing; `remove` shows the same list, asks once and removes only what it showed, never while a task is running. It cannot remove the folder it runs from or the menu entry, so it prints the commands for both. Both installation guides' "Removing" paragraphs now say this. There is still no command that deletes every project at once (`projects delete` is per project, with two questions and a backup named first); that is an open question in P19. **Next in Stage 6:** VS-6.5 move scratch, VS-6.2 Update (which would end in a refresh), VS-6.4 problem report, and the window pages for Backup, Refresh and Listen.
>
> **Then (2026-10-16; task VS-6.5, decision P20):** **Move scratch is built and tested in the sandbox, never run on a real computer or on a second drive**: `python3 -m voice_studio.scratch show | move`, checklist section I12. `move --to FOLDER` (or `--default`) checks the new place with the rules written for a new project (first used by a terminal here), copies every file and reads each back, checks the whole copy, switches the project's record to it only then, and asks separately before removing the old place. A failure at any step leaves the project on the old place and the same command carries on. Not in the window. **Next in Stage 6:** VS-6.2 Update (which would end in a refresh) and VS-6.4 problem report; and the window pages for Backup, Refresh and Listen.

> **Then (2026-10-16; task VS-6.2, decision P21):** **Update is built and tested in the sandbox, never run on a real computer or over a real connection**: `python3 -m voice_studio.update check | get RELEASE`, checklist section I13. A release is a git tag **whose name begins with `voice-studio-`** (the repository already holds the phone app's tags `v1.0-beta.1` to `v1.0-beta.7`, which are not releases of this tool and are left out; an earlier version of this note, the guides and the code wrongly said ACK had no tags at all and would have listed them, corrected before any release), and **no such tag exists yet**, so against the real address `check` says there is nothing to fetch (and `get.sh` still installs `main`, which `check` calls "not at a release"). Both commands say first what they will ask github.com, show the exact git commands and ask (a typed yes, or `--yes`); nothing is checked in the background. `get` fetches one release into a new folder beside the running copy, checks the commit and the package file, compares the two copies by area (lists of programs, download list, words on screen, recording tool, code, guides) and prints the commands to try the new copy and to switch to it (two `mv`); the tool cannot replace the folder it runs from, so the switch is left to the person. The address is in `data/sources.json` under `releases`; `fetch.run_networked` now also sets `GIT_TERMINAL_PROMPT=0`. Not in the window. The IT guide's network table, §7 and §11, both installation guides' "Updating" paragraphs and their "what it contacts" tables say this. **Next in Stage 6:** VS-6.4 problem report; and the window pages for Backup, Refresh, Listen and Update.

> **Then (2026-10-16; task VS-6.4, decision P22):** **The problem report is built and tested in the sandbox, never run on a real computer**: `python3 -m voice_studio.report show | save --to FILE`, checklist section I14. It is the report builder of VS-1.8 (names and folders blanked, no place for a recording or a phrase) wired to a command: `show` prints all of it and changes nothing; `save` prints it, asks, and writes exactly that text to the one file named (no folder made, no file replaced without `--replace`, owner-only, read back). Any command that fails after it began now ends with two lines pointing at it (a decorator, `reports_failures`, on every command's `main`), naming the problem only when exactly one was told. Not in the window then (it is now). **Stage 6 is now built in the sandbox, each task never run on a real computer.** **Next then:** the window pages for Backup, Refresh, Update, Report and Listen (built since, see the last update below), and the checklist sections I9 to I14 on a real computer.

> **Then (2026-10-16; Stage 8, decision P23):** **The documents and the release steps are written and held to the code by tests, in the sandbox; no real beginner or helper has read the guide or the handout yet, and no release has been made.** `docs/VOICE_STUDIO_GUIDE.md` and `docs/VOICE_STUDIO_HELPER_HANDOUT.md` (`test_vs_guide.py`); the two manual-route guides open with a note saying so; `DATA_SOVEREIGNTY.md` has rows for the tool (`test_vs_data_sovereignty_doc.py`); `THIRD_PARTY_NOTICES.md` section 7 gained rows for `git` and the build tools (read from the packages' copyright files on Ubuntu 24.04 only; `test_vs_notices.py`); the tool has its own `tools/voice_studio/CHANGELOG.md` (`test_vs_changelog.py`; the app's `CHANGELOG.md` is untouched); `CLAUDE.md` has an added section "ACK VOICE STUDIO — rules that must stay true" (`test_vs_claude_md.py`); the checklist has a contents table (`test_vs_device_test_contents.py`); and `docs/VOICE_STUDIO_RELEASE_RUNBOOK.md` says how to cut `voice-studio-vX.Y.Z` (`test_vs_release_runbook.py`, and `test_vs_release_ready.py`, which names what still disagrees with a tag when you run it with `ACK_VOICE_RELEASE=voice-studio-vX.Y.Z`). **Corrected on the way:** the update command had counted the phone app's tags as releases (see the P21 paragraph above); dates written as 2026-10-17 in the plan and this file were the day after the work, and are fixed. **Not done:** VS-8.7 (skipped on purpose), VS-8.8 (yours: Amy's licence), the first release (wait for real runs of the checklist; see P23), and the window pages for Backup, Refresh, Update, Report and Listen.

> **Then (2026-10-16; task VS-6.7, decision P24):** **The window has pages for the tools, built and tested in the sandbox, never run on WSLg or a native desktop, with a mouse, over a real connection, through a speaker or with a screen reader**: Hear the voice, Backup, Check the tool, Updates and Problem report (eleven pages in all, `windowmodel.PAGES`; the sidebar scrolls at the default window size), checklist section I15. Each is the face of a command (`voicefile listen`, `backup`, `refresh`, `update`, `report`): a button hands the command's own arguments to `Services.run`, so the plan and the question are the terminal's own words, asked with Yes and No buttons (No holds the focus). A form appears only where a value is needed: a folder, a backup file, a release, a set of programs, and the folder and name of a saved report (shown in the form with every problem, nothing chosen is lost, then the command's own question). A task that fails after it began offers `Make a problem report…`, which goes to the Problem report page. Nothing runs by itself or on a timer. **Network:** the pages that can lead to the internet are Updates and, on Check the tool, the buttons that mend or build fresh; each only after the command says what it will ask for and you say yes (an earlier line of the checklist said Updates alone, and was corrected). The tour (`window/selftest_tools.py`) passes under GTK 4.14 and in a copy of Ubuntu 22.04 (GTK 4.6.9); the headless file chooser cannot be made to hand back a folder, so the tour gives the page what the chooser would. **Next:** the checklist sections I9 to I15 on a real computer, then a page for getting a starting voice (still typed, `voices get`), sending recordings over Wi-Fi, and the recording paths for helpers.

> **Then (2026-10-16; tasks VS-3.5 and VS-5.1, decision P25):** **Sending the finished voice file to the phone over Wi-Fi is built and tested in the sandbox, never run on a real network, a phone or a terminal that draws the code**: `python3 -m voice_studio.voicefile send [--folder NAME] [--address IP] [--port N]`, checklist section I16. **It is the first and only place the tool listens for a connection**, and the rule that follows is in `CLAUDE.md`: only `core/lansend.py` may listen (imports `socket` and `ssl` only, never dials, binds once to the one home-network address, one file, one time, ten minutes at most, a random 22-character secret in the address; `test_vs_network_rules.py` reads the source), so every sentence elsewhere that said the tool "opens no listening port" now says "except during `voicefile send`" (the IT guide, the data-sovereignty page, the checklist; their tests read the code). The order in `core/voicesend_flow.py` is fixed: pick the voice file and re-verify it with the phone's own rules, the certificate (the first time it only makes the certificate file for the phone and **stops**), the address (`core/lanaddress.py`: the one real home-network address from `ip`, or `--address`), the plan and one question, then listen, show the address and a QR code (`core/qrcode.py`, pure Python, drawn only when `io.ansi` is true), and end by itself. `core/phonecert.py` makes the certificates with the computer's own `openssl`: **an authority limited by name constraints to the three home-network ranges and one impossible name** (so a changed address needs nothing on the phone, which settles the VS-0.3 inconsistency; kept in `state/phone-certificate/`, never replaced, not in any backup) and a seven-day certificate for one address, made for each send and removed afterwards. **Not confirmed on a phone: that Android enforces the name constraints, the real menu words for installing the file, that the code scans, and the network under WSL (VS-3.6 is not built; the plan carries a note when it runs under WSL).** The window has no page for sending yet (`ChannelIO.ansi` is false, so it would show the address only). Everything decided without asking is in P25 ("veto any"). **Tests:** 351 in the five new files; every one-line break of the new code was tried (1,206, then 1,183 after the fixes) and each survivor was closed or proved equivalent (the list is in the plan, VS-5.1); the whole suite was 5,807 passed, 178 skipped. A full suite run found two things the new files' own tests did not: a `$` at the end of the listener's file-name pattern (`\Z` now; a name with a trailing line break was accepted) and a test of the options each voicefile command publishes. **Next:** the checklist's real runs (I16 first), then VS-3.6, a window page for sending, and the rest of Stage 3.

> **Then (2026-10-17; task VS-3.6 and the F3 part of VS-4.4, decision P26):** **Help for Ubuntu under Windows is built and tested in the sandbox against a pretend Windows drive, never run on a real Windows computer**: `python3 -m voice_studio.wsl check | phone | idle`, checklist section I17. It exists because on WSL's usual network a phone cannot reach `voicefile send`, and because Ubuntu stops about a minute after its last window closes and takes a round with it (F3). Both are settings in the Windows file `.wslconfig`: `networkingMode=mirrored` in `[wsl2]` and `instanceIdleTimeout=-1` in `[general]`. `check` only looks; `phone` and `idle` show the one change, ask, copy the old file (`.wslconfig.bak`, never over an earlier copy), write through a temporary file and read it back; the file is reached through `/mnt/c/Users/<name>`, not through a Windows program (F4), and the rest of it is kept exactly (comments, order, Windows line ends, byte order mark; refused if it is not plain UTF-8 text or repeats a key). **It never restarts WSL and never runs the firewall command; it prints `New-NetFirewallHyperVRule` for one port, the command that removes the rule, and `wsl.exe --shutdown`.** `rounds start` now says, before its question, that closing the last Ubuntu window can stop the round (read-only), and `voicefile send`'s note about WSL names `wsl check`. **Unverified, and flagged as such in the plan and the checklist:** the firewall command and where Microsoft keeps each key (taken from a search summary of Microsoft's page, which the sandbox could not open), `wslinfo --networking-mode`, and that a phone then reaches Ubuntu. No window page for it yet. **Tests:** 73 for the library and 71 for the front, against a pretend Windows drive; mutation testing made 775 deliberate breaks in the first round (69 survived and every one was closed by a test or a simplification) and 735 in the second (725 caught; the 10 left are equivalent: nine opaque token strings that are only compared with each other, and the temporary file's name). Everything chosen without asking is in P26 ("veto any"). **Next:** the checklist's real runs (I16 and I17 first); then a window page for sending and for this; VS-3.1, VS-3.2, VS-3.3, the model card and the on-PC speech round trip.
> **Then (2026-10-17; task VS-5.2's last item, the model card, decision P27):** **The voice file now comes with a card, built and tested in the sandbox, never read on a real project.** `voicefile make` (and the window's Voice file page, which runs the same command) ends by writing `MODEL_CARD.txt` in the same new folder as the zip: **not inside the zip**, owner-only, written last so a card that fails (`card_failed`, exit 1) leaves the good zip. It is plain text built only from what the project stored: the starting voice named by the **first round of the chosen round's training** (not the project's present choice), the chain and the pages that state its terms in the very words shown before the download, the acknowledgments (date and revision) or "none recorded", the round and about how many minutes, own-or-someone-else's voice and, for someone else's, only the fixed way the note says the agreement was given, the tool's version and the training programs' build, and the check codes of the two files in the zip. It copies no name, path, recording or word of the consent note, **leaves the zip's file name off** (the first version printed it; it carries the project's folder name; the privacy test caught it), and never says or suggests that use is allowed. **Tests:** 53 for the card, the card cases in `test_vs_voicefile.py` and `test_vs_voicefile_flow.py`, and the checklist (I4: "Read the card" and "Check the card against the files"). **Not verified:** a card from your real project (the wording as you read it; a project older than acknowledgments should say none is recorded), and the card opened from Windows. Everything chosen without asking is in P27 ("veto any"), with four open questions. **Next:** the checklist's real runs (I4 now includes the card, then I16 and I17); then a window page for sending and for the WSL help (both are terminal-only today); VS-3.1, VS-3.2, VS-3.3 and the on-PC speech round trip.

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
computer heard. *Decided later the same day (D43):* the test clips are kept in the project's own `listening` folder, grouped by the round or voice file they came from; the large voice copy of `--round` is offered for
removal at the end of the run; and both are offered by Free up space (`rounds free --clips N`, `--copies N`, `--all`, and the window's page). Task VS-5.6, checklist I8 part E and I3.

## 4. A full GUI flow for install, update, refresh and uninstall

**What exists today, by action:**

| Action | Today | Planned (the plan already says how) |
|---|---|---|
| Install | The two scripts and the guided setup above. Terminal and PowerShell text, no screens. | Plan D40, VS-7.x. |
| Update | **Built and tested in the sandbox (VS-6.2, P21), never run on a real computer or over a real connection:** `python3 -m voice_studio.update check | get RELEASE` (checklist I13), run by the window's Updates page (VS-6.7, P24); the switch itself is still by hand: `cd ~/ack-tools && git pull`, then `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio` (Ubuntu guide section 8, Windows guide section 9). `get.sh` offers the pull when it is re-run. | **VS-6.2:** a button that asks before contacting the internet, fetches a tagged release, **shows what changes**, builds the new environments beside the old ones and **switches only after the self-test passes**. Never automatic (P4, D11). |
| Refresh | **Built and tested in the sandbox (VS-6.6, P18), never run on a real computer:** `python3 -m voice_studio.refresh check | repair | rebuild | older` (checklist I10). The window's Check the tool page runs it (VS-6.7, P24; checklist I15). | **VS-6.2** will end in a refresh; the menu entry and system packages are covered by the first setup step. |
| Uninstall | **Built and tested in the sandbox (VS-6.3, P19), never run on a real computer:** `python3 -m voice_studio.uninstall` with `show` or `remove` (checklist I11) takes the programs and downloaded files off the disk and nothing else, and prints the commands for the menu entry and the tool's own folder. The guides now say so. Deleting the whole data folder is still by hand, after the backup the guides name. | **VS-6.3, P5:** removes the tool and its environments only; **a project is never deleted by it**. Deleting a person's data is a separate action that asks twice, names a backup first, and is driven by a storage catalogue with a test that fails if a new folder is in no area (the Android app's `StorageCatalogue` idea). Each area is marked precious, rebuildable or disposable (P11). |

Stage 6 (backup, update, uninstall, delete) is **In progress** in the plan's progress table: VS-6.1 (a checked backup before changes, outside OneDrive and Documents), VS-6.6 (refresh) and VS-6.3 (deleting a project names its backup first; uninstall) are built in the sandbox;
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
