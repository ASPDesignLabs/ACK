# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for the rounds tests: a project on disk, a stand-in for what the trainer leaves behind, and jobs written by hand in every state."""
import os
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from voice_studio.core import jobs, rounds as rd
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.paths import ProjectPaths, ScratchPaths

NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
DATASET = "dataset-20261011-100000"
PROJECT = "anna"
VOICE = "voice-mike"


def slurp(path):
    with open(path, "rb") as handle:
        return handle.read()


def stamp(minutes=0, base=NOW):
    return jobs.utc_stamp(base + timedelta(minutes=minutes))


def write_checkpoint(path, whole=True):
    """A file shaped like what PyTorch writes: a zip whose index is at the end, with the pickled state in it. `whole=False` cuts it short, as a full disk or a crash does."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("last/data.pkl", b"state" * 20)
        archive.writestr("last/version", b"3\n")
        archive.writestr("last/data/0", os.urandom(4096))
    if not whole:
        with open(path, "rb") as handle:
            data = handle.read()
        with open(path, "wb") as handle:
            handle.write(data[: len(data) // 2])
    return path


@dataclass
class World:
    paths: ProjectPaths
    scratch: ScratchPaths
    jobs_root: str
    training: EnvPaths
    base_path: str

    @property
    def base(self):
        return rd.Base(VOICE, self.base_path)

    def dataset(self, name=DATASET):
        folder = self.scratch.datasets + "/" + name
        os.makedirs(folder + "/wav", exist_ok=True)
        with open(folder + "/wav/a.wav", "wb") as handle:
            handle.write(b"RIFFxxxx")
        with open(folder + "/metadata.csv", "w") as handle:
            handle.write("a.wav|hello there\n")
        return folder

    def trainer_makes(self, version, *, whole=True, extras=2, with_last=True):
        """What the trainer leaves in `run/lightning_logs/version_N` after a round."""
        folder = "%s/lightning_logs/version_%d/checkpoints" % (self.paths.run, version)
        if with_last:
            write_checkpoint(folder + "/last.ckpt", whole)
        for n in range(extras):
            write_checkpoint("%s/epoch=%d-val_mel=0.%d.ckpt" % (folder, 100 + version * 10 + n, 600 - n))
        with open(os.path.dirname(folder) + "/hparams.yaml", "w") as handle:
            handle.write("sample_rate: 22050\n")
        return folder

    def plan(self, record=None, **kw):
        record = rd.load(self.paths) if record is None else record
        kw.setdefault("dataset", DATASET)
        kw.setdefault("base", self.base)
        return rd.plan_round(self.paths, self.scratch, record, **kw)

    def begin(self, now=NOW, **kw):
        """Plan and write down the next round as `starting`, with the folders made, as `start_round` does before it starts a job."""
        self.dataset(kw.get("dataset", DATASET))
        plan = self.plan(**kw)
        rd.prepare_folders(self.paths, plan)
        rd.begin(self.paths, plan, now)
        return plan

    def command_of(self, plan):
        return rd.command_for(self.training, plan)

    def job_for(self, plan, status, **kw):
        return fake_job(self.jobs_root, self.command_of(plan).argv, status, run_dir=plan.run_dir, **kw)

    def reconcile(self, now=None):
        return rd.reconcile(self.paths, self.scratch, self.jobs_root, PROJECT, now=now or NOW + timedelta(minutes=30))

    def run_round(self, *, version, ends="finished", files="whole", later=26, reason="", **kw):
        """A whole round, written the way the pieces would write it: begin, a job, the trainer's files, an ended job, then reconcile.
        `ends` is how the job ended (finished, stopped, failed); `files` is what the trainer left (whole, cut, no_last, none)."""
        plan = self.begin(**kw)
        info = self.job_for(plan, "running")
        rd.attach_job(self.paths, plan.number, info.id)
        if files != "none":
            self.trainer_makes(version, whole=(files != "cut"), with_last=(files != "no_last"))
        end_job(info.dir, ends, ended_at=stamp(later), reason=reason)
        self.reconcile()
        return plan


def make_world(tmp_path):
    paths = ProjectPaths(str(tmp_path / "projects" / PROJECT))
    for folder in paths.folders:
        os.makedirs(folder)
    jobs_root = str(tmp_path / "state" / "jobs")
    os.makedirs(jobs_root)
    base = write_checkpoint(str(tmp_path / "voices" / "mike.ckpt"))
    return World(paths, ScratchPaths(paths.default_scratch), jobs_root, EnvPaths(str(tmp_path / "environments" / "training-abc")), base)


def _own_starttime():
    return jobs.parse_proc_starttime(jobs.read_text_file("/proc/%d/stat" % os.getpid()))


def fake_job(jobs_root, argv, status, *, run_dir=None, name=None, project=PROJECT, kind="train", exit_code=None, signal=None, error="", ended_at=None, age=5.0):
    """A job folder written by hand in one of the states the supervisor can report: running (this very process stands in for the runner), stopping, finished,
    stopped, failed, interrupted, never_started or starting."""
    name = name or "20261011-%06d-train-%04x" % (int(time.time() * 1000) % 1_000_000, len(os.listdir(jobs_root)))
    folder = jobs_root + "/" + name
    os.makedirs(folder)
    jobs.write_json(folder + "/job.json", {"schema": 1, "kind": kind, "project": project, "argv": list(argv), "cwd": run_dir, "env": {}, "gpu": True,
                                          "force_grace_s": 10.0, "started_at": jobs.utc_stamp(), "created_epoch": time.time() - age})
    live = {"pid": os.getpid(), "starttime": _own_starttime(), "boot_id": jobs.boot_id(), "child_pid": os.getpid(), "child_starttime": _own_starttime()}
    dead = dict(live, pid=2_000_000_000, child_pid=2_000_000_000)
    if status in ("running", "stopping"):
        jobs.write_json(folder + "/runner.json", live)
    elif status in ("finished", "stopped", "failed"):
        jobs.write_json(folder + "/runner.json", dead)
    elif status == "interrupted":
        jobs.write_json(folder + "/runner.json", dead)
    if status == "stopping":
        jobs.write_json(folder + "/stop.json", {"forced": False, "at": jobs.utc_stamp()})
    if status in ("finished", "stopped", "failed", "never_started"):
        end_job(folder, status, exit_code=exit_code, signal=signal, error=error, ended_at=ended_at)
    elif status == "starting":
        pass
    return jobs.job_info(folder)


def end_job(folder, how, *, exit_code=None, signal=None, error="", ended_at=None, reason=""):
    """Write the runner's last word. `how` is finished (exit 0), stopped (a stop was asked for), failed (exit 1 unless told otherwise) or never_started (a launch error)."""
    code = {"finished": 0, "stopped": 130, "failed": 1, "never_started": None}[how] if exit_code is None and signal is None else exit_code
    if how == "stopped":
        jobs.write_json(folder + "/stop.json", dict({"forced": False, "at": jobs.utc_stamp()}, **({"reason": reason} if reason else {})))
    if how == "never_started":
        error = error or "program_not_found"
    jobs.write_json(folder + "/result.json", {"exit_code": code, "signal": signal, "ended_at": ended_at or jobs.utc_stamp(), "stop_requested": how == "stopped",
                                              "forced": False, "error": error})
    if not os.path.exists(folder + "/runner.json") and how != "never_started":
        jobs.write_json(folder + "/runner.json", {"pid": 2_000_000_000, "starttime": 1, "boot_id": jobs.boot_id(), "child_pid": 2_000_000_000, "child_starttime": 1})


# ---------------------------------------------------------------- a stand-in trainer for the tests that run a real detached job

FAKE_TRAINER = '''\
import os, re, sys, zipfile
args = sys.argv[1:]
def option(name):
    return args[args.index(name) + 1]
checkpoint, cache, config = option("--ckpt_path"), option("--data.cache_dir"), option("--data.config_path")
if not zipfile.is_zipfile(checkpoint):
    print("not a checkpoint: " + checkpoint); sys.exit(3)
base = os.path.join(os.getcwd(), "lightning_logs")
os.makedirs(base, exist_ok=True)
taken = [int(m.group(1)) for n in os.listdir(base) for m in [re.match(r"^version_(\\d+)$", n)] if m]
version = max(taken) + 1 if taken else 0
folder = os.path.join(base, "version_%d" % version, "checkpoints")
os.makedirs(folder)
def make(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ckpt/data.pkl", ("from " + checkpoint).encode()); z.writestr("ckpt/data/0", b"w" * 1024)
make(os.path.join(folder, "last.ckpt"))
make(os.path.join(folder, "epoch=%d-val_mel=0.5.ckpt" % (version * 10)))
os.makedirs(cache); open(config, "w").write("{}")
print("trained version_%d from %s for %s" % (version, checkpoint, option("--trainer.max_time")))
'''


def make_fake_training_env(tmp_path):
    env = tmp_path / "environments" / "training-fake"
    (env / "venv" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, str(env / "venv" / "bin" / "python"))
    (env / "ack_run.py").write_text(FAKE_TRAINER)
    return EnvPaths(str(env))


def wait_for_end(info_dir, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = jobs.job_info(info_dir)
        if info.status not in jobs.ACTIVE:
            return info
        time.sleep(0.05)
    raise AssertionError("the job did not end")
