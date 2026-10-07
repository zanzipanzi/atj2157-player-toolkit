#!/usr/bin/env python3
"""Replace one same-size file inside the Actions LFI of a plaintext SPI image and fix checksums.

LFI rules (actions_flash fwhelper/main.c unpack_lfi):
  magic 0x0FF0AA55 at +0; head checksum16 of bytes 0..0x1FD stored at +0x1FE;
  dir checksum32 of bytes 0x200..0x1FFF stored at +0x10;
  dir entries 0x20 bytes from +0x200: name 8.3 (11 bytes), +0x10 offset in 512-byte sectors,
  +0x14 length, +0x1C checksum32 of the file data.

usage: lfi_replace.py <plain_spi.bin> <lfi_offset> <NAME.EXT> <new_file> <out.bin>
Prints the changed 4 KiB erase sectors so a writer only touches those.
"""
import struct
import sys


def sum16(b):
    return sum(struct.unpack_from('<%dH' % (len(b) // 2), b)) & 0xFFFF


def sum32(b):
    return sum(struct.unpack_from('<%dI' % (len(b) // 4), b)) & 0xFFFFFFFF


def name83(name):
    base, _, ext = name.upper().partition('.')
    return (base.ljust(8) + ext.ljust(3)).encode('ascii')


def check(img, lfi):
    h = img[lfi:lfi + 0x2000]
    assert struct.unpack_from('<I', h, 0)[0] == 0x0FF0AA55, 'LFI magic'
    assert sum16(h[:0x1FE]) == struct.unpack_from('<H', h, 0x1FE)[0], 'head checksum16'
    assert sum32(h[0x200:0x2000]) == struct.unpack_from('<I', h, 0x10)[0], 'dir checksum32'
    n = 0
    for e in range(0x200, 0x2000, 0x20):
        if not h[e]:
            break
        off = struct.unpack_from('<I', h, e + 0x10)[0] << 9
        ln = struct.unpack_from('<I', h, e + 0x14)[0]
        assert sum32(img[lfi + off:lfi + off + ln]) == struct.unpack_from('<I', h, e + 0x1C)[0], \
            'file checksum %r' % h[e:e + 11]
        n += 1
    return n


def main():
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    img = bytearray(open(sys.argv[1], 'rb').read())
    lfi = int(sys.argv[2], 0)
    want = name83(sys.argv[3])
    new = open(sys.argv[4], 'rb').read()
    print('original LFI ok, files:', check(img, lfi))
    for e in range(lfi + 0x200, lfi + 0x2000, 0x20):
        if img[e:e + 11] == want:
            break
    else:
        sys.exit('file %s not found in LFI directory' % sys.argv[3])
    off = struct.unpack_from('<I', img, e + 0x10)[0] << 9
    ln = struct.unpack_from('<I', img, e + 0x14)[0]
    if ln != len(new):
        sys.exit('size mismatch: LFI has %d, new file is %d (only same-size replacement supported)' % (ln, len(new)))
    before = bytes(img)
    img[lfi + off:lfi + off + ln] = new
    struct.pack_into('<I', img, e + 0x1C, sum32(new))
    struct.pack_into('<I', img, lfi + 0x10, sum32(bytes(img[lfi + 0x200:lfi + 0x2000])))
    struct.pack_into('<H', img, lfi + 0x1FE, sum16(bytes(img[lfi:lfi + 0x1FE])))
    print('patched LFI ok, files:', check(img, lfi))
    changed = sorted({i // 4096 for i in range(len(img)) if img[i] != before[i]})
    print('changed 4 KiB sectors: %d -> %s' % (len(changed), ', '.join('%#x' % (s * 4096) for s in changed[:8])
                                                + (' ...' if len(changed) > 8 else '')))
    open(sys.argv[5], 'wb').write(img)


if __name__ == '__main__':
    main()
