#!/usr/bin/env python3
"""Run the player's own RIFF/AVI/AMV header parser (MMM_VP.AL, function 0x120878) on a video file.

The firmware module is real Thumb-2 code; Unicorn only provides the CPU. The three file callbacks the
module expects from its host (read, seek, tell) are implemented here against a normal file. Nothing
is guessed about the parser: whatever it returns for the file is what the player's code returns.

Also repeats the extra layout test that the module's open function (0x120000) applies to AVI files:
bytes 342..345 of the file must be "AVI1" (APP0 identifier of the first JPEG frame).

usage: mmm_vp_walker_emu.py <video file> [--al path/to/MMM_VP.AL]   (or set MMM_VP_AL)
exit code 0 = parser accepts the file and (for AVI) the AVI1 test passes
"""
import argparse
import os
import struct
import sys
from pathlib import Path

from unicorn import (UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc, UcError)
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP

# The vendor module is NOT part of this repository: extract it from your own player's firmware
# (tools/lfi_tool.py extract) and point MMM_VP_AL at it, or pass --al.
DEFAULT_AL = Path(os.environ.get('MMM_VP_AL', 'MMM_VP.AL'))
CODE_FILE_OFFSET = 0x1000          # first section of the .AL image (header word 2)
CODE_BASE = 0x120000               # load address (header word 4)
CODE_SIZE = 0x3000
WALKER = 0x120878                  # AVI/AMV header walker (returns 0 when it reached the "movi" list)
HOOK_BASE = 0x300000
READ_HOOK, SEEK_HOOK, TELL_HOOK, DONE_HOOK = (HOOK_BASE + 0x10 * i for i in range(4))
STACK_TOP = 0x20F000
HANDLE, CTX = 0x208000, 0x209000

ERRORS = {0: 'ok: reached LIST movi', 0xFFFFFFFF: 'no handle (-1)', 0xFFFFFFFE: 'bad RIFF form type (-2)',
          0xFFFFFFFD: 'avih/amvh header short (-3)'}


class FileCallbacks:
    """Implements the module's host interface: read(H, buf, n), seek(H, off, whence), tell(H)."""

    def __init__(self, data):
        self.data, self.pos = data, 0

    def read(self, uc, buf, n):
        chunk = self.data[self.pos:self.pos + n]
        uc.mem_write(buf, chunk)
        self.pos += len(chunk)
        return len(chunk)

    def seek(self, off, whence):
        off = struct.unpack('<i', struct.pack('<I', off & 0xFFFFFFFF))[0]
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else len(self.data) + off
        self.pos = max(0, min(self.pos, len(self.data)))
        return 0

    def tell(self):
        return self.pos


def run_walker(data, al_path):
    image = Path(al_path).read_bytes()[CODE_FILE_OFFSET:CODE_FILE_OFFSET + CODE_SIZE]
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.ctl_set_cpu_model(__import__('unicorn.arm_const', fromlist=['x']).UC_CPU_ARM_CORTEX_M4)
    uc.mem_map(CODE_BASE, 0x4000)
    uc.mem_write(CODE_BASE, image)
    uc.mem_map(0x200000, 0x20000)
    uc.mem_map(HOOK_BASE, 0x1000)
    for addr in (READ_HOOK, SEEK_HOOK, TELL_HOOK, DONE_HOOK):
        uc.mem_write(addr, b'\x70\x47')                      # bx lr, never really executed
    uc.mem_write(HANDLE, struct.pack('<III', READ_HOOK | 1, SEEK_HOOK | 1, TELL_HOOK | 1))
    uc.mem_write(CTX, struct.pack('<I', HANDLE) + b'\0' * 0x1FC)

    host = FileCallbacks(data)

    def on_code(uc_, address, _size, _user):
        regs = [uc_.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        if address == READ_HOOK:
            ret = host.read(uc_, regs[1], regs[2])
        elif address == SEEK_HOOK:
            ret = host.seek(regs[1], regs[2])
        elif address == TELL_HOOK:
            ret = host.tell()
        elif address == DONE_HOOK:
            uc_.emu_stop()
            return
        else:
            return
        uc_.reg_write(UC_ARM_REG_R0, ret)
        uc_.reg_write(UC_ARM_REG_PC, uc_.reg_read(UC_ARM_REG_LR))   # keep the Thumb bit

    uc.hook_add(UC_HOOK_CODE, on_code, begin=HOOK_BASE, end=HOOK_BASE + 0x100)
    uc.reg_write(UC_ARM_REG_R0, CTX)
    uc.reg_write(UC_ARM_REG_SP, STACK_TOP)
    uc.reg_write(UC_ARM_REG_LR, DONE_HOOK | 1)
    try:
        uc.emu_start(WALKER | 1, DONE_HOOK, timeout=5_000_000, count=2_000_000)
    except UcError as exc:
        return None, b'', host.pos, str(exc)
    return uc.reg_read(UC_ARM_REG_R0), bytes(uc.mem_read(CTX, 0x100)), host.pos, ''


def avi1_layout_test(data):
    """The extra test in the module's open function: first 512 bytes, 'AVI ' form, then 'AVI1' at 342."""
    head = data[:512]
    if head[8:12] != b'AVI ':
        return None
    return head[342:346] == b'AVI1'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--al', default=str(DEFAULT_AL))
    args = ap.parse_args(argv)
    data = Path(args.video).read_bytes()
    form = data[8:12]
    status, ctx, consumed, error = run_walker(data, args.al)
    print('file      : %s (%d bytes), RIFF form type %r' % (args.video, len(data), form))
    if status is None:
        print('walker    : emulation failed: %s' % error)
        return 2
    print('walker    : r0 = %#x -> %s (read %d header bytes)' % (status, ERRORS.get(status, 'error'), consumed))
    words = struct.unpack_from('<8I', ctx, 0)
    movi_start, movi_end = struct.unpack_from('<I', ctx, 0x14)[0], struct.unpack_from('<I', ctx, 4)[0]
    print('ctx       : movi data starts at %d, ends at %d' % (movi_start, movi_end) if status == 0 else 'ctx       : %s' % [hex(x) for x in words])
    ok = status == 0
    if form == b'AVI ':
        layout = avi1_layout_test(data)
        first_soi = data.find(b'\xff\xd8')
        print('AVI1 test : bytes 342..345 = %r -> %s (first JPEG SOI at offset %d, must be 336)' %
              (data[342:346], 'PASS' if layout else 'FAIL (player rejects the file silently)', first_soi))
        ok = ok and bool(layout)
    print('verdict   : %s' % ('ACCEPTED by the firmware checks' if ok else 'REJECTED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
