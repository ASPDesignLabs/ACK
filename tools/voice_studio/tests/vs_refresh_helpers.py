# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for the refresh tests: the builder tests' computer and network (demo programs built from a small archive), a listening model of two files, a kept starting voice, and an
opener that serves their bytes so that the real downloader (and its checks) does the fetching."""
import functools
import itertools
import os
from dataclasses import replace
from pathlib import Path

from vs_env_helpers import NATIVE_OVER, FakeTime, make_rig
from vs_envfind_hub import REV, A, B, model_file
from vs_fetch_helpers import ADDRESS, FakeOpener, pinned_item
from voice_studio.core import envfind, fetch, refresh_flow as rff, startvoice
from voice_studio.core.consent import make_consent, save_consent
from voice_studio.core.registry import Registry
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")
VOICE_BYTES = b"voice bytes " * 100
SPEECH = {"a.bin": A, "b.bin": B}


class TermIO:
    def __init__(self, answers=(), interactive=True):
        self.interactive, self.answers, self.lines, self.prompts, self.events = interactive, list(answers), [], [], []

    def say(self, text):
        self.lines.append(text)
        self.events.append(("say", text))

    def ask(self, prompt):
        self.prompts.append(prompt)
        self.events.append(("ask", prompt))
        return self.answers.pop(0) if self.answers else None

    @property
    def text(self):
        return "\n".join(self.lines)


class ByAddress:
    """An opener that serves the bytes for the address asked, and remembers every address."""

    def __init__(self):
        self.payloads, self.calls, self.fail_with = {}, [], None

    def __call__(self, url, headers):
        self.calls.append(url)
        if self.fail_with is not None:
            raise self.fail_with
        return FakeOpener(self.payloads[url])(url, headers)


def ticking(step=1.0):
    counter = itertools.count()
    return lambda: next(counter) * step


class RefreshRig:
    def __init__(self, tmp_path, *, built=True, speech=True, voice=True, system_kw=None, gpu=True):
        self.env = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw=system_kw, gpu_ok=gpu)
        self.home, self.system, self.spec = self.env.ctx.home, self.env.system, self.env.spec
        self.opener = ByAddress()
        speech_items = [replace(model_file(payload, name, url=ADDRESS.replace("0123abcd", REV).replace("model.ckpt", name)), id="speech-" + name) for name, payload in SPEECH.items()]
        self.voice_item = replace(pinned_item(VOICE_BYTES, id="voice-mike", filename="mike.ckpt"), url=ADDRESS.replace("model.ckpt", "mike.ckpt"))
        self.speech_items = [replace(i, revision=REV) for i in speech_items]
        self.registry = Registry(tuple(self.env.registry.items) + tuple(self.speech_items) + (self.voice_item,))
        for item, payload in [(i, SPEECH[i.filename]) for i in self.speech_items] + [(self.voice_item, VOICE_BYTES)]:
            self.opener.payloads[item.url] = payload
        self.fetched = []
        self.agree()
        if built:
            assert self.env.build().ok
        if speech:
            self.put_speech()
        if voice:
            self.put_voice()

    # -- what is on the disk
    def agree(self, extra=()):
        save_consent(Path(self.home.consent_file), make_consent(list(self.registry.items) + list(extra), extra_ids=["pip:demo"]))

    def put_speech(self, names=None):
        folder = Path(envfind.speech_places(self.home)[0])
        folder.mkdir(parents=True, exist_ok=True)
        for name in names or SPEECH:
            (folder / name).write_bytes(SPEECH[name])
        return folder

    def voice_path(self):
        return startvoice.voice_folder(self.home, self.voice_item) / self.voice_item.filename

    def put_voice(self):
        self.voice_path().parent.mkdir(parents=True, exist_ok=True)
        self.voice_path().write_bytes(VOICE_BYTES)

    # -- running the command
    def fetcher(self, item, dest_dir, consent, **kw):
        if item.kind == "source":
            return self.env.doors.fetcher(item, dest_dir, consent, **kw)
        self.fetched.append(item.id)
        return fetch.fetch(item, dest_dir, consent, opener=self.opener, **kw)

    @property
    def seams(self):
        return {"read_lock": self.env.ctx.read_lock, "read_native": self.env.ctx.read_native, "fetcher": self.fetcher, "sleep": FakeTime().sleep}

    def run(self, *argv, answers=(), interactive=True, now=None, io=None):
        io = io or TermIO(answers, interactive)
        code = rff.run_refresh(list(argv), self.home, CAT, io, system=self.system, registry=self.registry, specs=[self.spec], networked=self.env.doors.networked, clock=ticking(),
                               now=now, seams=self.seams)
        return code, io

    def look(self, **kw):
        from voice_studio.core import refresh as rf
        return rf.look(self.home, self.registry, [self.spec], self.env.ctx, **kw)
