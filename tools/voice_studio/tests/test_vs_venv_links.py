# SPDX-License-Identifier: GPL-3.0-or-later
"""The Python of a tool-built environment must be the real one, and a broken one must be repaired in place (found on a real Ubuntu 22.04).

On Python 3.10 an environment made while another is active is linked to the other one's Python. The training environment was built that way, the other one (a
test clone) was deleted, and the environment's own `bin/python3` pointed at nothing, with 6 GB of installed packages beside it; and Python's own `venv` does not
repair a link that is already there. The tool now builds from the real interpreter, treats a missing or chained link as "not done", and replaces only those links."""
import os
import sys
import venv
from pathlib import Path

import pytest

from voice_studio.core import envbuild as eb
from voice_studio.core.system import RealSystem, real_interpreter

MINOR = (3, 10)


# ---------------------------------------------------------------- which interpreter to build from

def usable(*paths):
    return lambda p: p in paths


def test_outside_a_virtual_environment_the_running_python_is_the_real_one():
    assert real_interpreter("/usr/bin/python3", MINOR, "/usr", "/usr", "/usr", is_usable=usable()) == "/usr/bin/python3"


def test_outside_a_virtual_environment_the_running_python_is_kept_even_when_another_name_would_be_usable():
    assert real_interpreter("/opt/mine/bin/python3", MINOR, "/usr", "/usr", "/usr", is_usable=usable("/usr/bin/python3.10"), resolve=lambda p: "/usr/bin/python3.10") == "/opt/mine/bin/python3"


def test_inside_one_the_real_interpreter_is_named_from_where_it_lives():
    assert real_interpreter("/home/a/.venv/bin/python3", MINOR, "/home/a/.venv", "/usr", "/usr", is_usable=usable("/usr/bin/python3.10")) == "/usr/bin/python3.10"


def test_the_name_uses_the_running_version_and_the_base_execution_prefix():
    got = real_interpreter("/v/bin/python", (3, 12), "/v", "/opt/base", "/opt/exec", is_usable=usable("/opt/exec/bin/python3.12", "/opt/base/bin/python3.12", "/opt/exec/bin/python3.1"))
    assert got == "/opt/exec/bin/python3.12"


def test_when_that_name_is_not_a_usable_file_the_links_are_followed_to_the_real_file():
    got = real_interpreter("/v/bin/python3", MINOR, "/v", "/usr", "/usr", is_usable=usable("/real/bin/python3.10"), resolve=lambda p: "/real/bin/python3.10")
    assert got == "/real/bin/python3.10"


def test_a_followed_link_that_lands_inside_another_virtual_environment_is_not_trusted(tmp_path):
    other = tmp_path / "other"
    (other / "bin").mkdir(parents=True)
    (other / "pyvenv.cfg").write_text("home = /usr/bin\n")
    landed = str(other / "bin" / "python3")
    got = real_interpreter("/v/bin/python3", MINOR, "/v", "/usr", "/usr", is_usable=usable(landed), resolve=lambda p: landed)
    assert got == "/v/bin/python3", "nothing better is known, so it is left as it was rather than invented"


def test_a_followed_link_that_changes_nothing_or_is_not_usable_is_not_used():
    assert real_interpreter("/v/bin/python3", MINOR, "/v", "/usr", "/usr", is_usable=usable(), resolve=lambda p: p) == "/v/bin/python3"
    assert real_interpreter("/v/bin/python3", MINOR, "/v", "/usr", "/usr", is_usable=usable(), resolve=lambda p: "/x/python") == "/v/bin/python3"


def test_nothing_known_about_the_running_python_falls_back_to_a_name_to_look_up():
    assert real_interpreter("", MINOR, "/usr", "/usr", "/usr") == "python3"
    assert real_interpreter(None, MINOR, "/usr", "/usr", "/usr") == "python3"


def test_the_real_system_names_an_interpreter_that_runs_and_is_not_a_virtual_environments():
    exe = RealSystem().python_executable()
    ran = RealSystem().run([exe, "-c", "import sys; print(sys.version_info[0], sys.version_info[1], int(sys.prefix != sys.base_prefix))"], timeout=30)
    assert ran is not None and ran.returncode == 0
    major, minor, inside = ran.stdout.split()
    assert (int(major), int(minor)) == tuple(sys.version_info[:2]) and inside == "0", "the same Python version, running outside any virtual environment"
    assert not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(exe)), "pyvenv.cfg")), exe


def test_with_no_virtual_environment_involved_the_real_system_names_the_running_python():
    if sys.prefix == sys.base_prefix:
        assert RealSystem().python_executable() == sys.executable


# ---------------------------------------------------------------- which links are broken

def make_env(root: Path, name="env"):
    """A folder shaped like an environment: bin/ and a pyvenv.cfg."""
    env = root / name
    (env / "bin").mkdir(parents=True)
    (env / "pyvenv.cfg").write_text("home = /usr/bin\n")
    return env


def broken(env):
    return eb.broken_interpreter_links(str(env), MINOR)


def test_an_environment_with_links_to_the_systems_python_has_nothing_broken(tmp_path):
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    (system / "python3.10").write_text("#!/bin/sh\n")
    env = make_env(tmp_path)
    for name in ("python3.10",):
        os.symlink(system / "python3.10", env / "bin" / name)
    os.symlink("python3.10", env / "bin" / "python3")
    os.symlink("python3", env / "bin" / "python")
    assert broken(env) == []


def test_a_link_that_points_at_nothing_is_broken_and_so_are_the_links_that_lead_to_it(tmp_path):
    env = make_env(tmp_path)
    os.symlink(tmp_path / "gone" / "bin" / "python3", env / "bin" / "python3")
    os.symlink("python3", env / "bin" / "python3.10")
    os.symlink("python3", env / "bin" / "python")
    assert broken(env) == ["python", "python3", "python3.10"]


def test_a_link_to_another_virtual_environment_is_broken_even_while_that_one_exists(tmp_path):
    other = make_env(tmp_path, "other")
    (other / "bin" / "python3").write_text("#!/bin/sh\n")
    env = make_env(tmp_path)
    os.symlink(other / "bin" / "python3", env / "bin" / "python3")
    os.symlink("python3", env / "bin" / "python")
    os.symlink("python3", env / "bin" / "python3.10")
    assert broken(env) == ["python", "python3", "python3.10"]


def test_one_good_link_beside_a_chained_one_is_left_alone(tmp_path):
    other = make_env(tmp_path, "other")
    (other / "bin" / "python3").write_text("#!/bin/sh\n")
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    (system / "python3.10").write_text("#!/bin/sh\n")
    env = make_env(tmp_path)
    os.symlink(other / "bin" / "python3", env / "bin" / "python3")
    os.symlink(system / "python3.10", env / "bin" / "python3.10")
    assert broken(env) == ["python3"]


def test_a_copy_of_the_interpreter_is_not_a_link_and_is_not_touched(tmp_path):
    env = make_env(tmp_path)
    for name in ("python", "python3", "python3.10"):
        (env / "bin" / name).write_text("#!/bin/sh\n")
    assert broken(env) == []


def test_names_that_are_not_the_interpreters_are_never_reported(tmp_path):
    env = make_env(tmp_path)
    for name in ("pip", "python3.1", "python3.11", "python3.100", "python2", "piper", "activate"):
        os.symlink(tmp_path / "gone", env / "bin" / name)
    assert broken(env) == []


def test_the_minor_version_picks_the_versioned_name(tmp_path):
    env = make_env(tmp_path)
    os.symlink(tmp_path / "gone", env / "bin" / "python3.12")
    assert eb.broken_interpreter_links(str(env), (3, 12)) == ["python3.12"] and eb.broken_interpreter_links(str(env), (3, 10)) == []


def test_links_that_lead_round_in_a_circle_are_broken_and_do_not_hang(tmp_path):
    env = make_env(tmp_path)
    os.symlink("python3", env / "bin" / "python")
    os.symlink("python", env / "bin" / "python3")
    assert broken(env) == ["python", "python3"]


def test_an_environment_with_no_bin_or_no_links_has_nothing_to_report(tmp_path):
    assert eb.broken_interpreter_links(str(tmp_path / "nowhere"), MINOR) == []
    assert broken(make_env(tmp_path)) == []


def test_a_followed_link_stays_inside_the_environment_when_it_only_goes_between_its_own_names(tmp_path):
    env = make_env(tmp_path)
    system = tmp_path / "usr" / "bin"
    system.mkdir(parents=True)
    (system / "python3").write_text("#!/bin/sh\n")
    os.symlink(system / "python3", env / "bin" / "python3")
    os.symlink("python3", env / "bin" / "python")
    assert eb._links_out_of(str(env / "bin" / "python"), str(env / "bin")) == str(system / "python3")
    assert eb._links_out_of(str(env / "bin" / "python3"), str(env / "bin")) == str(system / "python3")
    (env / "bin" / "plain").write_text("x")
    assert eb._links_out_of(str(env / "bin" / "plain"), str(env / "bin")) is None
