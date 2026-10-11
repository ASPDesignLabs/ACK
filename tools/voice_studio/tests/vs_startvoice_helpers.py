# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins shared by the tests of the starting-voice logic and of the terminal fronts: two small made-up voices pinned the way the registry pins real ones,
a project, and a terminal that answers from a list."""
import re
from dataclasses import replace
from datetime import datetime, timezone

from vs_fetch_helpers import pinned_item
from voice_studio.core.project import Project
from voice_studio.core.registry import Registry

NOW = datetime(2026, 10, 11, 12, 30, tzinfo=timezone.utc)
STAMP = "2026-10-11T12:30:00Z"
LESSAC_PAGE = "https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html"
VOICE_A = b"the first voice, as bytes " * 80
VOICE_B = b"the second voice, as bytes " * 80


def make_voice(voice_id, payload, revision="0123abcd", **over):
    base = pinned_item(payload)
    pages = (("lessac", LESSAC_PAGE), ("mike" if voice_id == "voice-mike" else "amy", "https://github.com/example/recordings"))
    fields = dict(id=voice_id, url="https://huggingface.co/datasets/example/store/resolve/%s/%s.ckpt" % (revision, voice_id), filename=voice_id + ".ckpt",
                  revision=revision, pages=tuple(sorted(pages)))
    fields.update(over)
    return replace(base, **fields)


def make_registry(*, mike=VOICE_A, amy=VOICE_B, revision="0123abcd"):
    items = []
    if mike is not None:
        items.append(make_voice("voice-mike", mike, revision))
    if amy is not None:
        items.append(make_voice("voice-amy", amy, revision))
    return Registry(tuple(items))


def make_project(**over):
    base = dict(id="anna", name="Anna", whose_voice="own", created="2026-10-11T09:00:00Z")
    base.update(over)
    return Project(**base)


class Terminal:
    """A terminal for the flows: it says into `lines`, answers from `answers` in order (None when they run out: nobody there), and remembers each prompt."""

    def __init__(self, answers=(), interactive=True):
        self.interactive, self.answers, self.lines, self.prompts, self.events = interactive, list(answers), [], [], []

    def say(self, text):
        self.lines.append(text)
        self.events.append(("say", text))

    def ask(self, prompt):
        self.prompts.append(prompt)
        self.events.append(("ask", prompt))
        if self.answers and isinstance(self.answers[0], BaseException):
            raise self.answers.pop(0)
        return self.answers.pop(0) if self.answers else None

    @property
    def text(self):
        return "\n".join(self.lines)


KEY_SHAPE = re.compile(r"\b(?:cli|projects|voices|startvoice|newproject|project|fetch|connection|rounds|freeup|voicefile|voicezip|commands)\.[a-z_]+(?:\.[a-z_]+)+\b")


def leaked_keys(text):
    """Catalog keys that were printed instead of words (a key the catalog lacks reads as itself). The file name project.json.previous is not one."""
    return [k for k in KEY_SHAPE.findall(text) if not k.startswith("project.json")]


IMPLIES_PERMISSION = re.compile(r"\b(permit(?:ted|s)?|allowed|free (?:to|for)|legal(?:ly)? to|licensed for|may use|can use|fine to use|safe to use|ok(?:ay)? to use|entitled)\b", re.I)


def implies_permission(value):
    """The one sentence D27 asks for, "Whether ... is allowed is for you to decide", is not a grant; every other sentence is checked."""
    sentences = re.split(r"(?<=[.!?])\s+", value)
    return [s for s in sentences if IMPLIES_PERMISSION.search(s) and not re.match(r"Whether\b", s)]
