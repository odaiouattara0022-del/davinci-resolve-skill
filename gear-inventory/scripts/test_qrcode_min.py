"""Validation of qrcode_min against an independently written QR reader.

No QR library exists on a bare Python install, so correctness is proved three
ways instead: known spec constants, Reed-Solomon syndromes (a scanner's own
integrity check), and a decoder below that re-derives the geometry from the
spec rather than reusing the encoder's placement code.
"""

import unittest

import qrcode_min as q


# --- an independent reader --------------------------------------------------


def is_function_module(r, c, size, version):
    """True when (r, c) belongs to a function pattern, per ISO/IEC 18004."""
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        if r0 - 1 <= r <= r0 + 7 and c0 - 1 <= c <= c0 + 7:
            return True
    if r == 6 or c == 6:  # timing patterns
        return True
    if version >= 2:  # single alignment pattern for versions 2-4
        p = 4 * version + 10
        if p - 2 <= r <= p + 2 and p - 2 <= c <= p + 2:
            return True
    if r == 8 and (c <= 8 or c >= size - 8):  # format info + dark module
        return True
    if c == 8 and (r <= 8 or r >= size - 8):
        return True
    return False


def read_format(matrix):
    """Recover (ec_level, mask) from the first format-information copy."""
    size = len(matrix)
    bits = 0
    for i in range(15):
        if i < 6:
            cell = matrix[i][8]
        elif i < 8:
            cell = matrix[i + 1][8]
        else:
            cell = matrix[size - 15 + i][8]
        bits |= int(bool(cell)) << i
    data = bits ^ 0x5412
    # The BCH code must be self-consistent: re-encoding the top 5 bits agrees.
    if q._bch_format_bits(data >> 10) != bits:
        raise AssertionError("format information failed its BCH check")
    return (data >> 13) & 0b11, (data >> 10) & 0b111


def read_codewords(matrix, mask):
    size = len(matrix)
    version = (size - 17) // 4
    mask_fn = q._MASKS[mask]
    bits = []
    row, inc, col = size - 1, -1, size - 1
    while col > 0:
        if col == 6:
            col -= 1
        while True:
            for c in (col, col - 1):
                if not is_function_module(row, c, size, version):
                    dark = bool(matrix[row][c])
                    if mask_fn(row, c):
                        dark = not dark
                    bits.append(int(dark))
            row += inc
            if row < 0 or row >= size:
                row -= inc
                inc = -inc
                break
        col -= 2
    return [
        int("".join(str(b) for b in bits[i : i + 8]), 2)
        for i in range(0, len(bits) - 7, 8)
    ]


def decode(matrix):
    """Matrix -> text. Raises if anything about the symbol is malformed."""
    size = len(matrix)
    version = (size - 17) // 4
    ec_level, mask = read_format(matrix)
    assert ec_level == 0b01, "expected error-correction level L"
    total, ec_count = q._VERSIONS[version]
    codewords = read_codewords(matrix, mask)[:total]
    assert len(codewords) == total, "wrong codeword count for version %d" % version

    # A scanner rejects the symbol unless every syndrome is zero.
    for i in range(ec_count):
        syndrome = 0
        for coefficient in codewords:
            syndrome = q._gf_mul(syndrome, q._EXP[i]) ^ coefficient
        assert syndrome == 0, "non-zero Reed-Solomon syndrome %d" % i

    stream = []
    for cw in codewords[: total - ec_count]:
        stream.extend((cw >> s) & 1 for s in range(7, -1, -1))
    pos = 0

    def take(n):
        nonlocal pos
        value = 0
        for bit in stream[pos : pos + n]:
            value = (value << 1) | bit
        pos += n
        return value

    mode = take(4)
    if mode == 0b0010:
        count = take(9)
        out = []
        for _ in range(count // 2):
            pair = take(11)
            out.append(q.ALNUM[pair // 45])
            out.append(q.ALNUM[pair % 45])
        if count % 2:
            out.append(q.ALNUM[take(6)])
        return "".join(out)
    if mode == 0b0100:
        count = take(8)
        return bytes(take(8) for _ in range(count)).decode("utf-8")
    raise AssertionError("unexpected mode indicator %r" % mode)


# --- tests ------------------------------------------------------------------


class SpecConstants(unittest.TestCase):
    def test_format_information_level_l_mask_0(self):
        self.assertEqual(
            format(q._bch_format_bits((1 << 3) | 0), "015b"), "111011111000100"
        )

    def test_generator_polynomial_of_degree_10(self):
        self.assertEqual(
            [q._LOG[c] for c in q.rs_generator_poly(10)],
            [0, 251, 67, 46, 61, 118, 70, 64, 94, 32, 45],
        )

    def test_finder_and_timing_patterns(self):
        m = q.encode("CAM-0007")
        size = len(m)
        for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
            self.assertTrue(all(m[r0][c0 + i] for i in range(7)))
            self.assertTrue(all(m[r0 + 6][c0 + i] for i in range(7)))
            self.assertFalse(m[r0 + 1][c0 + 1])
            self.assertTrue(m[r0 + 3][c0 + 3])
        for i in range(8, size - 8):
            self.assertEqual(m[6][i], i % 2 == 0)
            self.assertEqual(m[i][6], i % 2 == 0)
        self.assertTrue(m[size - 8][8])


class RoundTrip(unittest.TestCase):
    payloads = [
        "CAM-0007",
        "A",
        "SITE-PARIS/CASE-12/LENS-0042",
        "0123456789" * 2 + "ABCDE",  # 25 chars: exactly fills version 1
        "https://inv.example/a/CAM-0007",  # byte mode (lowercase)
        "Caméra Sony FX6 — boîtier nº3",  # non-ASCII byte mode
        "X" * 114,  # the documented alphanumeric ceiling
    ]

    def test_round_trip(self):
        for payload in self.payloads:
            with self.subTest(payload=payload[:24]):
                self.assertEqual(decode(q.encode(payload)), payload)

    def test_every_mask_round_trips(self):
        for mask in range(8):
            with self.subTest(mask=mask):
                m = q.encode("CAM-0007", mask=mask)
                self.assertEqual(read_format(m)[1], mask)
                self.assertEqual(decode(m), "CAM-0007")

    def test_version_grows_with_payload(self):
        for text, version in (("X" * 25, 1), ("X" * 26, 2), ("X" * 48, 3), ("X" * 78, 4)):
            self.assertEqual((len(q.encode(text)) - 17) // 4, version)

    def test_payload_too_long_is_rejected(self):
        with self.assertRaises(ValueError):
            q.encode("X" * 115)
        with self.assertRaises(ValueError):
            q.encode("")


class Rendering(unittest.TestCase):
    def test_svg_path_covers_every_dark_module(self):
        m = q.encode("CAM-0007")
        self.assertEqual(
            q.to_svg_path(m).count("M"), sum(1 for row in m for cell in row if cell)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
