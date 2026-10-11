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
SNIPPETS = ("jobs-start", "jobs-list", "jobs-stop", "package-summary", "flip-a-byte", "voice-zip")


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
    assert tuple(re.findall(r"<!-- snippet: ([a-z-]+) -->", doc_text())) == tuple(s for s in ("jobs-start", "jobs-list", "jobs-stop", "package-summary", "flip-a-byte", "voice-zip"))
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
