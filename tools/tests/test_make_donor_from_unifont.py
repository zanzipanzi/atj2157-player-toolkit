"""Unit tests for make_donor_from_unifont (synthetic Unifont data, no download needed)."""
import gzip

import make_donor_from_unifont as m

REC = 33


def hexrows(rows):
    return ''.join('%02X' % r for r in rows)


# 8x16 glyphs: GHE (U+0413 style bar with ink in columns 1..6), a narrow letter with ink only in column 3
BAR = [0] * 6 + [0b01111110] + [0b01000000] * 7 + [0, 0]
NARROW = [0] * 4 + [0b00010000] * 10 + [0, 0]
SPACE = [0] * 16
HEX = '\n'.join(['0433:%s' % hexrows(BAR), '0456:%s' % hexrows(NARROW), '0420:%s' % hexrows(SPACE),
                 '4E00:%s' % ('FF' * 32)]) + '\n'


def parse(tmp_path, gz=False):
    path = tmp_path / ('u.hex.gz' if gz else 'u.hex')
    if gz:
        with gzip.open(path, 'wt', encoding='ascii') as fh:
            fh.write(HEX)
    else:
        path.write_text(HEX, encoding='ascii')
    return m.read_hex(path)


def test_read_hex_plain_and_gz(tmp_path):
    for gz in (False, True):
        glyphs = parse(tmp_path, gz)
        assert glyphs[0x433][0] == 8 and glyphs[0x433][1][6] == 0b01111110
        assert glyphs[0x4E00][0] == 16                 # 64 hex digits per glyph = 16 px wide


def test_proportional_trims_blank_columns(tmp_path):
    glyphs = parse(tmp_path)
    bar = m.make_record(*glyphs[0x433])
    assert bar[32] == 8                                 # 6 ink columns + 1 blank each side
    assert bar[6] == 0b01111110 and bar[7] == 0b01000000
    narrow = m.make_record(*glyphs[0x456])
    assert narrow[32] == 3                              # 1 ink column + 2 blanks
    assert narrow[4] == 0b01000000                      # ink is in the middle of a 3 px cell


def test_mono_keeps_eight_pixels(tmp_path):
    glyphs = parse(tmp_path)
    assert m.make_record(*glyphs[0x456], proportional=False)[32] == 8


def test_blank_glyph_gets_a_space_width(tmp_path):
    rec = m.make_record(*parse(tmp_path)[0x420])
    assert rec[32] == m.BLANK_WIDTH and not any(rec[:32])


def test_build_donor_fills_only_requested_ranges(tmp_path):
    font, filled = m.build_donor(parse(tmp_path))
    assert len(font) == 65536 * REC
    assert filled == 3                                  # 0433, 0456, 0420 are inside U+0400..U+04FF
    assert not any(font[0x4E00 * REC:(0x4E00 + 1) * REC])
    assert font[0x433 * REC + 32] == 8


def test_cli_writes_a_donor(tmp_path, capsys):
    (tmp_path / 'u.hex').write_text(HEX, encoding='ascii')
    out = tmp_path / 'donor.FON'
    assert m.main([str(tmp_path / 'u.hex'), str(out)]) == 0
    assert out.stat().st_size == 65536 * REC
    assert 'glyphs filled' in capsys.readouterr().out
