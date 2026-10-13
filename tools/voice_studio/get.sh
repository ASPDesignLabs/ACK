#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# The "no git yet" way in: fetches ACK's files and starts setup. Normally you would clone ACK yourself and run setup.sh. This is for a computer
# that has neither, and it can be run straight from the web page that offers it:   curl -fsSL <address of this file> | bash
#
# It is not pushed anywhere unless you ask: it asks before it installs git, it never touches a folder that is already there (a copy of ACK that is out of
# date is only brought up to date after a yes), and it never edits your shell settings. Answers are read from the terminal (/dev/tty), because when this is piped into bash its input is the script itself.
#   --yes       you have already said yes (to installing git); do not ask
#   --check, --dry-run   show what would run and change nothing
# Settings (environment):  ACK_VOICE_TAG (the release, tag or branch to fetch; default below)   ACK_VOICE_DIR (where to put it; default ~/ack-tools)
set -u

REPO_URL="https://github.com/ASPDesignLabs/ACK.git"
DEFAULT_TAG="main"          # what is fetched when nothing is chosen. When a release is cut, this one word becomes its name (install.ps1 holds the same word)
TAG="${ACK_VOICE_TAG:-$DEFAULT_TAG}"
DEST="${ACK_VOICE_DIR:-$HOME/ack-tools}"

say() { printf '%s\n' "$*"; }

YES=0; DRY=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --dry-run|--check) DRY=1 ;;
  esac
done

# ask_person QUESTION: 0 = yes, 1 = no, 2 = nobody to ask. --yes never answers this one.
ask_person() {
  { : </dev/tty; } 2>/dev/null || return 2
  printf '%s ' "$1" >/dev/tty
  read -r answer </dev/tty || return 2
  case "$answer" in y|Y|yes|Yes|YES) return 0 ;; *) return 1 ;; esac
}

# ask QUESTION: the same, except that --yes (already said yes to installing git) answers it
ask() {
  [ "$YES" -eq 1 ] && return 0
  ask_person "$1"
}

hand_over() {
  if { : </dev/tty; } 2>/dev/null; then exec "$DEST/tools/voice_studio/setup.sh" "$@" </dev/tty; fi
  exec "$DEST/tools/voice_studio/setup.sh" "$@"
}

# A copy that is already there is used as it is, but a git copy that is not the release asked for is said so and offered an update, because a copy older than
# the command that started this can stop with "Unknown option". Looking is read-only (git ls-remote); changing the copy is only ever git pull --ff-only, after a yes.
check_copy() {
  [ "$DRY" -eq 1 ] && return 0
  command -v git >/dev/null 2>&1 || return 0
  [ "$(git -C "$DEST" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ] || return 0
  here=$(git -C "$DEST" rev-parse HEAD 2>/dev/null) || return 0
  listing=$(git ls-remote "$REPO_URL" "refs/heads/$TAG" "refs/tags/$TAG" "refs/tags/$TAG^{}" 2>/dev/null </dev/null)
  there=${listing##*$'\n'}
  there=${there%%[[:space:]]*}
  [ -n "$there" ] || return 0
  [ "$here" = "$there" ] && return 0
  git -C "$DEST" merge-base --is-ancestor "$there" "$here" 2>/dev/null && return 0
  say "The copy of ACK at $DEST is not the same as ACK $TAG, so it may be older than this command expects."
  if [ -n "$(git -C "$DEST" status --porcelain 2>/dev/null)" ]; then
    say "It has changes of your own, so it was left as it is. To bring it up to date yourself: cd $DEST && git pull"
    return 0
  fi
  say "Updating it changes files in $DEST only (git pull --ff-only). Your projects and recordings are in ack-voice-studio, not here, and are not touched."
  ask_person "Update the copy now? Type y for yes, or press Enter to use it as it is:"
  case $? in
    0) if git -C "$DEST" pull --ff-only origin "$TAG" </dev/null; then
         say "The copy was updated."
       else
         say "The copy could not be updated here, and nothing was changed. To do it yourself: cd $DEST && git pull"
         exit 1
       fi ;;
    1) say "The copy was left as it is. If setup stops with Unknown option, the copy is too old: update it with cd $DEST && git pull" ;;
    *) say "This cannot ask you a question here, so the copy was left as it is. To update it: cd $DEST && git pull" ;;
  esac
}

if [ -x "$DEST/tools/voice_studio/setup.sh" ]; then
  say "ACK is already at $DEST, so that copy is being used and nothing is fetched."
  check_copy
  hand_over "$@"
fi
if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  say "A folder named $DEST already exists and does not look like ACK, so it was left alone and nothing was fetched."
  say "Choose another place by running this again with ACK_VOICE_DIR set to a new folder name."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  say "git is needed to fetch ACK's files. It is a small, standard program."
  if [ "$DRY" -eq 1 ]; then
    say "  Would run: sudo apt-get update"
    say "  Would run: sudo apt-get install -y git"
  else
    say "Installing it needs administrator rights. Ubuntu will ask for your password here; this script never sees it."
    ask "Install git now? Type y for yes, or press Enter for no:"
    case $? in
      0) sudo apt-get update && sudo apt-get install -y git || { say "git could not be installed. Nothing else was changed."; exit 1; } ;;
      1) say "Nothing was installed and nothing was changed."; exit 2 ;;
      *) say "This cannot ask you a question here, so it did nothing. To go ahead, run it again and add --yes."; exit 2 ;;
    esac
  fi
fi

if [ "$DRY" -eq 1 ]; then
  say "  Would run: git clone --depth 1 --branch $TAG $REPO_URL $DEST"
  say "  Would run: $DEST/tools/voice_studio/setup.sh"
  exit 0
fi

say "Fetching ACK $TAG into $DEST."
if ! git clone --depth 1 --branch "$TAG" "$REPO_URL" "$DEST"; then
  say "ACK could not be fetched. Check the internet connection and the release name. Nothing else was changed."
  exit 1
fi
hand_over "$@"
