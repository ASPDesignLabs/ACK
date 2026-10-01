"""install.sh and start.sh, driven with a stand-in Python so every branch runs without the network.

The stand-in logs each call it receives, answers the version and import probes the way a healthy environment would, and can
be told to misbehave (FAKE_MISSING=<module>, FAKE_PY_OLD=1, FAKE_PIP_FAIL=1). The real install (a fresh environment, real
packages, real `python -m freeform_studio --help`) was run by hand and is not repeated here because it needs the internet.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
INSTALL = HERE / "install.sh"
START = HERE / "start.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not installed")

STUB_PYTHON = """#!/bin/sh
echo "$*" >> "${FAKE_LOG:-/dev/null}"
case "$1" in
  -m)
    if [ "$2" = "pip" ] && [ "$3 $4" = "install -r" ] && [ -n "$FAKE_PIP_FAIL" ]; then exit 1; fi
    exit 0 ;;
  -c)
    case "$2" in
      *"version_info >= (3, 10)"*) [ -n "$FAKE_PY_OLD" ] && exit 1; exit 0 ;;
      *"version_info[:3]"*) if [ -n "$FAKE_PY_OLD" ]; then echo 3.8.18; else echo 3.11.4; fi; exit 0 ;;
      *nvidia.cublas.lib*) echo /fake/cublas:/fake/cudnn; exit 0 ;;
      "import $FAKE_MISSING") [ -n "$FAKE_MISSING" ] && exit 1; exit 0 ;;
    esac ;;
esac
exit 0
"""

ARG_ECHO = """#!/bin/sh
echo "CWD=$(pwd -P)"
for a in "$@"; do echo "ARG=$a"; done
"""


def script(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


@pytest.fixture()
def box(tmp_path):
    """A PATH holding only bash, dirname, sed and stand-in ffmpeg/ffprobe, plus a stand-in Python."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "dirname", "sed"):
        real = shutil.which(tool)
        assert real, f"{tool} is needed to run these tests"
        (bin_dir / tool).symlink_to(real)
    script(bin_dir / "ffmpeg", "#!/bin/sh\nexit 0\n")
    script(bin_dir / "ffprobe", "#!/bin/sh\nexit 0\n")
    py = script(tmp_path / "stub" / "python3.11", STUB_PYTHON)
    log = tmp_path / "calls.log"
    return {"dir": tmp_path, "bin": bin_dir, "python": py, "log": log, "venv": tmp_path / "venv"}


def run_install(box, *args, extra_env=None, cwd=None):
    env = {"PATH": str(box["bin"]), "HOME": str(box["dir"] / "home"), "FAKE_LOG": str(box["log"])}
    env.update(extra_env or {})
    return subprocess.run([BASH, str(INSTALL), "--python", str(box["python"]), "--venv", str(box["venv"]), *args],
                          env=env, cwd=cwd or box["dir"], capture_output=True, text=True, timeout=60)


def calls(box):
    return box["log"].read_text().splitlines() if box["log"].exists() else []


def make_venv(box):
    """An 'existing environment' whose python is the stand-in."""
    script(box["venv"] / "bin" / "python", STUB_PYTHON)


# ---------------------------------------------------------------- both scripts

@pytest.mark.parametrize("path", [INSTALL, START])
def test_scripts_are_valid_bash_and_executable(path):
    assert subprocess.run([BASH, "-n", str(path)], capture_output=True, text=True).returncode == 0
    assert os.access(path, os.X_OK), f"{path.name} should be executable (chmod +x)"


def test_help_shows_only_the_usage_text():
    out = subprocess.run([BASH, str(INSTALL), "--help"], capture_output=True, text=True)
    assert out.returncode == 0
    for word in ("--check", "--dry-run", "--gpu", "--venv", "--python"):
        assert word in out.stdout
    assert "set -u" not in out.stdout, "the usage text must stop at the end of the header comment"


def test_unknown_option_is_refused_with_the_usage(box):
    out = run_install(box, "--bogus")
    assert out.returncode == 2
    assert "Unknown option: --bogus" in out.stdout
    assert "--dry-run" in out.stdout
    assert not calls(box), "nothing runs when the options are wrong"


# ---------------------------------------------------------------- install.sh: looking only

def test_check_with_no_environment_reports_it_and_changes_nothing(box):
    out = run_install(box, "--check")
    assert out.returncode == 1
    assert "[FIX]   no environment at" in out.stdout
    assert not box["venv"].exists()
    assert not any(c.startswith(("-m venv", "-m pip")) for c in calls(box)), "check mode only asks questions"


def test_check_with_a_healthy_environment_passes_and_installs_nothing(box):
    make_venv(box)
    out = run_install(box, "--check")
    assert out.returncode == 0, out.stdout
    assert "Nothing was changed." in out.stdout
    for pkg in ("quart", "hypercorn", "numpy", "faster_whisper", "huggingface_hub"):
        assert f"[ok]    package {pkg}" in out.stdout
    assert "[ok]    the program starts" in out.stdout
    assert not any(c.startswith("-m pip") for c in calls(box))


def test_check_names_the_package_that_cannot_be_loaded(box):
    make_venv(box)
    out = run_install(box, "--check", extra_env={"FAKE_MISSING": "faster_whisper"})
    assert out.returncode == 1
    assert "[FIX]   package faster_whisper can't be loaded" in out.stdout
    assert "[ok]    package quart" in out.stdout, "the other packages are still reported"


def test_dry_run_lists_the_commands_and_runs_none_of_them(box):
    out = run_install(box, "--dry-run")
    assert out.returncode == 0, out.stdout
    assert "would run:" in out.stdout and "-m venv" in out.stdout
    assert "pip install -r" in out.stdout and "requirements.txt" in out.stdout
    assert "Nothing was changed." in out.stdout
    assert not box["venv"].exists()
    assert not any(c.startswith("-m venv") or c.startswith("-m pip") for c in calls(box))


# ---------------------------------------------------------------- install.sh: doing it

def test_install_into_an_existing_environment_upgrades_pip_then_installs_requirements(box):
    make_venv(box)
    out = run_install(box)
    assert out.returncode == 0, out.stdout
    log = calls(box)
    assert log.index("-m pip install --upgrade pip") < log.index(f"-m pip install -r {HERE / 'requirements.txt'}")
    assert "-m freeform_studio --help" in log
    assert "reusing the existing environment" in out.stdout
    assert "start.sh" in out.stdout, "it ends by saying how to start the program"
    assert not any("nvidia" in c for c in log), "GPU libraries are only installed when asked for"


def test_gpu_flag_adds_the_nvidia_libraries_and_prints_how_to_use_them(box):
    make_venv(box)
    out = run_install(box, "--gpu")
    assert out.returncode == 0, out.stdout
    assert any("nvidia-cublas-cu12" in c and "nvidia-cudnn-cu12" in c for c in calls(box))
    assert "export LD_LIBRARY_PATH=/fake/cublas:/fake/cudnn" in out.stdout
    assert "training is running" in out.stdout


def test_a_failed_download_is_reported_plainly_and_exits_nonzero(box):
    make_venv(box)
    out = run_install(box, extra_env={"FAKE_PIP_FAIL": "1"})
    assert out.returncode == 1
    assert "[FIX]   could not install the requirements" in out.stdout
    assert "Done." not in out.stdout


def test_works_from_any_folder(box, tmp_path):
    make_venv(box)
    elsewhere = tmp_path / "somewhere" / "else"
    elsewhere.mkdir(parents=True)
    out = run_install(box, "--check", cwd=elsewhere)
    assert out.returncode == 0, out.stdout
    assert "-m freeform_studio --help" in calls(box)


# ---------------------------------------------------------------- install.sh: what it refuses

def test_too_old_python_is_refused_with_the_fix(box):
    out = run_install(box, "--check", extra_env={"FAKE_PY_OLD": "1"})
    assert out.returncode == 1
    assert "is Python 3.8.18, which is too old" in out.stdout
    assert "3.10 or newer" in out.stdout
    assert not any(c.startswith("-m pip") for c in calls(box))


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe"])
def test_missing_ffmpeg_tools_are_named_with_the_install_command(box, missing):
    (box["bin"] / missing).unlink()
    out = run_install(box, "--check")
    assert out.returncode == 1
    assert f"[FIX]   {missing} is missing" in out.stdout
    assert "sudo apt install ffmpeg" in out.stdout
    other = "ffprobe" if missing == "ffmpeg" else "ffmpeg"
    assert f"[ok]    {other} found" in out.stdout


def test_a_python_that_cannot_make_environments_says_how_to_fix_it(box):
    # the stand-in answers every probe with success, so make only the venv probe fail
    broken = script(box["dir"] / "stub2" / "python3.11", STUB_PYTHON.replace(
        'case "$1" in', 'case "$2" in *"import venv, ensurepip"*) exit 1;; esac\ncase "$1" in', 1))
    env = {"PATH": str(box["bin"]), "HOME": str(box["dir"] / "home")}
    out = subprocess.run([BASH, str(INSTALL), "--check", "--python", str(broken), "--venv", str(box["venv"])],
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 1
    assert "[FIX]   Python can't make virtual environments" in out.stdout
    assert "python3-venv" in out.stdout


def test_nothing_outside_the_environment_folder_is_touched(box):
    make_venv(box)
    home = box["dir"] / "home"
    home.mkdir()

    def files():
        return {str(p.relative_to(box["dir"])) for p in box["dir"].rglob("*") if p.is_file() and p.name != "calls.log"}

    before = files()
    out = run_install(box)
    assert out.returncode == 0, out.stdout
    assert files() == before, "the installer may only touch the environment, and here the stand-in pip changes nothing"
    assert not any(home.iterdir()), "the script itself must never write into your home folder (shell settings and so on); only pip's cache may"


# ---------------------------------------------------------------- start.sh

def run_start(tmp_path, *args, env=None, cwd=None):
    full = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home")}
    full.update(env or {})
    return subprocess.run([BASH, str(START), *args], env=full, cwd=cwd or tmp_path, capture_output=True, text=True, timeout=60)


def lines(out, prefix):
    return [ln[len(prefix):] for ln in out.stdout.splitlines() if ln.startswith(prefix)]


def test_start_without_an_installed_environment_points_at_the_installer(tmp_path):
    out = run_start(tmp_path, env={"FREEFORM_VENV": str(tmp_path / "nope")})
    assert out.returncode == 2
    assert "install.sh" in out.stderr and str(tmp_path / "nope") in out.stderr


def test_start_runs_the_module_from_the_tools_folder_listening_on_the_network(tmp_path):
    script(tmp_path / "venv" / "bin" / "python", ARG_ECHO)
    out = run_start(tmp_path, env={"FREEFORM_VENV": str(tmp_path / "venv"), "FREEFORM_CERTS": str(tmp_path / "no-certs")},
                    cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    assert lines(out, "CWD=") == [str(HERE.parent.resolve())], "the module is found from tools/, wherever you ran it"
    assert lines(out, "ARG=")[:3] == ["-m", "freeform_studio", "--host"]
    assert "0.0.0.0" in lines(out, "ARG=")
    assert "--certs-dir" not in lines(out, "ARG=")
    assert "no certificate folder" in out.stderr, "without https the phone microphone can't work, so say so"


def test_start_uses_the_certificate_folder_when_it_exists(tmp_path):
    script(tmp_path / "venv" / "bin" / "python", ARG_ECHO)
    certs = tmp_path / "certs"
    certs.mkdir()
    out = run_start(tmp_path, env={"FREEFORM_VENV": str(tmp_path / "venv"), "FREEFORM_CERTS": str(certs)})
    args = lines(out, "ARG=")
    assert args[args.index("--certs-dir") + 1] == str(certs)
    assert "no certificate folder" not in out.stderr


def test_start_passes_extra_options_last_so_they_win(tmp_path):
    script(tmp_path / "venv" / "bin" / "python", ARG_ECHO)
    out = run_start(tmp_path, "--port", "8002", "--asr-device", "cuda", "--host", "127.0.0.1",
                    env={"FREEFORM_VENV": str(tmp_path / "venv"), "FREEFORM_OUTPUT": str(tmp_path / "out")})
    args = lines(out, "ARG=")
    assert args[args.index("--output") + 1] == str(tmp_path / "out")
    assert args[-6:] == ["--port", "8002", "--asr-device", "cuda", "--host", "127.0.0.1"]
    assert args.index("0.0.0.0") < args.index("127.0.0.1"), "the user's --host comes later, and argparse keeps the last one"


def test_start_leaves_the_output_and_backup_folders_to_the_program_unless_told(tmp_path):
    script(tmp_path / "venv" / "bin" / "python", ARG_ECHO)
    out = run_start(tmp_path, env={"FREEFORM_VENV": str(tmp_path / "venv")})
    assert "--output" not in lines(out, "ARG=") and "--backup-dir" not in lines(out, "ARG=")


def test_start_can_point_backups_somewhere_else_from_the_environment(tmp_path):
    script(tmp_path / "venv" / "bin" / "python", ARG_ECHO)
    out = run_start(tmp_path, env={"FREEFORM_VENV": str(tmp_path / "venv"), "FREEFORM_BACKUPS": "/mnt/c/Users/me/freeform-backups"})
    args = lines(out, "ARG=")
    assert args[args.index("--backup-dir") + 1] == "/mnt/c/Users/me/freeform-backups"
    out = run_start(tmp_path, "--backup-dir", "/elsewhere", env={"FREEFORM_VENV": str(tmp_path / "venv"), "FREEFORM_BACKUPS": "/mnt/c/x"})
    args = lines(out, "ARG=")
    assert args[-2:] == ["--backup-dir", "/elsewhere"] and args.index("/mnt/c/x") < args.index("/elsewhere"), "an explicit option still wins"
