# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the network may be used (plan decisions D5, D27): in one module, after agreement, and nowhere else.

Three kinds of proof, because each catches what another can miss: the source of every file is read (no network library imported, no
subprocess started, no web address written down outside the registry), `System.run` refuses network programs when the code runs, and the
download module itself refuses without agreement (test_vs_fetch.py).
"""
import ast
import re
import sys
from pathlib import Path

import pytest

from voice_studio.core.system import NetworkBlocked, RealSystem, is_network_command

PKG = Path(__file__).resolve().parents[1]
SHIPPED = sorted(p for p in PKG.rglob("*") if p.is_file() and "tests" not in p.relative_to(PKG).parts and "__pycache__" not in p.parts)
PY = [p for p in SHIPPED if p.suffix == ".py"]

DOWNLOAD_MODULE = "core/fetch.py"
MAY_START_PROGRAMS = {"core/system.py", "core/fetch.py", "core/jobs.py", "core/jobrunner.py"}     # the job supervisor and its runner
WEB_ADDRESS_ALLOWED = {"data/sources.json", "get.sh"}                # get.sh: the one address the person is shown before the first fetch of ACK itself
NETWORK_ROOTS = {"socket", "ssl", "http", "ftplib", "smtplib", "telnetlib", "xmlrpc", "poplib", "imaplib", "nntplib", "socketserver",
                 "requests", "httpx", "aiohttp", "websockets", "paramiko", "urllib3", "huggingface_hub", "asyncio"}


def rel(p):
    return str(p.relative_to(PKG))


def network_imports(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in NETWORK_ROOTS or (root == "urllib" and a.name != "urllib.parse"):
                    found.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            if root in NETWORK_ROOTS:
                found.add(node.module)
            elif node.module == "urllib":
                found |= {"urllib." + a.name for a in node.names if a.name != "parse"}
            elif root == "urllib" and node.module != "urllib.parse":
                found.add(node.module)
    return found


def process_starts(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names if a.name.split(".")[0] in {"subprocess", "pty", "multiprocessing"}}
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in {"subprocess", "pty", "multiprocessing"}:
            found.add(node.module)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os" and \
                (node.attr in {"system", "popen", "posix_spawn", "posix_spawnp", "fork", "forkpty"} or node.attr.startswith(("exec", "spawn"))):
            found.add("os." + node.attr)
    return found


# ---------------------------------------------------------------- read the source

def test_the_package_has_files_to_check():
    assert any(rel(p) == DOWNLOAD_MODULE for p in PY) and len(PY) >= 6


def test_only_the_download_module_imports_anything_that_can_reach_the_network():
    offenders = {rel(p): sorted(network_imports(ast.parse(p.read_text()))) for p in PY if rel(p) != DOWNLOAD_MODULE}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, "the network may be used only in %s:\n%s" % (DOWNLOAD_MODULE, offenders)


def test_the_download_module_really_is_the_one_that_uses_it():
    assert network_imports(ast.parse((PKG / DOWNLOAD_MODULE).read_text())) >= {"urllib.request"}


def test_only_two_modules_may_start_a_program_and_neither_may_use_a_shell():
    offenders = {rel(p): sorted(process_starts(ast.parse(p.read_text()))) for p in PY if rel(p) not in MAY_START_PROGRAMS}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, "starting a program goes through System.run or the download module:\n%s" % offenders
    for name in MAY_START_PROGRAMS:
        source = (PKG / name).read_text()
        assert "shell=True" not in source and "os.system" not in source, name


def test_no_web_address_is_written_anywhere_but_the_registry_and_the_bootstrap_script():
    pattern = re.compile(r"(?:https?|wss?|ftp)://")
    offenders = []
    for p in SHIPPED:
        if p.suffix in {".py", ".js", ".html", ".css", ".sh", ".json", ".txt"} and rel(p) not in WEB_ADDRESS_ALLOWED:
            for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if pattern.search(line):
                    offenders.append("%s:%d" % (rel(p), n))
    assert not offenders, "a web address belongs in data/sources.json, where the person sees it before it is used:\n" + "\n".join(offenders)


def test_the_source_checks_can_actually_fail():          # mutation guards: each detector is shown to catch what it is for
    assert network_imports(ast.parse("import requests\nimport asyncio\n")) == {"requests", "asyncio"}
    assert network_imports(ast.parse("import socket\nimport urllib.request\n")) == {"socket", "urllib.request"}
    assert network_imports(ast.parse("from urllib import request\n")) == {"urllib.request"}
    assert network_imports(ast.parse("from http.client import HTTPSConnection\n")) == {"http.client"}
    assert network_imports(ast.parse("from urllib.parse import urlparse\nimport os, json\n")) == set()
    assert network_imports(ast.parse("from urllib import parse\nimport urllib.parse\n")) == set()
    assert process_starts(ast.parse("import subprocess\nimport os\nos.system('x')\nos.execv('a', [])\n")) == {"subprocess", "os.system", "os.execv"}
    assert process_starts(ast.parse("import os\nos.path.join('a')\n")) == set()


# ---------------------------------------------------------------- the run-time gate

@pytest.mark.parametrize("argv", [
    ["curl", "-O", "x"], ["wget", "x"], ["git", "clone", "x"], ["pip", "install", "x"], ["pip3", "install", "x"], ["/usr/bin/apt-get", "install", "git"],
    ["sudo", "apt-get", "install", "git"], ["sudo", "-n", "apt", "update"], ["env", "FOO=1", "pip", "install"], ["timeout", "10", "git", "clone", "x"],
    ["nice", "-n", "5", "curl", "x"], ["/usr/bin/python3", "-m", "pip", "list"], ["python3.12", "-m", "pip", "install", "x"], ["ssh", "host"],
    ["rsync", "a", "b"], ["snap", "install", "x"],
])
def test_a_command_that_can_reach_the_network_is_refused_by_system_run(argv):
    assert is_network_command(argv)
    with pytest.raises(NetworkBlocked):
        RealSystem().run(argv)


@pytest.mark.parametrize("argv", [
    ["dpkg-query", "-W", "git", "curl"], ["nvidia-smi"], [sys.executable, "-c", "print(1)"], ["sudo", "-n", "true"], ["ls", "git"], ["python3", "-c", "import pip"],
    ["echo", "pip", "install"], [], ["sudo"],
])
def test_ordinary_local_commands_are_not_mistaken_for_network_ones(argv):
    assert not is_network_command(argv)


def test_system_run_still_runs_a_local_command():
    result = RealSystem().run([sys.executable, "-c", "print('ok')"])
    assert result is not None and result.returncode == 0 and result.stdout.strip() == "ok"


def test_the_bootstrap_script_holds_exactly_one_web_address_and_it_is_the_source_repository():
    lines = [l for l in (PKG / "get.sh").read_text().splitlines() if re.search(r"(?:https?|wss?|ftp)://", l)]
    assert len(lines) == 1 and lines[0].startswith('REPO_URL="https://github.com/')
