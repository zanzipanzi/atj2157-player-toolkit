/*
 * spiread.c - READ-ONLY bulk read of the ATJ2157 on-board SPI-NOR storage.
 *
 * Runs after adfus.bin via adfus CMD_ADFU_EXEC at 0x11e000.
 *
 * The host writes an 8/12-byte argument block to ARGS=0x120000 BEFORE each
 * exec (using actions_dump write_mem), then execs this payload, then reads the
 * data back with read_mem from DATA=0x120100:
 *     ARGS[0] = byte offset into flash       (u32)
 *     ARGS[1] = length in bytes, <= 0x4000   (u32, rounded down to 512)
 *     ARGS[2] = pin bank 0..2                (u32; use the one spiid validated)
 *
 * It reads by CALLING the ROM boot read routine func_2224 (0x0B fast read,
 * 24-bit address, DMA ch1, bounded completion wait) one 512-byte sector at a
 * time - the exact code a real boot uses. READ-ONLY: only 0xAB (wake) and
 * 0x0B (fast read, inside func_2224) touch the device. No WREN/erase/program.
 *
 * Returns {addr=DATA, size=len}.
 */
#include "spi_rom.h"

#define ARGS ((volatile uint32_t *)0x00120000u)
#define DATA ((volatile uint8_t  *)0x00120100u)
struct result { void *addr; unsigned size; };
#define RESULT ((volatile struct result *)0x00120010u)

#define MAX_LEN 0x4000u   /* 16 KB per call; DATA..DATA+0x4000 = 0x120100..0x124100 */

static int (* const rom_spi_wait)(void) = (int (*)(void))(0x3c8cu | 1);

static void spi_wake(void)
{
    /* 0xAB release deep power-down (read-only), mirrors ROM command phase */
    REG(SPI_BASE + SPI_CTL) |= 8;
    REG(SPI_BASE + SPI_CTL) &= ~8u;
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 2u;
    REG(SPI_BASE + SPI_TXD) = 0xABu;
    rom_spi_wait();
    REG(SPI_BASE + SPI_CTL) &= ~3u;
}

void *entry_main(void)
{
    uint32_t addr, len, bank, off;

    wd();
    addr = ARGS[0];
    len  = ARGS[1];
    bank = ARGS[2];
    if (bank > 2) bank = 0;
    if (len > MAX_LEN) len = MAX_LEN;
    len &= ~0x1ffu;                               /* whole 512-byte sectors */

    rom_spi_init();                               /* func_1ab4 */
    rom_spi_pinmux((int)bank);                    /* func_383c */
    spi_wake();

    /* 24-bit addressing. ARGS[3] -> CFG_F68 (CTL 0x1000, the descrambler the ROM boot
     * probe enables first, func_1b14 @0x1b68), ARGS[4] -> CFG_F6C (CTL 0x200). */
    REG(ROM_CFG + CFG_F68)  = ARGS[3] ? 1u : 0u;
    REG(ROM_CFG + CFG_F6C)  = ARGS[4] ? 1u : 0u;
    REG(ROM_CFG + CFG_ADDR4) = 0;

    for (off = 0; off < len; off += 0x200u) {
        wd();
        rom_spi_read_sec(addr + off, 0x200u, (void *)(DATA + off), 0); /* func_2224 */
    }

    RESULT->addr = (void *)DATA;
    RESULT->size = len;
    wd();
    return (void *)RESULT;
}
