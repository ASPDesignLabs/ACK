# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch and inspect the speech models. This is the ONE place in Freeform Studio that is allowed to use the internet.

    python -m freeform_studio.models list              # which models are on this computer
    python -m freeform_studio.models fetch small.en    # download one, once, after asking you

Everything else (the server, the review pages, export, backup, dataset building) works with no network at all. The server
loads a speech model only from this computer's own copy and never asks Hugging Face about it, so what you record, and
what the PC heard, never leaves the machine. `fetch` is separate and explicit so that the single time something is
downloaded is a time you chose. Nothing you recorded is ever sent: the request names the model and, as any web request
does, carries this computer's address and the versions of the libraries asking.

Already have a model folder (copied from another computer, or converted yourself)? Skip `fetch` and start the server with
`--asr-model /path/to/that/folder`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional

from .privacy import private_umask

# Rough download sizes, only to tell you what you are agreeing to. Anything not listed says "size varies".
APPROX_MB = {"tiny.en": 75, "base.en": 145, "small.en": 480, "medium.en": 1500, "distil-large-v3": 1500, "large-v3": 3000,
             "tiny": 75, "base": 145, "small": 480, "medium": 1500}
LISTED = ["tiny.en", "base.en", "small.en", "medium.en", "distil-large-v3"]


def _download_model(name: str, local_files_only: bool) -> str:
    from faster_whisper.utils import download_model  # heavy import, only when needed

    return download_model(name, local_files_only=local_files_only)


def resolve_local(name: str, download: Callable[[str, bool], str] = _download_model) -> Optional[str]:
    """Where this model already is on this computer, or None. Never touches the network."""
    folder = Path(name).expanduser()
    if folder.is_dir():
        return str(folder)
    try:
        return str(download(name, True))
    except Exception:  # not downloaded yet, or the libraries aren't installed: either way it isn't available
        return None


def is_available(name: str) -> bool:
    return resolve_local(name) is not None


def cache_folder() -> str:
    try:
        from huggingface_hub import constants

        return str(constants.HF_HUB_CACHE)
    except Exception:
        return str(Path("~/.cache/huggingface/hub").expanduser())


def size_phrase(name: str) -> str:
    mb = APPROX_MB.get(name)
    if not mb:
        return "size varies"
    return f"about {mb / 1000:.1f} GB" if mb >= 1000 else f"about {mb} MB"


def fetch(name: str, assume_yes: bool = False, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
          download: Callable[[str, bool], str] = _download_model) -> int:
    """Download `name` after asking. Returns a process exit code (0 = it is now on this computer)."""
    here = resolve_local(name, download)
    if here:
        say(f"\n'{name}' is already on this computer ({here}). Nothing to download.\n")
        return 0
    if Path(name).expanduser().is_absolute() or name.startswith(("~", ".")):
        say(f"\n'{name}' looks like a folder, but it doesn't exist. Check the path.\n")
        return 2
    say(f"\nThis will download the speech model '{name}' ({size_phrase(name)}) from huggingface.co into:")
    say(f"  {cache_folder()}")
    say("It uses the internet once. Nothing you recorded is sent: the request names the model, and (like any web request) shows")
    say("this computer's address and the versions of the libraries asking. After this the server loads the model from disk,")
    say("with no network.\n")
    if not assume_yes:
        try:
            answer = ask("Download it now? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            say("\nNothing was downloaded.\n")
            return 1
    try:
        download(name, False)
    except Exception as err:  # noqa: BLE001 - a person reads this, not a log
        first = (str(err).strip().splitlines() or [""])[0][:200]
        say(f"\nThe download did not finish: {first}")
        say("Check the connection and free disk space, then run the same command again; a partial download resumes.\n")
        return 1
    here = resolve_local(name, download)
    if not here:
        say("\nThe download finished but the model can't be found afterwards. Run `python -m freeform_studio.models list`.\n")
        return 1
    say(f"\nDone: '{name}' is on this computer ({here}). The server will now load it with no network.\n")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="which models are on this computer (no network)")
    f = sub.add_parser("fetch", help="download a model once, after asking")
    f.add_argument("name", help="e.g. small.en, medium.en, distil-large-v3, or a Hugging Face id like Systran/faster-whisper-small.en")
    f.add_argument("--yes", action="store_true", help="don't ask (for scripts)")
    args = p.parse_args(argv)
    with private_umask():
        if args.cmd == "list":
            print()
            for name in LISTED:
                here = resolve_local(name)
                print(f"  {name:18s} " + (f"on this computer: {here}" if here else f"not downloaded ({size_phrase(name)})"))
            print(f"\nDownloaded models are kept in {cache_folder()}\n")
            return 0
        # `fetch` is the one command that is meant to use the network, and you have just asked for it, so an offline switch left
        # in your shell must not silently defeat it. This has to happen before anything imports the Hugging Face libraries.
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("DO_NOT_TRACK", "1")
        return fetch(args.name, assume_yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
