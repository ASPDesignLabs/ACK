# SPDX-License-Identifier: GPL-3.0-or-later
"""The two shell scripts (plan task VS-1.4), run for real with stand-ins for python, git and sudo, so nothing is installed or fetched.

get.sh is run in a pseudo-terminal when the test needs a person to type an answer: it reads answers from /dev/tty (when it is piped into bash,
its own input is the script), and the checks have to cover that path too.
"""
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
TOOLS = PKG.parent
SETUP, GET = PKG / "setup.sh", PKG / "get.sh"
BASH = shutil.which("bash") or "/bin/bash"
URL = re.search(r'^REPO_URL="([^"]+)"', GET.read_text(), re.M).group(1)

needs_pty = pytest.mark.skipif(not hasattr(os, "openpty") or sys.platform == "win32", reason="needs a pseudo-terminal")

PTY_DRIVER = r'''
import json, os, pty, select, sys
argv, env, answers = json.loads(sys.argv[1]), json.loads(sys.argv[2]), json.loads(sys.argv[3])
pid, fd = pty.fork()
if pid == 0:
    os.execve(argv[0], argv, env)
os.write(fd, "".join(a + "\n" for a in answers).encode())
out = b""
while True:
    ready, _, _ = select.select([fd], [], [], 30)
    if not ready:
        break
    try:
        data = os.read(fd, 4096)
    except OSError:
        break
    if not data:
        break
    out += data
_, status = os.waitpid(pid, 0)
print(json.dumps({"code": os.waitstatus_to_exitcode(status), "out": out.decode("utf-8", "replace")}))
'''


def write_exe(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class Box:
    """A scratch home and a PATH holding only the stand-ins and the few plain tools the scripts use."""
    def __init__(self, tmp: Path):
        self.home, self.bin, self.log = tmp / "home", tmp / "bin", tmp / "calls.log"
        self.cwd = tmp / "cwd"                     # the scripts run from here, so a script that wandered would write here and nowhere else
        self.cwd.mkdir()
        self.home.mkdir()
        self.bin.mkdir()
        self.log.write_text("")
        for tool in ("ls", "dirname", "cat", "env", "sh", "true", "mkdir", "chmod", "cp"):
            found = shutil.which(tool)
            if found:
                (self.bin / tool).symlink_to(found)
        self.dest = tmp / "ack-tools"

    def env(self, **extra):
        env = {"PATH": str(self.bin), "HOME": str(self.home), "CALLS": str(self.log)}
        env.update(extra)
        return env

    def calls(self):
        return [line for line in self.log.read_text().splitlines() if line]

    def stand_in(self, name, body=""):
        return write_exe(self.bin / name, 'echo "%s $*" >> "$CALLS"\n%s' % (name, body))

    def git_that_clones(self, fail=False):
        make = "" if fail else ('mkdir -p "$DEST_OF_CLONE/tools/voice_studio"\n'
                                'printf "#!/bin/sh\\necho \\"setup.sh \\$*\\" >> \\"\\$CALLS\\"\\n" > "$DEST_OF_CLONE/tools/voice_studio/setup.sh"\n'
                                'chmod +x "$DEST_OF_CLONE/tools/voice_studio/setup.sh"\n')
        body = ('for last; do :; done\nDEST_OF_CLONE="$last"\n' + make) + ("exit 128\n" if fail else "")
        return self.stand_in("git", body)

    def sudo_that_installs_git(self, fail_on=None):
        body = ""
        if fail_on:
            body += 'case "$*" in *"%s"*) exit 100 ;; esac\n' % fail_on
        body += 'case "$*" in *"install -y git"*) cp "%s" "%s/git" ;; esac\n' % (self.bin / "git-stand-in", self.bin)
        self.stand_in("git-stand-in", "")
        return self.stand_in("sudo", body)

    def bash(self, script, *args, env=None, answers=None, timeout=60):
        env = env if env is not None else self.env()
        if answers is None:
            result = subprocess.run([BASH, str(script), *args], env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                                    start_new_session=True, cwd=str(self.cwd))
            return result.returncode, result.stdout + result.stderr
        driver = subprocess.run([sys.executable, "-I", "-c", PTY_DRIVER, json.dumps([BASH, str(script), *args]), json.dumps(env), json.dumps(answers)],
                                capture_output=True, text=True, timeout=timeout, cwd=str(self.cwd))
        assert driver.returncode == 0, driver.stderr
        data = json.loads(driver.stdout.strip().splitlines()[-1])
        return data["code"], data["out"]


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


# ================================================================ setup.sh

def fake_python(box, *, old=False, name="python3"):
    body = 'if [ "$1" = "-c" ]; then exit %d; fi\necho "ARGS: $*"\necho "PYTHONPATH: $PYTHONPATH"\n' % (1 if old else 0)
    return write_exe(box.bin / name, body)


def test_setup_stops_with_a_plain_sentence_when_there_is_no_python(box):
    code, out = box.bash(SETUP)
    assert code == 2 and "Python 3 was not found" in out and "sudo apt install python3" in out


def test_setup_stops_when_python_is_too_old(box):
    fake_python(box, old=True)
    code, out = box.bash(SETUP)
    assert code == 2 and "too old" in out and "3.10" in out and "ARGS" not in out


def python_pretending_to_be(box, version):
    """A python3 that is the real one, except that it says it is `version`, so the script's own check is what is tested."""
    body = ('if [ "$1" = "-c" ]; then exec "%s" -c "import sys; sys.version_info = (%s); $2"; fi\n'
            'echo "ARGS: $*"\n') % (sys.executable, version)
    return write_exe(box.bin / "python3", body)


@pytest.mark.parametrize("version, accepted", [("2, 7, 18", False), ("3, 0, 0", False), ("3, 9, 18", False), ("3, 9, 99", False),
                                              ("3, 10, 0", True), ("3, 10, 12", True), ("3, 12, 3", True), ("3, 13, 0", True), ("4, 0, 0", True)])
def test_setup_accepts_python_3_10_and_newer_and_nothing_older(box, version, accepted):
    python_pretending_to_be(box, version)
    code, out = box.bash(SETUP)
    assert (code == 0 and "ARGS: -m voice_studio" in out) if accepted else (code == 2 and "too old" in out and "ARGS" not in out)


def test_setup_hands_every_argument_to_the_program_unchanged_and_in_order(box):
    fake_python(box)
    code, out = box.bash(SETUP, "--check", "--dry-run", "a b", "$HOME", "*")
    assert code == 0
    assert "ARGS: -m voice_studio --check --dry-run a b $HOME *" in out


def test_setup_puts_the_tools_folder_first_on_the_python_path_and_keeps_what_was_there(box):
    fake_python(box)
    _, plain = box.bash(SETUP)
    assert "PYTHONPATH: %s\n" % TOOLS in plain
    _, kept = box.bash(SETUP, env=box.env(PYTHONPATH="/already/here"))
    assert "PYTHONPATH: %s:/already/here" % TOOLS in kept


def test_setup_passes_the_exit_status_of_the_program_through(box):
    write_exe(box.bin / "python3", 'if [ "$1" = "-c" ]; then exit 0; fi\nexit 7\n')
    assert box.bash(SETUP)[0] == 7


def test_setup_uses_the_python_it_was_told_to_use(box):
    fake_python(box, name="python3.12")
    code, out = box.bash(SETUP, env=box.env(PYTHON="python3.12"))
    assert code == 0 and "ARGS: -m voice_studio" in out


def test_setup_works_from_any_folder_it_is_started_in(box, tmp_path):
    fake_python(box)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = subprocess.run([BASH, str(SETUP), "--check"], env=box.env(), cwd=str(elsewhere), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert result.returncode == 0 and "PYTHONPATH: %s" % TOOLS in result.stdout


def test_setup_end_to_end_with_the_real_program_names_a_mistyped_option_and_does_nothing(tmp_path):
    result = subprocess.run([BASH, str(SETUP), "--chek"], env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHON": sys.executable},
                            capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=str(tmp_path))
    assert result.returncode == 2 and "--chek" in result.stdout and list(tmp_path.iterdir()) == []


# ================================================================ get.sh

def test_get_says_so_and_fetches_nothing_when_no_release_was_chosen(box):
    box.git_that_clones()
    code, out = box.bash(GET)
    assert code == 2 and "ACK_VOICE_TAG" in out and box.calls() == [] and not box.dest.exists()


def test_get_uses_an_existing_copy_and_fetches_nothing(box):
    box.git_that_clones()
    write_exe(box.dest / "tools/voice_studio/setup.sh", 'echo "setup.sh $*" >> "$CALLS"\n')
    code, out = box.bash(GET, "--check", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0 and box.calls() == ["setup.sh --check"] and "already at" in out


def test_get_never_touches_a_folder_that_is_there_and_is_not_ack(box):
    box.git_that_clones()
    (box.dest).mkdir()
    (box.dest / "photos.txt").write_text("keep me")
    code, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 1 and box.calls() == [] and (box.dest / "photos.txt").read_text() == "keep me" and list(box.dest.iterdir()) == [box.dest / "photos.txt"]
    assert "left alone" in out and "ACK_VOICE_DIR" in out


def test_get_uses_an_empty_folder_that_is_already_there(box):
    box.git_that_clones()
    box.dest.mkdir()
    code, _ = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0 and (box.dest / "tools/voice_studio/setup.sh").exists()


def test_get_fetches_exactly_the_chosen_release_into_the_chosen_folder_then_starts_setup(box):
    box.git_that_clones()
    code, out = box.bash(GET, "--yes", env=box.env(ACK_VOICE_TAG="v1.2", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0
    assert box.calls() == ["git clone --depth 1 --branch v1.2 %s %s" % (URL, box.dest), "setup.sh --yes"]


def test_get_defaults_to_a_folder_in_the_home_directory(box):
    box.git_that_clones()
    code, _ = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1"))
    assert code == 0 and box.calls()[0].endswith(" %s/ack-tools" % box.home)


def test_get_keeps_odd_folder_and_release_names_in_one_piece(box):
    box.git_that_clones()
    dest = box.home / "my folder; $(touch gotcha)"
    code, _ = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1 --x", ACK_VOICE_DIR=str(dest)))
    assert code == 0 and not (box.home / "gotcha").exists() and list(box.cwd.iterdir()) == []
    assert box.calls()[0] == "git clone --depth 1 --branch v1 --x %s %s" % (URL, dest)


def test_get_reports_a_failed_fetch_and_does_not_start_setup(box):
    box.git_that_clones(fail=True)
    code, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 1 and "could not be fetched" in out and "Nothing else was changed" in out
    assert not any(c.startswith("setup.sh") for c in box.calls())


def test_get_dry_run_shows_what_it_would_do_and_does_none_of_it(box):
    box.git_that_clones()
    code, out = box.bash(GET, "--dry-run", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0 and box.calls() == [] and not box.dest.exists()
    assert "Would run: git clone --depth 1 --branch v1 %s %s" % (URL, box.dest) in out
    assert "setup.sh" in out


def test_get_check_is_a_dry_run_too(box):
    box.git_that_clones()
    code, _ = box.bash(GET, "--check", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0 and box.calls() == [] and not box.dest.exists()


# ---- when git is missing

def test_get_without_git_in_a_dry_run_lists_the_two_commands_and_runs_neither(box):
    box.sudo_that_installs_git()
    code, out = box.bash(GET, "--dry-run", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0 and box.calls() == []
    assert "Would run: sudo apt-get update" in out and "Would run: sudo apt-get install -y git" in out


def test_get_without_git_and_nobody_to_ask_installs_nothing_and_says_how_to_go_ahead(box):
    box.sudo_that_installs_git()
    code, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 2 and box.calls() == [] and "--yes" in out and not box.dest.exists()


def test_get_without_git_and_a_yes_on_the_command_line_installs_it_then_fetches(box):
    box.sudo_that_installs_git()
    box.stand_in("git-real", "")
    # the git that appears after the install is the cloning one
    (box.bin / "git-stand-in").unlink()
    box_git = box.git_that_clones()
    box_git.rename(box.bin / "git-stand-in")
    code, out = box.bash(GET, "--yes", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 0
    assert box.calls()[:2] == ["sudo apt-get update", "sudo apt-get install -y git"]
    assert box.calls()[2] == "git clone --depth 1 --branch v1 %s %s" % (URL, box.dest)
    assert box.calls()[3] == "setup.sh --yes"
    assert "password" in out and "never sees it" in out


def test_get_stops_when_the_install_fails_and_changes_nothing_else(box):
    box.sudo_that_installs_git(fail_on="update")
    code, out = box.bash(GET, "--yes", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 1 and box.calls() == ["sudo apt-get update"] and "git could not be installed" in out and not box.dest.exists()


def test_get_stops_when_the_second_install_command_fails_too(box):
    box.sudo_that_installs_git(fail_on="install -y git")
    code, _ = box.bash(GET, "--yes", env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)))
    assert code == 1 and box.calls() == ["sudo apt-get update", "sudo apt-get install -y git"] and not box.dest.exists()


@needs_pty
def test_get_asks_at_the_terminal_and_a_yes_installs_git(box):
    box.sudo_that_installs_git()
    (box.bin / "git-stand-in").unlink()
    box.git_that_clones().rename(box.bin / "git-stand-in")
    code, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)), answers=["y"])
    assert code == 0 and box.calls()[:2] == ["sudo apt-get update", "sudo apt-get install -y git"]
    assert "Install git now?" in out and "setup.sh" in box.calls()[-1]


@needs_pty
@pytest.mark.parametrize("answer", ["", "n", "no", "yes please", "yy"])
def test_get_treats_anything_but_a_plain_yes_as_no(box, answer):
    box.sudo_that_installs_git()
    code, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)), answers=[answer])
    assert code == 2 and box.calls() == [] and "Nothing was installed" in out and not box.dest.exists()


@needs_pty
def test_get_asks_exactly_once(box):
    box.sudo_that_installs_git()
    _, out = box.bash(GET, env=box.env(ACK_VOICE_TAG="v1", ACK_VOICE_DIR=str(box.dest)), answers=["n"])
    assert out.count("Install git now?") == 1


# ---- the rules the scripts must keep

SCRIPTS = [SETUP, GET]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_the_scripts_are_executable_have_a_licence_line_and_are_valid_bash(script):
    assert script.stat().st_mode & stat.S_IXUSR
    assert script.read_text().splitlines()[0] == "#!/usr/bin/env bash" and "SPDX-License-Identifier: GPL-3.0-or-later" in script.read_text().splitlines()[1]
    assert subprocess.run([BASH, "-n", str(script)], capture_output=True).returncode == 0


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_the_scripts_never_edit_shell_settings_or_leave_things_behind(script):
    code = "\n".join(l for l in script.read_text().splitlines() if not l.lstrip().startswith("#"))
    for forbidden in (".bashrc", ".profile", ".zshrc", ".bash_profile", "/etc/", ">>", "chmod", "rm ", "rm -", "curl", "wget", "eval", "| sh", "| bash", "mkdir", "pip"):
        assert forbidden not in code, "%s: %s" % (script.name, forbidden)


def commands_only(script):
    """The script's own commands: comments and everything inside double quotes (the sentences it says) removed."""
    lines = [l for l in script.read_text().splitlines() if not l.lstrip().startswith("#")]
    return re.sub(r'"[^"]*"', '""', "\n".join(lines))


def test_setup_never_uses_sudo_itself_and_get_uses_it_only_to_install_git():
    assert not re.search(r"\bsudo\b", commands_only(SETUP)), "setup.sh may mention sudo in a sentence for the person, never run it"
    code = commands_only(GET)
    assert len(re.findall(r"\bsudo\b", code)) == 2
    allowed = re.findall(r"\bsudo apt-get (?:update|install -y git)(?=\s|$)", GET.read_text())
    assert "sudo apt-get update" in allowed and "sudo apt-get install -y git" in allowed


def test_get_fetches_over_https_from_the_one_host_the_project_names():
    from voice_studio.core.registry import ALLOWED_HOSTS
    assert URL.startswith("https://") and URL.split("/")[2] in ALLOWED_HOSTS and URL.endswith(".git")
    assert GET.read_text().count("://") == 1, "REPO_URL is the one web address in this file"


def test_get_reads_answers_from_the_terminal_not_from_its_own_input():
    code = GET.read_text()
    assert "/dev/tty" in code and 'read -r answer </dev/tty' in code
    assert "read -r" not in code.replace("read -r answer </dev/tty", "")


def test_get_never_fetches_without_a_named_release():
    code = GET.read_text()
    assert 'TAG="${ACK_VOICE_TAG:-}"' in code and '--branch "$TAG"' in code
    assert "main" not in code.replace("remaining", "") and "master" not in code
