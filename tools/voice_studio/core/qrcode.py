# SPDX-License-Identifier: GPL-3.0-or-later
"""A QR code for a short address, so that a phone can open it by looking at the screen (plan task VS-5.1, decision D10, choices P25).

Written here, in plain Python, because the tool takes no new library for something this small. It makes the one kind of code the tool needs and no other: *byte mode* (any text, here an
address), error correction level M (about a seventh of the code can be damaged or hidden and it still reads), versions 1 to 10 (a square 21 to 57 modules wide, up to 213 bytes). A longer
text is refused rather than made in a form nobody has tested.

The pieces follow ISO/IEC 18004: Reed-Solomon codes over GF(256) with the polynomial 0x11D, the function patterns (finders, timing, alignment, format and version information), the zig-zag
placement of the data, the eight masks and their penalty rules. tests/test_vs_qrcode.py holds them to the standard's own worked values and to an independent reader that decodes every code
this module makes; it cannot say whether a particular phone's camera reads it, which is why the address is always printed beside it.

Nothing here touches the disk, the network or the screen: it turns text into a grid of dark and light squares and, on request, into text lines.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

Matrix = List[List[bool]]                           # True is a dark square; matrix[row][column]

MAX_VERSION = 10
ERROR_CODES = ("too_long",)

# Per version at level M: (error-correction codewords in each block, [(number of blocks, data codewords in each block), ...]).
_BLOCKS = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]), 6: (16, [(4, 27)]), 7: (18, [(4, 31)]),
    8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]), 10: (26, [(4, 43), (1, 44)]),
}
# The standard's table of alignment pattern centres (ISO 18004 Annex E). With two numbers only the last pair is drawn, so the first (6) is never seen in versions 2 to 6; it is kept so the table reads as the standard's.
_ALIGNMENT = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
_REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}
_FORMAT_LEVEL_M = 0                                 # the two bits for level M in the format information
_PAD = (0xEC, 0x11)


class QrError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def data_codewords(version: int) -> int:
    return sum(count * size for count, size in _BLOCKS[version][1])


def capacity(version: int) -> int:
    """How many bytes of text a code of this version holds."""
    count_bits = 8 if version < 10 else 16
    return (data_codewords(version) * 8 - 4 - count_bits) // 8


def smallest_version(length: int) -> int:
    for version in range(1, MAX_VERSION + 1):
        if length <= capacity(version):
            return version
    raise QrError("too_long")


# ---------------------------------------------------------------- Reed-Solomon over GF(256)

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _multiply(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(degree: int) -> List[int]:
    """The polynomial (x - a^0)(x - a^1)...(x - a^(degree-1)), highest power first, without its leading 1."""
    poly = [1]
    for i in range(degree):
        grown = poly + [0]
        for j, coefficient in enumerate(poly):
            grown[j + 1] ^= _multiply(coefficient, _EXP[i])
        poly = grown
    return poly[1:]


def error_codewords(data: Sequence[int], degree: int) -> List[int]:
    """The `degree` error-correction codewords for a block of data codewords (the remainder of the data times x^degree divided by the generator)."""
    generator = _generator(degree)
    remainder = [0] * degree
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        for i in range(degree):
            remainder[i] ^= _multiply(generator[i], factor)
    return remainder


# ---------------------------------------------------------------- the data

def data_bits(payload: bytes, version: int) -> List[int]:
    """Mode 0100 (bytes), the length, the bytes, a terminator, zeros to a whole byte, then the two pad bytes until the code is full."""
    bits: List[int] = []

    def put(value: int, width: int) -> None:
        bits.extend((value >> (width - 1 - i)) & 1 for i in range(width))

    put(0b0100, 4)
    put(len(payload), 8 if version < 10 else 16)
    for byte in payload:
        put(byte, 8)
    total = data_codewords(version) * 8
    bits.extend([0] * min(4, total - len(bits)))
    bits.extend([0] * (-len(bits) % 8))
    pad = 0
    while len(bits) < total:
        put(_PAD[pad % 2], 8)
        pad += 1
    return bits


def codewords(payload: bytes, version: int) -> List[int]:
    """The data codewords split into blocks, each given its error-correction codewords, then interleaved: the first codeword of every block, the second of every block, and so on."""
    bits = data_bits(payload, version)
    data = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    degree, groups = _BLOCKS[version]
    blocks: List[List[int]] = []
    at = 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(data[at:at + size])
            at += size
    checks = [error_codewords(block, degree) for block in blocks]
    out: List[int] = []
    for i in range(max(len(b) for b in blocks)):
        out.extend(block[i] for block in blocks if i < len(block))
    for i in range(degree):
        out.extend(check[i] for check in checks)
    return out


# ---------------------------------------------------------------- the grid

def _bch(value: int, width: int, generator: int, check_bits: int) -> int:
    remainder = value
    for _ in range(width):
        remainder = (remainder << 1) ^ ((remainder >> (check_bits - 1)) * generator)
    return remainder


def format_bits(mask: int) -> int:
    """The 15 bits that say the level (M) and the mask: 5 data bits, 10 check bits, then XOR 0x5412 so that the pattern is never all light."""
    data = (_FORMAT_LEVEL_M << 3) | mask
    return ((data << 10) | _bch(data, 10, 0x537, 10)) ^ 0x5412


def version_bits(version: int) -> int:
    """The 18 bits that say the version (only from version 7)."""
    return (version << 12) | _bch(version, 12, 0x1F25, 12)


def _bit(value: int, index: int) -> bool:
    return bool((value >> index) & 1)


class _Grid:
    def __init__(self, version: int):
        self.version = version
        self.size = 17 + 4 * version
        self.dark = [[False] * self.size for _ in range(self.size)]
        self.fixed = [[False] * self.size for _ in range(self.size)]
        self._patterns()

    def _set(self, x: int, y: int, dark: bool) -> None:
        self.dark[y][x] = dark
        self.fixed[y][x] = True

    def _finder(self, cx: int, cy: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.size and 0 <= y < self.size:
                    distance = max(abs(dx), abs(dy))
                    self._set(x, y, distance not in (2, 4))

    def _alignment(self, cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def _patterns(self) -> None:
        for i in range(self.size):                                      # the timing lines
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (self.size - 4, 3), (3, self.size - 4)):
            self._finder(cx, cy)
        places = _ALIGNMENT[self.version]
        for i, cy in enumerate(places):
            for j, cx in enumerate(places):
                if not ((i == 0 and j == 0) or (i == 0 and j == len(places) - 1) or (i == len(places) - 1 and j == 0)):
                    self._alignment(cx, cy)
        self.draw_format(0)                                             # reserve the places; the real bits are drawn for each mask
        if self.version >= 7:
            bits = version_bits(self.version)
            for i in range(18):
                a, b = self.size - 11 + i % 3, i // 3
                self._set(a, b, _bit(bits, i))
                self._set(b, a, _bit(bits, i))

    def draw_format(self, mask: int) -> None:
        bits = format_bits(mask)
        size = self.size
        for i in range(0, 6):
            self._set(8, i, _bit(bits, i))
        self._set(8, 7, _bit(bits, 6))
        self._set(8, 8, _bit(bits, 7))
        self._set(7, 8, _bit(bits, 8))
        for i in range(9, 15):
            self._set(14 - i, 8, _bit(bits, i))
        for i in range(0, 8):
            self._set(size - 1 - i, 8, _bit(bits, i))
        for i in range(8, 15):
            self._set(8, size - 15 + i, _bit(bits, i))
        self._set(8, size - 8, True)                                    # the one square that is always dark

    def place(self, words: Sequence[int]) -> None:
        """The data, two columns at a time from the right, up and down in turn, skipping the timing column and every fixed square."""
        size, at, total = self.size, 0, len(words) * 8
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for step in range(size):
                for offset in range(2):
                    x = right - offset
                    upward = ((right + 1) & 2) == 0
                    y = size - 1 - step if upward else step
                    if not self.fixed[y][x] and at < total:
                        self.dark[y][x] = _bit(words[at >> 3], 7 - (at & 7))
                        at += 1
            right -= 2

    def masked(self, mask: int) -> Matrix:
        """A copy with the mask applied to the data squares and the format bits for that mask drawn."""
        copy = _Grid(self.version)
        copy.dark = [row[:] for row in self.dark]
        copy.fixed = [row[:] for row in self.fixed]
        for y in range(self.size):
            for x in range(self.size):
                if not self.fixed[y][x] and _MASKS[mask](y, x):
                    copy.dark[y][x] = not copy.dark[y][x]
        copy.draw_format(mask)
        return copy.dark


_MASKS = (
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
)


def _lines(matrix: Matrix) -> List[List[bool]]:
    return [list(row) for row in matrix] + [list(column) for column in zip(*matrix)]


def penalty_runs(matrix: Matrix) -> int:
    """Rule 1: every run of five or more squares alike in a row or a column costs 3, and 1 more for each square beyond five."""
    score = 0
    for line in _lines(matrix):
        run = 1
        for i in range(1, len(line)):
            if line[i] == line[i - 1]:
                run += 1
            else:
                score += 3 + run - 5 if run >= 5 else 0
                run = 1
        score += 3 + run - 5 if run >= 5 else 0
    return score


def penalty_blocks(matrix: Matrix) -> int:
    """Rule 2: every 2x2 block of squares alike costs 3 (blocks may overlap, so a 3x3 of one colour holds four)."""
    size = len(matrix)
    return 3 * sum(1 for y in range(size - 1) for x in range(size - 1) if matrix[y][x] == matrix[y][x + 1] == matrix[y + 1][x] == matrix[y + 1][x + 1])


def penalty_finder_like(matrix: Matrix) -> int:
    """Rule 3: the pattern dark-light-dark dark dark-light-dark (1:1:3:1:1) with four light squares before or after it, in a row or a column, costs 40 each time (overlaps count)."""
    score = 0
    for line in _lines(matrix):
        text = "".join("1" if v else "0" for v in line)
        for pattern in ("00001011101", "10111010000"):
            start = text.find(pattern)
            while start != -1:
                score += 40
                start = text.find(pattern, start + 1)
    return score


def penalty_balance(matrix: Matrix) -> int:
    """Rule 4: 10 for every whole 5% the share of dark squares is away from half (the first 5% costs nothing)."""
    total = len(matrix) * len(matrix)
    dark = sum(sum(row) for row in matrix)
    return max(0, -(-abs(dark * 20 - total * 10) // total) - 1) * 10


def penalty(matrix: Matrix) -> int:
    """The standard's four rules added up: the lower, the easier a camera finds its way."""
    return penalty_runs(matrix) + penalty_blocks(matrix) + penalty_finder_like(matrix) + penalty_balance(matrix)


def encode(text: str) -> Matrix:
    """The code for `text` (UTF-8). Raises QrError("too_long") when it does not fit version 10."""
    payload = text.encode("utf-8")
    version = smallest_version(len(payload))
    grid = _Grid(version)
    grid.place(codewords(payload, version))
    best, best_score = None, None
    for mask in range(8):
        candidate = grid.masked(mask)
        score = penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score
    return best


# ---------------------------------------------------------------- for the screen

SET_BLACK_ON_WHITE = "\x1b[30;47m"
RESET = "\x1b[0m"


def lines(matrix: Matrix, quiet: int = 4, color: bool = False) -> List[str]:
    """Text lines that draw the code, two rows of squares to a line with the half blocks ▀ ▄ █. Read as dark squares on a light ground; with `color` each line says black on white
    itself, so a light-on-dark terminal does not turn the code inside out."""
    size = len(matrix)

    def dark(x: int, y: int) -> bool:
        return 0 <= x < size and 0 <= y < size and matrix[y][x]
    glyph = {(False, False): " ", (True, False): "▀", (False, True): "▄", (True, True): "█"}
    out = []
    for y in range(-quiet, size + quiet, 2):
        row = "".join(glyph[(dark(x, y), dark(x, y + 1))] for x in range(-quiet, size + quiet))
        out.append(SET_BLACK_ON_WHITE + row + RESET if color else row)
    return out
