# SPDX-License-Identifier: GPL-3.0-or-later
"""The shipped alignment source (data/native/monotonic_align_core.pyx) really compiles and aligns correctly.

The builder tests use a stand-in for the compiler. This one uses the real thing, so it needs Cython, numpy, a C compiler and the Python headers
(the same things the setup check asks of a person); without any of them it is **skipped, never failed**. It builds exactly as the builder does:
`python -m Cython.Build.Cythonize -i core.pyx` in a folder of its own.
"""
import importlib.util
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

from voice_studio.core import envspec as es

np = pytest.importorskip("numpy")
pytest.importorskip("Cython")
if shutil.which("gcc") is None and shutil.which("cc") is None:
    pytest.skip("no C compiler", allow_module_level=True)
if not (Path(sysconfig.get_paths()["include"]) / "Python.h").exists():
    pytest.skip("no Python headers", allow_module_level=True)

NATIVE = next(s.native for s in es.load_environments() if s.native is not None)


@pytest.fixture(scope="module")
def core(tmp_path_factory):
    work = tmp_path_factory.mktemp("native-build")
    (work / (NATIVE.module + ".pyx")).write_bytes(NATIVE.path.read_bytes())
    done = subprocess.run([sys.executable, "-m", "Cython.Build.Cythonize", "-i", NATIVE.module + ".pyx"], cwd=str(work), capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    built = sorted(work.glob(NATIVE.artifact))
    assert len(built) == 1, "one compiled file is what the builder looks for: %s" % [p.name for p in work.iterdir()]
    spec = importlib.util.spec_from_file_location(NATIVE.module, str(built[0]))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference(value, t_y, t_x):
    """The same dynamic programme written out in plain Python: the best monotonic path from the first column at the top to the last column at the bottom."""
    value = value.copy()
    path = np.zeros(value.shape, dtype=np.int32)
    neg = -1e9
    for y in range(t_y):
        for x in range(max(0, t_x + y - t_y), min(t_x, y + 1)):
            v_cur = neg if x == y else value[y - 1, x]
            v_prev = (0.0 if y == 0 else neg) if x == 0 else value[y - 1, x - 1]
            value[y, x] += max(v_prev, v_cur)
    index = t_x - 1
    for y in range(t_y - 1, -1, -1):
        path[y, index] = 1
        if index != 0 and (index == y or value[y - 1, index] < value[y - 1, index - 1]):
            index -= 1
    return path


def run(core, scores, lengths):
    paths = np.zeros(scores.shape, dtype=np.int32)
    values = np.ascontiguousarray(scores, dtype=np.float32).copy()
    t_ys = np.array([l[0] for l in lengths], dtype=np.int32)
    t_xs = np.array([l[1] for l in lengths], dtype=np.int32)
    core.maximum_path_c(paths, values, t_ys, t_xs)
    return paths


def test_the_compiled_module_offers_the_one_function_the_trainer_imports(core):
    assert callable(core.maximum_path_c)


def test_a_small_case_worked_out_by_hand(core):
    # 3 frames (rows) against 2 symbols (columns); symbol 0 fits the first frame best, symbol 1 the other two.
    scores = np.array([[[0.0, -5.0], [-5.0, 0.0], [-5.0, 0.0]]], dtype=np.float32)
    paths = run(core, scores, [(3, 2)])[0]
    assert paths.tolist() == [[1, 0], [0, 1], [0, 1]]


@pytest.mark.parametrize("seed, shape", [(1, (1, 4, 4)), (2, (3, 7, 3)), (3, (5, 12, 12)), (4, (2, 30, 9))])
def test_it_agrees_with_the_plain_python_version_and_every_frame_gets_one_symbol(core, seed, shape):
    rng = np.random.default_rng(seed)
    scores = rng.normal(size=shape).astype(np.float32)
    lengths = [(shape[1], shape[2])] * shape[0]
    paths = run(core, scores, lengths)
    for b in range(shape[0]):
        assert (paths[b] == reference(scores[b], shape[1], shape[2])).all()
        assert paths[b].sum(axis=1).tolist() == [1] * shape[1], "exactly one symbol per frame"
        columns = paths[b].argmax(axis=1)
        assert columns[0] == 0 and columns[-1] == shape[2] - 1 and (np.diff(columns) >= 0).all() and (np.diff(columns) <= 1).all(), "starts first, ends last, never goes back or skips"


def test_a_shorter_item_inside_a_longer_batch_only_uses_its_own_part(core):
    rng = np.random.default_rng(9)
    scores = rng.normal(size=(2, 10, 6)).astype(np.float32)
    paths = run(core, scores, [(10, 6), (6, 3)])
    assert paths[1][6:].sum() == 0 and paths[1][:, 3:].sum() == 0
    assert (paths[1][:6, :3] == reference(scores[1][:6, :3].copy(), 6, 3)).all()
