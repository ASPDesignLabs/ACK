#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Gets this computer ready for ACK Voice Studio. Run it from the ACK folder you cloned:
#
#   ./tools/voice_studio/setup.sh              look at the computer, list what is missing, ask once, install it
#   ./tools/voice_studio/setup.sh --check      only look; change nothing (exit 0 when ready, 1 when something needs fixing)
#   ./tools/voice_studio/setup.sh --dry-run    show what would be run; change nothing
#   ./tools/voice_studio/setup.sh --yes        you have already said yes, so do not ask
#
# The only thing it ever needs from you is your password, once, and Ubuntu asks for it, here in this terminal: this program never sees it.
# It installs nothing but the few Ubuntu programs it lists first, never edits your shell settings, and downloads nothing itself.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(dirname "$HERE")"
PYTHON="${PYTHON:-python3}"

say() { printf '%s\n' "$*"; }

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  say "Python 3 was not found, so setup cannot start. Ubuntu 22.04 and 24.04 include it."
  say "Ask whoever looks after this computer to install it, or run:  sudo apt install python3"
  exit 2
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  say "The Python on this computer is too old (3.10 or newer is needed). Updating Ubuntu will fix this."
  exit 2
fi

export PYTHONPATH="$TOOLS${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m voice_studio "$@"
