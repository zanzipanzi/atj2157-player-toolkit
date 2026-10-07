#!/usr/bin/env python3
"""Convert any video into a file the Actions ATJ2157 "nano clone" player's firmware accepts.

Why this exists: the player's video module (MMM_VP.AL) only knows MJPEG video in two containers, and
for AVI it applies a hard layout test (see mmm_vp_walker_emu.py): bytes 342..345 of the file must be
"AVI1", i.e. the first JPEG frame must start at byte 336 and carry an "AVI1" APP0 marker. ffmpeg's own
AVI muxer never satisfies that (4 KiB JUNK blocks, JFIF markers), so ordinary AVI files are rejected
silently. This script lets ffmpeg do the encoding and then re-muxes the streams into the exact layout.

  --format avi  (default)  MJPEG + IMA-ADPCM in a minimal AVI, JPEG frames re-tagged JFIF -> AVI1
  --format amv             ffmpeg's native AMV muxer (the format family these players were built for)

Everything is checked at the end by running the player's own header parser (mmm_vp_walker_emu.py, needs
the "unicorn" package) when available. NOT tested on a real player: the check is the firmware's code,
not the hardware decoder.

usage: make_player_avi.py input.mp4 output.avi [--size 160x128] [--fps 15] [--quality 5]
                          [--audio-rate 22050] [--stereo] [--no-audio] [--format avi|amv]
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

FIRST_FRAME_OFFSET = 336          # SOI of frame 0 must sit here so that "AVI1" lands on byte 342
MAX_AUDIO_CHUNK = 2560            # firmware message: "AMV_audio pkt too long!"
parser_ran = False                # set by emulate() once the firmware's own parser has been run
AVIF_HASINDEX = 0x10
AVIIF_KEYFRAME = 0x10


@dataclass(frozen=True)
class Node:
    cid: bytes
    list_type: bytes | None
    body_start: int
    body_end: int


@dataclass(frozen=True)
class Source:
    width: int
    height: int
    fps: int
    frames: tuple[bytes, ...]
    audio: tuple[bytes, ...]
    order: tuple[int, ...]            # 0 = next video frame, 1 = next audio block, in file order
    audio_strh: bytes | None
    audio_strf: bytes | None


def u32(buf: bytes, pos: int) -> int:
    return struct.unpack_from('<I', buf, pos)[0]


def iter_nodes(buf: bytes, start: int, end: int) -> Iterator[Node]:
    pos = start
    while pos + 8 <= end:
        cid, size = buf[pos:pos + 4], u32(buf, pos + 4)
        if cid in (b'RIFF', b'LIST'):
            yield Node(cid, buf[pos + 8:pos + 12], pos + 12, min(end, pos + 8 + size))
        else:
            yield Node(cid, None, pos + 8, min(end, pos + 8 + size))
        pos += 8 + size + (size & 1)


def chunk(cid: bytes, payload: bytes) -> bytes:
    return cid + struct.pack('<I', len(payload)) + payload + (b'\0' if len(payload) & 1 else b'')


def lst(kind: bytes, payload: bytes) -> bytes:
    return b'LIST' + struct.pack('<I', 4 + len(payload)) + kind + payload


def run_ffmpeg(ffmpeg: str, src: Path, dst: Path, args: argparse.Namespace) -> None:
    width, height = args.size
    video_filter = (f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                    f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={args.fps},format=yuvj420p')
    cmd = [ffmpeg, '-v', 'error', '-y', '-i', str(src), '-vf', video_filter,
           '-c:v', 'mjpeg', '-q:v', str(args.quality), '-pix_fmt', 'yuvj420p']
    if args.no_audio:
        cmd += ['-an']
    else:
        cmd += ['-c:a', 'adpcm_ima_wav', '-ar', str(args.audio_rate), '-ac', '2' if args.stereo else '1']
    subprocess.run(cmd + ['-f', 'avi', str(dst)], check=True)


def read_streams(avi: bytes) -> Source:
    """Pull the strh/strf pair of each stream and the raw frame/audio chunks out of an ffmpeg AVI."""
    top = next(iter_nodes(avi, 0, len(avi)))
    frames, audio, order = [], [], []
    audio_strh = audio_strf = None
    width = height = fps = 0
    for node in iter_nodes(avi, top.body_start, top.body_end):
        if node.list_type == b'hdrl':
            for sub in iter_nodes(avi, node.body_start, node.body_end):
                if sub.cid == b'avih':
                    width, height = struct.unpack_from('<II', avi, sub.body_start + 32)
                if sub.list_type == b'strl':
                    strh, strf = stream_headers(avi, sub)
                    if strh[:4] == b'vids':
                        fps = round(u32(strh, 24) / max(1, u32(strh, 20)))
                    elif strh[:4] == b'auds':
                        audio_strh, audio_strf = strh, strf
        elif node.list_type == b'movi':
            for item in iter_nodes(avi, node.body_start, node.body_end):
                kind = item.cid[2:]
                if kind == b'dc':
                    frames.append(avi[item.body_start:item.body_end])
                    order.append(0)
                elif kind == b'wb':
                    audio.append(avi[item.body_start:item.body_end])
                    order.append(1)
    return Source(width, height, fps, tuple(frames), tuple(audio), tuple(order), audio_strh, audio_strf)


def stream_headers(avi: bytes, strl: Node) -> tuple[bytes, bytes]:
    found = {item.cid: avi[item.body_start:item.body_end] for item in iter_nodes(avi, strl.body_start, strl.body_end)}
    return found[b'strh'], found[b'strf']


def retag_jpeg(frame: bytes) -> bytes:
    """JFIF APP0 -> AVI1 APP0 (same 16-byte segment), or insert one when the frame has no APP0."""
    if frame[:2] != b'\xff\xd8':
        raise ValueError('frame does not start with a JPEG SOI marker')
    app0 = b'\xff\xe0\x00\x10AVI1' + b'\0' * 10      # marker, length 16, "AVI1", polarity 0, reserved
    if frame[2:4] == b'\xff\xe0':
        length = struct.unpack_from('>H', frame, 4)[0]
        return frame[:2] + app0 + frame[4 + length:]
    return frame[:2] + app0 + frame[2:]


def avih(source: Source, streams: int) -> bytes:
    micro = round(1_000_000 / source.fps)
    biggest = max(len(f) for f in source.frames)
    return struct.pack('<14I', micro, 0, 0, AVIF_HASINDEX, len(source.frames), 0, streams, biggest,
                       source.width, source.height, 0, 0, 0, 0)


def video_strl(source: Source) -> bytes:
    biggest = max(len(f) for f in source.frames)
    strh = struct.pack('<4s4sIHHIIIIIIIIhhhh', b'vids', b'MJPG', 0, 0, 0, 0, 1, source.fps, 0,
                       len(source.frames), biggest, 0xFFFFFFFF, 0, 0, 0, source.width, source.height)
    strf = struct.pack('<IiiHH4sIiiII', 40, source.width, source.height, 1, 24, b'MJPG',
                       source.width * source.height * 3, 0, 0, 0, 0)
    return lst(b'strl', chunk(b'strh', strh) + chunk(b'strf', strf))


def build_avi(source: Source) -> bytes:
    """Assemble the AVI with the exact header layout the firmware test needs."""
    audio_strh, audio_strf = source.audio_strh, source.audio_strf
    has_audio = audio_strh is not None and audio_strf is not None and bool(source.audio)
    if audio_strf is not None and has_audio and len(audio_strf) != 20:
        raise ValueError('audio must be IMA ADPCM (20-byte strf); got %d bytes' % len(audio_strf))
    strls = video_strl(source)
    if audio_strh is not None and audio_strf is not None and has_audio:
        strls += lst(b'strl', chunk(b'strh', audio_strh) + chunk(b'strf', audio_strf))
    hdrl = lst(b'hdrl', chunk(b'avih', avih(source, 2 if has_audio else 1)) + strls)
    junk = padding_junk(12 + len(hdrl))
    entries, body = interleave(source, has_audio)
    movi = lst(b'movi', body)
    idx1 = chunk(b'idx1', b''.join(entries))
    payload = b'AVI ' + hdrl + junk + movi + idx1
    return b'RIFF' + struct.pack('<I', len(payload)) + payload


def padding_junk(before: int) -> bytes:
    """JUNK chunk that moves the first frame to byte 336 when the header is shorter (video-only files)."""
    pad = FIRST_FRAME_OFFSET - (before + 12 + 8)
    if pad < 0 or 0 < pad < 8 or pad & 1:
        if pad == 0:
            return b''
        raise ValueError('header layout cannot be aligned (needs %d padding bytes)' % pad)
    return chunk(b'JUNK', b'\0' * (pad - 8)) if pad else b''


def interleave(source: Source, has_audio: bool) -> tuple[list[bytes], bytes]:
    order = list(source.order) if has_audio else [0] * len(source.frames)
    if has_audio and order and order[0] != 0:               # the first chunk must be a video frame
        order.remove(0)
        order.insert(0, 0)
    vi = ai = 0
    parts, entries, offset = [], [], 4                       # idx1 offsets count from the 'movi' fourcc
    for kind in order:
        if kind == 0:
            cid, data = b'00dc', retag_jpeg(source.frames[vi])
            vi += 1
        else:
            cid, data = b'01wb', source.audio[ai]
            ai += 1
        piece = chunk(cid, data)
        entries.append(cid + struct.pack('<III', AVIIF_KEYFRAME, offset, len(data)))
        parts.append(piece)
        offset += len(piece)
    return entries, b''.join(parts)


def verify(path: Path) -> list[str]:
    """Own checks first, then the firmware's header parser under emulation when available."""
    data = path.read_bytes()
    problems = []
    if data[:4] != b'RIFF' or data[8:12] != b'AVI ':
        problems.append('not a RIFF/AVI file')
    if data[342:346] != b'AVI1':
        problems.append('bytes 342..345 are %r, the firmware needs b"AVI1"' % data[342:346])
    if data.find(b'\xff\xd8') != FIRST_FRAME_OFFSET:
        problems.append('first JPEG frame starts at %d, must be %d' % (data.find(b'\xff\xd8'), FIRST_FRAME_OFFSET))
    if b'JFIF' in data[FIRST_FRAME_OFFSET:FIRST_FRAME_OFFSET + 32]:
        problems.append('first frame still has a JFIF marker')
    for node in iter_nodes(data, 12, len(data)):
        if node.list_type == b'movi':
            biggest = max((n.body_end - n.body_start for n in iter_nodes(data, node.body_start, node.body_end)
                           if n.cid == b'01wb'), default=0)
            if biggest > MAX_AUDIO_CHUNK:
                problems.append('audio block of %d bytes exceeds the firmware limit %d' % (biggest, MAX_AUDIO_CHUNK))
    return problems + emulate(path)


def emulate(path: Path) -> list[str]:
    """Run the firmware's own header parser when its pieces are present; otherwise say so and skip."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mmm_vp_walker_emu as emu
    except ImportError:
        print('note: firmware-parser check skipped (needs mmm_vp_walker_emu.py and "pip install unicorn")', file=sys.stderr)
        return []
    if not Path(emu.DEFAULT_AL).exists():
        print('note: firmware-parser check skipped (MMM_VP.AL not found at %s)' % emu.DEFAULT_AL, file=sys.stderr)
        return []
    global parser_ran
    status, ctx, _, error = emu.run_walker(path.read_bytes(), emu.DEFAULT_AL)
    parser_ran = True
    if status is None:
        return ['firmware parser emulation failed: %s' % error]
    if status != 0:
        return ['firmware parser returned %#x' % status]
    if path.suffix.lower() == '.avi' and struct.unpack_from('<I', ctx, 0x14)[0] == 0:
        return ['firmware parser never found the LIST movi chunk']
    return []


def parse_size(text: str) -> tuple[int, int]:
    width, _, height = text.lower().partition('x')
    return int(width), int(height)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--size', type=parse_size, default=(160, 128), help='frame size, default 160x128 (screen is 128x160)')
    ap.add_argument('--fps', type=int, default=15)
    ap.add_argument('--quality', type=int, default=5, help='ffmpeg mjpeg -q:v, 2 = best ... 31 = worst')
    ap.add_argument('--audio-rate', type=int, default=22050)
    ap.add_argument('--stereo', action='store_true')
    ap.add_argument('--no-audio', action='store_true')
    ap.add_argument('--format', choices=('avi', 'amv'), default='avi')
    ap.add_argument('--ffmpeg', default=shutil.which('ffmpeg') or 'ffmpeg')
    return ap.parse_args(argv)


def convert_amv(args: argparse.Namespace) -> None:
    width, height = args.size
    if height % 16 or args.audio_rate % args.fps:
        raise SystemExit('AMV needs a frame height multiple of 16 and an audio rate divisible by the fps')
    video_filter = (f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                    f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={args.fps}')
    subprocess.run([args.ffmpeg, '-v', 'error', '-y', '-i', str(args.input), '-vf', video_filter,
                    '-c:v', 'amv', '-c:a', 'adpcm_ima_amv', '-ac', '1', '-ar', str(args.audio_rate),
                    '-block_size', str(args.audio_rate // args.fps), '-r', str(args.fps), str(args.output)], check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.size[0] % 16 or args.size[1] % 16:
        print('warning: frame size is not a multiple of 16; the hardware decoder may dislike it', file=sys.stderr)
    if args.format == 'amv':
        convert_amv(args)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp) / 'ffmpeg.avi'
            run_ffmpeg(args.ffmpeg, args.input, temp, args)
            source = read_streams(temp.read_bytes())
        args.output.write_bytes(build_avi(source))
    problems = verify(args.output) if args.format == 'avi' else emulate(args.output)
    for line in problems:
        print('PROBLEM:', line, file=sys.stderr)
    verdict = ('REJECTED by the checks' if problems else
               'passes the firmware checks' if parser_ran else 'passes the layout checks (firmware parser not run)')
    print('%s: %s (%d bytes)' % (args.output, verdict, args.output.stat().st_size))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
