# Payloads that run on the chip

Small freestanding Thumb-2 programs that the host loads into chip RAM over ADFU (see
[../docs/technical-notes.md](../docs/technical-notes.md), sections 2 and 4-5).

| File | What it does | Writes to flash? |
|---|---|---|
| `spiid.c` | JEDEC id | no |
| `spistat.c` | JEDEC id + status registers 1-3 | no |
| `spiread.c` | reads flash through the ROM routine, descrambler selectable | no |
| `spiwrite.c` | erase + program one 4 KiB sector with the scrambler; whitelist, dry run, volatile unprotect and restore | **yes** |

Build (Linux or WSL, `arm-none-eabi-gcc` with Thumb-2 support): `make`. This produces `*.bin` files that are
**ignored by git on purpose**; build them yourself.

## Prebuilt read-only payloads

Every release has `spiid.bin`, `spistat.bin` and `spiread.bin` plus `SHA256SUMS`, built by CI from the tagged source
(`.github/workflows/release-assets.yml`). They only **read**, so you can dump your flash without a compiler: download them, check
`sha256sum -c SHA256SUMS`, and use them in place of the files you would build with `make`. `spiwrite.bin` is deliberately
**not** attached: build it yourself (`make`) and read `spiwrite.c` first. The released binaries are byte-identical to the ones that were
run on the tested unit (`spiread` SHA-256 `950b4e70...`, `spistat` `c6e983ce...`). Rebuilding with another compiler version can give
different bytes, so compare the behaviour (or your own build), not just the hash.

`host/` holds the shell drivers that call `actions_dump` from the
[actions_flash](https://github.com/ilyakurdyukov/actions_flash) project:

- `dump_spi.sh`: read-only 4 MiB dump (reloads `spiread.bin` before every chunk).
- `test_free_sector.sh`: validates the write path on an **erased, unused** sector first.
- `apply_font_fix.sh`: the guarded write of the font sectors, with read-back and a rollback mode.

The address whitelist in `spiwrite.c` and the sector lists in `apply_font_fix.sh` are for the tested unit. **Do not reuse
them on another firmware without checking where the data you want to change actually lives.** Read
[../SAFETY.md](../SAFETY.md) first.
