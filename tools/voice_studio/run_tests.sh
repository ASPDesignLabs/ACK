#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Runs ACK Voice Studio's tests. Extra arguments go to pytest, for example:  ./run_tests.sh -k preflight -x
#
# Uses the Python in PYTHON (default: python3), which needs pytest. A throwaway environment is enough:
#   python3 -m venv ~/voice-studio-test-venv && ~/voice-studio-test-venv/bin/pip install pytest
#   PYTHON=~/voice-studio-test-venv/bin/python ./run_tests.sh
# Nothing here uses the network, a GPU or a display.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(dirname "$HERE")"
PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
  echo "pytest is not installed for $PYTHON, so the tests can't run. To set one up:" >&2
  echo "  python3 -m venv ~/voice-studio-test-venv && ~/voice-studio-test-venv/bin/pip install pytest" >&2
  echo "  PYTHON=~/voice-studio-test-venv/bin/python $0" >&2
  exit 2
fi

cd "$TOOLS" || exit 2
exec "$PYTHON" -m pytest voice_studio/tests -q "$@"
