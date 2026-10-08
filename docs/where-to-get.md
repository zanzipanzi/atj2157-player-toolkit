# Where to get everything you need

This repository contains **no firmware, no vendor code and no fonts**. Everything below is either free software you
install yourself, or something you take from **your own player**. Other languages: [Українська](where-to-get.uk.md),
[Русский](where-to-get.ru.md). Read [SAFETY.md](../SAFETY.md) before you write anything to a player.

| You need | For | Where it comes from |
|---|---|---|
| Python 3.10+ | all `tools/` | https://www.python.org/downloads/ |
| `ffmpeg` | video converter | https://ffmpeg.org/download.html (Windows: `winget install Gyan.FFmpeg`, Debian/Ubuntu: `apt install ffmpeg`) |
| `actions_dump` + `adfus.bin` | talking to the chip over USB | https://github.com/ilyakurdyukov/actions_flash (build it yourself, see below) |
| `arm-none-eabi-gcc` | building `payload/` | `apt install gcc-arm-none-eabi` or https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads |
| a Linux host with USB | everything that touches the chip | `actions_dump` is a Linux tool (libusb): https://libusb.info/ |
| your firmware dump | `lfi_tool.py`, font patches | you read it from **your** player (below) |
| a donor font | Cyrillic / Ukrainian font patch | build a free one from GNU Unifont (recommended), or see the options below |
| `MMM_VP.AL` | only the optional emulator check | extracted from **your** firmware dump (below) |

## 1. `actions_dump` and `adfus.bin`

```
git clone https://github.com/ilyakurdyukov/actions_flash
cd actions_flash && make                  # builds actions_dump (needs the libusb-1.0 development package)
cd payload_arm && make NAME=adfus         # builds adfus.bin for the ATJ2157 (needs arm-none-eabi-gcc)
```

`adfus.bin` is built from open source, so there is nothing to download. For the ATJ2157 it must be loaded at
`0x118000` (see the project's README). Run `actions_dump` from this checkout; the shell drivers in
[`payload/host/`](../payload/host) expect it in the current directory.

## 2. Your own firmware dump

1. Put the player into ADFU mode (hardware key, see [technical notes, section 1](technical-notes.md)) and check the chip with
   `adfu_info`.
2. Build the payloads (`make -C payload`), copy `payload/*.bin` and `payload/host/*.sh` into your `actions_flash`
   checkout (the scripts call `./actions_dump` and load `spiread.bin` from the current directory), start `adfus` and read the
   flash twice, raw and descrambled. The script only **reads** ([technical notes, section 4](technical-notes.md)):

   ```
   sudo ./actions_dump chip 2157 simple_switch 0x118000 adfus.bin
   SIZE=4194304 F68=0 OUT=dump_raw.bin   ./dump_spi.sh      # as stored on the flash
   SIZE=4194304 F68=1 OUT=dump_plain.bin ./dump_spi.sh      # descrambled by the controller
   ```
3. Check the descrambled image: `python tools/lfi_tool.py validate dump_plain.bin` must report every checksum `OK`.
4. Keep both dumps. They are your backup and your rollback source. **Never publish them.**

## 3. A donor font (only for the Cyrillic / Ukrainian patch)

The patch tools copy Cyrillic glyphs from a "donor" font file (65536 records of 33 bytes, the Actions `UNICODE.FON`
layout). Three ways to get one, best first:

**a) Build a free donor from GNU Unifont (recommended: nothing proprietary involved).**
Unifont is free software (SIL Open Font License 1.1 or GPL 2+ with the font embedding exception) and covers the whole
Cyrillic block including `Є І Ї Ґ`.

```
curl -LO https://ftp.gnu.org/gnu/unifont/unifont-18.0.01/unifont_all-18.0.01.hex.gz   # newer versions: https://ftp.gnu.org/gnu/unifont/
python tools/make_donor_from_unifont.py unifont_all-18.0.01.hex.gz donor.FON --preview preview.png
python tools/fnt_patch.py   NEW_M.FNT      donor.FON NEW_M_ru.FNT      # narrow Russian letters
python tools/fnt_add_ukr.py NEW_M_ru.FNT   donor.FON NEW_M_uk.FNT      # add Є І Ї Ґ
```

The letters are 8x16 and a bit wider and rounder than the original Actions font; the default makes them proportional (blank
columns trimmed). `--mono` keeps a fixed 8 px advance. The preview PNG only shows Cyrillic (spaces and punctuation come from
the player's own font, so words look glued in this preview).

**b) The stock Actions SDK font.** The `UNICODE.FON` of the Actions SDK is what the AGPTEK A02 firmware ships too; we checked
that both files are byte-identical (2 162 688 bytes, SHA-256
`4ebc2bed57ac29ab145c11455d4a5ae67a4bce7aae07cfd14676b4ffbadb1c85`). It is available in a public third-party repository
that contains Actions' SDK sources:
https://github.com/malos17713/US212A_ATJ2127/tree/master/case/fwpkg/font (raw file:
`https://raw.githubusercontent.com/malos17713/US212A_ATJ2127/master/case/fwpkg/font/UNICODE.FON`).
**We do not host or endorse that repository**; its legal status is not ours to judge, so check what is allowed where you live,
or prefer option (a). Verify the download with `sha256sum UNICODE.FON`.

**c) From another Actions player's firmware.** Extract `UNICODE.FON` from that player's own firmware dump with
`python tools/lfi_tool.py extract dump_plain.bin out/`. The AGPTEK A02 (also an ATJ2157) is documented, with tooling that
downloads its official update and verifies it by hash, in https://github.com/TheWirelessPhoenix/a02-os (see its
`docs/FLASH-INSTALL.md`).

## 4. `MMM_VP.AL` (optional)

Only `tools/mmm_vp_walker_emu.py` (and the extra check inside `make_player_avi.py`) needs the player's video module. Take it from
**your** dump and point the tool at it:

```
python tools/lfi_tool.py extract dump_plain.bin out/
export MMM_VP_AL=out/MMM_VP.AL        # Windows PowerShell: $env:MMM_VP_AL = "out\MMM_VP.AL"
pip install -r requirements.txt       # installs unicorn (the CPU emulator) and pytest
python tools/make_player_avi.py movie.mp4 for_player.avi
```

Without it the converter still works and says that the firmware-parser check was skipped.

## 5. Related projects worth knowing

- [actions_flash](https://github.com/ilyakurdyukov/actions_flash): `actions_dump`, the ADFU command set, `fwhelper` for LFI images.
- [a02-os](https://github.com/TheWirelessPhoenix/a02-os) (MIT): an open replacement OS for the AGPTEK A02 (ATJ2157) with documented flash
  procedures; useful if your player is an A02.
- [Rockbox `atjboottool`](https://github.com/Rockbox/rockbox/tree/master/utils/atj2137/atjboottool): decrypts `UPGRADE.HEX` /
  `.FWU` update files of ATJ213x/ATJ2127 players.

Never upload firmware, dumps or fonts taken from a device to this repository or to an issue. Hashes, offsets and short hex
excerpts are enough to describe a finding.
