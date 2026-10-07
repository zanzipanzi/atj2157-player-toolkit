#!/usr/bin/env python3
"""Inspect the Actions "LFI" firmware image of an ATJ2157-class player.

LFI layout (verified on an ATJ2157 player with a GD25Q32 SPI NOR, firmware version string "1.101.56"):

  +0x000  magic 55 AA F0 0F, then an ASCII version string
  +0x010  checksum32 of the directory (bytes 0x200..0x1FFF of the LFI)
  +0x1FE  checksum16 of the head (bytes 0x000..0x1FD)
  +0x200  directory, 32-byte entries: 8.3 name (11 bytes), +0x10 offset in 512-byte sectors (from the
          LFI start), +0x14 length, +0x1C checksum32 of the file data
  both checksums are plain sums of 16/32-bit little-endian words, no cryptography

The image must be PLAINTEXT. A raw dump of the flash is scrambled by the controller; read it with the
descrambler enabled (see docs/technical-notes.md, "SPI flash and the scrambler").

usage:
  lfi_tool.py find     <image>                       list offsets of the LFI magic
  lfi_tool.py validate <image> [lfi_offset]          check checksums, list the files
  lfi_tool.py extract  <image> <out_dir> [lfi_offset]  write every file of the directory
"""
import struct
import sys
from pathlib import Path

MAGIC = b'\x55\xaa\xf0\x0f'


def u16(buf, pos):
    return struct.unpack_from('<H', buf, pos)[0]


def u32(buf, pos):
    return struct.unpack_from('<I', buf, pos)[0]


def sum16(buf, start, length):
    return sum(struct.unpack_from('<%dH' % (length // 2), buf, start)) & 0xFFFF


def sum32(buf, start, length):
    return sum(struct.unpack_from('<%dI' % (length // 4), buf, start)) & 0xFFFFFFFF


def find_lfi(data):
    found, pos = [], data.find(MAGIC)
    while pos != -1:
        found.append(pos)
        pos = data.find(MAGIC, pos + 1)
    return found


def entries(data, lfi):
    """Yield (name, absolute offset, length, stored checksum32) for every directory entry."""
    pos = lfi + 0x200
    while pos < lfi + 0x2000 and data[pos]:
        raw = data[pos:pos + 11]
        name = raw[:8].rstrip(b' ').decode('latin1')
        ext = raw[8:11].rstrip(b' ').decode('latin1')
        yield (name + ('.' + ext if ext else ''), lfi + (u32(data, pos + 0x10) << 9), u32(data, pos + 0x14), u32(data, pos + 0x1C))
        pos += 0x20


def validate(data, lfi):
    if data[lfi:lfi + 4] != MAGIC:
        print('no LFI magic at %#x' % lfi)
        return False
    ok = True
    head_stored, head_calc = u16(data, lfi + 0x1FE), sum16(data, lfi, 0x1FE)
    dir_stored, dir_calc = u32(data, lfi + 0x10), sum32(data, lfi + 0x200, 0x1E00)
    print('LFI @ %#x  version %r' % (lfi, data[lfi + 4:lfi + 16].split(b'\0')[0].decode('latin1')))
    print('  head checksum16 stored %04x calculated %04x  %s' % (head_stored, head_calc, 'OK' if head_stored == head_calc else 'BAD'))
    print('  dir  checksum32 stored %08x calculated %08x  %s' % (dir_stored, dir_calc, 'OK' if dir_stored == dir_calc else 'BAD'))
    ok &= head_stored == head_calc and dir_stored == dir_calc
    for name, off, length, stored in entries(data, lfi):
        good = off + length <= len(data) and sum32(data, off, length) == stored
        ok &= good
        print('    %-13s at %#09x  %9d bytes  %s' % (name, off, length, 'OK' if good else 'BAD'))
    return ok


def extract(data, lfi, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, off, length, _ in entries(data, lfi):
        (out / name).write_bytes(data[off:off + length])
        count += 1
    print('wrote %d files to %s' % (count, out))


def main(argv):
    if len(argv) < 2 or argv[0] not in ('find', 'validate', 'extract'):
        print(__doc__)
        return 2
    data = Path(argv[1]).read_bytes()
    if argv[0] == 'find':
        print('LFI magic at:', [hex(x) for x in find_lfi(data)])
        return 0
    rest = argv[2:]
    if argv[0] == 'extract':
        if not rest:
            print(__doc__)
            return 2
        out_dir, rest = rest[0], rest[1:]
    lfi = int(rest[0], 0) if rest else (find_lfi(data) or [0])[0]
    if argv[0] == 'validate':
        return 0 if validate(data, lfi) else 1
    extract(data, lfi, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
