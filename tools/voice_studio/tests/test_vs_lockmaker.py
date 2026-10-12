# SPDX-License-Identifier: GPL-3.0-or-later
"""The maintainers' lock generator (tools/voice_studio_maint/make_lock.py): which wheels it counts, what it refuses, and that what it writes is a
lock the builder accepts. The generator is not part of the app; these tests keep it honest because the lock it writes decides what gets installed."""
import importlib.util
import io
import json
from pathlib import Path

import pytest

from voice_studio.core import envspec as es

PKG = Path(__file__).resolve().parents[1]
MAKER = PKG.parent / "voice_studio_maint" / "make_lock.py"
spec = importlib.util.spec_from_file_location("make_lock_under_test", MAKER)
ml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml)

PY310, PY311, PY312, PY313 = (3, 10), (3, 11), (3, 12), (3, 13)
MANY = "manylinux_2_17_x86_64.manylinux2014_x86_64"


@pytest.mark.parametrize("filename, minor, expected", [
    ("numpy-2.2.6-cp312-cp312-%s.whl" % MANY, PY312, True),
    ("numpy-2.2.6-cp312-cp312-%s.whl" % MANY, PY311, False),
    ("numpy-2.2.6-cp312-cp312-%s.whl" % MANY, PY313, False),
    ("numpy-2.2.6-cp310-cp310-%s.whl" % MANY, PY310, True),
    ("foo-1-cp39-abi3-manylinux2014_x86_64.whl", PY310, True),
    ("foo-1-cp310-abi3-manylinux2014_x86_64.whl", PY310, True),
    ("foo-1-cp311-abi3-manylinux2014_x86_64.whl", PY310, False),
    ("foo-1-cp312-abi3-manylinux2014_x86_64.whl", PY312, True),
    ("foo-1-cp312-abi3-manylinux2014_x86_64.whl", PY311, False),
    ("foo-1-py3-none-any.whl", PY310, True),
    ("foo-1-py2.py3-none-any.whl", PY312, True),
    ("foo-1-py310-none-any.whl", PY310, True),
    ("foo-1-py311-none-any.whl", PY310, False),
    ("foo-1-py3-none-manylinux_2_28_x86_64.whl", PY312, True),
    ("foo-1-cp312-none-manylinux2014_x86_64.whl", PY312, True),
    ("foo-1-1-cp312-cp312-manylinux2014_x86_64.whl", PY312, True),                  # with a build tag
    ("foo-1-cp312-cp312-manylinux1_x86_64.whl", PY312, True),
    ("foo-1-cp312-cp312-musllinux_1_2_x86_64.whl", PY312, False),
    ("foo-1-cp312-cp312-manylinux2014_aarch64.whl", PY312, False),
    ("foo-1-cp312-cp312-manylinux_2_28_i686.whl", PY312, False),
    ("foo-1-cp312-cp312-macosx_11_0_arm64.whl", PY312, False),
    ("foo-1-cp312-cp312-win_amd64.whl", PY312, False),
    ("foo-1-cp312-cp312-linux_x86_64.whl", PY312, False),                           # PyPI refuses bare linux tags; never counted
    ("foo-1-cp313-cp313t-manylinux_2_17_x86_64.whl", PY313, False),                 # free-threaded builds are a different interpreter
    ("foo-1-cp313-abi3t-manylinux_2_17_x86_64.whl", PY313, False),
    ("foo-1-pp310-pypy310_pp73-manylinux2014_x86_64.whl", PY310, False),
    ("foo-1-py27-none-any.whl", PY312, False),
    ("foo-1-py3-cp312-manylinux2014_x86_64.whl", PY312, False),                     # a pure-Python tag never goes with a compiled ABI
    ("foo-py3-none-any.whl", PY312, False), ("py3-none-any.whl", PY312, False),     # no version in the name: not a wheel file name
    ("foo-1.tar.gz", PY312, False), ("foo-1-py3-none-any.zip", PY312, False), ("junk.whl", PY312, False),
])
def test_which_wheels_count_for_which_python(filename, minor, expected):
    assert ml.wheel_covers(filename, minor) is expected


def file(name, digest_char="a", yanked=False, **extra):
    return {"filename": name, "digests": {"sha256": digest_char * 64}, "yanked": yanked, **extra}


def release(*files):
    return {"urls": list(files)}


def fake_fetch(table):
    def fetch(name, version):
        return table[(name, version)]
    return fetch


NOTES = ["made for a test"]


def test_the_lock_lists_each_package_sorted_with_every_usable_checksum_once():
    table = {
        ("Zed", "1.0"): release(file("zed-1.0-py3-none-any.whl", "b")),
        ("numpy", "2.2.6"): release(file("numpy-2.2.6-cp312-cp312-%s.whl" % MANY, "d"), file("numpy-2.2.6-cp310-cp310-%s.whl" % MANY, "c"),
                                    file("numpy-2.2.6-cp313-cp313-%s.whl" % MANY, "e"),            # not asked for
                                    file("numpy-2.2.6-cp311-cp311-musllinux_1_2_x86_64.whl", "f"),   # not this system
                                    file("numpy-2.2.6.tar.gz", "9"),                                 # never installed from source
                                    file("numpy-2.2.6-cp311-cp311-%s.whl" % MANY, "a", yanked=True),
                                    file("numpy-2.2.6-cp311-cp311-%s.whl" % MANY, "c")),
    }
    text, counts = ml.build_lock([("Zed", "1.0"), ("numpy", "2.2.6")], fake_fetch(table), [PY310, PY311, PY312], NOTES)
    assert text == ("# made for a test\n\n"
                    "numpy==2.2.6 \\\n    --hash=sha256:%s \\\n    --hash=sha256:%s\n"
                    "Zed==1.0 \\\n    --hash=sha256:%s\n") % ("c" * 64, "d" * 64, "b" * 64)
    assert counts == {"Zed": 1, "numpy": 2}


def test_checksums_are_in_order_of_their_own_value_not_of_the_file_names():
    table = {("p", "1"): release(file("p-1-cp310-cp310-%s.whl" % MANY, "f"), file("p-1-cp311-cp311-%s.whl" % MANY, "3"), file("p-1-cp312-cp312-%s.whl" % MANY, "9"))}
    text, _ = ml.build_lock([("p", "1")], fake_fetch(table), [PY310, PY311, PY312], NOTES)
    assert [l.strip()[-64] for l in text.splitlines() if "--hash" in l] == ["3", "9", "f"]


def test_what_it_writes_is_a_lock_the_builder_accepts_and_the_order_of_the_input_does_not_matter():
    table = {("a", "1"): release(file("a-1-py3-none-any.whl", "1")), ("B_c", "2.0"): release(file("B_c-2.0-cp312-cp312-%s.whl" % MANY, "2"))}
    one, _ = ml.build_lock([("a", "1"), ("B_c", "2.0")], fake_fetch(table), [PY312], NOTES)
    two, _ = ml.build_lock([("B_c", "2.0"), ("a", "1")], fake_fetch(table), [PY312], NOTES)
    assert one == two
    pins, problems = es.parse_lock(one)
    assert problems == [] and [(p.name, p.version, p.hashes) for p in pins] == [("a", "1", ("1" * 64,)), ("b-c", "2.0", ("2" * 64,))]


def test_a_package_with_no_wheel_for_a_python_asked_for_stops_everything_and_says_which():
    table = {
        ("old", "1"): release(file("old-1-cp312-cp312-%s.whl" % MANY, "1")),                  # nothing for 3.10
        ("src", "1"): release(file("src-1.tar.gz", "2")),                                    # nothing at all
        ("fine", "1"): release(file("fine-1-py3-none-any.whl", "3")),
        ("gone", "1"): release(file("gone-1-py3-none-any.whl", "4", yanked=True)),            # a yanked file does not count
    }
    with pytest.raises(ml.LockError) as caught:
        ml.build_lock([("old", "1"), ("src", "1"), ("fine", "1"), ("gone", "1")], fake_fetch(table), [PY310, PY312], NOTES)
    said = str(caught.value)
    lines = [l.strip() for l in said.splitlines()]
    assert "old 1: no Linux x86_64 wheel for Python 3.10" in lines
    assert "src 1: no Linux x86_64 wheel for Python 3.10, 3.12" in lines and "gone 1: no Linux x86_64 wheel for Python 3.10, 3.12" in lines
    assert not [l for l in lines if l.startswith("fine")]
    assert "decision for the maintainer" in said


def test_a_wheel_for_only_some_of_the_pythons_is_not_enough_but_is_enough_when_only_those_are_asked_for():
    table = {("p", "1"): release(file("p-1-cp312-cp312-%s.whl" % MANY, "1"))}
    with pytest.raises(ml.LockError):
        ml.build_lock([("p", "1")], fake_fetch(table), [PY311, PY312], NOTES)
    assert ml.build_lock([("p", "1")], fake_fetch(table), [PY312], NOTES)[1] == {"p": 1}


@pytest.mark.parametrize("digests", [None, {}, {"sha256": "short"}, {"sha256": "A" * 64}, {"sha256": 5}, {"md5": "a" * 32}, {"sha256": "a" * 63}, {"sha256": "a" * 65}])
def test_a_listing_without_a_usable_checksum_is_refused(digests):
    bad = {"filename": "p-1-py3-none-any.whl", "yanked": False}
    if digests is not None:
        bad["digests"] = digests
    with pytest.raises(ml.LockError, match="no usable sha256"):
        ml.build_lock([("p", "1")], fake_fetch({("p", "1"): release(bad)}), [PY312], NOTES)


def test_no_python_asked_for_is_an_error():
    with pytest.raises(ml.LockError):
        ml.build_lock([("p", "1")], fake_fetch({}), [], NOTES)


@pytest.mark.parametrize("text", ["3.12", "3.10", "3.9"])
def test_python_versions_are_read(text):
    assert ml.parse_minor(text) == (3, int(text.split(".")[1]))


@pytest.mark.parametrize("text", ["3", "312", "3.x", "2.7", "3.12.1", "", " 3.12", "4.0"])
def test_a_python_version_that_is_not_three_dot_n_is_refused(text):
    with pytest.raises(ml.LockError):
        ml.parse_minor(text)


def test_the_list_of_versions_is_read_and_editable_installs_are_set_aside_and_reported():
    pairs, skipped = ml.parse_versions("# comment\nabsl-py==2.5.1\n\n-e git+file:///x@abc#egg=piper_tts\nJinja2==3.1.6  # trailing\ntorch==2.14.1+cu130\n")
    assert pairs == [("absl-py", "2.5.1"), ("Jinja2", "3.1.6"), ("torch", "2.14.1+cu130")]
    assert skipped == ["line 4: -e git+file:///x@abc#egg=piper_tts"]


@pytest.mark.parametrize("text, fragment", [
    ("numpy>=1\n", "line 1"), ("numpy\n", "line 1"), ("git+https://x/y\n", "line 1"), ("a==1\nb @ file:///x\n", "line 2"), ("a==1.*\n", "line 1"),
    ("a==1\nA==2\n", "listed twice"), ("a-b==1\na_b==1\n", "listed twice"), ("", "no name==version"), ("# only a comment\n", "no name==version"),
])
def test_a_list_that_is_not_plain_pins_is_refused(text, fragment):
    with pytest.raises(ml.LockError, match=fragment):
        ml.parse_versions(text)


# ---------------------------------------------------------------- reading the package site

class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_dropped_connection_is_tried_again_and_the_waits_grow():
    calls, waits = [], []

    def opener(url, timeout):
        calls.append((url, timeout))
        if len(calls) < 3:
            raise OSError("connection reset")
        return Reply(json.dumps({"urls": []}).encode())

    assert ml.fetch_from_package_site("Lazy_loader", "0.6", opener=opener, sleep=waits.append) == {"urls": []}
    assert calls[0] == ("https://pypi.org/pypi/lazy-loader/0.6/json", 30) and len(calls) == 3 and waits == [1.5, 3.0]


def test_a_missing_release_is_not_retried_and_a_run_of_failures_gives_up_with_the_reason():
    seen = []

    def missing(url, timeout):
        seen.append(1)
        raise OSError("HTTP Error 404: Not Found")

    with pytest.raises(ml.LockError, match="could not read its listing .*404"):
        ml.fetch_from_package_site("x", "1", opener=missing, sleep=lambda s: None)
    assert len(seen) == 1
    seen.clear()

    def down(url, timeout):
        seen.append(1)
        raise OSError("timed out")

    with pytest.raises(ml.LockError, match="timed out"):
        ml.fetch_from_package_site("x", "1", tries=3, opener=down, sleep=lambda s: None)
    assert len(seen) == 3


@pytest.mark.parametrize("body", [b"[]", b'{"urls": 5}', b'{"info": {}}'])
def test_a_listing_in_the_wrong_shape_is_refused_and_not_retried(body):
    seen = []

    def opener(url, timeout):
        seen.append(1)
        return Reply(body)

    with pytest.raises(ml.LockError, match="not in the shape"):
        ml.fetch_from_package_site("x", "1", opener=opener, sleep=lambda s: None)
    assert len(seen) == 1


# ---------------------------------------------------------------- the command

def run_main(monkeypatch, tmp_path, table, extra=(), versions="a==1\n"):
    (tmp_path / "v.txt").write_text(versions)
    monkeypatch.setattr(ml, "fetch_from_package_site", fake_fetch(table))
    return ml.main(["--versions", str(tmp_path / "v.txt"), "--python", "3.12", "--out", str(tmp_path / "out.lock.txt"), *extra])


def test_the_command_writes_the_lock_and_says_its_checksum(monkeypatch, tmp_path, capsys):
    table = {("a", "1"): release(file("a-1-py3-none-any.whl", "1")), ("setuptools", "81.0.0"): release(file("setuptools-81.0.0-py3-none-any.whl", "2"))}
    assert run_main(monkeypatch, tmp_path, table, ["--add", "setuptools==81.0.0", "--note", "hello"]) == 0
    written = (tmp_path / "out.lock.txt").read_text()
    pins, problems = es.parse_lock(written)
    assert problems == [] and [p.name for p in pins] == ["a", "setuptools"]
    lines = written.splitlines()
    assert lines[0] == "# hello" and "# Python versions covered: 3.12. Linux x86_64 wheels only; Python 3.13 and newer are not covered." in lines
    assert any(l.startswith("# Input list sha256: ") for l in lines)
    assert "lock sha256: %s" % es.lock_digest(written.encode()) in capsys.readouterr().out


def test_an_existing_lock_is_kept_beside_the_new_one_and_never_lost(monkeypatch, tmp_path):
    table = {("a", "1"): release(file("a-1-py3-none-any.whl", "1"))}
    out = tmp_path / "out.lock.txt"
    out.write_text("the first\n")
    assert run_main(monkeypatch, tmp_path, table) == 0
    assert (tmp_path / "out.lock.txt.before-1").read_text() == "the first\n"
    first = out.read_text()
    assert run_main(monkeypatch, tmp_path, table) == 0
    assert (tmp_path / "out.lock.txt.before-1").read_text() == "the first\n" and (tmp_path / "out.lock.txt.before-2").read_text() == first


def test_when_anything_fails_nothing_is_written_and_an_existing_lock_is_untouched(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out.lock.txt"
    out.write_text("keep me\n")
    table = {("a", "1"): release(file("a-1.tar.gz", "1"))}
    assert run_main(monkeypatch, tmp_path, table) == 2
    assert out.read_text() == "keep me\n" and not list(tmp_path.glob("*.before-*"))
    err = capsys.readouterr().err
    assert err.startswith("NOT WRITTEN:") and "a 1: no Linux x86_64 wheel for Python 3.12" in err
    assert run_main(monkeypatch, tmp_path, {}, versions="nonsense\n") == 2 and out.read_text() == "keep me\n"
    (tmp_path / "v.txt").unlink()
    assert ml.main(["--versions", str(tmp_path / "v.txt"), "--python", "3.12", "--out", str(out)]) == 2 and out.read_text() == "keep me\n"


# ---------------------------------------------------------------- where it lives

def test_the_generator_is_a_maintainers_tool_outside_the_app():
    """The app never imports it and it is not in the shipped package: it uses the network, which the app may do only in core/fetch.py."""
    assert PKG not in MAKER.parents and MAKER.read_text().startswith("# SPDX-License-Identifier: GPL-3.0-or-later\n")
    offenders = [str(p.relative_to(PKG)) for p in PKG.rglob("*.py") if "tests" not in p.relative_to(PKG).parts and "voice_studio_maint" in p.read_text()]
    assert offenders == []
