#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds the Windows setup program (ACK-Voice-Studio-Setup-<version>.exe) with NSIS. It runs on Linux, macOS or Windows (Git Bash); it needs only makensis and python3.
#
#   installer/build.sh [output-folder]        (default: installer/dist, which git ignores)
#
# It copies exactly five files into a staging folder (engine.ps1, install.ps1, LICENSE, NOTICE and an icon the tool draws itself), builds the .exe from ack-voice-studio.nsi, and writes the
# SHA-256 of the .exe beside it. Nothing is signed (plan decision D44: signing is postponed). Nothing is downloaded: the program the .exe installs is fetched from its source later, on the
# computer that runs it.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
tools=$(cd "$here/../.." && pwd)
root=$(cd "$tools/.." && pwd)
out=${1:-$here/dist}

command -v makensis >/dev/null 2>&1 || { echo "makensis (NSIS) is not installed. On Ubuntu: sudo apt install nsis" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is not installed." >&2; exit 2; }

version=$(sed -n 's/^__version__ = "\([0-9][0-9.]*\)".*/\1/p' "$tools/voice_studio/__init__.py" | head -n 1)
[ -n "$version" ] || { echo "Could not read the version from voice_studio/__init__.py." >&2; exit 1; }

mkdir -p "$out"
out=$(cd "$out" && pwd)
stage="$out/stage"
rm -rf "$stage"
mkdir -p "$stage"
cp "$here/engine.ps1" "$here/../install.ps1" "$root/LICENSE" "$root/NOTICE" "$stage/"
python3 -I -c '
import sys
sys.path.insert(0, sys.argv[1])
from voice_studio.core import iconmake
with open(sys.argv[2], "wb") as handle:
    handle.write(iconmake.ico_bytes((16, 32, 48, 64, 256)))
' "$tools" "$stage/ack.ico"

exe="$out/ACK-Voice-Studio-Setup-$version.exe"
rm -f "$exe" "$exe.sha256"
makensis -V2 "-DSTAGE=$stage" "-DVERSION=$version" "-DOUTFILE=$exe" "$here/ack-voice-studio.nsi"
( cd "$out" && sha256sum "$(basename "$exe")" > "$(basename "$exe").sha256" )
echo "Built $exe"
cat "$exe.sha256"
