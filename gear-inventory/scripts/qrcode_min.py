"""Dependency-free QR Code encoder - just enough for asset labels.

Versions 1-4, error-correction level L, alphanumeric and byte modes. That is
25 / 47 / 77 / 114 alphanumeric characters, or 17 / 32 / 53 / 78 bytes. Asset
tags and short URLs fit comfortably; longer payloads raise ValueError.

Why hand-rolled: the whole inventory toolchain must run on a bare Python 3.9+
install (no pip, no network), so `labels.py` can print a sheet anywhere.

    >>> m = encode("CAM-0007")
    >>> len(m), len(m[0])
    (21, 21)

The matrix is a list of rows of booleans, True = dark module. Add a quiet zone
of >= 4 modules when rendering.
"""

from __future__ import annotations

# --- GF(256) arithmetic, primitive polynomial 0x11D, generator 2 ------------

_EXP = [0] * 512
_LOG = [0] * 256


def _init_gf() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _poly_mul(p, q):
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        for j, b in enumerate(q):
            out[i + j] ^= _gf_mul(a, b)
    return out


def rs_generator_poly(degree: int):
    """Generator polynomial for `degree` error-correction codewords."""
    g = [1]
    for i in range(degree):
        g = _poly_mul(g, [1, _EXP[i]])
    return g


def rs_encode(data, ec_count: int):
    """Reed-Solomon error-correction codewords for `data` (list of ints)."""
    gen = rs_generator_poly(ec_count)
    rem = [0] * ec_count
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i, g in enumerate(gen[1:]):
                rem[i] ^= _gf_mul(g, factor)
    return rem


# --- QR structure -----------------------------------------------------------

# version -> (total codewords, ecc codewords at level L). Single block for L
# in versions 1-4, which is why the encoder stops at 4.
_VERSIONS = {1: (26, 7), 2: (44, 10), 3: (70, 15), 4: (100, 20)}

ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

_MODE_ALNUM = 0b0010
_MODE_BYTE = 0b0100

_G15 = 0x537
_G15_MASK = 0x5412
_EC_L = 1  # level indicator used in the format-information bits

_PAD = (0xEC, 0x11)


def _bch_format_bits(data: int) -> int:
    d = data << 10
    while d.bit_length() - _G15.bit_length() >= 0:
        d ^= _G15 << (d.bit_length() - _G15.bit_length())
    return ((data << 10) | d) ^ _G15_MASK


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


class _Bits:
    def __init__(self):
        self.bits = []

    def put(self, value: int, length: int) -> None:
        for shift in range(length - 1, -1, -1):
            self.bits.append((value >> shift) & 1)

    def __len__(self):
        return len(self.bits)


def _can_alnum(text: str) -> bool:
    return all(c in ALNUM for c in text)


def _encode_payload(text: str, version: int, mode: int):
    """Bit stream for `text` at `version`, or None if it does not fit."""
    total, ec = _VERSIONS[version]
    capacity = (total - ec) * 8
    bits = _Bits()
    if mode == _MODE_ALNUM:
        bits.put(_MODE_ALNUM, 4)
        bits.put(len(text), 9)  # versions 1-9 count length
        for i in range(0, len(text) - 1, 2):
            bits.put(ALNUM.index(text[i]) * 45 + ALNUM.index(text[i + 1]), 11)
        if len(text) % 2:
            bits.put(ALNUM.index(text[-1]), 6)
    else:
        raw = text.encode("utf-8")
        bits.put(_MODE_BYTE, 4)
        bits.put(len(raw), 8)
        for byte in raw:
            bits.put(byte, 8)
    if len(bits) > capacity:
        return None
    # Terminator, then pad to a whole codeword, then alternating pad bytes.
    bits.put(0, min(4, capacity - len(bits)))
    while len(bits) % 8:
        bits.bits.append(0)
    codewords = [
        int("".join(str(b) for b in bits.bits[i : i + 8]), 2)
        for i in range(0, len(bits), 8)
    ]
    while len(codewords) < total - ec:
        codewords.append(_PAD[len(codewords) % 2])
    return codewords + rs_encode(codewords, ec)


def _blank(size: int):
    return [[None] * size for _ in range(size)]


def _place_function_patterns(m, version: int) -> None:
    size = len(m)
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if not (0 <= rr < size and 0 <= cc < size):
                    continue
                edge = r in (0, 6) and 0 <= c <= 6
                side = c in (0, 6) and 0 <= r <= 6
                core = 2 <= r <= 4 and 2 <= c <= 4
                m[rr][cc] = edge or side or core
    for i in range(8, size - 8):
        m[6][i] = i % 2 == 0
        m[i][6] = i % 2 == 0
    if version >= 2:
        pos = 4 * version + 10
        for r in range(-2, 3):
            for c in range(-2, 3):
                m[pos + r][pos + c] = max(abs(r), abs(c)) != 1
    m[size - 8][8] = True  # the always-dark module


def _reserve_format_area(m) -> None:
    size = len(m)
    for i in range(9):
        if m[8][i] is None:
            m[8][i] = False
        if m[i][8] is None:
            m[i][8] = False
    for i in range(8):
        if m[8][size - 1 - i] is None:
            m[8][size - 1 - i] = False
        if m[size - 1 - i][8] is None:
            m[size - 1 - i][8] = False


def _place_format_bits(m, mask: int) -> None:
    size = len(m)
    bits = _bch_format_bits((_EC_L << 3) | mask)
    for i in range(15):
        dark = ((bits >> i) & 1) == 1
        if i < 6:
            m[i][8] = dark
        elif i < 8:
            m[i + 1][8] = dark
        else:
            m[size - 15 + i][8] = dark
        if i < 8:
            m[8][size - 1 - i] = dark
        elif i == 8:
            m[8][7] = dark
        else:
            m[8][14 - i] = dark


def _place_data(m, codewords, mask: int):
    """Write the data bits along the zig-zag path, masking as we go."""
    size = len(m)
    mask_fn = _MASKS[mask]
    bit_index, byte_index = 7, 0
    row, inc = size - 1, -1
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        while True:
            for c in (col, col - 1):
                if m[row][c] is not None:
                    continue
                dark = False
                if byte_index < len(codewords):
                    dark = ((codewords[byte_index] >> bit_index) & 1) == 1
                if mask_fn(row, c):
                    dark = not dark
                m[row][c] = dark
                bit_index -= 1
                if bit_index == -1:
                    byte_index += 1
                    bit_index = 7
            row += inc
            if row < 0 or row >= size:
                row -= inc
                inc = -inc
                break
        col -= 2
    return m


def _penalty(m) -> int:
    size = len(m)
    score = 0
    # Rule 1: runs of five or more same-colour modules in a row or column.
    for line in list(m) + [list(col) for col in zip(*m)]:
        run, prev = 1, line[0]
        for cell in line[1:]:
            if cell == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, cell
        if run >= 5:
            score += 3 + (run - 5)
    # Rule 2: 2x2 blocks of one colour.
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    # Rule 3: finder-like 1:1:3:1:1 patterns.
    a = [True, False, True, True, True, False, True]
    pats = (a + [False] * 4, [False] * 4 + a)
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(size - 10):
            window = line[i : i + 11]
            if window in pats:
                score += 40
    # Rule 4: deviation from a 50/50 dark ratio.
    dark = sum(1 for row in m for cell in row if cell)
    pct = dark * 100 // (size * size)
    score += 10 * min(abs(pct - 50) // 5, abs(pct + 1 - 50) // 5)
    return score


def encode(text: str, version: int = None, mask: int = None):
    """Encode `text` and return the QR matrix (list of rows of bool)."""
    if not text:
        raise ValueError("refusing to encode an empty payload")
    mode = _MODE_ALNUM if _can_alnum(text) else _MODE_BYTE
    versions = [version] if version else sorted(_VERSIONS)
    codewords = None
    for candidate in versions:
        if candidate not in _VERSIONS:
            raise ValueError("only QR versions 1-4 are supported")
        codewords = _encode_payload(text, candidate, mode)
        if codewords is not None:
            version = candidate
            break
    if codewords is None:
        raise ValueError(
            "payload too long for QR version 4 level L "
            "(max 114 alphanumeric / 78 bytes) - shorten it or print the tag "
            "as text only"
        )

    def build(mask_value: int):
        m = _blank(17 + 4 * version)
        _place_function_patterns(m, version)
        _reserve_format_area(m)
        _place_data(m, codewords, mask_value)
        _place_format_bits(m, mask_value)
        return m

    if mask is not None:
        return build(mask)
    best, best_score = None, None
    for candidate in range(8):
        m = build(candidate)
        score = _penalty(m)
        if best_score is None or score < best_score:
            best, best_score = m, score
    return best


def to_svg_path(matrix, module: float = 1.0) -> str:
    """One SVG path `d` attribute drawing every dark module as a square."""
    parts = []
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                parts.append(
                    "M%g %gh%gv%gh-%gz" % (c * module, r * module, module, module, module)
                )
    return "".join(parts)


def to_text(matrix) -> str:
    """ASCII rendering, handy for eyeballing a code in a terminal."""
    quiet = "  " * (len(matrix) + 8)
    lines = [quiet, quiet]
    for row in matrix:
        lines.append("    " + "".join("##" if cell else "  " for cell in row) + "    ")
    lines += [quiet, quiet]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    print(to_text(encode(sys.argv[1] if len(sys.argv) > 1 else "CAM-0007")))
