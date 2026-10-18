# ACK Voice Studio: making a release

This page is for the developer. It says how to make a numbered release of the tool, what each step changes, and which test notices if a step was missed. It makes no release by itself:
nothing here runs until a person types it.

## What a release is

A release is a **git tag** named `voice-studio-v` plus the version, for example `voice-studio-v0.1.0`. The repository also holds the phone app's tags (`v1.0-beta.1` to `v1.0-beta.7`).
Those are not releases of this tool: the registry (`tools/voice_studio/data/sources.json`, under `releases`, as `tag_prefix`) makes `python3 -m voice_studio.update` count only tags that
begin with `voice-studio-`, and show them without it (`v0.1.0`). The tool's own history is `tools/voice_studio/CHANGELOG.md`; the app's is `CHANGELOG.md` at the top of the repository, and
a release of the tool does not touch it.

A tag is **not signed**. `update get` checks only that the copy it fetched holds the commit GitHub listed for the tag and that it is a copy of this tool (plan decision P21), so a tag says
"this is the version I mean", not "this is proved to be mine".

## The version number

`MAJOR.MINOR.PATCH`, three whole numbers, written once in `tools/voice_studio/__init__.py` as `__version__`. The plan's decision P23 chose this rule (open to veto): **MINOR** goes up when a
command, a screen or a kind of file is added or changed in a way a person would notice; **PATCH** goes up when only mistakes were fixed or words were made clearer; **MAJOR** stays 0
until the checklist (`docs/VOICE_STUDIO_DEVICE_TEST.md`) has been run on a real computer from the first section to the last and the differences it found were dealt with.

## Before you start

- [ ] The work is merged into `main`, and you are on `main` with nothing uncommitted.
- [ ] `./tools/voice_studio/run_tests.sh` passes (warnings are errors; it needs only pytest, no network, no graphics card, no screen).
- [ ] You have run the sections of `docs/VOICE_STUDIO_DEVICE_TEST.md` that this release claims on a real computer, and written the results in. **A release must not say a step works when the
  checklist has no real run of it.** If a section was never run, say so under "Not done yet" in the changelog entry.
- [ ] If a download, a lock or a pin must change (a package with a known problem, a moved file), do that first and read the change through: `python3 tools/voice_studio_maint/make_lock.py`
  makes a lock and `python3 tools/voice_studio_maint/make_pins.py` pins the downloads (each says in its first lines what it needs; both need a network and are not part of the tool). A lock or a pin
  is **not** remade only because time has passed. When one changes, put the new checksum in `tools/voice_studio/data/environments.json`, re-read the licence of every package that changed,
  and update section 7 of `THIRD_PARTY_NOTICES.md` in the same commit, saying how each was checked and on what date.

## Steps

1. **Choose the version** by the rule above, and write the tag it will have: `voice-studio-vX.Y.Z`.
2. **Set the version.** In `tools/voice_studio/__init__.py`, set `__version__ = "X.Y.Z"`.
3. **Date the changelog.** In `tools/voice_studio/CHANGELOG.md`, change the newest heading from `## [X.Y.Z] - Unreleased` to `## [X.Y.Z] - YYYY-MM-DD`, and read the entry once more against what
   the checklist records (the first rule above). `test_vs_changelog.py` holds the newest entry to `__version__`.
4. **Move the default release.** One-line installs fetch `main` until a release exists. Change the word in these places, and nowhere else:
   `DEFAULT_TAG` in `tools/voice_studio/get.sh`; `DefaultRef` and `OneLiner` in `tools/voice_studio/install.ps1` (the address in the one command names the same tag); the sentence "The default is
   `main`." in `docs/ACK_Voice_Studio_Installation_Guide.MD` and `docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD`, and the one command at the top of each; and the paragraph in
   section I7 of the checklist that says the commands fetch `main` (`tools/voice_studio/tests/test_vs_install_guides.py` and `test_vs_install_ps1.py` hold the scripts and the guides equal). Also change
   the "Release." bullet of `docs/VOICE_STUDIO_IT_GUIDE.md` and the `get.sh` paragraph of `tools/voice_studio/README.md`, which say `main` by default, and record the new default in decision D39 of
   `docs/VOICE_STUDIO_SETUP_PLAN.md`.
5. **Check it all agrees.** Run
   `ACK_VOICE_RELEASE=voice-studio-vX.Y.Z ./tools/voice_studio/run_tests.sh -k release_ready` and then the whole suite without it. The first says in plain sentences what still disagrees
   with the tag (the version, the changelog's date, the two installers, the one command, and any of the documents in step 4 that still say `main`) and that the tag does not exist yet and is
   higher than every earlier one.
6. **Commit and merge** ("Voice Studio X.Y.Z"), as any change goes in.
7. **Make the tag on the merge commit** and push it:
   `git tag -a voice-studio-vX.Y.Z -m "ACK Voice Studio X.Y.Z"` and `git push origin voice-studio-vX.Y.Z`. An annotated tag is what to make; the update command reads both kinds.
8. **Look at it from outside.** `git ls-remote --tags https://github.com/ASPDesignLabs/ACK.git 'voice-studio-*'` lists the tag. On a computer, `python3 -m voice_studio.update check` lists the
   release (it asks first), and the one command in an installation guide now fetches it. Run sections I7 and I13 of the checklist against the tag and write what happened in them.
9. **Open the next version.** In `tools/voice_studio/__init__.py` set `__version__` to the next PATCH number, and add an empty `## [X.Y.Z+1] - Unreleased` entry at the top of the changelog
   (the test requires the two to move together). `get.sh` and `install.ps1` keep the release's tag as their default; they are changed again only by the next release.

## If something is wrong with a release

**Never move or delete a published tag.** Someone may have fetched it, and the update command compares a copy with the commit the tag was listed with, so a moved tag would make a good copy
look wrong and a wrong copy look right. Make the next version instead: fix the mistake, give it a changelog entry that says what was wrong and in which version, and follow the steps again.
Until the new tag exists the installers keep fetching the old one; if the old one is harmful, change `DEFAULT_TAG` and `DefaultRef` back to `main` in a commit of its own, and say so in the changelog.

## What a release does not do

It does not publish a package, a download or an installer outside this repository, it does not change the phone app or its changelog, and it does not make anything check for updates by itself.
People get a release when they run the update command or the one-line install, and not before.
