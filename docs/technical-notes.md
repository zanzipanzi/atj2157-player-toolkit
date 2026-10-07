# Technical notes: Actions ATJ2157 "nano clone" players

Everything here was measured on **one** unit (generic MP3/MP4 player, Actions **ATJ2157**, ARM Cortex-M4F,
firmware on a **GD25Q32** 4 MiB SPI NOR, microSD for media, firmware version string `1.101.56`). Other
units with the same chip are likely similar, but nothing below is guaranteed for them. Statements marked
**(unverified)** come from reading code or documentation and were not confirmed on hardware.

Russian version of these notes: [technical-notes.ru.md](technical-notes.ru.md). (The charts below have Russian labels.)

## 1. Identify the device

| Mode | USB id | What you see |
|---|---|---|
| normal | `10d6:1101` | mass storage, `ACTIONS USB DISK FOB 2.0`; `lsusb` may call it "D-Wave 2GB MP4 Player / AK1025" (an old database entry with the same id, **not** a chip identification) |
| ADFU service mode | `10d6:10d6` | Actions firmware-upgrade protocol, no filesystem |

The only reliable chip identification is the ADFU `adfu_info` answer: bytes `00 'CADFUD' 30 51`, where
`0x3051` means ATJ2157 (a similar chip, ATJ2127, answers differently). A web search by label predicted the
wrong chip for this unit, so check before you load any code.

**Entering ADFU.** On the tested unit: slider OFF, hold the **centre button**, plug in USB. Software
`adfu_reboot` (vendor CDB `0xCC`, then `0xCB 0x21`) works from normal mode too. Leaving ADFU: unplug, slider
OFF/ON, hold centre+MENU if needed; a software `reset` from ADFU returned to ADFU. A program that hangs in
service mode can leave the player dead until the battery runs flat, so find the hardware entry key **before**
you run anything that writes.

## 2. ADFU protocol and memory map

USB Mass Storage bulk-only transport with vendor commands. CDB `0xCD` carries a subcommand:

| Subcommand | Meaning |
|---|---|
| `0x13` WRITERAM | write bytes to chip RAM |
| `0x93` READRAM | read RAM |
| `0x20` SWITCH | start the downloaded server stub (`adfus`) at an address |
| `0x21` EXEC | run code at an address (the entry is called as Thumb: address with bit 0 set) |
| `0x22` RETSIZE / `0x23` READRET | size / bytes of the result block the program returned |
| `0x10`, `0x60` | flash access through the vendor flash driver |

The host tool is [`actions_dump`](https://github.com/ilyakurdyukov/actions_flash) from the actions_flash
project; this repository only contains the payload code that runs on the chip.

Addresses used by the payloads in [`payload/`](../payload):

| Region | Address | Use |
|---|---|---|
| adfus (server stub) | `0x118000` | loaded with SWITCH; do **not** SWITCH a running adfus again |
| payload code | `0x11E000` | entry returns a pointer to `{address, size}` of the result |
| ARGS | `0x120000` | input words for the payload |
| RESULT | `0x120010` | `{pointer, size}` |
| DATA | `0x120100` .. `0x124100` | output buffer (16 KiB) |
| SRC | `0x121000` | data to be written (overlaps DATA; the write payload only uses the first 56 bytes of DATA) |

`read_mem2` copies through a helper that lands on `0x11E000`, so a payload must be **reloaded before every
`read_mem2`**. A stale "unexpected status" answer after a failed command is cured by replugging.

![RAM map of the chip](img/chart_sram.png)

Build the payloads with `arm-none-eabi-gcc -march=armv7-m -mthumb` (without the flags the assembler fails with
`invalid constant ... after fixup`, because the default target is ARM, not Thumb-2).

## 3. Boot ROM

The 64 KiB mask ROM sits at address 0 and is **not** readable with plain `read_mem`; `read_mem2` through adfus
can read it. SRAM is `0x100000`..`0x137FFF` (224 KiB). The vector table starts with SP `0x00101B18` and reset
`0x189`. What the disassembly shows (function addresses are ROM addresses):

- `0x2488` main; `0x1B14` boot from SPI NOR; `0x1AB4` SPI init; `0x383C` pin mux; `0x31AC` read JEDEC id;
  `0x2224` read one 512-byte sector (command `0x0B` + DMA); `0x28D8` watchdog feed.
- Boot candidates: SPI offsets `0, 0x1000, 0x10000` (table at `0x5364`), card offsets `0, 0x80, 0x100, 0x200`
  (table at `0x5370`).
- The loader reads 1024 bytes at each candidate offset, first with the descrambler **on**
  (`ROM_CFG+0x68 = 1`), then off, and accepts a block whose byte 2 is `0xA5` (or `0x5A`) and whose checksum is right (MBREC).
  A live SRAM image at `0x101000` was byte-identical to the descrambled flash sector 0.
- **(unverified)** A word read from `0xC0020000` selects between NAND, SPI and card branches; the NAND branch
  was only skimmed (the NAND id read back as zeros, which is why we concluded there is no NAND).

## 4. SPI flash and the scrambler

SPI controller at `0xC00A0000`: CTL `+0x00`, STAT `+0x04`, TXD `+0x08`, RXD `+0x0C`, LEN `+0x10`. Standard
GD25-family opcodes work: `0x9F` JEDEC id (`C8 40 16`), `0xAB` wake, `0x0B` fast read, `0x05/0x35/0x15` status
registers 1-3, `0x06` write enable, `0x20` 4 KiB erase, `0x02` page program (wraps at 256 bytes), `0x50` volatile
write-enable, `0x01` write status.

![Entropy: raw vs descrambled flash](img/chart_entropy.png)

**The flash content is scrambled by the controller.** A raw dump has entropy ~7.91 bits/byte and no readable
strings. Facts that characterise the scrambler:

- 1492 sectors whose plaintext is all zero produce **one** identical raw sector: it is deterministic and does not
  depend on the address.
- The first keystream word of a block takes only 8 values across the dump, but a single XOR pad does not decode
  the image: it depends on the data. A GF(2)-affine fit of the plaintext word from the current and the previous 8 or
  16 ciphertext words was inconsistent for all 32 bits. We did **not** try richer models, and we never reproduced
  the algorithm offline.
![Models of the scrambler that failed](img/chart_models.png)

- So always go through the hardware:
  - **Read:** set the CTL descramble bit `0x1000` (the ROM does this from `ROM_CFG+0x68`, `CTL` mask `0xF000`).
  - **Write:** set the CTL scramble bit `0x2000` around the data bytes of the program command only.
    The scrambler restarts at every command and treats one **512-byte block as one stream**, but a program command
    takes at most 256 bytes. The working trick: send page A (first 256 bytes) normally, then send page B as a
    **512-byte transfer addressed at page B** (A's bytes then B's bytes). The chip's 256-byte page buffer wraps and
    keeps the last 256 bytes, and the scrambler state at that point is the correct continuation.
  - ![Write stream: why the second page is sent as 512 bytes](img/chart_stream.png)
  - Test on a free sector first: writing known plaintext and reading it back descrambled gave 0 differences, and the
    raw bytes equalled the factory raw bytes. Setting only `0x1000` while writing does nothing useful (`0x1000` is the
    read bit).

## 5. Write protection

On the tested unit `SR1 = 0x08` (BP1) and `SR2 = 0x40` (CMP): everything **except the top 128 KiB**
(`0x3E0000`..`0x3FFFFF`) is write protected. The top area holds the settings the firmware writes by itself.
A write to a protected sector is silently ignored by the chip: our first test "passed" on sector `0x3DD000`
because the sector was empty and nothing was written; the only sign was a status-poll counter of 0 for the erase.
Always use an **independent** success signal (read-back, poll counters).

![What the protection covers](img/chart_protection.png)

Unprotect volatilely: `0x50` (volatile write enable) then `0x01 <SR1> <SR2>` **without** `0x06`, so the
non-volatile bits are untouched and a power cycle restores the protection. Verify the registers after the change and
restore them after the write (the payload does both and reports error codes, see `payload/spiwrite.c`).
After ADFU entry `SR1` may read `0x0A` instead of `0x08`: the ROM leaves WEL set.

## 6. The LFI firmware image

![Flash map](img/chart_flash_map.png)

The firmware is a directory of files ("LFI") starting at flash offset `0x11400` and ending at `0x3D8600`
(81 files, ~3.78 MiB). ![Largest files of the firmware](img/chart_lfi_sizes.png)

Format and checksums are documented in the docstring of [`tools/lfi_tool.py`](../tools/lfi_tool.py);
both checksums are plain 16/32-bit sums, so a same-size file can be replaced and the sums recomputed
([`tools/lfi_replace.py`](../tools/lfi_replace.py) prints the 4 KiB sectors that changed).

## 7. Font file NEW_M.FNT

`NEW_M.FNT` (267 776 bytes) has: a 16-byte header (`FNT`, version 5, cell 14x16, record size 33, data offset
`0x2810`, 1024 index entries); an index of 1024 entries of 10 bytes (one per 64 code points: `u16` count of glyphs before
the block, `u64` presence bitmap); 7791 glyph records of 33 bytes sorted by code point; a 417-byte trailer.
Glyph number = `base + popcount(bitmap bits below the code)`. A record is 32 bytes of 16 rows (`ceil(width/8)` bytes per
row, MSB left) plus a width byte, which is the **cursor advance**, not the image width.

On the tested unit all Cyrillic glyphs had width 14 (the width of a CJK character), which is why text looked spaced
out. The fix replaces the 66 records (U+0401, U+0410..U+044F, U+0451) in place with narrow glyphs from another
Actions font (width 5-12, mean 14.00 -> 7.92) and crops four quote glyphs. Ukrainian letters (`Є І Ї Ґ є і ї ґ`) were
missing: they are added by deleting eight Roman numerals `U+2172..U+2179` and rebuilding the sorted array and
index, so the file size does not change and the LFI does not move. Tools: [`tools/fnt_patch.py`](../tools/fnt_patch.py),
[`tools/fnt_add_ukr.py`](../tools/fnt_add_ukr.py). The donor font is **not** included (copyright); supply your own.

![All 66 Russian glyphs before and after](img/chart_glyph_grid.png)

![Glyph width distribution](img/chart_width_hist.png)

![Letters per text line before and after the font fix](img/chart_letters.png)

Changed flash sectors: Russian patch `0xEE000` + `0x11000` (LFI head with the new checksums); Ukrainian
patch `0xEE000`, `0xE9000`, `0xEA000`, `0x11000`. After flashing, a full 4 MiB read-back (raw and descrambled) differed from the
target only in the top settings area; below `0x3E0000` there were 0 differences.

## 8. Safe writing procedure (what `payload/host/apply_font_fix.sh` does)

1. Read the target sectors in both modes and require them to equal your reference dumps, otherwise stop.
2. Dry run: the payload runs every check but sends **no** write command (returns code `0x10`).
3. Ask for a typed confirmation per sector; write data sectors first and the LFI head sector `0x11000` **last**.
4. Read back descrambled and compare with the target; on any mismatch stop and print the rollback command.
5. Rollback writes the **original raw bytes** with the scrambler off (`ROLLBACK=1`). The raw-write path was proven on a
   free sector, but rollback was **never run on the real sectors**.

The payload refuses any address outside a whitelist (`0x11000`, `0xE9000`, `0xEA000`, `0xEE000` in our build) unless
a magic argument is passed, requires 4 KiB alignment and length, bounds every wait loop and feeds the watchdog.
Sector 0 (boot record) is never written.

## 9. Video

The video module is `MMM_VP.AL` inside the LFI (load address `0x120000`, code from file offset `0x1000`). From its
disassembly and from running its own header parser under emulation ([`tools/mmm_vp_walker_emu.py`](../tools/mmm_vp_walker_emu.py)):

- Only two RIFF form types are accepted: `AVI ` and `AMV `. Anything else logs `video format invalid!`.
- Exactly one video decoder (`mjpeg`), one demuxer (`avi`, which also reads AMV) and one audio plugin (`wave`) are
  registered. No H.264, XviD, DivX or MPEG-4, so changing the codec inside an AVI cannot help.
- For AVI there is a hard layout test: after reading the first 512 bytes, bytes **342..345 must be `AVI1`**, otherwise
  the player gives up **silently**. They are the APP0 identifier of the first JPEG frame, which therefore must start at byte
  **336** with an `AVI1` marker. A minimal AVI with a video stream (strf 40 bytes) and an IMA-ADPCM audio stream
  (strf 20 bytes) gives exactly 336: 12 + 12 + 64 + (12+64+48) + (12+64+28) + 12 + 8.
- In our test ffmpeg's default AVI has `JFIF` frames and starts the first frame at byte 9994 (4 KiB `JUNK` blocks, `vprp`,
  `LIST INFO`), so it is rejected. [`tools/make_player_avi.py`](../tools/make_player_avi.py) lets ffmpeg encode MJPEG +
  IMA ADPCM and re-muxes the streams into the exact layout (JFIF re-tagged to AVI1, `idx1` index).
- AMV: ffmpeg's native muxer (`-c:v amv -c:a adpcm_ima_amv -ac 1 -ar 22050 -block_size 1470`, frame height a multiple of
  16, block size = audio rate / fps) produces a header that the firmware parser accepts.
- The picture is scaled to fit the screen with the aspect ratio kept, upscaling capped at 1.7x (from the fit function at `0x1205FC`); the SDK documents a
  128x160 screen (**unverified** for this unit).

**Not verified on a real player:** the hardware JPEG decoder's limits, whether the audio plugin takes IMA-ADPCM as in
WAV or wants the AMV flavour, and how the player treats the zero RIFF/LIST sizes that ffmpeg writes into AMV. The
converter's result is only known to pass the **firmware's own header parser** (run under emulation) and to be a valid AVI
for ffmpeg. Reports from real players are very welcome.

## 10. Credits and references

- [actions_flash](https://github.com/ilyakurdyukov/actions_flash) by Ilya Kurdyukov: the `actions_dump` host tool, ADFU
  command set and `fwhelper` (LFI) that made all of this possible.
- [Rockbox `atjboottool`](https://github.com/Rockbox/rockbox/tree/master/utils/atj2137/atjboottool) for the ATJ boot
  image conventions.
- [US212A_ATJ2127 SDK sources](https://github.com/malos17713/US212A_ATJ2127) for the `UNICODE.FON` layout (the font format
  of this unit's `NEW_M.FNT` is a sparse variant that we reverse engineered).
