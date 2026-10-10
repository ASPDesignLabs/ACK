# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for the download tests: a pinned item built from real bytes, and an opener that serves them (with or without Range support)."""
import hashlib
import io
import urllib.error
from dataclasses import replace

from voice_studio.core.registry import Item

PAYLOAD = bytes(range(256)) * 8          # 2,048 bytes
ADDRESS = "https://huggingface.co/datasets/example/store/resolve/0123abcd/voice/model.ckpt"


def pinned_item(payload=PAYLOAD, **overrides):
    item = Item("voice-test", "voice", "fetch.why.test", "voice-test-card", approx_size_bytes=len(payload), url=ADDRESS, filename="model.ckpt",
                revision="0123abcd", size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    return replace(item, **overrides) if overrides else item


class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class FakeOpener:
    def __init__(self, payload=PAYLOAD, *, honor_range=True, serve=None, raise_first=None, status=None):
        self.payload, self.honor_range, self.serve = payload, honor_range, serve
        self.raise_first, self.status = raise_first, status
        self.calls = []
        self.bytes_sent = 0

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        if self.raise_first is not None and len(self.calls) == 1:
            raise self.raise_first
        body = self.payload if self.serve is None else self.serve
        rng = headers.get("Range")
        if rng and self.honor_range:
            start = int(rng[len("bytes="):-1])
            chunk = body[start:]
            self.bytes_sent += len(chunk)
            return FakeResponse(chunk, self.status or 206, {"Content-Range": "bytes %d-%d/%d" % (start, len(body) - 1, len(body))})
        self.bytes_sent += len(body)
        return FakeResponse(body, self.status or 200)


def http_error(code):
    return urllib.error.HTTPError(ADDRESS, code, "error", {}, None)
