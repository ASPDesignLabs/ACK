# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's icon as a Windows `.ico`, drawn from the same shapes as `data/icons/org.aspdesignlabs.AckVoiceStudio.svg`: ACK's cut-corner square (top left and bottom right cut) in void black with a cyan
outline, and five cyan bars.

A Windows shortcut cannot use an SVG, and a binary icon file is not committed to the repository (THIRD_PARTY_NOTICES: no binary assets), so the tool draws it when it is asked to make the
shortcut: plain Python, no image library, no outside artwork. Each size is a PNG inside the ICO container (supported since Windows Vista). The same bytes come out every time.
"""
from __future__ import annotations

import math
import struct
import zlib
from typing import List, Tuple

SIZES = (16, 32, 48, 64, 256)
BACKGROUND = (0x05, 0x05, 0x05)
ACCENT = (0x00, 0xF3, 0xFF)
# in the SVG's own 128 x 128 units
POLYGON = ((36.0, 8.0), (120.0, 8.0), (120.0, 92.0), (92.0, 120.0), (8.0, 120.0), (8.0, 36.0))     # the cut-corner square; the line is drawn centred on its edge
STROKE = 4.0
BARS = ((22.0, 52.0, 10.0, 24.0), (40.0, 38.0, 10.0, 52.0), (58.0, 24.0, 10.0, 80.0), (76.0, 40.0, 10.0, 48.0), (94.0, 54.0, 10.0, 20.0))      # x, y, width, height; ends are round
VIEW = 128.0


def _distance_to_rounded_box(px: float, py: float, x: float, y: float, w: float, h: float, r: float) -> float:
    """Signed distance from (px, py) to a rounded rectangle: negative inside, positive outside."""
    cx, cy = x + w / 2.0, y + h / 2.0
    qx = abs(px - cx) - (w / 2.0 - r)
    qy = abs(py - cy) - (h / 2.0 - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _distance_to_shape(px: float, py: float) -> float:
    """Signed distance to the cut-corner square (exact inside and along its edges, a little short of exact near an outside corner, which is all the soft edge needs)."""
    worst = -1e9
    count = len(POLYGON)
    for i in range(count):
        (x1, y1), (x2, y2) = POLYGON[i], POLYGON[(i + 1) % count]
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = (y2 - y1) / length, -(x2 - x1) / length                   # the outward normal for a polygon listed clockwise on the screen
        worst = max(worst, (px - x1) * nx + (py - y1) * ny)
    return worst


def _coverage(distance_in_pixels: float) -> float:
    return min(1.0, max(0.0, 0.5 - distance_in_pixels))


def _pixel(ix: int, iy: int, size: int) -> Tuple[int, int, int, int]:
    unit = VIEW / size
    px, py = (ix + 0.5) * unit, (iy + 0.5) * unit
    d = _distance_to_shape(px, py)
    outer = _coverage((d - STROKE / 2.0) / unit)                           # everything inside the outer edge of the line
    if outer <= 0.0:
        return (0, 0, 0, 0)
    inner = _coverage((d + STROKE / 2.0) / unit)                           # the part inside the line
    base = tuple(ACCENT[i] * (1.0 - inner) + BACKGROUND[i] * inner for i in range(3))
    bars = 0.0
    for x, y, w, h in BARS:
        bars = max(bars, _coverage(_distance_to_rounded_box(px, py, x, y, w, h, w / 2.0) / unit))
    mixed = tuple(round(base[i] * (1.0 - bars) + ACCENT[i] * bars) for i in range(3))
    return (mixed[0], mixed[1], mixed[2], round(255 * outer))


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(size: int) -> bytes:
    """One square RGBA image of the icon."""
    rows = []
    for iy in range(size):
        row = bytearray([0])                                          # filter type 0 for every row
        for ix in range(size):
            row.extend(_pixel(ix, iy, size))
        rows.append(bytes(row))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)       # 8 bits, colour type 6 (RGBA)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + _chunk(b"IEND", b"")


def ico_bytes(sizes: Tuple[int, ...] = SIZES) -> bytes:
    """The whole `.ico`: a header, one directory entry per size, then the PNGs."""
    images: List[Tuple[int, bytes]] = [(size, png(size)) for size in sizes]
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for size, image in images:
        entries += struct.pack("<BBBBHHII", 0 if size >= 256 else size, 0 if size >= 256 else size, 0, 0, 1, 32, len(image), offset + len(data))
        data += image
    return head + entries + data
