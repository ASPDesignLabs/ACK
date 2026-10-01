#!/usr/bin/env bash
# Installs Freeform Studio into its own virtual environment, so nothing here can disturb the recorder or your training setup.
#
#   ./install.sh                  install (or repair) into ~/freeform-studio-venv
#   ./install.sh --check          only look: report what is missing, change nothing
#   ./install.sh --dry-run        show every command it would run, change nothing
#   ./install.sh --gpu            also install the NVIDIA libraries for the speech model on the GPU
#   ./install.sh --venv DIR       use another environment folder
#   ./install.sh --python CMD     use a particular Python (default: the newest 3.10+ it finds)
#
# Safe to run again: it reuses an existing environment and only adds what is missing. It writes only to the environment
# folder (plus pip's usual download cache), and never edits your shell settings or installs system packages.
set -u -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$(dirname "$HERE")"
REQ="$HERE/requirements.txt"
VENV="${FREEFORM_VENV:-$HOME/freeform-studio-venv}"
PYTHON=""
GPU=0
CHECK=0
DRY=0
FAILS=0

usage() { sed -n '2,/^[^#]/{/^#/s/^# \{0,1\}//p;}' "$0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --venv) VENV="${2:?--venv needs a folder}"; shift 2 ;;
    --python) PYTHON="${2:?--python needs a command}"; shift 2 ;;
    --gpu) GPU=1; shift ;;
    --check) CHECK=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 2 ;;
  esac
done

ok()   { printf '  [ok]    %s\n' "$*"; }
note() { printf '  [note]  %s\n' "$*"; }
bad()  { printf '  [FIX]   %s\n' "$*"; FAILS=$((FAILS + 1)); }
step() { printf '\n%s\n' "$*"; }
run()  {
  if [ "$DRY" -eq 1 ]; then printf '  would run: %s\n' "$*"; return 0; fi
  "$@"
}

py_ok() {  # is "$1" a Python 3.10 or newer?
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}
py_version() { "$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null; }

echo "Freeform Studio installer"
echo "  environment: $VENV"
[ "$CHECK" -eq 1 ] && echo "  mode: check only (nothing will be changed)"
[ "$DRY" -eq 1 ] && echo "  mode: dry run (nothing will be changed)"

# ---------------------------------------------------------------- 1. Python
step "1. Python"
if [ -z "$PYTHON" ]; then
  for c in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then PYTHON="$c"; break; fi
  done
fi
if [ -z "$PYTHON" ] || ! command -v "$PYTHON" >/dev/null 2>&1; then
  bad "Python 3.10 or newer was not found. On Ubuntu: sudo apt install python3 python3-venv"
elif ! py_ok "$PYTHON"; then
  bad "$PYTHON is Python $(py_version "$PYTHON"), which is too old. Freeform Studio needs 3.10 or newer (sudo apt install python3.11 python3.11-venv)."
else
  ok "Python $(py_version "$PYTHON") ($PYTHON)"
  if "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1; then
    ok "Python can make virtual environments"
  else
    bad "Python can't make virtual environments yet. On Ubuntu: sudo apt install python3-venv"
  fi
fi

# ---------------------------------------------------------------- 2. ffmpeg
step "2. ffmpeg (decodes your phone's recordings)"
for tool in ffmpeg ffprobe; do
  if command -v "$tool" >/dev/null 2>&1; then ok "$tool found"; else bad "$tool is missing. On Ubuntu: sudo apt install ffmpeg"; fi
done

# ---------------------------------------------------------------- 3. the files
step "3. Program files"
if [ -f "$REQ" ] && [ -f "$HERE/__main__.py" ]; then ok "found $HERE"; else bad "this doesn't look like the freeform_studio folder (no requirements.txt or __main__.py next to install.sh)"; fi

if [ "$FAILS" -gt 0 ]; then
  printf '\n%s problem(s) above. Fix them, then run this again.\n' "$FAILS"
  exit 1
fi

# ---------------------------------------------------------------- 4. environment
step "4. Environment"
VPY="$VENV/bin/python"
if [ -x "$VPY" ]; then
  if py_ok "$VPY"; then ok "reusing the existing environment (Python $(py_version "$VPY"))"; else bad "$VENV exists but its Python is too old. Move it aside and run again."; fi
elif [ "$CHECK" -eq 1 ]; then
  bad "no environment at $VENV yet. Run ./install.sh to make it."
else
  echo "  making $VENV"
  run "$PYTHON" -m venv "$VENV" || bad "could not make the environment at $VENV"
fi

if [ "$CHECK" -eq 0 ] && [ "$FAILS" -eq 0 ]; then
  step "5. Packages (the first run downloads the speech model's libraries, so it can take a few minutes)"
  run "$VPY" -m pip install --upgrade pip || bad "could not update pip (is the network reachable?)"
  run "$VPY" -m pip install -r "$REQ" || bad "could not install the requirements. The message just above says which package failed."
  if [ "$GPU" -eq 1 ]; then
    echo "  adding the NVIDIA libraries for the GPU"
    run "$VPY" -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" || bad "could not install the NVIDIA libraries"
  fi
fi

# ---------------------------------------------------------------- 6. verify
if [ "$DRY" -eq 0 ] && [ "$FAILS" -eq 0 ]; then
  step "6. Does it work?"
  for mod in quart hypercorn numpy faster_whisper huggingface_hub; do
    if "$VPY" -c "import $mod" >/dev/null 2>&1; then ok "package $mod"; else bad "package $mod can't be loaded. Run ./install.sh (without --check) to install it."; fi
  done
  if (cd "$TOOLS" && "$VPY" -m freeform_studio --help >/dev/null 2>&1); then ok "the program starts"; else bad "the program didn't start. Try: cd $TOOLS && $VPY -m freeform_studio --help"; fi
  if [ "$GPU" -eq 1 ]; then
    LIBS="$("$VPY" -c 'import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))' 2>/dev/null || true)"
    if [ -n "$LIBS" ]; then
      note "To use the GPU, start the server with this set first (it must be set before Python starts):"
      echo "          export LD_LIBRARY_PATH=$LIBS"
      note "Don't use the GPU for speech recognition while training is running; free it from the Review page first."
    else
      bad "the NVIDIA libraries were installed but can't be found"
    fi
  fi
fi

if [ "$FAILS" -gt 0 ]; then
  printf '\n%s problem(s) above. Fix them, then run this again.\n' "$FAILS"
  exit 1
fi

step "Done."
if [ "$CHECK" -eq 1 ] || [ "$DRY" -eq 1 ]; then
  echo "  Nothing was changed."
else
  echo "  Start it:        $HERE/start.sh"
  echo "  If a phone can't connect:  $VPY -m freeform_studio.doctor   (run it in a second terminal, from $TOOLS)"
  echo "  Back up your recordings:   cd $TOOLS && $VPY -m freeform_studio.backup"
fi
exit 0
