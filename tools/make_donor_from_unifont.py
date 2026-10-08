#!/usr/bin/env python3
"""Build a free donor font from GNU Unifont, so that no vendor / SDK font is needed.

fnt_patch.py, fnt_add_ukr.py and font_transplant.py take Cyrillic glyphs from a "donor" file in the Actions
UNICODE.FON layout: 65536 records of 33 bytes (16 rows of ceil(width/8) bytes, MSB = leftmost pixel, then one
width byte, which is the cursor advance). This tool writes such a file from Unifont's .hex file. Only the
requested ranges are filled (default: the Cyrillic block U+0400..U+04FF and the apostrophe U+02BC); everything
else stays empty, which is all the patch tools need.

Unifont glyphs are 8x16 and always carry blank columns. By default the glyphs are made proportional the same way
the original fonts are: the blank columns are trimmed and one blank column is left on each side, so narrow letters
(i, l, ...) take little room and a text line holds more letters. --mono keeps the fixed 8 px advance instead.

Unifont is free software (SIL Open Font License 1.1 or GPL 2+ with the font embedding exception); get the
.hex file yourself, see docs/where-to-get.md. This repository does not contain it.

usage: make_donor_from_unifont.py unifont_all-X.hex[.gz] out_UNICODE.FON [--mono] [--preview out.png]
"""
import argparse
import gzip
import sys
from pathlib import Path

from font_transplant import COUNT, FONT_SIZE, REC, pack, render_png

DEFAULT_RANGES = ((0x02BC, 0x02BC), (0x0400, 0x04FF))
BLANK_WIDTH = 4                       # advance of a glyph without any ink
PREVIEW_CYRILLIC = 'Михаил Булгаков - Дьяволиада. Їжак, ґанок, Євген, Іван, пʼять, щоденник, чашка'


def read_hex(path):
    """Return {code point: (pixel width, [16 row ints])} from a Unifont .hex or .hex.gz file."""
    opener = gzip.open if str(path).endswith('.gz') else open
    glyphs = {}
    with opener(path, 'rt', encoding='ascii') as handle:
        for line in handle:
            code, _, bits = line.strip().partition(':')
            if not bits or len(bits) % 32:
                continue
            per_row = len(bits) // 16
            glyphs[int(code, 16)] = (per_row * 4, [int(bits[i * per_row:(i + 1) * per_row], 16) for i in range(16)])
    return glyphs


def make_record(width, rows, proportional=True):
    """Convert one Unifont glyph to a 33-byte donor record."""
    if not proportional:
        return pack(width, rows)
    ink = 0
    for row in rows:
        ink |= row
    if not ink:
        return pack(BLANK_WIDTH, [0] * 16)
    columns = [x for x in range(width) if ink >> (width - 1 - x) & 1]
    first, last = columns[0], columns[-1]
    new_width = last - first + 3                       # ink plus one blank column on each side
    trimmed = [((row >> (width - 1 - last)) & ((1 << (last - first + 1)) - 1)) << 1 for row in rows]
    return pack(new_width, trimmed)


def build_donor(glyphs, ranges=DEFAULT_RANGES, proportional=True):
    font = bytearray(FONT_SIZE)
    filled = 0
    for lo, hi in ranges:
        for code in range(lo, hi + 1):
            if code in glyphs:
                width, rows = glyphs[code]
                font[code * REC:(code + 1) * REC] = make_record(width, rows, proportional)
                filled += 1
    return bytes(font), filled


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('hexfile', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--mono', action='store_true', help='keep the fixed 8 px advance of Unifont')
    ap.add_argument('--preview', help='write a PNG preview of a Cyrillic sample (128 px wide screen)')
    args = ap.parse_args(argv)
    glyphs = read_hex(args.hexfile)
    font, filled = build_donor(glyphs, proportional=not args.mono)
    assert len(font) == REC * COUNT
    args.out.write_bytes(font)
    print('wrote %s: %d glyphs filled (%s)' % (args.out, filled, 'fixed 8 px' if args.mono else 'proportional'))
    if args.preview:
        lines = render_png(font, PREVIEW_CYRILLIC, args.preview)
        print('preview: %s (%d lines)' % (args.preview, lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
