# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for the folder Freeform Studio's `models fetch` leaves in the Hugging Face folder: blobs named for their checksum and a snapshot folder of links to them, plus a
registry that pins the same bytes. Shared by the tests of the lookup and of the flow that uses it."""
import hashlib
import os
from dataclasses import replace

from vs_fetch_helpers import ADDRESS, pinned_item
from voice_studio.core import envfind
from voice_studio.core.registry import Registry

REV = "d1d751a5f8271d482d14ca55d9e2deeebbae577f"
A, B = b"first part " * 200, b"second part " * 300


def model_file(payload, name, **over):
    return replace(pinned_item(payload), id="speech-" + name, kind="model", folder=envfind.SPEECH_FOLDER, filename=name, **over)


def registry_for(a=A, b=B, revision=REV):
    address = ADDRESS.replace("0123abcd", revision)                    # a pinned address carries its revision
    return Registry((model_file(a, "a.bin", revision=revision, url=address), model_file(b, "b.bin", revision=revision, url=address)))


def put_hub(hub, files, revision=REV, link=True):
    """Write a snapshot of `files` ({name: bytes}) under `hub` and return the snapshot's folder."""
    repo = os.path.join(str(hub), envfind.HF_REPO_FOLDER)
    for name, payload in files.items():
        blob = os.path.join(repo, "blobs", hashlib.sha256(payload).hexdigest())
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        with open(blob, "wb") as handle:
            handle.write(payload)
        target = os.path.join(repo, "snapshots", revision, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if link:
            os.symlink(os.path.join("..", "..", "blobs", os.path.basename(blob)), target)
        else:
            with open(target, "wb") as handle:
                handle.write(payload)
    return os.path.join(repo, "snapshots", revision)
