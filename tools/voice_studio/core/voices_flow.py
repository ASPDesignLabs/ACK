# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for starting voices (until the window exists): see them, read where one comes from, choose one, and get it.

It is the front of core/startvoice.py and decides nothing that module does not. The order of `get` is the module's order and cannot be shortened from here:
the notes are shown, the person confirms they have read them (`yes` at the question, or `--acknowledge`), then, if the file has to be downloaded, the person agrees
to that one download (`yes`, or `--yes`), and only then does anything reach the network. Each of the two is a separate act and is saved separately: the
acknowledgment in the project (with the date and the exact file), the agreement on this computer. Both files are replaced safely, and the project's earlier
version is kept as `project.json.previous`.

Every sentence comes from the text catalog; the tool says nothing about whether anyone's use of a voice is allowed. Exit codes: 0 done, 1 something failed,
2 nothing was done (declined, nobody to ask, a project or voice that could not be told, or an option that is not understood).
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from . import connection, fetch, startvoice as sv
from .buildenv_flow import duration_text
from .cliargs import ArgError, Parsed, parse_args
from .describe import error_text
from .paths import DataHome, ProjectPaths
from .project import Project, ProjectError, save_project
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, VOICES_COMMAND, resolve_project, say_bad_arg
from .registry import Registry
from .setup_flow import IO, _said_yes
from .text import Catalog, size_text

PROGRESS_STEP = 10                       # a line for every this many percent of a download: plain lines, no moving bar, so a screen reader or a log reads it as it is
YES = {"--yes": "yes", "-y": "yes"}
PROJECT = {"--project": "project"}
GET_FLAGS = {**YES, "--acknowledge": "acknowledge"}
OPTIONS = {"list": frozenset(PROJECT), "show": frozenset(), "choose": frozenset(YES) | frozenset(PROJECT), "get": frozenset(GET_FLAGS) | frozenset(PROJECT)}      # the checklist is held to these


def _say_parts(cat: Catalog, io: IO, namespace: str, code: str, detail: str = "") -> None:
    parts = error_text(cat, namespace, code)
    io.say("  " + parts.what)
    io.say("  " + parts.changed)
    io.say("  " + parts.next)
    if detail:
        io.say("  " + cat.t("cli.technical", detail=detail))


def _voice_arg(parsed: Parsed, registry: Registry, cat: Catalog, io: IO) -> Optional[str]:
    ids = ", ".join(entry.voice_id for entry in sv.voices(registry))
    if not parsed.words:
        io.say(cat.t("voices.which", ids=ids))
        return None
    found = sv.find_voice(registry, parsed.words[0])
    if found is None:
        io.say(cat.t("voices.unknown", name=parsed.words[0][:60], ids=ids))
    return found


def _project_path(home: DataHome, project: Project) -> ProjectPaths:
    return ProjectPaths(home.projects + "/" + project.id)


def _ask_yes(io: IO, prompt: str) -> Optional[bool]:
    """True for a yes, False for any other answer, None when nobody is there to ask."""
    if not io.interactive:
        return None
    answer = io.ask(prompt + " ")                              # a catalog sentence never ends in a space, so the prompt gets its own
    if answer is None:
        return None
    return _said_yes(answer)


# ---------------------------------------------------------------- list and show

def _list(args: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voices.title"))
    project = None
    if "project" in parsed.values:
        project, code = resolve_project(parsed.values["project"], home, cat, io)
        if project is None:
            return code
    entries = sv.voices(registry)
    for entry in entries:
        io.say(cat.t("voices.list.row", id=entry.voice_id, choice=cat.t("startvoice.choice." + entry.choice), size=size_text(entry.size_bytes), site=entry.host or "-"))
        if not entry.pinned:
            io.say("  " + cat.t("voices.list.unavailable"))
            continue
        io.say("  " + cat.t("voices.list.on_computer" if sv.kept_path(home, registry, entry.voice_id) else "voices.list.not_on_computer"))
        if project is not None:
            step = sv.next_step(project, registry, entry.voice_id, home)
            io.say("  " + cat.t("voices.list.step", project=project.id, step=cat.t("startvoice.step." + step)))
            if project.starting_voice == entry.voice_id:
                io.say("  " + cat.t("voices.list.chosen", project=project.id))
    if entries:
        io.say(cat.t("voices.list.next", command="%s show %s" % (VOICES_COMMAND, entries[0].voice_id)))
    return EXIT_OK


def _show_notes(entry: sv.VoiceCard, cat: Catalog, io: IO) -> None:
    """Everything a person is shown before a voice is fetched, in the order the chain goes: the voice, then each voice it came from."""
    io.say(cat.t("voices.show.line", id=entry.voice_id, choice=cat.t("startvoice.choice." + entry.choice), size=size_text(entry.size_bytes), site=entry.host or "-"))
    io.say("")
    io.say(cat.t("startvoice.intro"))
    for link in entry.links:
        io.say("")
        io.say(cat.t("startvoice.link.%s.name" % link.id))
        for statement in link.statements:
            io.say("  " + cat.t("startvoice.says." + statement))
        io.say("  " + (cat.t("voices.show.page", page=link.page) if link.page else cat.t("voices.show.no_page")))
    io.say("")
    io.say(cat.t("startvoice.read_on", date=entry.read_on))
    io.say(cat.t("startvoice.not_advice"))
    io.say(cat.t("startvoice.not_hosted"))
    io.say(cat.t("startvoice.head_start"))


def _show(args: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voices.title"))
    voice_id = _voice_arg(parsed, registry, cat, io)
    if voice_id is None:
        return EXIT_NOTHING_DONE
    _show_notes(sv.card(registry, voice_id), cat, io)
    return EXIT_OK


# ---------------------------------------------------------------- choose

def _choose(args: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voices.title"))
    voice_id = _voice_arg(parsed, registry, cat, io)
    if voice_id is None:
        return EXIT_NOTHING_DONE
    project, code = resolve_project(parsed.values.get("project"), home, cat, io)
    if project is None:
        return code
    if project.starting_voice == voice_id:
        io.say(cat.t("voices.choose.already", project=project.id, voice=voice_id))
        return EXIT_OK
    if "yes" not in parsed.flags:
        answer = _ask_yes(io, cat.t("voices.choose.question", project=project.id, voice=voice_id))
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not answer:
            io.say(cat.t("cli.nothing_done"))
            return EXIT_NOTHING_DONE
    try:
        save_project(_project_path(home, project), sv.choose(project, registry, voice_id))
    except (ProjectError, OSError) as error:
        io.say(cat.t("voices.choose.not_saved", project=project.id))
        io.say("  " + cat.t("cli.technical", detail=getattr(error, "strerror", None) or getattr(error, "code", None) or type(error).__name__))
        return EXIT_PROBLEM
    io.say(cat.t("voices.choose.done", project=project.id, voice=voice_id))
    return EXIT_OK


# ---------------------------------------------------------------- get

class _Download:
    """The lines a download says: how far it is in steps of PROGRESS_STEP percent, and what the connection is doing."""

    def __init__(self, cat: Catalog, io: IO):
        self.cat, self.io, self.said = cat, io, 0

    def progress(self, done: int, total: int) -> None:
        if total <= 0:
            return
        percent = min(100, done * 100 // total)
        reached = 100 if percent >= 100 else percent - percent % PROGRESS_STEP
        if reached > self.said:
            self.said = reached
            self.io.say("  " + self.cat.t("voices.get.progress", percent=percent, done=size_text(done), total=size_text(total)))

    def wait(self, wait: connection.Wait) -> None:
        if wait.first:
            self.io.say("  " + self.cat.t("connection.offline_first", seconds=wait.pause_s, minutes=wait.budget_s // 60))
        else:
            self.io.say("  " + self.cat.t("connection.offline_again", seconds=wait.pause_s, waited=duration_text(self.cat, wait.waited_s)))

    def back(self) -> None:
        self.io.say("  " + self.cat.t("connection.online"))


def _after(project: Project, voice_id: str, cat: Catalog, io: IO) -> None:
    if project.starting_voice == voice_id:
        io.say(cat.t("voices.get.is_chosen", project=project.id))
    else:
        io.say(cat.t("voices.get.next_choose", command="%s choose %s --project %s" % (VOICES_COMMAND, voice_id, project.id)))


def _get(args: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO, sleep: Callable[[float], None],
         clock: Callable[[], float], fetcher: Optional[Callable]) -> int:
    try:
        parsed = parse_args(args, flags=GET_FLAGS, values=PROJECT, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voices.title"))
    voice_id = _voice_arg(parsed, registry, cat, io)
    if voice_id is None:
        return EXIT_NOTHING_DONE
    project, code = resolve_project(parsed.values.get("project"), home, cat, io)
    if project is None:
        return code
    try:
        return _get_steps(parsed, voice_id, project, home, registry, cat, io, sleep, clock, fetcher)
    except sv.StartVoiceError as error:
        _say_parts(cat, io, "startvoice", error.code, error.detail)
        return EXIT_PROBLEM
    except fetch.FetchError as error:
        _say_parts(cat, io, "fetch", error.code, error.detail)
        return EXIT_PROBLEM


def _get_steps(parsed: Parsed, voice_id: str, project: Project, home: DataHome, registry: Registry, cat: Catalog, io: IO, sleep: Callable[[float], None],
               clock: Callable[[], float], fetcher: Optional[Callable]) -> int:
    entry = sv.card(registry, voice_id)
    step = sv.next_step(project, registry, voice_id, home)           # refuses a voice that cannot be fetched yet, in words
    if step == "acknowledge":
        _show_notes(entry, cat, io)
        io.say("")
        if "acknowledge" not in parsed.flags:
            answer = _ask_yes(io, cat.t("voices.get.ack_question"))
            if answer is None:
                io.say(cat.t("voices.get.cannot_acknowledge"))
                return EXIT_NOTHING_DONE
            if not answer:
                io.say(cat.t("cli.nothing_done"))
                return EXIT_NOTHING_DONE
        updated = sv.acknowledge(project, registry, voice_id)
        try:
            save_project(_project_path(home, project), updated)
        except (ProjectError, OSError) as error:
            io.say(cat.t("voices.get.ack_not_saved"))
            io.say("  " + cat.t("cli.technical", detail=getattr(error, "strerror", None) or getattr(error, "code", None) or type(error).__name__))
            return EXIT_PROBLEM
        project = updated
        io.say(cat.t("voices.get.ack_saved", project=project.id))
        step = sv.next_step(project, registry, voice_id, home)

    if step == "ready":
        path = sv.kept_path(home, registry, voice_id)
        io.say(cat.t("voices.get.ready", project=project.id))
        io.say(cat.t("voices.get.where", path=str(path)))
        _after(project, voice_id, cat, io)
        return EXIT_OK

    folder = str(sv.voice_folder(home, registry.get(voice_id)))
    if step == "agree":
        if "yes" not in parsed.flags:
            answer = _ask_yes(io, cat.t("voices.get.download_question", size=size_text(entry.size_bytes), site=entry.host or "-", folder=folder))
            if answer is None:
                io.say(cat.t("cli.cannot_ask"))
                return EXIT_NOTHING_DONE
            if not answer:
                io.say(cat.t("cli.nothing_done"))
                return EXIT_NOTHING_DONE
        try:
            sv.agree_to_download(registry, voice_id, home)
        except OSError as error:                                  # nothing is downloaded on a yes that could not be kept
            io.say(cat.t("voices.get.agree_not_saved"))
            io.say("  " + cat.t("cli.technical", detail=error.strerror or type(error).__name__))
            return EXIT_PROBLEM
        io.say(cat.t("voices.get.agree_saved"))
    else:
        io.say(cat.t("voices.get.already_agreed"))

    shown = _Download(cat, io)
    io.say(cat.t("voices.get.downloading", size=size_text(entry.size_bytes), site=entry.host or "-"))
    path = sv.fetch_voice(project, registry, voice_id, home, on_wait=shown.wait, on_back=shown.back, sleep=sleep, clock=clock, fetcher=fetcher,
                          progress=shown.progress)
    io.say(cat.t("voices.get.done"))
    io.say(cat.t("voices.get.where", path=str(path)))
    _after(project, voice_id, cat, io)
    return EXIT_OK


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("voices.title"))
    io.say(cat.t("voices.usage.head"))
    for key in ("voices.usage.list", "voices.usage.show", "voices.usage.choose", "voices.usage.get", "voices.usage.options"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_voices(argv: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO, *, sleep: Callable[[float], None],
               clock: Callable[[], float], fetcher: Optional[Callable] = None) -> int:
    """`python3 -m voice_studio.voices COMMAND ...`. Ctrl+C at any point stops cleanly: a download keeps what arrived, and the same command carries on."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "list":
            return _list(rest, home, registry, cat, io)
        if command == "show":
            return _show(rest, home, registry, cat, io)
        if command == "choose":
            return _choose(rest, home, registry, cat, io)
        if command == "get":
            return _get(rest, home, registry, cat, io, sleep, clock, fetcher)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("voices.interrupted"))
        return EXIT_PROBLEM
