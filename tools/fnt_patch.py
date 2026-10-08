#!/usr/bin/env python3
"""Patch NEW_M.FNT (vendor font of this ATJ2157 player) with narrow Cyrillic from a donor UNICODE.FON.

NEW_M.FNT layout (reversed 2026-10-07 from this unit's dump):
  header 0x2810 bytes ("FNT\\x05", sparse index - not needed here), then 33-byte glyph records
  sorted by Unicode code point (only code points present in the font). Record = 32 bytes of
  16 rows (ceil(w/8) bytes each, MSB = left) + 1 width byte.
  Verified by rendering: record 222 = U+0401 'Ё', 223..254 = U+0410..U+042F, 255..286 =
  U+0430..U+044F, 287 = U+0451 'ё', 288 = U+2014 '—', then ‖ ‘ ’ “ ” … ‰ ...

The patch replaces those 66 Cyrillic records in place (same size, same order) with the donor's
records for the same code points, and crops the CJK-width quote/dash records that follow.

usage: fnt_patch.py <NEW_M.FNT> <donor UNICODE.FON> <out.FNT>
"""
import sys

REC = 33
DATA = 0x2810
CYRILLIC = [(222, 0x0401)] + [(223 + i, 0x0410 + i) for i in range(32)] + \
           [(255 + i, 0x0430 + i) for i in range(32)] + [(287, 0x0451)]
# records right after 'ё': — ‖ ‘ ’ “ ” …  (crop the quotes; keep dashes/ellipsis)
CROP_RECORDS = [290, 291, 292, 293]
EXPECTED_SIZE = 267776


def unpack(rec):
    w = rec[32]
    bpr = (w + 7) // 8
    return w, [int.from_bytes(rec[y * bpr:(y + 1) * bpr], 'big') >> (bpr * 8 - w) if bpr else 0
               for y in range(16)]


def pack(w, rows):
    bpr = (w + 7) // 8
    out = bytearray(REC)
    for y, r in enumerate(rows):
        out[y * bpr:(y + 1) * bpr] = (r << (bpr * 8 - w)).to_bytes(bpr, 'big')
    out[32] = w
    return bytes(out)


def crop(rec):
    w, rows = unpack(rec)
    ink = 0
    for r in rows:
        ink |= r
    if not ink:
        return rec
    cols = [x for x in range(w) if ink >> (w - 1 - x) & 1]
    new_w = cols[-1] - cols[0] + 3
    if new_w >= w:
        return rec
    shift = w - 1 - cols[-1]
    return pack(new_w, [((r >> shift) << 1) & ((1 << new_w) - 1) for r in rows])


def main():
    if sys.argv[1:2] in (['-h'], ['--help']):
        print(__doc__)
        return
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    fnt = bytearray(open(sys.argv[1], 'rb').read())
    donor = open(sys.argv[2], 'rb').read()
    if len(fnt) != EXPECTED_SIZE or fnt[:4] != b'FNT\x05':
        sys.exit('unexpected NEW_M.FNT (size %d, magic %r)' % (len(fnt), bytes(fnt[:4])))
    if len(donor) != 65536 * REC:
        sys.exit('donor must be a 65536 x 33 UNICODE.FON')
    for idx, cp in CYRILLIC:
        old = fnt[DATA + idx * REC:DATA + (idx + 1) * REC]
        if old[32] != 14:
            sys.exit('record %d (U+%04X) has width %d, expected the vendor 14 - layout mismatch' % (idx, cp, old[32]))
        fnt[DATA + idx * REC:DATA + (idx + 1) * REC] = donor[cp * REC:(cp + 1) * REC]
    for idx in CROP_RECORDS:
        o = DATA + idx * REC
        fnt[o:o + REC] = crop(bytes(fnt[o:o + REC]))
    assert len(fnt) == EXPECTED_SIZE
    open(sys.argv[3], 'wb').write(fnt)
    print('patched %d Cyrillic records, cropped %d punctuation records' % (len(CYRILLIC), len(CROP_RECORDS)))


if __name__ == '__main__':
    main()
