# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for projects (until the window exists): list them, show one, make a new one.

It is the front of core/project.py and core/newproject.py and decides nothing they do not: the form is judged by `newproject.evaluate`, the project is made
by `newproject.create`. Every sentence comes from the text catalog; every decision is made from a `System`, an `IO` and a `DataHome` handed in, so it is tested
without a terminal.

Two rules for a person who has to be able to trust it. **Nothing is made without a yes** (typed `yes` at the question, or `--yes` on the command line), and the
question is asked only after the whole project has been shown. **Every answer can be given as an option**, so one pasted line does the whole job; anything left out
is asked one question at a time, and only when someone is there to answer. Exit codes: 0 done, 1 something failed, 2 nothing was done (declined, nobody to ask, a
form that is not complete, or an option that is not understood).
"""
from __future__ import annotations

import os
from dataclasses import astuple, replace
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .cliargs import ArgError, Parsed, parse_args
from .describe import error_text
from .newproject import FormInput, FormState, Problem, create, evaluate
from .paths import DataHome
from .project import HOW_GIVEN, MAX_NOTE, OWN, SOMEONE_ELSE, Consent, Project, ProjectError, clean_text, list_projects
from .registry import Registry
from .setup_flow import IO, _said_yes
from .startvoice import find_voice, voices
from .system import System
from .text import Catalog, size_text

EXIT_OK, EXIT_PROBLEM, EXIT_NOTHING_DONE = 0, 1, 2
COMMANDS = ("list", "show", "new")
PROJECTS_COMMAND = "python3 -m voice_studio.projects"
VOICES_COMMAND = "python3 -m voice_studio.voices"
WHOSE_WORDS = {OWN: "projects.whose.own", SOMEONE_ELSE: "projects.whose.someone_else"}
CONSENT_PARTS = ("given_by", "what_to", "when", "withdraw")
NEW_VALUES = {"--name": "name", "--given-by": "given_by", "--agreed-to": "what_to", "--when": "when", "--withdraw": "withdraw", "--how-given": "how_given",
              "--how-given-other": "how_given_other", "--hours": "hours", "--voice": "voice"}
NEW_FLAGS = {"--own": "own", "--someone-else": "someone_else", "--yes": "yes", "-y": "yes"}
OPTIONS = {"list": frozenset(), "show": frozenset(), "new": frozenset(NEW_VALUES) | frozenset(NEW_FLAGS)}          # the options each command takes: the checklist is held to these
ARG_ERRORS = {"unknown": "cli.bad_option", "missing_value": "cli.missing_value", "repeated": "cli.repeated", "extra_word": "cli.extra_word"}


def say_bad_arg(error: ArgError, cat: Catalog, io: IO) -> int:
    io.say(cat.t(ARG_ERRORS[error.code], option=error.arg[:60], word=error.arg[:60]))
    return EXIT_NOTHING_DONE


def _hours(value: float) -> str:
    return "%g" % value


# ---------------------------------------------------------------- finding a project

def _project_ids(home: DataHome) -> Tuple[List[str], List[str]]:
    listing = list_projects(home.projects)
    return [p.id for p in listing.projects], [folder for folder, _ in listing.problems]


def resolve_project(wanted: Optional[str], home: DataHome, cat: Catalog, io: IO) -> Tuple[Optional[Project], int]:
    """The project meant, or (None, why it could not be told). A name is exact. With none given and only one project, that one is used and the person is told."""
    listing = list_projects(home.projects)
    ids = [p.id for p in listing.projects]
    if wanted is not None:
        for project in listing.projects:
            if project.id == wanted:
                return project, EXIT_OK
        if wanted in [folder for folder, _ in listing.problems]:
            io.say(cat.t("projects.is_damaged", id=wanted[:80]))
        elif ids:
            io.say(cat.t("projects.not_found", id=wanted[:80], ids=", ".join(ids)))
        else:
            io.say(cat.t("projects.not_found_none", id=wanted[:80]))
        return None, EXIT_NOTHING_DONE
    if len(ids) == 1:                                        # a damaged folder cannot be used, so it does not make the choice unclear
        io.say(cat.t("projects.using_only", id=ids[0]))
        return listing.projects[0], EXIT_OK
    if not ids:
        io.say(cat.t("projects.none"))
        io.say(cat.t("projects.none_next", command=PROJECTS_COMMAND + " new"))
    else:
        io.say(cat.t("projects.which", ids=", ".join(ids)))
    return None, EXIT_NOTHING_DONE


# ---------------------------------------------------------------- list and show

def _list(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parse_args(args, flags={}, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    listing = list_projects(home.projects)
    if not listing.projects and not listing.problems:
        io.say(cat.t("projects.none"))
        io.say(cat.t("projects.none_next", command=PROJECTS_COMMAND + " new"))
        return EXIT_OK
    io.say(cat.t("projects.where", folder=home.projects))
    for project in listing.projects:
        io.say("  " + cat.t("projects.row", id=project.id, name=project.name, whose=cat.t(WHOSE_WORDS[project.whose_voice]), hours=_hours(project.planned_hours),
                            voice=project.starting_voice or cat.t("projects.no_voice")))
    for folder, code in listing.problems:
        io.say("  " + cat.t("projects.damaged", folder=home.projects + "/" + folder))
        io.say("    " + error_text(cat, "project", code).what)
    return EXIT_OK


def _consent_lines(consent: Consent, cat: Catalog) -> List[str]:
    lines = []
    for part in CONSENT_PARTS:
        lines.append(cat.t("projects.show.consent_line", question=cat.t("project.consent.missing." + part), answer=getattr(consent, part)))
    given = cat.t("project.how_given." + consent.how_given) if consent.how_given in HOW_GIVEN else consent.how_given
    lines.append(cat.t("projects.show.consent_line", question=cat.t("project.consent.missing.how_given"), answer=given))
    if consent.how_given_other:
        lines.append(cat.t("projects.show.consent_line", question=cat.t("project.consent.missing.how_given_other"), answer=consent.how_given_other))
    return lines


def _show(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parsed = parse_args(args, flags={}, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    project, code = resolve_project(parsed.words[0] if parsed.words else None, home, cat, io)
    if project is None:
        return code
    io.say(cat.t("projects.show.head", id=project.id, name=project.name))
    io.say("  " + cat.t("projects.show.whose", whose=cat.t(WHOSE_WORDS[project.whose_voice])))
    io.say("  " + cat.t("projects.show.folder", folder=home.projects + "/" + project.id))
    io.say("  " + cat.t("projects.show.created", created=project.created))
    io.say("  " + cat.t("projects.show.hours", hours=_hours(project.planned_hours)))
    io.say("  " + cat.t("projects.show.voice", voice=project.starting_voice or cat.t("projects.no_voice")))
    if project.whose_voice == SOMEONE_ELSE:
        io.say("  " + cat.t("projects.show.consent_head"))
        for line in _consent_lines(project.consent, cat):
            io.say("    " + line)
    if project.acknowledgments:
        io.say("  " + cat.t("projects.show.acks_head"))
        for ack in project.acknowledgments:
            io.say("    " + cat.t("projects.show.ack", voice=ack.voice, date=ack.at, revision=ack.revision[:12]))
    else:
        io.say("  " + cat.t("projects.show.acks_none"))
    return EXIT_OK


# ---------------------------------------------------------------- new

def _problem_text(cat: Catalog, problem: Problem) -> str:
    head, _, part = problem.field.partition(".")
    if head == "consent" and part and problem.code == "missing":
        return cat.t("project.consent.missing." + part) + " " + cat.t("newproject.problem.consent.missing")
    key = "newproject.problem.%s.%s" % (head, problem.code)
    return cat.t(key) if cat.has(key) else "%s: %s" % (problem.field, problem.code)


def _how_given_from(typed: str) -> str:
    """A number from the list, or the word for it ("through-guardian" and "through_guardian" are the same); anything else is kept as typed, for the form to refuse."""
    word = " ".join(typed.split()).lower().replace("-", "_")
    if word.isdigit() and 1 <= int(word) <= len(HOW_GIVEN):
        return HOW_GIVEN[int(word) - 1]
    return word


def _form_from(parsed: Parsed, registry: Registry) -> FormInput:
    values = parsed.values
    whose = OWN if "own" in parsed.flags else SOMEONE_ELSE if "someone_else" in parsed.flags else ""
    consent = Consent(values.get("given_by", ""), values.get("what_to", ""), values.get("when", ""), values.get("withdraw", ""),
                      _how_given_from(values["how_given"]) if "how_given" in values else "", values.get("how_given_other", ""))
    voice = None
    if "voice" in values:
        voice = find_voice(registry, values["voice"]) or values["voice"]          # an unknown one stays as typed, for the form to name
    return FormInput(name=values.get("name", ""), whose_voice=whose, consent=consent, hours=values.get("hours", "1"), starting_voice=voice)


def _ask(io: IO, prompt: str) -> str:
    answer = io.ask(prompt + " ")                              # a catalog sentence never ends in a space, so the prompt gets its own
    return "" if answer is None else answer


def _ask_whose(cat: Catalog, io: IO) -> str:
    answer = " ".join(_ask(io, cat.t("projects.new.ask_whose")).split()).lower()
    if answer in ("1", "own", "mine", "my own"):
        return OWN
    if answer in ("2", "someone", "someone else", "someone_else", "else", "other"):
        return SOMEONE_ELSE
    return ""


def _ask_consent(consent: Consent, cat: Catalog, io: IO) -> Consent:
    answers: Dict[str, str] = {part: getattr(consent, part) for part in CONSENT_PARTS}
    for part in CONSENT_PARTS:
        if not answers[part].strip():
            answers[part] = _ask(io, cat.t("project.consent.missing." + part))
    how, other = consent.how_given, consent.how_given_other
    if how not in HOW_GIVEN:
        io.say(cat.t("project.consent.missing.how_given"))
        for number, choice in enumerate(HOW_GIVEN, 1):
            io.say("  " + cat.t("projects.new.choice", number=number, words=cat.t("project.how_given." + choice)))
        how = _how_given_from(_ask(io, cat.t("projects.new.ask_choice")))
    if how == "other" and not other.strip():
        other = _ask(io, cat.t("project.consent.missing.how_given_other"))
    return Consent(answers["given_by"], answers["what_to"], answers["when"], answers["withdraw"], how, other)


def _complete(form: FormInput, parsed: Parsed, cat: Catalog, io: IO) -> FormInput:
    """Ask, one question at a time, for what was left out. Nothing that was given is asked again, and nothing is asked when nobody is there to answer."""
    name = form.name if form.name.strip() else _ask(io, cat.t("projects.new.ask_name"))
    whose = form.whose_voice if form.whose_voice in (OWN, SOMEONE_ELSE) else _ask_whose(cat, io)
    consent = _ask_consent(form.consent, cat, io) if whose == SOMEONE_ELSE else form.consent
    hours = form.hours
    if "hours" not in parsed.values:
        typed = _ask(io, cat.t("projects.new.ask_hours"))
        if typed.strip():
            hours = typed
    return replace(form, name=name, whose_voice=whose, consent=consent, hours=hours)


def _taken(home: DataHome) -> List[str]:
    try:
        return os.listdir(home.projects)
    except OSError:
        return []


def _judge(form: FormInput, home: DataHome, registry: Registry, free: Optional[int]) -> FormState:
    return evaluate(form, taken_ids=_taken(home), voice_ids=[c.voice_id for c in voices(registry)], free={"project": free})


def _new(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parsed = parse_args(args, flags=NEW_FLAGS, values=NEW_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    if "own" in parsed.flags and "someone_else" in parsed.flags:
        io.say(cat.t("projects.new.both_whose"))
        return EXIT_NOTHING_DONE
    io.say(cat.t("projects.new.intro"))
    disk = system.disk_free(home.home)
    free = disk[1] if disk else None
    form = _form_from(parsed, registry)
    if io.interactive:
        form = _complete(form, parsed, cat, io)
    state = _judge(form, home, registry, free)
    if not state.can_create:
        io.say(cat.t("projects.new.not_made_because"))
        for problem in state.problems:
            io.say("  " + _problem_text(cat, problem))
        if not io.interactive:
            io.say(cat.t("projects.new.give_options", command=PROJECTS_COMMAND + " help"))
        io.say(cat.t("projects.new.not_made"))
        return EXIT_NOTHING_DONE

    _summary(state, form, home, free, cat, io)
    if "yes" not in parsed.flags:
        answer = io.ask(cat.t("projects.new.question") + " ") if io.interactive else None
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not _said_yes(answer):
            io.say(cat.t("projects.new.not_made"))
            return EXIT_NOTHING_DONE
    try:
        result = create(form, state, home.projects, now)
    except ProjectError as error:
        parts = error_text(cat, "project", error.code)
        io.say("  " + parts.what)
        io.say("  " + parts.changed)
        io.say("  " + parts.next)
        return EXIT_PROBLEM
    except OSError as error:
        io.say(cat.t("projects.new.not_made_disk"))
        io.say("  " + cat.t("cli.technical", detail=error.strerror or type(error).__name__))
        return EXIT_PROBLEM
    project = result.project
    io.say(cat.t("projects.new.made", id=project.id))
    io.say(cat.t("projects.new.where", folder=home.projects + "/" + project.id))
    io.say(cat.t("projects.new.next", command="%s list --project %s" % (VOICES_COMMAND, project.id)))
    return EXIT_OK


def _summary(state: FormState, form: FormInput, home: DataHome, free: Optional[int], cat: Catalog, io: IO) -> None:
    io.say(cat.t("projects.new.summary_head"))
    io.say("  " + cat.t("projects.show.head", id=state.project_id, name=state.clean_name))
    io.say("  " + cat.t("projects.show.whose", whose=cat.t(WHOSE_WORDS[form.whose_voice])))
    io.say("  " + cat.t("projects.show.folder", folder=home.projects + "/" + state.project_id))
    io.say("  " + cat.t("projects.show.hours", hours=_hours(state.hours or 0.0)))
    io.say("  " + cat.t("projects.show.voice", voice=form.starting_voice or cat.t("projects.no_voice")))
    if form.whose_voice == SOMEONE_ELSE:
        io.say("  " + cat.t("projects.show.consent_head"))
        for line in _consent_lines(Consent(*(clean_text(value, MAX_NOTE) for value in astuple(form.consent))), cat):          # as it will be saved
            io.say("    " + line)
    estimate = state.estimate
    if estimate is not None:
        need = estimate.need.get("project", 0)
        if free is None:
            io.say(cat.t("projects.new.disk_unknown", need=size_text(need)))
        else:
            io.say(cat.t("projects.new.disk", need=size_text(need), free=size_text(free)))
            if estimate.short_by.get("project", 0) > 0:
                io.say(cat.t("projects.new.disk_short"))
        if estimate.rough:
            io.say(cat.t("projects.new.disk_rough"))


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("projects.title"))
    io.say(cat.t("projects.usage.head"))
    for key in ("projects.usage.list", "projects.usage.show", "projects.usage.new", "projects.usage.options"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_projects(argv: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime] = None) -> int:
    """`python3 -m voice_studio.projects COMMAND ...`. Ctrl+C at any point stops cleanly."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        handler = {"list": _list, "show": _show, "new": _new}.get(command)
        if handler is None:
            io.say(cat.t("cli.bad_command", command=command[:60]))
            return EXIT_NOTHING_DONE
        return handler(rest, system, home, registry, cat, io, now)
    except KeyboardInterrupt:
        io.say(cat.t("projects.interrupted", command=PROJECTS_COMMAND + " list"))
        return EXIT_PROBLEM
