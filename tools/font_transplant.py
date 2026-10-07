#!/usr/bin/env python3
"""Fix full-width Cyrillic in an Actions UNICODE.FON by transplanting glyphs from a donor font.

UNICODE.FON layout (Actions US212A/US215A SDK, bank_c_ui_putstring_sub.c):
  65536 records x 33 bytes, record index = UTF-16 code unit.
  bytes 0..31: 16 rows, each row ceil(width/8) bytes, MSB = leftmost pixel.
  byte 32:     advance width in pixels.

What it changes (everything else is copied byte-for-byte):
  - U+0400..U+04FF (Cyrillic incl. Ukrainian Є І Ї Ґ) and U+02BC: taken from the donor font.
  - Typographic punctuation drawn in a CJK-width cell (– — ‘ ’ “ ” … №): cropped to its ink
    plus one blank column, so it no longer takes a 14-16 px cell.

usage: font_transplant.py <target.FON> <donor.FON> <out.FON> [--preview out.png]
"""
import argparse
import struct
import sys
import zlib

REC = 33
COUNT = 65536
FONT_SIZE = REC * COUNT
COPY_RANGES = [(0x0400, 0x04FF), (0x02BC, 0x02BC)]
CROP_CODEPOINTS = [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2116]
MAX_NARROW_WIDTH = 10
PREVIEW_TEXT = ('Михаил Булгаков — «Дьяволиада». В то время, как все люди скакали… '
                'Їжак, ґанок, Євген, Іван, пʼять, “лапки” ‘так’ № 13')


def unpack(rec):
    """Return (width, rows) where rows are ints with bit (width-1-x) = pixel x."""
    width = rec[32]
    bpr = (width + 7) // 8
    rows = []
    for y in range(16):
        raw = int.from_bytes(rec[y * bpr:(y + 1) * bpr], 'big') if bpr else 0
        rows.append(raw >> (bpr * 8 - width) if bpr else 0)
    return width, rows


def pack(width, rows):
    if not 0 <= width <= 16:
        raise ValueError('width out of range: %d' % width)
    bpr = (width + 7) // 8
    out = bytearray(REC)
    for y, row in enumerate(rows):
        if row >> width:
            raise ValueError('row %d wider than %d px' % (y, width))
        out[y * bpr:(y + 1) * bpr] = (row << (bpr * 8 - width)).to_bytes(bpr, 'big') if bpr else b''
    out[32] = width
    return bytes(out)


def crop(rec):
    """Crop a glyph to its ink columns plus one blank column on each side."""
    width, rows = unpack(rec)
    ink = 0
    for row in rows:
        ink |= row
    if not ink:
        return rec
    cols = [x for x in range(width) if ink >> (width - 1 - x) & 1]
    left, right = cols[0], cols[-1]
    new_w = right - left + 3
    if new_w >= width:
        return rec
    shift = width - 1 - right
    new_rows = [((row >> shift) << 1) & ((1 << new_w) - 1) for row in rows]
    return pack(new_w, new_rows)


def transplant(target, donor):
    out = bytearray(target)
    changed = []
    for lo, hi in COPY_RANGES:
        for cp in range(lo, hi + 1):
            rec = donor[cp * REC:(cp + 1) * REC]
            if not any(rec[:32]):
                continue
            if out[cp * REC:(cp + 1) * REC] != rec:
                out[cp * REC:(cp + 1) * REC] = rec
                changed.append(cp)
    for cp in CROP_CODEPOINTS:
        old = bytes(out[cp * REC:(cp + 1) * REC])
        if old[32] <= MAX_NARROW_WIDTH:
            continue
        new = crop(old)
        if new != old:
            out[cp * REC:(cp + 1) * REC] = new
            changed.append(cp)
    return bytes(out), changed


def render_png(font, text, path, screen_w=128, scale=4):
    lines, line, x = [], [], 0
    for ch in text:
        w = font[ord(ch) * REC + 32]
        if x + w > screen_w:
            lines.append(line)
            line, x = [], 0
        line.append((ord(ch), x))
        x += w
    lines.append(line)
    height = 20 * len(lines)
    px = [[0] * screen_w for _ in range(height)]
    for li, ln in enumerate(lines):
        for cp, x0 in ln:
            w, rows = unpack(font[cp * REC:(cp + 1) * REC])
            for y in range(16):
                for c in range(w):
                    if rows[y] >> (w - 1 - c) & 1 and x0 + c < screen_w:
                        px[li * 20 + 2 + y][x0 + c] = 1
    raw = bytearray()
    for row in px:
        line_bytes = b''.join((b'\x10\x20\x40' if v else b'\xd8\xec\xf7') * scale for v in row)
        for _ in range(scale):
            raw += b'\x00' + line_bytes

    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body))
    ihdr = struct.pack('>IIBBBBB', screen_w * scale, height * scale, 8, 2, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
                + chunk(b'IEND', b''))
    return len(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target')
    ap.add_argument('donor')
    ap.add_argument('out')
    ap.add_argument('--preview', help='write a 128 px wide PNG preview of the result')
    a = ap.parse_args()
    target = open(a.target, 'rb').read()
    donor = open(a.donor, 'rb').read()
    for name, blob in (('target', target), ('donor', donor)):
        if len(blob) != FONT_SIZE:
            sys.exit('%s is %d bytes, expected %d (65536 x 33)' % (name, len(blob), FONT_SIZE))
    result, changed = transplant(target, donor)
    assert len(result) == FONT_SIZE
    open(a.out, 'wb').write(result)
    print('changed %d records: Cyrillic %d, other %s' % (
        len(changed), sum(1 for c in changed if 0x400 <= c <= 0x4FF),
        ['U+%04X' % c for c in changed if not 0x400 <= c <= 0x4FF]))
    if a.preview:
        print('preview lines (before -> after): %d -> %d' % (
            render_png(target, PREVIEW_TEXT, a.preview.replace('.png', '_before.png')),
            render_png(result, PREVIEW_TEXT, a.preview)))


if __name__ == '__main__':
    main()
