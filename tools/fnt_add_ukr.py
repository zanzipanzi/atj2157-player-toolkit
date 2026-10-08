#!/usr/bin/env python3
"""Add Ukrainian letters (Є І Ї Ґ є і ї ґ) to NEW_M.FNT without changing the file size.

NEW_M.FNT index (reversed 2026-10-07, verified on Cyrillic):
  0x10 byte header, then 1024 entries of 10 bytes (one per 64 code points, entry k covers
  U+[k*64 .. k*64+63]): u16 LE base (number of glyph records before this block) + u64 LE bitmap
  (bit i = code k*64+i is present). Glyph record index of a present code = base + popcount(bitmap
  bits below it). Records start at 0x2810, 33 bytes each (32 B bitmap rows, 1 B width), sorted by code.

Adding records would grow the file and shift every later file in the LFI, so instead this removes
8 rarely used code points (small Roman numerals) and puts the 8 Ukrainian letters in their place;
the sorted record array is rebuilt, the index recomputed, the size stays identical.

usage: fnt_add_ukr.py <in.FNT> <donor UNICODE.FON> <out.FNT> [--selftest]
"""
import struct
import sys

REC = 33
HDR = 0x10
NBLK = 1024
DATA = HDR + NBLK * 10          # 0x2810
UKR = [0x0404, 0x0406, 0x0407, 0x0490, 0x0454, 0x0456, 0x0457, 0x0491]
DROP_CANDIDATES = [0x2179, 0x2178, 0x2177, 0x2176, 0x2175, 0x2174, 0x2173, 0x2172, 0x2171, 0x2170]


def parse(fnt):
    codes = []
    for k in range(NBLK):
        base, bm = struct.unpack_from('<HQ', fnt, HDR + k * 10)
        for i in range(64):
            if bm >> i & 1:
                codes.append(k * 64 + i)
    n = len(codes)
    assert DATA + n * REC <= len(fnt), (n, len(fnt))
    recs = {c: bytes(fnt[DATA + j * REC:DATA + (j + 1) * REC]) for j, c in enumerate(codes)}
    # verify bases
    run = 0
    for k in range(NBLK):
        base, bm = struct.unpack_from('<HQ', fnt, HDR + k * 10)
        assert base == run, 'base mismatch at block %d: %d != %d' % (k, base, run)
        run += bin(bm).count('1')
    return recs


def build(head16, recs, trailer=b''):
    codes = sorted(recs)
    out = bytearray(head16)
    run, ci = 0, 0
    for k in range(NBLK):
        bm = 0
        start = run
        while ci < len(codes) and codes[ci] // 64 == k:
            bm |= 1 << (codes[ci] % 64)
            ci += 1
            run += 1
        out += struct.pack('<HQ', start, bm)
    for c in codes:
        out += recs[c]
    return bytes(out) + trailer


def main():
    if sys.argv[1:2] in (['-h'], ['--help']):
        print(__doc__)
        return
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    fnt = open(sys.argv[1], 'rb').read()
    donor = open(sys.argv[2], 'rb').read()
    recs = parse(fnt)
    trailer = fnt[DATA + len(recs) * REC:]      # bytes after the last glyph record, kept verbatim
    print('trailer after glyph records: %d bytes' % len(trailer))
    # self-test: rebuild must be identical
    assert build(fnt[:HDR], recs, trailer) == fnt, 'round-trip rebuild differs - index model wrong'
    print('round-trip rebuild identical; %d glyph records' % len(recs))
    if '--selftest' in sys.argv:
        return
    present_drop = [c for c in DROP_CANDIDATES if c in recs][:8]
    if len(present_drop) < 8:
        sys.exit('not enough droppable code points present: %s' % present_drop)
    for c in UKR:
        if c in recs:
            sys.exit('U+%04X already present' % c)
        rec = donor[c * REC:(c + 1) * REC]
        if not any(rec[:32]) or not 1 <= rec[32] <= 16:
            sys.exit('donor has no glyph for U+%04X' % c)
    for c in present_drop:
        del recs[c]
    for c in UKR:
        recs[c] = donor[c * REC:(c + 1) * REC]
    out = build(fnt[:HDR], recs, trailer)
    assert len(out) == len(fnt), 'size changed'
    open(sys.argv[3], 'wb').write(out)
    print('removed %s' % ['U+%04X' % c for c in present_drop])
    print('added   %s' % ['U+%04X' % c for c in UKR])
    print('wrote %s (%d bytes, same size)' % (sys.argv[3], len(out)))


if __name__ == '__main__':
    main()
