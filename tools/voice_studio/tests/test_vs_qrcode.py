# SPDX-License-Identifier: GPL-3.0-or-later
"""The QR code maker (plan task VS-5.1, decision D10, choices P25): held to the standard's own worked values, and to an independent reader written here from the specification, which must
read back every code the maker makes. The reader shares no code with the maker (it finds the fixed squares by region, finds the data by walking the columns, and checks the error-correction
words by evaluating the polynomial, where the maker divides)."""
import random

import pytest

from voice_studio.core import qrcode as qr

TOTAL_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346}        # ISO/IEC 18004 table 1: all codewords in a code
DATA_CODEWORDS_M = {1: 16, 2: 28, 3: 44, 4: 64, 5: 86, 6: 108, 7: 124, 8: 154, 9: 182, 10: 216}         # table 7: the data codewords at level M
BYTE_CAPACITY_M = {1: 14, 2: 26, 3: 42, 4: 62, 5: 84, 6: 106, 7: 122, 8: 152, 9: 180, 10: 213}           # table 7: bytes of text at level M


# ---------------------------------------------------------------- values from the standard

def test_the_tables_agree_with_the_standards_totals_for_every_version():
    for version in range(1, 11):
        degree, groups = qr._BLOCKS[version]
        blocks = sum(count for count, _ in groups)
        assert sum(count * (size + degree) for count, size in groups) == TOTAL_CODEWORDS[version], version
        assert qr.data_codewords(version) == DATA_CODEWORDS_M[version] == TOTAL_CODEWORDS[version] - blocks * degree, version
        assert qr.capacity(version) == BYTE_CAPACITY_M[version], version


def test_the_error_correction_words_of_the_standards_worked_example_are_the_standards():
    """ISO/IEC 18004 annex I: "01234567", version 1, level M."""
    data = [0x10, 0x20, 0x0C, 0x56, 0x61, 0x80, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11, 0xEC, 0x11]
    assert qr.error_codewords(data, 10) == [0xA5, 0x24, 0xD4, 0xC1, 0xED, 0x36, 0xC7, 0x87, 0x2C, 0x55]


def test_the_error_correction_words_of_the_common_tutorial_example_match():
    data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]                        # "HELLO WORLD", version 1, level M
    assert qr.error_codewords(data, 10) == [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]


def test_the_generator_polynomial_for_seven_check_words_is_the_standards():
    assert qr._generator(7) == [qr._EXP[e] for e in (87, 229, 146, 149, 238, 102, 21)]                      # x^7 + a^87 x^6 + a^229 x^5 + ... : the standard lists the powers of a


def test_the_format_words_for_level_m_are_the_standards_for_each_mask():
    expected = ["101010000010010", "101000100100101", "101111001111100", "101101101001011", "100010111111001", "100000011001110", "100111110010111", "100101010100000"]
    assert [format(qr.format_bits(mask), "015b") for mask in range(8)] == expected


def test_the_version_words_are_the_standards():
    assert [format(qr.version_bits(v), "018b") for v in (7, 8, 9, 10)] == ["000111110010010100", "001000010110111100", "001001101010011001", "001010010011010011"]


def test_the_galois_field_arithmetic_is_the_one_the_standard_names():
    assert qr._EXP[:10] == [1, 2, 4, 8, 16, 32, 64, 128, 29, 58] and len(qr._EXP) == 255 and qr._LOG[1] == 0 and qr._multiply(qr._EXP[254], 2) == 1 and qr._multiply(2, 128) == 29
    assert all(qr._multiply(a, 1) == a and qr._multiply(a, 0) == 0 for a in range(256))
    assert all(qr._multiply(a, b) == qr._multiply(b, a) for a in range(0, 256, 7) for b in range(0, 256, 11))


def test_the_data_bits_of_a_short_text_are_mode_length_bytes_terminator_and_the_two_pad_bytes():
    bits = "".join(str(b) for b in qr.data_bits(b"Hi", 1))
    assert len(bits) == 128 and bits.startswith("0100" + "00000010" + "01001000" + "01101001" + "0000")
    words = [int(bits[i:i + 8], 2) for i in range(0, 128, 8)]
    assert words == [0x40, 0x24, 0x86, 0x90] + [0xEC, 0x11] * 6


def test_a_text_that_fills_the_code_exactly_gets_no_pad_and_a_shortened_terminator():
    text = b"x" * qr.capacity(1)
    bits = "".join(str(b) for b in qr.data_bits(text, 1))
    assert len(bits) == 128 and bits[-4:] == "0000" and bits[:12] == "010000001110"        # 14 bytes: the terminator is only what fits; no pad bytes
    one_less = "".join(str(b) for b in qr.data_bits(b"x" * (qr.capacity(1) - 1), 1))
    assert one_less[-8:] == "11101100", "room for one pad byte"


def test_data_for_a_code_that_is_too_small_is_refused_rather_than_cut():
    assert len(qr.data_bits(b"x" * qr.capacity(1), 1)) == 128
    with pytest.raises(qr.QrError) as caught:
        qr.data_bits(b"x" * (qr.capacity(1) + 1), 1)
    assert caught.value.code == "too_long"
    assert len(qr.data_bits(b"x" * qr.capacity(10), 10)) == qr.data_codewords(10) * 8
    with pytest.raises(qr.QrError):
        qr.data_bits(b"x" * (qr.capacity(10) + 1), 10)


def test_from_version_ten_the_length_has_sixteen_bits():
    bits = "".join(str(b) for b in qr.data_bits(b"abc", 10))
    assert bits[:4 + 16] == "0100" + "0000000000000011"


# ---------------------------------------------------------------- an independent reader

def bch_remainder(value, generator, width):
    """Polynomial division of value (shifted left by the check width) by the generator, bit by bit."""
    value <<= width
    top = generator.bit_length() - 1
    for shift in range(value.bit_length() - 1 - top, -1, -1):
        if value >> (shift + top) & 1:
            value ^= generator << shift
    return value


def expected_format(mask):
    data = (0 << 3) | mask
    return ((data << 10) | bch_remainder(data, 0x537, 10)) ^ 0x5412


def function_map(size, version):
    """True where a square is not data: found by region, as the standard draws it."""
    fixed = [[False] * size for _ in range(size)]
    for y in range(9):
        for x in range(9):
            fixed[y][x] = True
        for x in range(size - 8, size):
            fixed[y][x] = True
    for y in range(size - 8, size):
        for x in range(9):
            fixed[y][x] = True
    for i in range(size):
        fixed[6][i] = fixed[i][6] = True
    centers = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}[version]
    for cy in centers:
        for cx in centers:
            if (cx, cy) in ((6, 6), (6, centers[-1]), (centers[-1], 6)):
                continue
            for y in range(cy - 2, cy + 3):
                for x in range(cx - 2, cx + 3):
                    fixed[y][x] = True
    if version >= 7:
        for y in range(6):
            for x in range(size - 11, size - 8):
                fixed[y][x] = fixed[x][y] = True
    return fixed


MASK_RULES = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
              lambda r, c: r * c % 2 + r * c % 3 == 0, lambda r, c: (r * c % 2 + r * c % 3) % 2 == 0, lambda r, c: ((r + c) % 2 + r * c % 3) % 2 == 0]


def read_format(m):
    size = len(m)
    first = [(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (7, 8), (8, 8), (8, 7), (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0)]                 # (column, row), highest bit first
    second = [(8, size - 1 - i) for i in range(7)] + [(size - 8 + i, 8) for i in range(8)]
    a = int("".join("1" if m[y][x] else "0" for x, y in first), 2)
    b = int("".join("1" if m[y][x] else "0" for x, y in second), 2)
    assert a == b, "the two copies of the format word agree"
    return a


def gf_exp_table():
    exp, x = [], 1
    for _ in range(255):
        exp.append(x)
        x = (x << 1) ^ (0x11D if x & 0x80 else 0)
    return exp


def mul(a, b, exp=gf_exp_table()):
    if not a or not b:
        return 0
    log = {v: i for i, v in enumerate(exp)}
    return exp[(log[a] + log[b]) % 255]


def decode(m):
    size = len(m)
    version = (size - 17) // 4
    word = read_format(m)
    mask = next(k for k in range(8) if expected_format(k) == word)
    fixed = function_map(size, version)
    bits = []
    column, upward = size - 1, True
    while column > 0:
        if column == 6:
            column -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (column, column - 1):
                if not fixed[r][c]:
                    bits.append(m[r][c] != MASK_RULES[mask](r, c))
        upward = not upward
        column -= 2
    remainder = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}[version]
    assert len(bits) == TOTAL_CODEWORDS[version] * 8 + remainder
    assert not any(bits[TOTAL_CODEWORDS[version] * 8:]), "the remainder bits of the standard are light before the mask"
    words = [int("".join("1" if b else "0" for b in bits[i:i + 8]), 2) for i in range(0, TOTAL_CODEWORDS[version] * 8, 8)]
    degree, groups = qr._BLOCKS[version]
    sizes = [size_ for count, size_ in groups for _ in range(count)]
    # undo the interleaving: data words are dealt out round and round, then the check words
    blocks = [[] for _ in sizes]
    at = 0
    for i in range(max(sizes)):
        for k, length in enumerate(sizes):
            if i < length:
                blocks[k].append(words[at])
                at += 1
    checks = [[] for _ in sizes]
    for i in range(degree):
        for k in range(len(sizes)):
            checks[k].append(words[at])
            at += 1
    exp = gf_exp_table()
    for block, check in zip(blocks, checks):
        whole = block + check
        for power in range(degree):                                    # every syndrome (the value at a^power) of a good block is zero
            value = 0
            for coefficient in whole:
                value = mul(value, exp[power]) ^ coefficient
            assert value == 0, "syndrome %d of a block is not zero" % power
    data = [w for block in blocks for w in block]
    stream = "".join(format(w, "08b") for w in data)
    assert stream[:4] == "0100", "byte mode"
    count_bits = 8 if version < 10 else 16
    length = int(stream[4:4 + count_bits], 2)
    body = stream[4 + count_bits:4 + count_bits + 8 * length]
    assert len(body) == 8 * length
    after = stream[4 + count_bits + 8 * length:]
    assert after[:4] == "0000" and len(after[4:]) % 8 == 0, "a four-bit terminator, and then whole bytes"
    pads = [int(after[i:i + 8], 2) for i in range(4, len(after), 8)]
    assert pads == ([0xEC, 0x11] * len(pads))[:len(pads)], "the pad bytes alternate, starting with 0xEC"
    return bytes(int(body[i:i + 8], 2) for i in range(0, len(body), 8)).decode("utf-8"), version, mask


def test_the_reader_reads_back_a_short_address():
    text = "https://192.168.1.23:8443/AbCdEfGhIjKlMnOpQrStUv/my_voice_backup.zip"
    assert decode(qr.encode(text))[0] == text


@pytest.mark.parametrize("length", sorted(set(list(range(1, 30)) + [qr.capacity(v) + d for v in range(1, 11) for d in (-1, 0, 1) if qr.capacity(v) + d > 0 and qr.capacity(v) + d <= 213])))
def test_every_length_reads_back_in_the_smallest_version_that_holds_it(length):
    text = "".join(chr(ord("a") + (i * 7) % 26) for i in range(length))
    got, version, _ = decode(qr.encode(text))
    assert got == text and version == qr.smallest_version(length)
    assert version == 1 or length > qr.capacity(version - 1)


def test_text_beyond_two_hundred_and_thirteen_bytes_is_refused():
    assert qr.capacity(10) == 213
    qr.encode("a" * 213)
    with pytest.raises(qr.QrError) as caught:
        qr.encode("a" * 214)
    assert caught.value.code == "too_long" == qr.ERROR_CODES[0]


def test_text_that_is_not_ascii_reads_back_as_the_same_text():
    for text in ("café ☕ — ok", "日本語のテキスト", "a" * 50 + "é"):
        assert decode(qr.encode(text))[0] == text


def test_random_text_of_random_length_reads_back_in_every_version():
    rng = random.Random(20261016)
    seen = set()
    for _ in range(120):
        length = rng.randint(1, 213)
        text = "".join(chr(rng.randint(33, 126)) for _ in range(length))
        got, version, mask = decode(qr.encode(text))
        assert got == text
        seen.add(version)
    assert seen == set(range(1, 11)) or len(seen) >= 8


def test_the_fixed_squares_are_where_the_standard_puts_them():
    m = qr.encode("fixed squares")
    size = len(m)
    assert size == 21
    finder = ["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"]
    for ox, oy in ((0, 0), (size - 7, 0), (0, size - 7)):
        assert ["".join("1" if m[oy + y][ox + x] else "0" for x in range(7)) for y in range(7)] == finder
    for ox, oy, xs, ys in ((0, 0, range(7, 8), range(0, 8)), (0, 0, range(0, 8), range(7, 8))):
        assert not any(m[y][x] for x in xs for y in ys), "the light border of a finder"
    assert [m[6][i] for i in range(8, size - 8)] == [i % 2 == 0 for i in range(8, size - 8)]
    assert [m[i][6] for i in range(8, size - 8)] == [i % 2 == 0 for i in range(8, size - 8)]
    assert m[size - 8][8] is True, "the one square that is always dark"


def test_a_larger_code_has_its_alignment_pattern_and_version_squares():
    m = qr.encode("x" * 50)                         # version 4 (size 33)
    assert len(m) == 33
    box = ["".join("1" if m[26 + y][26 + x] else "0" for x in range(-2, 3)) for y in range(-2, 3)]
    assert box == ["11111", "10001", "10101", "10001", "11111"]
    big = qr.encode("x" * 110)                      # version 7: version information is drawn
    assert len(big) == 45
    bits = qr.version_bits(7)
    assert all(big[i // 3][45 - 11 + i % 3] == bool(bits >> i & 1) and big[45 - 11 + i % 3][i // 3] == bool(bits >> i & 1) for i in range(18))


def test_the_mask_chosen_is_the_one_with_the_lowest_penalty():
    for text in ("a", "https://192.168.1.23:8443/token/file.zip", "x" * 100):
        m = qr.encode(text)
        version = qr.smallest_version(len(text))
        grid = qr._Grid(version)
        grid.place(qr.codewords(text.encode(), version))
        scores = [qr.penalty(grid.masked(mask)) for mask in range(8)]
        _, _, used = decode(m)
        assert scores[used] == min(scores) and qr.penalty(m) == min(scores)


def grid(rows):
    return [[c == "1" for c in row] for row in rows]


def checker(size, parity=0):
    return [[(x + y) % 2 == parity for x in range(size)] for y in range(size)]


def test_rule_one_costs_three_for_a_run_of_five_and_one_more_for_each_square_beyond():
    assert qr.penalty_runs(checker(6)) == 0
    five = checker(5)
    five[0] = [True] * 5
    assert qr.penalty_runs(five) == 3, "one row of five alike; every column has no run of five"
    six = checker(6)
    six[0] = [True] * 6
    assert qr.penalty_runs(six) == 4
    seven = checker(7)
    seven[0] = [True] * 7
    assert qr.penalty_runs(seven) == 5
    four = checker(5)
    four[0] = [True, True, True, True, False]
    assert qr.penalty_runs(four) == 0, "a run of four costs nothing"
    assert qr.penalty_runs(grid(["00000"] * 5)) == 5 * 3 + 5 * 3, "five rows and five columns, each one run of five"


def test_rule_one_counts_a_run_that_ends_at_the_edge_and_a_run_in_the_middle():
    middle = grid(["0111110", "1010101", "0101010", "1010101", "0101010", "1010101", "0101010"])
    assert qr.penalty_runs(middle) == 3
    edge = grid(["0011111", "1010101", "0101010", "1010101", "0101010", "1010101", "0101010"])
    assert qr.penalty_runs(edge) == 3
    column = [list(r) for r in zip(*middle)]
    assert qr.penalty_runs(column) == 3, "the same in a column"


def test_rule_two_costs_three_for_every_two_by_two_block_of_one_colour_overlaps_included():
    assert qr.penalty_blocks(checker(5)) == 0
    assert qr.penalty_blocks(grid(["11", "11"])) == 3
    assert qr.penalty_blocks(grid(["111", "111", "111"])) == 4 * 3
    assert qr.penalty_blocks(grid(["000", "000", "000"])) == 4 * 3
    assert qr.penalty_blocks(grid(["110", "110", "001"])) == 3
    assert qr.penalty_blocks(grid(["10", "11"])) == 0


def test_rule_three_costs_forty_for_the_finder_like_pattern_with_four_light_squares_on_either_side():
    size = 13
    for pattern in ("00001011101", "10111010000"):
        for transpose in (False, True):
            m = checker(size)
            for k, c in enumerate(pattern):
                if transpose:
                    m[2 + k][1] = c == "1"
                else:
                    m[1][2 + k] = c == "1"
            lines_with_pattern = [("".join("1" if v else "0" for v in line)) for line in m + [list(c) for c in zip(*m)]]
            expected = 40 * sum(1 for t in lines_with_pattern if pattern in t)
            assert expected >= 40
            assert qr.penalty_finder_like(m) == expected, (pattern, transpose)
    assert qr.penalty_finder_like(checker(size)) == 0


def test_rule_three_counts_two_patterns_that_share_squares_and_ignores_near_misses():
    both = grid(["000010111010000"] + ["0" * 15] * 14)               # 00001011101 starts at 0 and 10111010000 at 4: they share their middle
    assert qr.penalty_finder_like(both) == 80
    near = grid(["000010111000000"] + ["0" * 15] * 14)
    assert qr.penalty_finder_like(near) == 0
    assert qr.penalty_finder_like(grid(["0000101110"] + ["0" * 10] * 9)) == 0, "ten squares are too short for the pattern"


def test_rule_four_costs_ten_for_every_five_percent_beyond_the_first_five_away_from_half():
    nine = lambda dark: [[i * 3 + j < dark for j in range(3)] for i in range(3)]
    assert [qr.penalty_balance(nine(d)) for d in range(10)] == [90, 70, 50, 30, 10, 10, 30, 50, 70, 90]
    assert qr.penalty_balance([[True, False], [False, True]]) == 0, "exactly half: nothing, never a negative"
    c21 = checker(21)
    assert sum(map(sum, c21)) == 221 and qr.penalty_balance(c21) == 0, "221 of 441 is within the first 5%"


def test_the_whole_penalty_is_the_four_rules_added():
    for m in (checker(9), grid(["111", "111", "111"]), qr.encode("sum of the rules")):
        assert qr.penalty(m) == qr.penalty_runs(m) + qr.penalty_blocks(m) + qr.penalty_finder_like(m) + qr.penalty_balance(m)
    blank = [[False] * 21 for _ in range(21)]
    assert qr.penalty(blank) == 42 * (3 + 16) + 400 * 3 + 90


# ---------------------------------------------------------------- for the screen

def test_the_text_lines_draw_two_rows_of_squares_each_with_a_quiet_zone():
    m = qr.encode("lines")
    size = len(m)
    out = qr.lines(m)
    assert len(out) == (size + 8 + 1) // 2 and all(len(line) == size + 8 for line in out)
    assert set("".join(out)) <= set(" ▀▄█")
    assert out[0] == " " * (size + 8), "the first two rows are the quiet zone"
    assert out[2] == " " * 4 + "".join("█▀"[0] if (m[0][x] and m[1][x]) else "▀" if m[0][x] else "▄" if m[1][x] else " " for x in range(size)) + " " * 4, "the first row of squares sits in the third line, beside the second"


def test_each_character_stands_for_the_two_squares_it_covers():
    m = [[True, False], [False, True]]
    out = qr.lines(m, quiet=0)
    assert out == ["▀▄"]
    assert qr.lines([[True, True], [True, False]], quiet=0) == ["█▀"]
    three = [[True, False, True], [False, False, True], [True, True, False]]
    assert qr.lines(three, quiet=0) == ["▀ █", "▀▀ "], "an odd number of rows ends with a row of light squares below"
    assert qr.lines([[False, False], [True, True]], quiet=0) == ["▄▄"]
    assert qr.lines([[False]], quiet=0) == [" "]
    assert qr.lines([[True]], quiet=0) == ["▀"]


def test_with_colour_each_line_says_black_on_white_itself_and_resets():
    out = qr.lines(qr.encode("c"), color=True)
    assert all(line.startswith("\x1b[30;47m") and line.endswith("\x1b[0m") for line in out)
    assert [line[len("\x1b[30;47m"):-len("\x1b[0m")] for line in out] == qr.lines(qr.encode("c"))
