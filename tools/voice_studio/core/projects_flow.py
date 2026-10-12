# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for projects (the window runs these same flows): list them, show one, make a new one, change one's details, put one away, bring it back, delete one.

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
from .paths import ProjectPaths
from .profiles import EditInput, ProfileError, delete_project, evaluate_edit, plan_delete, split, task_running
from .project import HOW_GIVEN, MAX_NOTE, OWN, SOMEONE_ELSE, Consent, Project, ProjectError, clean_text, list_projects, save_project, with_archived
from .registry import Registry
from .setup_flow import IO, _said_yes
from .startvoice import find_voice, voices
from .system import System
from .text import Catalog, size_text

EXIT_OK, EXIT_PROBLEM, EXIT_NOTHING_DONE = 0, 1, 2
COMMANDS = ("list", "show", "new", "edit", "archive", "unarchive", "delete")
PROJECTS_COMMAND = "python3 -m voice_studio.projects"
VOICES_COMMAND = "python3 -m voice_studio.voices"
WHOSE_WORDS = {OWN: "projects.whose.own", SOMEONE_ELSE: "projects.whose.someone_else"}
CONSENT_PARTS = ("given_by", "what_to", "when", "withdraw")
NEW_VALUES = {"--name": "name", "--given-by": "given_by", "--agreed-to": "what_to", "--when": "when", "--withdraw": "withdraw", "--how-given": "how_given",
              "--how-given-other": "how_given_other", "--hours": "hours", "--voice": "voice"}
NEW_FLAGS = {"--own": "own", "--someone-else": "someone_else", "--yes": "yes", "-y": "yes"}
EDIT_VALUES = {"--name": "name", "--hours": "hours", "--given-by": "given_by", "--agreed-to": "what_to", "--when": "when", "--withdraw": "withdraw", "--how-given": "how_given",
               "--how-given-other": "how_given_other"}
YES_FLAGS = {"--yes": "yes", "-y": "yes"}
LIST_FLAGS = {"--away": "away"}
OPTIONS = {"list": frozenset(LIST_FLAGS), "show": frozenset(), "new": frozenset(NEW_VALUES) | frozenset(NEW_FLAGS), "edit": frozenset(EDIT_VALUES) | frozenset(YES_FLAGS),
           "archive": frozenset(YES_FLAGS), "unarchive": frozenset(YES_FLAGS), "delete": frozenset(YES_FLAGS)}          # the options each command takes: the checklist is held to these
MAX_FAILED_SHOWN = 5
FIELD_WORDS = {"name": "projects.field.name", "hours": "projects.field.hours", "consent.given_by": "projects.field.consent.given_by", "consent.what_to": "projects.field.consent.what_to",
               "consent.when": "projects.field.consent.when", "consent.withdraw": "projects.field.consent.withdraw", "consent.how_given": "projects.field.consent.how_given",
               "consent.how_given_other": "projects.field.consent.how_given_other"}
PART_WORDS = {"recordings": "projects.delete.what.recordings", "rounds": "projects.delete.what.rounds", "exports": "projects.delete.what.exports", "scratch": "projects.delete.what.scratch",
              "record": "projects.delete.what.record", "other": "projects.delete.what.other"}
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


def resolve_project(wanted: Optional[str], home: DataHome, cat: Catalog, io: IO, *, allow_away: bool = False) -> Tuple[Optional[Project], int]:
    """The project meant, or (None, why it could not be told). A name is exact. With none given and only one project in use, that one is used and the person is told. A project that is
    put away is found only when the command is one that may use it (`allow_away`): any other command says so and what to run."""
    listing = list_projects(home.projects)
    in_use, away = split(listing.projects)
    ids = [p.id for p in in_use]
    if wanted is not None:
        for project in listing.projects:
            if project.id == wanted:
                if project.archived and not allow_away:
                    io.say(cat.t("projects.is_away", id=project.id[:80], command="%s unarchive %s" % (PROJECTS_COMMAND, project.id)))
                    return None, EXIT_NOTHING_DONE
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
        return in_use[0], EXIT_OK
    if not ids:
        if away:
            io.say(cat.t("projects.all_away", command=PROJECTS_COMMAND + " list --away"))
        else:
            io.say(cat.t("projects.none"))
            io.say(cat.t("projects.none_next", command=PROJECTS_COMMAND + " new"))
    else:
        io.say(cat.t("projects.which", ids=", ".join(ids)))
    return None, EXIT_NOTHING_DONE


# ---------------------------------------------------------------- list and show

def _list(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parsed = parse_args(args, flags=LIST_FLAGS, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    listing = list_projects(home.projects)
    in_use, away = split(listing.projects)
    if not listing.projects and not listing.problems:
        io.say(cat.t("projects.none"))
        io.say(cat.t("projects.none_next", command=PROJECTS_COMMAND + " new"))
        return EXIT_OK
    io.say(cat.t("projects.where", folder=home.projects))
    if "away" in parsed.flags:
        if not away:
            io.say(cat.t("projects.none_away"))
            return EXIT_OK
        io.say(cat.t("projects.list.away_head"))
        shown = away
    else:
        shown = in_use
        if not in_use and away:
            io.say(cat.t("projects.all_away", command=PROJECTS_COMMAND + " list --away"))
    for project in shown:
        io.say("  " + cat.t("projects.row", id=project.id, name=project.name, whose=cat.t(WHOSE_WORDS[project.whose_voice]), hours=_hours(project.planned_hours),
                            voice=project.starting_voice or cat.t("projects.no_voice")))
    for folder, code in listing.problems:
        io.say("  " + cat.t("projects.damaged", folder=home.projects + "/" + folder))
        io.say("    " + error_text(cat, "project", code).what)
    if "away" not in parsed.flags and in_use and away:
        io.say(cat.count("projects.list.away_count", len(away), command=PROJECTS_COMMAND + " list --away"))
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
    project, code = resolve_project(parsed.words[0] if parsed.words else None, home, cat, io, allow_away=True)
    if project is None:
        return code
    io.say(cat.t("projects.show.head", id=project.id, name=project.name))
    if project.archived:
        io.say("  " + cat.t("projects.show.away", command="%s unarchive %s" % (PROJECTS_COMMAND, project.id)))
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


def _ask_yes(io: IO, prompt: str) -> Optional[bool]:
    """True for a yes, False for any other answer, None when nobody is there to ask. A window asks with a Yes and a No button instead of a typed word: an IO that has `confirm` is given the question."""
    if not io.interactive:
        return None
    confirm = getattr(io, "confirm", None)
    if confirm is not None:
        return confirm(prompt)
    answer = io.ask(prompt + " ")                              # a catalog sentence never ends in a space, so the prompt gets its own
    if answer is None:
        return None
    return _said_yes(answer)


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
        answer = _ask_yes(io, cat.t("projects.new.question"))
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not answer:
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


# ---------------------------------------------------------------- edit, put away, bring back, delete

def _paths_of(home: DataHome, project: Project) -> ProjectPaths:
    return ProjectPaths(home.projects + "/" + project.id)


def _field_words(field: str, cat: Catalog) -> str:
    return cat.t(FIELD_WORDS[field])


def _value_words(field: str, value: str, cat: Catalog) -> str:
    if not value:
        return cat.t("projects.edit.empty")
    if field == "consent.how_given" and value in HOW_GIVEN:
        return cat.t("project.how_given." + value)
    return value


def _edit(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parsed = parse_args(args, flags=YES_FLAGS, values=EDIT_VALUES, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    project, code = resolve_project(parsed.words[0] if parsed.words else None, home, cat, io)
    if project is None:
        return code
    values = parsed.values
    if not values:
        io.say(cat.t("projects.edit.nothing_given", command=PROJECTS_COMMAND + " help"))
        return EXIT_NOTHING_DONE
    c = project.consent
    consent = Consent(values.get("given_by", c.given_by), values.get("what_to", c.what_to), values.get("when", c.when), values.get("withdraw", c.withdraw),
                      _how_given_from(values["how_given"]) if "how_given" in values else c.how_given, values.get("how_given_other", c.how_given_other))
    state = evaluate_edit(project, EditInput(values.get("name", project.name), values.get("hours", _hours(project.planned_hours)), consent))
    if state.problems:
        io.say(cat.t("projects.edit.not_changed_because"))
        for problem in state.problems:
            io.say("  " + _problem_text(cat, problem))
        io.say(cat.t("projects.nothing_changed"))
        return EXIT_NOTHING_DONE
    if not state.changes:
        io.say(cat.t("projects.edit.no_change"))
        return EXIT_NOTHING_DONE
    io.say(cat.t("projects.edit.head", id=project.id))
    for change in state.changes:
        io.say("  " + cat.t("projects.edit.change", field=_field_words(change.field, cat), before=_value_words(change.field, change.before, cat),
                            after=_value_words(change.field, change.after, cat)))
    if "yes" not in parsed.flags:
        answer = _ask_yes(io, cat.t("projects.edit.question"))
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not answer:
            io.say(cat.t("projects.nothing_changed"))
            return EXIT_NOTHING_DONE
    paths = _paths_of(home, project)
    try:
        save_project(paths, state.project)
    except (ProjectError, OSError) as error:
        io.say(cat.t("projects.edit.not_saved"))
        io.say("  " + cat.t("cli.technical", detail=getattr(error, "strerror", None) or getattr(error, "code", None) or type(error).__name__))
        return EXIT_PROBLEM
    io.say(cat.t("projects.edit.saved", id=project.id))
    io.say(cat.t("projects.edit.kept", file=paths.previous_json))
    return EXIT_OK


def _set_away(args: Sequence[str], home: DataHome, cat: Catalog, io: IO, away: bool) -> int:
    try:
        parsed = parse_args(args, flags=YES_FLAGS, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    project, code = resolve_project(parsed.words[0] if parsed.words else None, home, cat, io, allow_away=True)
    if project is None:
        return code
    if project.archived == away:
        io.say(cat.t("projects.archive.already" if away else "projects.unarchive.already", id=project.id))
        return EXIT_NOTHING_DONE
    if away and task_running(home, project.id):
        io.say(cat.t("projects.archive.blocked", name=project.name))
        io.say(cat.t("projects.nothing_changed"))
        return EXIT_NOTHING_DONE
    if "yes" not in parsed.flags:
        answer = _ask_yes(io, cat.t("projects.archive.question" if away else "projects.unarchive.question", name=project.name))
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not answer:
            io.say(cat.t("projects.nothing_changed"))
            return EXIT_NOTHING_DONE
    try:
        save_project(_paths_of(home, project), with_archived(project, away))
    except (ProjectError, OSError) as error:
        io.say(cat.t("projects.edit.not_saved"))
        io.say("  " + cat.t("cli.technical", detail=getattr(error, "strerror", None) or getattr(error, "code", None) or type(error).__name__))
        return EXIT_PROBLEM
    if away:
        io.say(cat.t("projects.archive.done", id=project.id, command="%s unarchive %s" % (PROJECTS_COMMAND, project.id)))
    else:
        io.say(cat.t("projects.unarchive.done", id=project.id))
    return EXIT_OK


def _archive(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    return _set_away(args, home, cat, io, True)


def _unarchive(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    return _set_away(args, home, cat, io, False)


def _say_profile_error(error: ProfileError, cat: Catalog, io: IO) -> None:
    parts = error_text(cat, "profiles", error.code)
    for text in (parts.what, parts.changed, parts.next):
        io.say("  " + text)


def _delete(args: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime]) -> int:
    try:
        parsed = parse_args(args, flags=YES_FLAGS, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("projects.title"))
    project, code = resolve_project(parsed.words[0] if parsed.words else None, home, cat, io, allow_away=True)
    if project is None:
        return code
    try:
        plan = plan_delete(home, project)
    except ProfileError as error:
        _say_profile_error(error, cat, io)
        return EXIT_NOTHING_DONE
    except OSError as error:
        io.say(cat.t("projects.delete.cannot_look", folder=home.projects + "/" + project.id))
        io.say("  " + cat.t("cli.technical", detail=error.strerror or type(error).__name__))
        return EXIT_PROBLEM
    io.say(cat.t("projects.delete.head", id=project.id, name=project.name))
    io.say("  " + cat.t("projects.show.folder", folder=plan.root))
    for kind, size, files in plan.by_kind:
        io.say("  " + cat.count("projects.delete.part", files, what=cat.t(PART_WORDS[kind]), size=size_text(size)))
    io.say(cat.count("projects.delete.total", plan.total_files, size=size_text(plan.total_bytes)))
    if plan.voice_files:
        io.say(cat.t("projects.delete.voice_files", names=", ".join(plan.voice_files)))
    else:
        io.say(cat.t("projects.delete.no_voice_files"))
    if plan.left_scratch:
        io.say(cat.t("projects.delete.left", folder=plan.left_scratch))
    io.say(cat.t("projects.delete.backup"))
    if plan.blocked:
        _say_profile_error(ProfileError("job_running"), cat, io)
        return EXIT_NOTHING_DONE
    if "yes" not in parsed.flags:
        answer = _ask_yes(io, cat.t("projects.delete.first", name=project.name))
        if answer is None:
            io.say(cat.t("cli.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not answer:
            io.say(cat.t("projects.delete.not_deleted"))
            return EXIT_NOTHING_DONE
    answer = _ask_yes(io, cat.count("projects.delete.second", plan.total_files, name=project.name, size=size_text(plan.total_bytes)))          # never skipped by --yes: the last word is always a person's
    if answer is None:
        io.say(cat.t("cli.cannot_ask"))
        io.say(cat.t("projects.delete.not_deleted"))
        return EXIT_NOTHING_DONE
    if not answer:
        io.say(cat.t("projects.delete.not_deleted"))
        return EXIT_NOTHING_DONE
    try:
        result = delete_project(home, project, plan)
    except ProfileError as error:
        _say_profile_error(error, cat, io)
        return EXIT_NOTHING_DONE
    if result.gone and not result.failed:
        io.say(cat.t("projects.delete.done", id=project.id, size=size_text(result.bytes)))
        return EXIT_OK
    io.say(cat.t("projects.delete.partial_head"))
    for path, why in result.failed[:MAX_FAILED_SHOWN]:
        io.say("  " + cat.t("projects.delete.failed_row", path=path, reason=why))
    if len(result.failed) > MAX_FAILED_SHOWN:
        io.say("  " + cat.t("projects.delete.failed_more", count=len(result.failed) - MAX_FAILED_SHOWN))
    io.say(cat.t("projects.delete.partial_next"))
    return EXIT_PROBLEM


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("projects.title"))
    io.say(cat.t("projects.usage.head"))
    for key in ("projects.usage.list", "projects.usage.list_away", "projects.usage.show", "projects.usage.new", "projects.usage.options", "projects.usage.edit", "projects.usage.edit_options", "projects.usage.archive",
                "projects.usage.unarchive", "projects.usage.delete"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_projects(argv: Sequence[str], system: System, home: DataHome, registry: Registry, cat: Catalog, io: IO, now: Optional[datetime] = None) -> int:
    """`python3 -m voice_studio.projects COMMAND ...`. Ctrl+C at any point stops cleanly."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        handler = {"list": _list, "show": _show, "new": _new, "edit": _edit, "archive": _archive, "unarchive": _unarchive, "delete": _delete}.get(command)
        if handler is None:
            io.say(cat.t("cli.bad_command", command=command[:60]))
            return EXIT_NOTHING_DONE
        return handler(rest, system, home, registry, cat, io, now)
    except KeyboardInterrupt:
        io.say(cat.t("projects.interrupted", command=PROJECTS_COMMAND + " list"))
        return EXIT_PROBLEM
