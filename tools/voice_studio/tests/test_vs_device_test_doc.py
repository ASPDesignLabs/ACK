# SPDX-License-Identifier: GPL-3.0-or-later
"""The device-test checklist (docs/VOICE_STUDIO_DEVICE_TEST.md) tells a person to run commands. A checklist whose commands do not work wastes the one
afternoon they have for it, so every command it names is checked here: the programs exist and take the options given, the paths it points to are
there, the training command is the one the tool builds, and each snippet is run for real against made-up inputs, in a home folder of its own."""
import json
import os
import re
import shlex
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from voice_studio.core import commands, ackimport as _ackimport      # noqa: F401  (ackimport needs numpy: the tests that use it skip without it)
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.setup_flow import parse_options

import vs_voice_helpers as vh

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "tools"
DOC = REPO / "docs" / "VOICE_STUDIO_DEVICE_TEST.md"
SNIPPETS = ("jobs-start", "jobs-list", "jobs-stop", "package-summary", "flip-a-byte", "disk-guard", "checkpoint-check", "voice-zip")


def doc_text():
    return DOC.read_text(encoding="utf-8")


def fenced_after(marker):
    """The lines of the code block that follows `<!-- snippet: marker -->`, without the indentation the list gives them."""
    lines = doc_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "<!-- snippet: %s -->" % marker)
    fence = lines[start + 1]
    indent = len(fence) - len(fence.lstrip())
    assert fence.strip().startswith("```"), marker
    body = []
    for line in lines[start + 2:]:
        if line.strip() == "```":
            return [l[indent:] for l in body]
        body.append(line)
    raise AssertionError("block not closed: " + marker)


def heredoc(marker):
    """(the arguments after `python3 -`, the python program) of a block that runs one heredoc."""
    block = fenced_after(marker)
    head = next(i for i, line in enumerate(block) if "<<'EOF'" in line)
    call = shlex.split(block[head].split("<<")[0])
    end = block.index("EOF", head)
    program = "\n".join(block[head + 1:end]) + "\n"
    found = False
    if call[0] == "PYTHONPATH=~/ack-tools/tools":
        call, found = call[1:], True
    assert call[:2] == ["python3", "-"], marker
    assert found or "voice_studio" not in program, (marker, "a snippet that uses the tool must find it from any folder, as the person's terminal may be anywhere")
    return call[2:], program


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    return folder


SPY_ON_THE_SECOND_LOOK = """
import os, voice_studio.core.voicezip as _v
_real = _v.verify_voice_zip
def _spy(path):
    with open(os.path.join(os.environ["HOME"], "second-look"), "a") as note:
        note.write(str(path) + "\\n")
    return _real(path)
_v.verify_voice_zip = _spy
"""


def run_snippet(marker, home, *args, stdin="", use_doc_args=True, preamble=""):
    """Run the block's python the way the heredoc does (`PYTHONPATH=… python3 - ARGS`, from a folder that is not the tools folder), with `-c` so that standard input can carry the answers."""
    doc_args, program = heredoc(marker)
    given = [os.path.expanduser(a) for a in (doc_args if use_doc_args else [])] + [str(a) for a in args]
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = str(TOOLS)                       # the doc's `PYTHONPATH=~/ack-tools/tools`, pointed at this checkout
    elsewhere = Path(home) / "somewhere-else"            # not the tools folder: the person's terminal may be in any folder
    elsewhere.mkdir(exist_ok=True)
    return subprocess.run([sys.executable, "-c", preamble + program, *given], input=stdin, cwd=str(elsewhere), env=env, text=True, capture_output=True, timeout=60)


# ---------------------------------------------------------------- the checklist's promises that need no input

def test_every_snippet_the_checklist_relies_on_is_there_and_nothing_else_is_marked():
    assert tuple(re.findall(r"<!-- snippet: ([a-z-]+) -->", doc_text())) == SNIPPETS
    for name in SNIPPETS:
        assert fenced_after(name), name


def test_it_says_how_to_get_the_branch_this_tool_is_on_before_anything_needs_it():
    text = doc_text()
    first_use = text.index("run_tests.sh")
    step = text.index("## 0. Get this branch")
    assert step < text.index("## B.") and step < first_use, "the clone comes before the first command that needs it"
    assert "git clone --branch claude/voice-studio-guided-setup https://github.com/ASPDesignLabs/ACK.git ~/ack-tools" in text
    assert "mv ~/ack-tools ~/ack-tools.old" in text, "an older folder is moved aside, never replaced"


def option_words(text):
    return re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", text)


def test_the_freeform_studio_commands_it_names_exist_and_take_the_options_it_gives():
    seen = {}
    for line in doc_text().splitlines():
        for module, rest in re.findall(r"python -m freeform_studio\.([a-z_]+)([^`]*)", line):
            seen.setdefault(module, set()).update(option_words(rest))
            if module == "models":
                assert re.search(r"\b(list|fetch)\b", rest), line
    assert {"ack_import", "asr_smoke", "build_dataset", "models", "process"} <= set(seen)
    for module, options in seen.items():
        out = subprocess.run([sys.executable, "-m", "freeform_studio." + module, "--help"], cwd=str(TOOLS), env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0 and "No module named" in out.stderr:
            pytest.skip("Freeform Studio's libraries are not installed here: " + out.stderr.strip().splitlines()[-1])
        assert out.returncode == 0, (module, out.stderr[-300:])
        for option in options:
            assert re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(option), out.stdout), (module, option)


def test_the_setup_options_it_names_are_ones_the_first_step_accepts():
    named = set(re.findall(r"setup\.sh (--[a-z-]+)", doc_text()))
    assert {"--check", "--dry-run"} <= named
    for flag in named:
        opts, unknown = parse_options([flag])
        assert opts is not None, flag


def test_the_files_and_documents_it_points_to_exist():
    text = doc_text()
    for rel in sorted(set(re.findall(r"`((?:docs|tools)/[\w./-]+\.(?:md|py|sh))`", text))):
        assert (REPO / rel).is_file(), rel
    for rel in sorted(set(re.findall(r"~/ack-tools/(tools/[\w./-]+\.(?:py|sh))", text))):
        assert (REPO / rel).is_file(), rel


def test_the_training_command_in_the_checklist_is_the_one_the_tool_builds(tmp_path):
    lines = next(b for b in _fences() if "piper.train fit" in b).splitlines()
    first = next(i for i, l in enumerate(lines) if '"$TRAIN/venv/bin/python" "$TRAIN/ack_run.py" piper.train fit' in l)
    last = next(i for i in range(first, len(lines)) if not lines[i].rstrip().endswith("\\"))          # the command ends at the first line with no continuation
    words = shlex.split(" ".join(l.rstrip("\\").strip() for l in lines[first:last + 1]).split(" 2>&1")[0])
    shown = {words[i][2:]: words[i + 1] for i in range(4, len(words) - 1, 2) if words[i].startswith("--")}
    dataset = tmp_path / "dataset-1"
    (dataset / "wav").mkdir(parents=True)
    (dataset / "wav" / "a.wav").write_bytes(b"x")
    (dataset / "metadata.csv").write_text("a.wav|hello\n")
    (tmp_path / "base.ckpt").write_bytes(b"x")
    built = commands.train_command(EnvPaths("/e/training-x"), str(dataset), str(tmp_path / "run"), str(tmp_path / "cache"), str(tmp_path / "config.json"),
                                   str(tmp_path / "base.ckpt"), minutes=5).argv
    made = {built[i][2:]: built[i + 1] for i in range(4, len(built) - 1, 2) if built[i].startswith("--")}
    paths = {"data.csv_path", "data.audio_dir", "data.cache_dir", "data.config_path", "ckpt_path"}
    assert set(shown) == set(made), "the checklist and the tool must give the trainer the same options"
    assert {k: v for k, v in shown.items() if k not in paths} == {k: v for k, v in made.items() if k not in paths}


def test_the_build_command_the_checklist_gives_takes_the_options_it_gives_and_changes_nothing_when_only_looking(home):
    from voice_studio.core.buildenv_flow import parse_build_options
    commands_given = re.findall(r"PYTHONPATH=~/ack-tools/tools python3 -m voice_studio\.buildenv ([^;\n`]*)", doc_text())
    assert len(commands_given) >= 2
    for given in commands_given:
        parsed, unknown = parse_build_options(shlex.split(given))
        assert parsed is not None, given
        assert parsed.env_id == "training"
    assert any("--check" in c for c in commands_given) and any("--check" not in c for c in commands_given)
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(TOOLS))
    done = subprocess.run([sys.executable, "-m", "voice_studio.buildenv", "training", "--check"], cwd=str(home), env=env, text=True, capture_output=True, timeout=120)
    assert done.returncode == 1 and done.stdout.startswith("ACK Voice Studio: setting up one set of programs"), done.stdout + done.stderr
    assert not (Path(home) / "ack-voice-studio").exists() and sorted(p.name for p in Path(home).iterdir()) == []


def test_the_folders_the_checklist_names_for_the_tool_built_programs_are_where_the_tool_puts_them():
    from voice_studio.core.paths import DATA_HOME_NAME, DataHome
    assert "~/%s/tool/environments/training-" % DATA_HOME_NAME in doc_text()
    assert DataHome("/h").environments == "/h/%s/tool/environments" % DATA_HOME_NAME


def _fences():
    return re.findall(r"```bash\n(.*?)```", doc_text(), flags=re.S)


# ---------------------------------------------------------------- the snippets, run for real in a home folder of their own

def poll(check, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.2)
    return check()


def _listing(home, wanted):
    out = run_snippet("jobs-list", home).stdout
    return out if wanted in out else ""


def test_a_job_can_be_started_looked_at_and_asked_to_stop_with_the_checklists_snippets(home):
    started = run_snippet("jobs-start", home)
    assert started.returncode == 0 and re.search(r"^started \S+-check-\S+ running runner \d+$", started.stdout.strip()), (started.stdout, started.stderr)
    listing = poll(lambda: _listing(home, "hello from the check job"))
    assert " running exit None" in listing and "log: hello from the check job" in listing
    stopped = run_snippet("jobs-stop", home)
    assert stopped.returncode == 0 and stopped.stdout.strip().endswith(" asked")
    asked_for = [json.loads(p.read_text()) for p in (home / "ack-voice-check" / "jobs").glob("*/job.json")]
    assert len(asked_for) == 1 and asked_for[0]["gpu"] is False and asked_for[0]["project"] == "", "the check job must never hold the graphics card"
    notes = list((home / "ack-voice-check" / "jobs").glob("*/stop.json"))
    assert len(notes) == 1 and json.loads(notes[0].read_text())["forced"] is False, "the gentle stop (like Ctrl+C once), never the forced one"
    final = poll(lambda: _listing(home, " stopped "))
    assert " stopped " in final, final
    assert "Traceback" not in started.stderr + stopped.stderr


@pytest.fixture
def phone_package(home):
    pytest.importorskip("numpy", reason="the package builder needs numpy (it is installed with Freeform Studio's environment)")
    sys.path.insert(0, str(TOOLS / "freeform_studio" / "tests"))
    from ack_package_builder import ClipSpec, PackageBuilder
    b = PackageBuilder()
    b.script_session([ClipSpec("The tide came in.", speech=2.0), ClipSpec("We walked along the shore.", speech=3.0), ClipSpec("Gulls circled overhead.", speech=1.5)])
    (home / "Downloads").mkdir()
    return b.write(home / "Downloads" / "ack-training-XXXX.zip")


def takes_of(home):
    folder = home / "ack-voice-check" / "recordings" / "_freeform" / "en-US" / "takes"
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def test_a_package_is_looked_at_first_added_only_when_told_to_and_recognised_the_next_time(home, phone_package):
    before = phone_package.read_bytes()
    looked = run_snippet("package-summary", home)
    assert looked.returncode == 0, (looked.stdout, looked.stderr)
    assert "to add: 1" in looked.stdout and "(new copy)" in looked.stdout and "run this again with the word add at the end" in looked.stdout
    assert takes_of(home) == [], "without the word add, nothing is added"
    assert (home / "ack-voice-check" / "recordings" / "_freeform" / "en-US" / "incoming" / "ack-training-XXXX.zip").is_file()
    added = run_snippet("package-summary", home, "add")
    assert added.returncode == 0 and added.stdout.count("  added ") == 1 and len(takes_of(home)) == 1, (added.stdout, added.stderr)
    again = run_snippet("package-summary", home, "add")
    assert "to add: 0" in again.stdout and "Already added" in again.stdout and "(already there)" in again.stdout and len(takes_of(home)) == 1
    assert "Nothing to add: everything in this package is already in." in again.stdout and again.stdout.count("  added ") == 0
    assert phone_package.read_bytes() == before, "the package on the computer is never changed"
    assert "Traceback" not in looked.stderr + added.stderr + again.stderr


def test_the_package_snippet_never_waits_for_an_answer_because_a_heredoc_leaves_it_nothing_to_read(home, phone_package):
    """The doc runs it as `python3 - ARGS <<'EOF'`, so the program is what standard input carries: an `input()` in it fails with EOFError. Run it exactly that way."""
    doc_args, program = heredoc("package-summary")
    env = dict(os.environ, HOME=str(home), PYTHONPATH=str(TOOLS), PYTHONDONTWRITEBYTECODE="1")
    given = [os.path.expanduser(a) for a in doc_args]
    done = subprocess.run([sys.executable, "-", *given], input=program, cwd=str(home), env=env, text=True, capture_output=True, timeout=60)
    assert done.returncode == 0 and "Nothing was added." in done.stdout and "EOFError" not in done.stderr, (done.stdout, done.stderr)
    assert "input(" not in program


def test_a_package_with_one_byte_changed_is_refused_in_plain_words_and_leaves_nothing(home, phone_package):
    damaged = home / "ack-voice-check" / "damaged.zip"
    damaged.parent.mkdir(parents=True)
    damaged.write_bytes(phone_package.read_bytes())
    flipped = run_snippet("flip-a-byte", home)
    assert flipped.returncode == 0 and damaged.read_bytes() != phone_package.read_bytes() and len(damaged.read_bytes()) == len(phone_package.read_bytes())
    refused = run_snippet("package-summary", home, damaged, home / "ack-voice-check" / "recordings", "add", use_doc_args=False)
    assert refused.returncode == 1, (refused.stdout, refused.stderr)
    assert "This file is not a complete ACK package, so it was not used." in refused.stdout
    assert "Nothing was added. The original file was not changed." in refused.stdout and "Copy the file from the phone again" in refused.stdout
    assert not (home / "ack-voice-check" / "recordings" / "_freeform" / "en-US" / "incoming" / "damaged.zip").exists()
    assert takes_of(home) == [] and "Traceback" not in refused.stderr


def test_a_voice_is_checked_zipped_checked_again_and_never_written_over(home):
    folder = home / "piper" / "voice-check"
    model, config = vh.write_voice(folder, name="my_voice")
    dest = home / "ack-voice-check" / "my_voice_backup.zip"
    dest.parent.mkdir(parents=True)
    made = run_snippet("voice-zip", home, preamble=SPY_ON_THE_SECOND_LOOK)
    assert (home / "second-look").read_text().split() == [str(dest)], "the finished zip is checked a second time, as the phone would"
    assert made.returncode == 0 and "written: " in made.stdout and "checked again as the phone would: no problems" in made.stdout, (made.stdout, made.stderr)
    with zipfile.ZipFile(dest) as z:
        assert z.namelist() == ["model.onnx", "model.onnx.json"]
    first = dest.read_bytes()
    second = run_snippet("voice-zip", home)
    assert second.returncode == 1 and "A file with that name is already there." in second.stdout and "It was left as it is, and nothing new was written." in second.stdout
    assert dest.read_bytes() == first
    (folder / "raw.onnx").write_bytes(vh.onnx_bytes({}))
    (folder / "raw.onnx.json").write_text((folder / "my_voice.onnx.json").read_text())
    raw = run_snippet("voice-zip", home, use_doc_args=False, *[folder / "raw.onnx", folder / "raw.onnx.json", home / "ack-voice-check" / "raw.zip"])
    assert raw.returncode == 1 and "has not been prepared for the phone yet" in raw.stdout and "This voice is not ready to send to the phone." in raw.stdout
    assert sorted(p.name for p in dest.parent.iterdir()) == ["my_voice_backup.zip"], "no zip and no half-written file is left"
    assert "Traceback" not in made.stderr + second.stderr + raw.stderr


# ---------------------------------------------------------------- section I1: projects and starting voices

def section(prefix):
    match = re.search(r"^## %s.*?(?=^## |\Z)" % re.escape(prefix), doc_text(), flags=re.S | re.M)
    assert match, prefix
    return match.group(0)


def test_the_project_and_voice_commands_it_gives_exist_and_take_the_options_it_gives():
    from voice_studio.core import projects_flow as pf, voices_flow as vf
    from voice_studio.core.project import slugify
    from voice_studio.core.registry import load_registry
    from voice_studio.core.startvoice import find_voice
    registry = load_registry()
    found = re.findall(r"python3 -m voice_studio\.(projects|voices) ([a-z]+)([^\n`;<]*)", doc_text())
    assert {(m, c) for m, c, _ in found} >= {("projects", "list"), ("projects", "new"), ("projects", "show"), ("voices", "show"), ("voices", "list"), ("voices", "get"), ("voices", "choose")}
    takes_a_value = {"projects": set(pf.NEW_VALUES), "voices": set(vf.PROJECT)}
    for module, command, rest in found:
        table = (pf if module == "projects" else vf).OPTIONS
        assert command in table, (module, command)
        words, i = shlex.split(rest), 0
        positional = []
        while i < len(words):
            if words[i].startswith("-"):
                assert words[i] in table[command], (module, command, words[i])
                i += 2 if words[i] in takes_a_value[module] else 1
            else:
                positional.append(words[i])
                i += 1
        if module == "voices" and command in ("show", "choose", "get"):
            assert len(positional) == 1 and find_voice(registry, positional[0]), (command, positional)
        if "--project" in words:
            assert words[words.index("--project") + 1] == slugify("Voice check") == "voice-check"
    assert "--name \"Voice check\"" in doc_text()


def says(sentence, truncated=False):
    """Is `sentence` something the tool says? Whole sentences must match a catalog sentence with its placeholders filled by anything. A quote that the checklist
    ends with an ellipsis may be only the start of one. A template that begins with a placeholder ("{question} {answer}") would match almost any text, so it cannot
    vouch for anything and is left out."""
    for template in text_catalog_strings():
        if template.startswith("{") or (truncated and template[:6] != sentence[:6]):
            continue
        if sentence in template:
            return True
        units = [u for part in re.split(r"(\{[a-z_0-9]+\})", template) for u in ([part] if part.startswith("{") else list(part))]
        for k in (range(len(units), 0, -1) if truncated else (len(units),)):
            if truncated and units[k - 1].startswith("{"):
                continue                                  # a cut-off quote ends on real wording: ending in a placeholder would let it swallow any text
            if re.fullmatch("".join(".+?" if u.startswith("{") else re.escape(u) for u in units[:k]), sentence, re.S):
                return True
    return False


def text_catalog_strings():
    """Every sentence the tool says: the plain ones and every form of a plural one."""
    from voice_studio.core import text as vtext
    data = json.loads((vtext.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    return list(data["strings"].values()) + [form for forms in data["plurals"].values() for form in forms.values()]


def test_the_check_that_a_quoted_sentence_is_one_the_tool_says_can_actually_fail():
    assert says("Nothing was made.") and says("Made the project voice-check.")
    assert says("Download this voice now? It is 846 MB from huggingface.co and will be kept in", truncated=True)
    assert says("Saved: project voice-check has acknowledged this voice", truncated=True)
    assert not says("Download this voice now? It is 846 MB from huggingface.co and will be kept in"), "a cut-off quote is only allowed when the checklist marks it with an ellipsis"
    assert not says("Make this project? Type y to make it.") and not says("A sentence nobody wrote.") and not says("Made the projects voice-check.")
    assert not says("Saved: project voice-check has acknowledged that voice", truncated=True) and not says("Anything goes here at all", truncated=True)


def test_every_sentence_the_section_quotes_as_the_tools_output_is_one_the_tool_says():
    spans = re.findall(r"`([^`\n]+)`", section("I1."))
    quoted = [(s.rstrip(" …").rstrip(), s.endswith("…")) for s in spans if " " in s and s.rstrip()[-1] in ".?…" and not s.startswith(("PYTHONPATH", "ls ", "sha256sum", "~/", "rm "))]
    assert len(quoted) >= 18 and any(cut for _, cut in quoted), quoted
    for sentence, cut in quoted:
        assert says(sentence, cut), "the section quotes a sentence the tool does not say: " + sentence


def test_the_section_states_the_facts_about_mike_that_the_registry_pins():
    from voice_studio.core.registry import load_registry
    from voice_studio.core.text import size_text
    mike = load_registry().get("voice-mike")
    body = section("I1.")
    for fact in (mike.filename, str(mike.size_bytes), mike.sha256, size_text(mike.size_bytes) + " from huggingface.co", "2026-10-11"):
        assert fact in body, fact


def test_the_section_says_what_the_two_flags_are_and_that_neither_stands_for_the_other():
    body = section("I1.")
    assert "**`--acknowledge`**" in body and "**`--yes`**" in body and "Neither can stand in for the other" in body


def test_the_read_only_commands_and_the_refusal_run_as_the_section_shows_them(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")

    def run(*argv):
        return subprocess.run([sys.executable, "-m"] + list(argv), cwd=str(TOOLS), env=env, text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    listed = run("voice_studio.projects", "list")
    assert listed.returncode == 0 and "There are no projects yet." in listed.stdout and "Traceback" not in listed.stderr
    shown = run("voice_studio.voices", "show", "mike")
    assert shown.returncode == 0 and "This project gives no legal advice. Whether your use is allowed is for you to decide." in shown.stdout
    assert "Mike" in shown.stdout and "Lessac" in shown.stdout and "Traceback" not in shown.stderr
    made = run("voice_studio.projects", "new", "--own", "--name", "Voice check", "--voice", "mike", "--yes")
    assert made.returncode == 0 and "Made the project voice-check." in made.stdout
    refused = run("voice_studio.voices", "get", "mike", "--project", "voice-check", "--yes")
    assert refused.returncode == 2 and "There was nobody to ask, and --acknowledge was not given. Nothing was done." in refused.stdout
    assert not (tmp_path / "ack-voice-studio" / "tool").exists(), "the refusal fetched nothing and made no folder for it"
    project = json.loads((tmp_path / "ack-voice-studio" / "projects" / "voice-check" / "project.json").read_text())
    assert project["acknowledgments"] == [] and project["starting_voice"] == "voice-mike"


def test_the_cleanup_line_names_the_folder_the_section_made_and_keeps_the_voices():
    from voice_studio.core.paths import DataHome
    body = section("M.")
    assert "`rm -r ~/ack-voice-studio/projects/voice-check`" in body and DataHome("~").projects + "/voice-check" in doc_text()
    assert "Keep the voices in" in body and DataHome("~").voices in body


# ---------------------------------------------------------------- section I2: training rounds with the tool

def test_the_rounds_commands_it_gives_exist_and_take_the_options_it_gives():
    from voice_studio.core import rounds_flow as rf
    found = re.findall(r"python3 -m voice_studio\.rounds ([a-z]+)([^\n`;<]*)", section("I2."))
    assert {c for c, _ in found} >= {"list", "start", "stop", "back", "keep", "note"}
    takes_a_value = {"--project", "--set", "--minutes", "--text"}
    for command, rest in found:
        assert command in rf.OPTIONS, command
        words, i, positional = shlex.split(rest), 0, []
        while i < len(words):
            option = words[i].split("=")[0]
            if words[i].startswith("-"):
                assert option in rf.OPTIONS[command], (command, words[i])
                i += 2 if option in takes_a_value and "=" not in words[i] else 1
            else:
                positional.append(words[i])
                i += 1
        assert len(positional) == (1 if command == "note" else 0), (command, positional)
        if "--project" in words:
            assert words[words.index("--project") + 1] == "voice-check"
        if command == "start":
            assert words[words.index("--set") + 1] == "dataset-1" and words[words.index("--minutes") + 1].isdigit()


def test_every_sentence_the_rounds_section_quotes_as_the_tools_output_is_one_the_tool_says():
    spans = re.findall(r"`([^`\n]+)`", section("I2."))
    quoted = [(s.rstrip(" …").rstrip(), s.endswith("…")) for s in spans if " " in s and s.rstrip()[-1] in ".?…" and not s.startswith(("PYTHONPATH", "ls ", "tail ", "grep ", "~/", "rm ", "cp ", "mkdir "))]
    assert len(quoted) >= 12 and any(cut for _, cut in quoted), quoted
    for sentence, cut in quoted:
        assert says(sentence, cut), "the section quotes a sentence the tool does not say: " + sentence


def test_the_places_the_rounds_section_names_are_where_the_tool_puts_things():
    from voice_studio.core.paths import DataHome, ProjectPaths, ScratchPaths
    from voice_studio.core.registry import load_registry
    body = section("I2.")
    home = DataHome("~")
    paths = ProjectPaths(home.projects + "/voice-check")
    assert ScratchPaths(paths.default_scratch).datasets in body and paths.rounds in body and paths.run.replace(paths.rounds, "rounds") in body
    assert paths.run + "/lightning_logs" in body and home.jobs in body
    mike = load_registry().get("voice-mike")
    assert mike.filename in body and "/tool/downloads/voices/voice-mike/" in body and home.voices.endswith("/tool/downloads/voices")


def test_the_section_says_what_the_first_two_rounds_start_from_and_that_the_second_must_not_be_the_voice_file():
    from voice_studio.core.registry import load_registry
    body = " ".join(section("I2.").split())
    assert "Round 1's ends in Mike's own file name, `%s`" % load_registry().get("voice-mike").filename in body
    assert "Round 2's must never be the voice file" in body and "close the terminal while it runs" in body
    assert "Nothing here deletes or moves a file" in body and "never from the starting voice again by accident" in body


def test_the_grep_the_section_gives_finds_what_each_round_was_started_from(tmp_path):
    from voice_studio.core import jobs
    for n, ckpt in enumerate(("/home/u/ack-voice-studio/tool/downloads/voices/voice-mike/epoch=5460-val_mos=4.2686.ckpt", "/home/u/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/version_0/checkpoints/last.ckpt")):
        folder = tmp_path / "ack-voice-studio" / "state" / "jobs" / ("2026101%d-000000-train-abcd" % n)
        folder.mkdir(parents=True)
        jobs.write_json(str(folder / "job.json"), {"schema": 1, "kind": "train", "project": "voice-check", "argv": ["py", "run", "--data.cache_dir", "/c", "--ckpt_path", ckpt], "env": {}})
    line = next(l for l in section("I2.").splitlines() if l.strip().startswith("grep -h -o"))
    done = subprocess.run(["bash", "-c", line.strip()], env=dict(os.environ, HOME=str(tmp_path)), text=True, capture_output=True, timeout=30)
    assert done.returncode == 0 and done.stdout.splitlines() == ['"--ckpt_path", "/home/u/ack-voice-studio/tool/downloads/voices/voice-mike/epoch=5460-val_mos=4.2686.ckpt"',
                                                                  '"--ckpt_path", "/home/u/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/version_0/checkpoints/last.ckpt"']


def test_the_saved_file_check_the_section_gives_says_true_for_a_whole_file_and_false_for_a_cut_one(home):
    from vs_rounds_helpers import write_checkpoint
    root = home / "ack-voice-studio"
    mike = write_checkpoint(str(root / "tool" / "downloads" / "voices" / "voice-mike" / "epoch=5460-val_mos=4.2686.ckpt"))
    good = write_checkpoint(str(root / "projects" / "voice-check" / "rounds" / "run" / "lightning_logs" / "version_0" / "checkpoints" / "last.ckpt"))
    cut = write_checkpoint(str(root / "projects" / "voice-check" / "rounds" / "run" / "lightning_logs" / "version_1" / "checkpoints" / "last.ckpt"), whole=False)
    done = run_snippet("checkpoint-check", home)
    assert done.returncode == 0 and done.stderr == "" and done.stdout.splitlines() == ["True " + mike, "True " + good, "False " + cut]


def test_the_read_only_rounds_commands_run_as_the_section_shows_them_and_write_nothing(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")

    def run(*argv):
        return subprocess.run([sys.executable, "-m"] + list(argv), cwd=str(TOOLS), env=env, text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    made = run("voice_studio.projects", "new", "--own", "--name", "Voice check", "--voice", "mike", "--yes")
    assert made.returncode == 0
    listed = run("voice_studio.rounds", "list", "--project", "voice-check")
    assert listed.returncode == 0 and "There are no rounds yet. The first round starts from the starting voice." in listed.stdout
    assert "No round is chosen yet, so the next round starts from the starting voice." in listed.stdout and "Traceback" not in listed.stderr
    kept = run("voice_studio.rounds", "keep", "--project", "voice-check")
    assert kept.returncode == 0 and "This command removes nothing." in kept.stdout
    folder = tmp_path / "ack-voice-studio" / "projects" / "voice-check" / "rounds"
    assert sorted(p.name for p in folder.iterdir()) == [], "looking wrote nothing"
    asked = run("voice_studio.rounds", "start", "--set", "dataset-1", "--minutes", "3", "--project", "voice-check")
    assert asked.returncode == 2 and "no training set yet" in asked.stdout and "Traceback" not in asked.stderr
    assert sorted(p.name for p in folder.iterdir()) in ([], [".rounds.lock"]), "asking for a round that cannot start made no round (the lock file is only the place changes are taken turns)"


def test_the_disk_guard_snippet_makes_the_real_runner_stop_a_waiting_job_and_say_it_was_the_disk(home):
    done = run_snippet("disk-guard", home)
    assert done.returncode == 0 and done.stderr == "" and done.stdout.strip() == "stopped stop reason: disk", (done.stdout, done.stderr)
    note = json.loads(next((home / "ack-voice-check" / "jobs").glob("*-guard-*/stop.json")).read_text())
    assert note["reason"] == "disk" and note["forced"] is False and note["floor"] > note["free"]


def test_the_section_tells_what_the_new_checks_say_and_that_the_numbers_are_to_be_written_down():
    body = " ".join(section("I2.").split())
    assert "Checked before starting:" in body and "Write down the two checks' numbers" in body and "disk guard" in body


# ---------------------------------------------------------------- section I3: freeing up space

def test_the_free_commands_it_gives_exist_and_take_the_options_it_gives():
    from voice_studio.core import rounds_flow as rf
    found = re.findall(r"python3 -m voice_studio\.rounds (free)([^\n`;<]*)", section("I3."))
    assert len(found) >= 6
    takes_a_value = {"--project", "--saved", "--working"}
    seen = set()
    for command, rest in found:
        words, i = shlex.split(rest), 0
        while i < len(words):
            assert words[i].startswith("-") and words[i] in rf.OPTIONS[command], (command, words[i])
            seen.add(words[i])
            i += 2 if words[i] in takes_a_value else 1
        assert words[words.index("--project") + 1] == "voice-check"
    assert seen >= {"--saved", "--working", "--all", "--project"}


def test_every_sentence_the_free_section_quotes_as_the_tools_output_is_one_the_tool_says():
    spans = re.findall(r"`([^`\n]+)`", section("I3."))
    quoted = [(s.rstrip(" …").rstrip(), s.endswith("…")) for s in spans if " " in s and s.rstrip()[-1] in ".?…" and not s.startswith(("PYTHONPATH", "ls ", "df ", "~/"))]
    assert len(quoted) >= 8 and any(cut for _, cut in quoted), quoted
    for sentence, cut in quoted:
        assert says(sentence, cut), "the section quotes a sentence the tool does not say: " + sentence


def test_the_free_section_says_it_removes_files_asks_first_and_that_the_first_steps_remove_nothing():
    body = " ".join(section("I3.").split())
    assert "the one section that removes files you made" in body and "asks first" in body and "cannot be brought back" in body
    assert "stop after the first two steps" in body and "It never offers recordings" in body and "Only if you are willing to lose it" in body
    assert "Look. This changes nothing" in body and "The saved point is missing" in body and "must never do" in body


def test_the_free_section_follows_the_order_the_sections_run_in():
    names = re.findall(r"^## ([A-Z][0-9]?)\. ", doc_text(), flags=re.M)
    assert names.index("I2") < names.index("I3") < names.index("J")


def test_free_on_a_project_with_nothing_to_free_says_so_and_writes_nothing(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")

    def run(*argv):
        return subprocess.run([sys.executable, "-m"] + list(argv), cwd=str(TOOLS), env=env, text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    assert run("voice_studio.projects", "new", "--own", "--name", "Voice check", "--voice", "mike", "--yes").returncode == 0
    folder = tmp_path / "ack-voice-studio" / "projects" / "voice-check" / "rounds"
    looked = run("voice_studio.rounds", "free", "--project", "voice-check")
    assert looked.returncode == 0 and "There is nothing to free up." in looked.stdout and "What could be freed up for Voice check:" in looked.stdout
    assert "Traceback" not in looked.stderr and sorted(p.name for p in folder.iterdir()) == []
    asked = run("voice_studio.rounds", "free", "--all", "--project", "voice-check", "--yes")
    assert asked.returncode == 2 and "There is nothing to free up." in asked.stdout and sorted(p.name for p in folder.iterdir()) in ([], [".rounds.lock"])
    for argv, said in ((("--saved", "99"), "There is nothing to free up."), (("--saved", "one"), "I did not understand one."), (("--all", "--saved", "1"), "Give either --all or a list of rounds, not both.")):
        done = run("voice_studio.rounds", "free", *argv, "--project", "voice-check")
        assert done.returncode == 2 and said in done.stdout, (argv, done.stdout)


# ---------------------------------------------------------------- section I4: the voice file with one command

def test_the_voicefile_commands_it_gives_exist_and_take_the_options_it_gives():
    from voice_studio.core import voicefile_flow as vff
    found = re.findall(r"python3 -m voice_studio\.voicefile ([a-z]+)([^\n`;<]*)", section("I4."))
    assert {c for c, _ in found} == {"list", "make"} and len(found) >= 4
    seen = set()
    for command, rest in found:
        assert command in vff.OPTIONS, command
        words, i = shlex.split(rest), 0
        while i < len(words):
            assert words[i].startswith("-") and words[i] in vff.OPTIONS[command], (command, words[i])
            seen.add(words[i])
            i += 2 if words[i] == "--project" else 1
        assert words[words.index("--project") + 1] == "voice-check"
    assert seen >= {"--project", "--yes"}


def test_every_sentence_the_voice_file_section_quotes_as_the_tools_output_is_one_the_tool_says():
    spans = re.findall(r"`([^`\n]+)`", section("I4."))
    quoted = [(s.rstrip(" …").rstrip(), s.endswith("…")) for s in spans if " " in s and s.rstrip()[-1] in ".?…" and not s.startswith(("PYTHONPATH", "ls ", "unzip ", "mv ", "time ", "~/"))]
    assert len(quoted) >= 7 and any(cut for _, cut in quoted), quoted
    for sentence, cut in quoted:
        assert says(sentence, cut), "the section quotes a sentence the tool does not say: " + sentence


def test_the_places_the_voice_file_section_names_are_where_the_tool_puts_things():
    from voice_studio.core import voicefile
    from voice_studio.core.paths import DataHome, ProjectPaths
    body = section("I4.")
    paths = ProjectPaths(DataHome("~").projects + "/voice-check")
    assert paths.exports in body and voicefile.settings_file(paths, 3) in body and voicefile.settings_file(paths, 3) + ".aside" in body
    assert paths.round_configs in body and "my_voice.onnx.before-patch" in body and voicefile.VOICE_NAME + ".onnx.json" in body


def test_the_voice_file_section_says_it_writes_only_a_new_folder_and_puts_the_moved_file_back():
    body = " ".join(section("I4.").split())
    assert "writes only into **one new folder**" in body and "never changes, replaces or removes anything that was there" in body
    assert "Only if you want to see a refusal" in body and "Put the file back (the third command) even if something looks wrong" in body
    assert "it does not run while a round is training" in body and "Write down how long it takes" in body
    moves = re.findall(r"^\s*mv (\S+) (\S+)$", section("I4."), flags=re.M)
    assert len(moves) == 2 and moves[0] == (moves[1][1], moves[1][0]), "the second move undoes the first"


def test_the_voice_file_section_follows_the_free_up_section_and_comes_before_the_manual_one():
    names = re.findall(r"^## ([A-Z][0-9]?)\. ", doc_text(), flags=re.M)
    assert names.index("I3") < names.index("I4") < names.index("J")
