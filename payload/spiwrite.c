/*
 * spiwrite.c - GUARDED, bounded SPI-NOR 4 KiB sector writer for ATJ2157.
 *
 * Runs after adfus (0x118000) via adfus CMD_ADFU_EXEC at 0x11e000.
 *
 * ARGS @0x120000 (u32):
 *   [0] flash_addr   (MUST be 4 KiB aligned)
 *   [1] len          (MUST be 4096)
 *   [2] bank         (0..2)
 *   [3] scramble     (0/1 -> CFG_F68 / CTL 0x1000, as spiread's F68)
 *   [4] dry_run      (1 = do everything EXCEPT send 0x06/0x20/0x02)
 *   [5] allow_any    (0x414C4C57 overrides the sector whitelist)
 * SRC  @0x121000 : 4096 bytes of PLAINTEXT data (host fills via write_mem).
 *   0x121000..0x121FFF is above ARGS(0x120000) + result(0x120010) + status
 *   DATA(0x120100), below the 0x124000 area and well clear of adfus
 *   (0x118000-0x11BFFF) and the code image (0x11e000-0x11FFFF).
 *
 * Whitelist: only {0x11000, 0xEE000} (the two font-fix sectors) are allowed,
 * unless ARGS[5]==0x414C4C57. This protects MBREC/BREC/LFI head.
 *
 * Sequence (per spec): WREN(0x06) -> sector erase(0x20)+addr -> bounded WIP poll
 * -> for each 256-B NOR page: WREN -> page program(0x02)+addr+data -> bounded
 * WIP poll. The SCRAMBLER (CTL 0x1000) is enabled ONLY around the program DATA
 * bytes (mirroring read, where only the data phase is (de)scrambled; opcode,
 * address, WREN, erase and all RDSR polls run with scrambler OFF so WIP is read
 * raw). GD25Q32 page-program wraps at 256 B, so a 4 KiB sector = 16 pages.
 *
 * TX-SCRAMBLE CAVEAT: that the HW scrambler is symmetric on program TX is a
 * hypothesis (the read de-scramble via CTL 0x1000 is proven; TX direction is
 * NOT proven from vendor code). See write_analysis.md - validate empirically
 * with a single 512-B block + immediate raw restore before trusting it.
 *
 * NO status-register write (0x01/0x31) is issued: we do NOT clear block-protect
 * bits. If SR1 BP bits are set, erase/program will be rejected by the chip and
 * reported (error 3/4); we never touch WRSR (the vendor dump showed BP=0).
 */
#include "spi_cmd.h"

#define ARGS ((volatile uint32_t *)0x00120000u)
#define SRC  ((volatile uint8_t  *)0x00121000u)
#define DATA ((volatile uint32_t *)0x00120100u)
struct result { void *addr; unsigned size; };
#define RESULT ((volatile struct result *)0x00120010u)

#define WIP_BOUND   0x200000u   /* bounded RDSR spins (4K erase ~45ms worst) */
#define ALLOW_MAGIC 0x414C4C57u
#define UNPROT_MAGIC 0x554E5052u /* 'UNPR' */

/* Volatile status-register write: 0x50 then 0x01 <SR1> <SR2>. Never uses WREN (0x06), so the
 * non-volatile status bits cannot change. */
static void wr_vsr(uint8_t sr1, uint8_t sr2, int *timed_out)
{
    spi_scramble(0);
    spi_cmd0(0x50u);
    spi_begin_cmd(0x01u);
    spi_tx_byte(sr1);
    spi_tx_byte(sr2);
    spi_end();
    spi_wait_wip(WIP_BOUND, timed_out);
}

/* Whitelist: LFI head/dir sector and the sectors holding the NEW_M.FNT index + Cyrillic glyph records. */
static int sector_allowed(uint32_t a)
{
    return a == 0x11000u || a == 0xE9000u || a == 0xEA000u || a == 0xEE000u;
}

static void tx_addr(uint32_t a)             /* 24-bit, MSB first (scrambler off) */
{
    spi_tx_byte((a >> 16) & 0xff);
    spi_tx_byte((a >> 8) & 0xff);
    spi_tx_byte(a & 0xff);
}

void *entry_main(void)
{
    uint32_t addr, len, bank, scr, dry, allow;
    uint32_t err = 0, prog_loops = 0, erase_loops = 0, bytes = 0, page, i;
    int to = 0, to_any = 0;
    uint8_t sr_before = 0xff, sr_after = 0xff, sr1_o = 0xff, sr2_o = 0xff;
    int did_unprot = 0;

    wd();
    addr  = ARGS[0]; len = ARGS[1]; bank = ARGS[2];
    scr   = ARGS[3] ? 1u : 0u; dry = ARGS[4]; allow = ARGS[5];
    if (bank > 2) bank = 0;

    DATA[0] = 0x53504957u;        /* 'SPIW' */
    DATA[10] = DATA[11] = DATA[12] = DATA[13] = 0;

    /* --- guards: refuse with NO device access on violation --- */
    if (len != 4096u || (addr & 0xfffu)) { err = 1; goto done_noinit; }
    if (!sector_allowed(addr) && allow != ALLOW_MAGIC) {
        err = 2; goto done_noinit;
    }

    rom_spi_init();               /* func_1ab4 */
    rom_spi_pinmux((int)bank);    /* func_383c */
    spi_scramble(0);
    spi_cmd0(0xABu);              /* wake (read-only) */

    sr_before = spi_read_sr(0x05u);
    sr2_o = spi_read_sr(0x35u);
    sr1_o = sr_before;

    /* Optional volatile unprotect (only for the two whitelisted font sectors, never with allow_any).
     * 0x50 = "volatile status-register write enable": the new SR1/SR2 live in the chip's volatile copy
     * only, the non-volatile bits are untouched and the protection returns at the next power cycle.
     * We clear SR1 BP/TB/SEC (bits 2..6) and SR2 CMP (bit 6), and restore the original bytes before exit. */
    if (!dry && ARGS[6] == UNPROT_MAGIC && sector_allowed(addr)) {
        wr_vsr((uint8_t)(sr1_o & 0x80u), (uint8_t)(sr2_o & ~0x40u), &to);
        did_unprot = 1;
        DATA[10] = spi_read_sr(0x05u);
        DATA[11] = spi_read_sr(0x35u);
        if ((DATA[10] & 0x7cu) || (DATA[11] & 0x40u)) { err = 5; goto readsr; }
    }

    if (!dry) {
        /* erase 4 KiB sector */
        spi_cmd0(0x06u);                      /* WREN */
        spi_scramble(0);
        spi_begin_cmd(0x20u); tx_addr(addr); spi_end();  /* sector erase */
        erase_loops = spi_wait_wip(WIP_BOUND, &to);
        if (to) { err = 3; goto readsr; }
    }

    /* The scrambler restarts at every command, but the reader descrambles each 512-B block as one
     * stream. So per 512-B block: page A = first 256 B (fresh state), page B = a 512-B transfer
     * (A's data then B's data, address of page B): the chip's 256-B page buffer wraps, keeps only the
     * last 256 B (B), and the scrambler state at that point is the correct continuation. */
    for (page = 0; page < 4096u; page += 512u) {
        uint32_t half, cnt;
        for (half = 0; half < 2u; half++) {
            uint32_t pa = addr + page + half * 256u;
            uint32_t first = page + (half ? 0u : 0u);
            cnt = half ? 512u : 256u;
            if (!dry) {
                spi_cmd0(0x06u);              /* WREN */
                spi_scramble(0);
                spi_begin_cmd(0x02u);         /* page program */
                tx_addr(pa);
                spi_tx_scramble((int)scr);    /* data through TX scrambler (CTL 0x2000) */
                for (i = 0; i < cnt; i++) spi_tx_byte(SRC[first + i]);
                spi_tx_scramble(0);
                spi_scramble(0);
                spi_end();
                prog_loops += spi_wait_wip(WIP_BOUND, &to);
                if (to) { to_any = 1; err = err ? err : 4; }
            }
            bytes += 256u;
        }
    }

readsr:
    spi_scramble(0);
    if (did_unprot) {                         /* always restore the original protection */
        wr_vsr((uint8_t)(sr1_o & 0xfcu), sr2_o, &to);
        DATA[12] = spi_read_sr(0x05u);
        DATA[13] = spi_read_sr(0x35u);
        if (((DATA[12] ^ sr1_o) & 0x7cu) || ((DATA[13] ^ sr2_o) & 0x40u)) err = err ? err : 6;
    }
    sr_after = spi_read_sr(0x05u);
    if (dry && !err) err = 0x10u;             /* dry-run completed */

done_noinit:
    DATA[1] = err;
    DATA[2] = sr_before;
    DATA[3] = sr_after;
    DATA[4] = erase_loops;
    DATA[5] = prog_loops;
    DATA[6] = dry ? 0u : bytes;
    DATA[7] = (uint32_t)(to | (to_any << 1));
    DATA[8] = addr;
    DATA[9] = 0x444e4544u;        /* 'DEND' */

    RESULT->addr = (void *)DATA;
    RESULT->size = 14 * 4;
    wd();
    return (void *)RESULT;
}
