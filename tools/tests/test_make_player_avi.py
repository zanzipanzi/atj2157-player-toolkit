"""Unit tests for make_player_avi: layout arithmetic and JPEG re-tagging (no ffmpeg needed)."""
import struct

import pytest

import make_player_avi as m

JFIF_FRAME = (b'\xff\xd8' + b'\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' +
              b'\xff\xdb' + b'\x00' * 20 + b'\xff\xd9')
BARE_FRAME = b'\xff\xd8\xff\xdb' + b'\x00' * 20 + b'\xff\xd9'


def make_source(with_audio=True, frames=3):
    strh = struct.pack('<4s4sIHHIIIIIIII4h', b'auds', b'\0\0\0\0', 0, 0, 0, 0, 512, 22050, 0, 4, 0, 0xFFFFFFFF, 512, 0, 0, 0, 0)
    strf = struct.pack('<HHIIHHHH', 0x11, 1, 22050, 11025, 512, 4, 2, 505)
    order = (0, 1, 0, 1, 0, 1) if with_audio else (0, 0, 0)
    return m.Source(160, 128, 15, tuple([JFIF_FRAME] * frames), tuple([b'\x01' * 512] * frames), order,
                    strh if with_audio else None, strf if with_audio else None)


def test_retag_replaces_jfif_with_avi1_keeping_length():
    out = m.retag_jpeg(JFIF_FRAME)
    assert out[6:10] == b'AVI1'
    assert len(out) == len(JFIF_FRAME)
    assert out[2:4] == b'\xff\xe0' and out[4:6] == b'\x00\x10'


def test_retag_inserts_marker_when_missing():
    out = m.retag_jpeg(BARE_FRAME)
    assert out[2:4] == b'\xff\xe0' and out[6:10] == b'AVI1'
    assert out.endswith(b'\xff\xd9')


def test_retag_rejects_non_jpeg():
    with pytest.raises(ValueError):
        m.retag_jpeg(b'RIFF....')


def test_video_audio_layout_puts_avi1_on_byte_342():
    avi = m.build_avi(make_source())
    assert avi[8:12] == b'AVI '
    assert avi.find(b'\xff\xd8') == m.FIRST_FRAME_OFFSET == 336
    assert avi[342:346] == b'AVI1'
    assert struct.unpack_from('<I', avi, 4)[0] == len(avi) - 8


def test_video_only_is_padded_with_junk_to_the_same_offset():
    avi = m.build_avi(make_source(with_audio=False))
    assert b'JUNK' in avi[:336]
    assert avi.find(b'\xff\xd8') == 336 and avi[342:346] == b'AVI1'


def test_first_chunk_is_always_video():
    source = make_source()
    swapped = m.Source(source.width, source.height, source.fps, source.frames, source.audio, (1, 0, 0, 1, 0, 1),
                       source.audio_strh, source.audio_strf)
    assert m.build_avi(swapped)[324:336].endswith(b'00dc' + struct.pack('<I', len(JFIF_FRAME)))


def test_idx1_offsets_count_from_the_movi_fourcc():
    avi = m.build_avi(make_source())
    idx = avi.rfind(b'idx1')
    size = struct.unpack_from('<I', avi, idx + 4)[0]
    first = struct.unpack_from('<4sIII', avi, idx + 8)
    assert size == 16 * 6 and first == (b'00dc', 0x10, 4, len(JFIF_FRAME))


def test_wrong_audio_format_is_refused():
    source = make_source()
    bad = m.Source(source.width, source.height, source.fps, source.frames, source.audio, source.order,
                   source.audio_strh, source.audio_strf[:18])
    with pytest.raises(ValueError):
        m.build_avi(bad)


def test_verify_accepts_built_file_and_rejects_foreign_layout(tmp_path):
    good = tmp_path / 'good.avi'
    good.write_bytes(m.build_avi(make_source()))
    assert m.verify(good) == [] or all('emulation' in p or 'parser' in p for p in m.verify(good))
    foreign = tmp_path / 'foreign.avi'
    foreign.write_bytes(b'RIFF' + b'\0\0\0\0' + b'AVI ' + b'\0' * 400)
    assert any('AVI1' in p for p in m.verify(foreign))


def test_parse_size():
    assert m.parse_size('160x128') == (160, 128)
