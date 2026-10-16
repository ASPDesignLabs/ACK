# ACK Voice Studio: changelog

This is the changelog of ACK Voice Studio only (`tools/voice_studio/`). The Android app's changes are in `CHANGELOG.md` at the top of the repository, and nothing here changes
that file or the notes the app shows with `/info`.

The version is `__version__` in `tools/voice_studio/__init__.py`. A release of this tool is a git tag named `voice-studio-v` plus that version, for example `voice-studio-v0.1.0`
(`docs/VOICE_STUDIO_RELEASE_RUNBOOK.md`). The repository's other tags (`v1.0-beta.1` and the rest) belong to the phone app and are not releases of this tool.

Everything below was built and tested in a build sandbox without a graphical screen, a speaker, a microphone, a GPU or a phone. What was and was not run on a real computer is
listed, section by section, in `docs/VOICE_STUDIO_DEVICE_TEST.md`; nothing here says a step works on a real computer unless that checklist records it.

## [0.0.1] - Unreleased

### Added
- **Set-up in one command.** The guided setup (`python3 -m voice_studio`) checks the computer, asks before it installs anything, builds two sets of programs beside each other
  (`python3 -m voice_studio.buildenv`) and ends at the window. Windows has its own one-line installer that sets up Ubuntu under WSL first.
- **Projects and recordings.** `python3 -m voice_studio.projects` makes, shows, changes and puts away a project, with its consent note, and deletes one only after two questions;
  `python3 -m voice_studio.recordings` brings in a package ACK saved on the phone (or a folder of audio files), lets the computer listen to what is waiting once the listening model
  has been fetched, and makes the training set.
- **Starting voices.** `python3 -m voice_studio.voices` lists the starting voices, shows where each one comes from before anything is downloaded, and fetches one only after you say you
  read that and agree to the download.
- **Training rounds.** `python3 -m voice_studio.rounds` starts a round, shows how it is going, stops it, chooses the round to use, goes back to an earlier one, keeps a note, and
  frees the space a round used. Nothing is removed without a question that shows what goes.
- **The voice file.** `python3 -m voice_studio.voicefile` makes the zip ACK takes from the chosen round, lists the ones made, and plays a finished voice on the computer.
- **Backup.** `python3 -m voice_studio.backup` copies a project's recordings, notes and finished voices to a folder (the one used last, or the tool's own backups folder, unless you
  name another), reads the copy back before it counts, and restores from it by adding what is missing. It never replaces or removes an earlier backup.
- **Refresh.** `python3 -m voice_studio.refresh` looks at the tool's own programs, downloads and notes, mends what is broken, builds a fresh copy beside the old one, and lists the
  older copies.
- **Move scratch.** `python3 -m voice_studio.scratch` says where a project's working files are and moves them to another place.
- **Uninstall.** `python3 -m voice_studio.uninstall` shows what it would take off the disk and what it keeps (projects, recordings, backups and the starting voices you chose), then
  removes only that.
- **Update.** `python3 -m voice_studio.update` asks github.com which releases of the tool exist (tags that begin with `voice-studio-`) and fetches one into a new folder beside the copy
  you use. It says first what it will ask, asks before it contacts anything, never changes the running copy, and prints the commands for switching so you can type them.
- **Problem report.** `python3 -m voice_studio.report` builds a report a helper can read, with names and folders blanked and no recordings or phrases in it. It shows all of it
  first and saves it only where you say. A command that fails after it began ends with two lines pointing at it.
- **Guides.** A beginner guide (`docs/VOICE_STUDIO_GUIDE.md`), a page for the helper (`docs/VOICE_STUDIO_HELPER_HANDOUT.md`), two installation guides, an IT guide, a device
  checklist and a data-sovereignty page, each held to the code by tests.

### Kept the same on purpose
- **Nothing is sent anywhere.** The tool reaches the internet only through one download module, only when you say yes to a question that names what will be asked, and never for
  your recordings, text or voices. Nothing checks for updates by itself.
- **Nothing is deleted unless you ask.** Every command that changes or removes something shows what it will do first and asks; with nobody to ask it does nothing.

### Not done yet
- The window's pages for backup, refresh, update, the problem report and listening; sending recordings over Wi-Fi; the recording paths for helpers; a real run on native Ubuntu,
  with a screen reader, on a real GPU, through a real speaker and over a real connection (all of these are rows in the device checklist).
