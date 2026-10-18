# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for the update tests: a real git repository on this disk with some releases in it (reached by a file:// address, so the real `git ls-remote` and `git clone` run), a copy of its
first release to be the copy that is running, and a stand-in for the download module that runs those same commands after checking the agreement, and remembers what it was asked."""
import os
import subprocess
from pathlib import Path

from voice_studio.core.registry import ReleaseSource
from voice_studio.core.system import CommandResult, RealSystem

GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "init.defaultBranch=main", "-c", "tag.gpgSign=false", "-c", "commit.gpgSign=false"]


def git(*args, cwd=None):
    done = subprocess.run(GIT + list(args), cwd=cwd, capture_output=True, text=True, env=dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null"))
    assert done.returncode == 0, (args, done.stderr)
    return done.stdout.strip()


FIRST = {"tools/voice_studio/__init__.py": '__version__ = "1.0.0"\n', "tools/voice_studio/data/locks/studio.lock.txt": "a==1\n", "tools/voice_studio/data/sources.json": '{"items": []}\n',
         "tools/voice_studio/core/x.py": "x = 1\n", "tools/voice_studio/data/text/en.json": '{"a": "one"}\n', "tools/freeform_studio/app.py": "app = 1\n",
         "docs/VOICE_STUDIO_GUIDE.md": "one\n", "docs/ACK_Voice_Studio_Installation_Guide.MD": "one\n", "docs/OTHER.md": "not ours\n"}
SECOND = {"tools/voice_studio/__init__.py": '__version__ = "1.1.0"\n', "tools/voice_studio/data/locks/studio.lock.txt": "a==2\n", "tools/voice_studio/core/y.py": "y = 1\n",
          "tools/voice_studio/data/text/en.json": '{"a": "two"}\n', "tools/freeform_studio/app.py": "app = 2\n", "docs/VOICE_STUDIO_GUIDE.md": "two\n", "docs/OTHER.md": "changed but not ours\n"}


class UpdateSystem(RealSystem):
    """The real disk, with `git` present or not and the free room chosen by the test."""

    def __init__(self, git_present=True, free=None):
        self.git_present, self.free = git_present, free

    def which(self, name):
        return ("/usr/bin/" + name) if (name != "git" or self.git_present) else None

    def disk_free(self, path):
        return self.free if self.free is not None else (10 ** 13, 10 ** 12)


class UpdateRig:
    def __init__(self, tmp_path, *, releases=("v1.0", "v1.1"), here_at="v1.0", tag_prefix="", app_tags=()):
        """`releases` are the names the person sees; the repository's tags are `tag_prefix` + name. `app_tags` are tags of the phone app, made first, that must never be taken for releases."""
        self.tmp = Path(tmp_path)
        self.repo = self.tmp / "origin"
        self.repo.mkdir()
        git("init", "-q", "-b", "main", cwd=self.repo)
        self.url = "file://" + str(self.repo)
        self.source = ReleaseSource(self.url, "update.why", tag_prefix)
        self.tag_prefix = tag_prefix
        self.commits = {}
        files = (FIRST, SECOND)
        for tag in app_tags:
            self.release(tag, FIRST, tag=tag)
        for index, name in enumerate(releases):
            self.release(name, files[min(index, 1)], annotated=(index % 2 == 1), tag=tag_prefix + name)
        self.here = self.tmp / "ack-tools"
        if here_at:
            git("clone", "-q", "--depth", "1", "--branch", tag_prefix + here_at, self.url, str(self.here))
        self.system = UpdateSystem()
        self.calls = []                       # (argv, ids) of everything the download stand-in was asked
        self.offline = False
        self.refuse = None                    # an exception for the stand-in to raise
        self.after_clone = None

    def release(self, name, files, annotated=False, tag=None):
        tag = tag or name
        for rel, data in files.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        git("add", "-A", cwd=self.repo)
        git("commit", "-q", "--allow-empty", "-m", "release " + name, cwd=self.repo)
        git(*(["tag", "-a", "-m", tag, tag] if annotated else ["tag", tag]), cwd=self.repo)
        self.commits[name] = git("rev-parse", tag + "^{commit}", cwd=self.repo)

    def networked(self, consent, argv, item_ids, **kw):
        self.calls.append((list(argv), list(item_ids)))
        if self.refuse is not None:
            raise self.refuse
        assert consent is not None and all(consent.covers_id(i) for i in item_ids), "the download module is only used with agreement"
        if self.offline:
            return CommandResult(128, "fatal: unable to access: Could not resolve host\n", "")
        done = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null"))
        if self.after_clone and argv[:2] == ["git", "clone"]:
            self.after_clone(argv)
        return CommandResult(done.returncode, done.stdout + done.stderr, "")

    @property
    def tools_dir(self):
        return str(self.here / "tools")

    def tree(self, root):
        found = {}
        for path in sorted(Path(root).rglob("*")):
            if ".git" in path.relative_to(root).parts:
                continue
            if path.is_file() and not path.is_symlink():
                found[str(path.relative_to(root))] = path.read_bytes()
        return found
