#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Starts Freeform Studio the usual way. Extra options go on the end and win over the defaults, for example:
#   ./start.sh --asr-device cuda          use the GPU while training isn't running
#   ./start.sh --port 8002
# Settings can come from the environment: FREEFORM_VENV, FREEFORM_CERTS (your mkcert folder), FREEFORM_OUTPUT, and
# FREEFORM_BACKUPS (where backups are kept; point it somewhere outside WSL, such as /mnt/c/Users/<you>/freeform-backups).
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(dirname "$HERE")"
VENV="${FREEFORM_VENV:-$HOME/freeform-studio-venv}"
CERTS="${FREEFORM_CERTS:-$HOME/piper-recording-studio/certs}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Freeform Studio isn't installed in $VENV yet. Run:  $HERE/install.sh" >&2
  exit 2
fi

args=(--host 0.0.0.0)
[ -n "${FREEFORM_OUTPUT:-}" ] && args+=(--output "$FREEFORM_OUTPUT")
[ -n "${FREEFORM_BACKUPS:-}" ] && args+=(--backup-dir "$FREEFORM_BACKUPS")
if [ -d "$CERTS" ]; then
  args+=(--certs-dir "$CERTS")
else
  echo "Note: no certificate folder at $CERTS, so the phone microphone won't work (it needs https)." >&2
  echo "      Set FREEFORM_CERTS to your mkcert folder, or see docs/VOICE_TRAINING_GUIDE.md." >&2
fi

cd "$TOOLS" || exit 2
exec "$VENV/bin/python" -m freeform_studio "${args[@]}" "$@"
