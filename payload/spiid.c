/*
 * spiid.c - READ-ONLY identification of the ATJ2157 on-board SPI-NOR storage.
 *
 * Runs after adfus.bin (loaded at 0x118000) via adfus CMD_ADFU_EXEC at 0x11e000.
 * Returns a result pointer {void *addr; unsigned size} (hello.c convention).
 *
 * What it does, per candidate pin bank (0,1,2 - the ROM boot tries all three
 * at func_17ec/func_1b14):
 *   1. rom_spi_init()         (ROM func_1ab4: pins, clock, controller reset)
 *   2. rom_spi_pinmux(bank)   (ROM func_383c: route SPI pins for this bank)
 *   3. wake 0xAB              (release deep power-down - read-only)
 *   4. JEDEC 0x9F read        (capture manufacturer + 2 device-id bytes)
 *   5. rom_spi_read_id(0)     (ROM func_31ac authoritative present/absent)
 * then snapshots the controller registers. No write/erase command is ever
 * sent (grep-provable: search this file and spi_rom.h for 0x06/0x02/0x20/
 * 0xD8/0xC7 - they do not appear as transmitted bytes).
 *
 * Output buffer layout (little-endian u32 words, at 0x120100):
 *   [0]   magic 0x53504944 ('SPID')
 *   [1]   SPI_BASE (0xC00A0000) for sanity
 *   then per bank b (0..2), 6 words at [2 + b*6]:
 *     +0 bank number
 *     +1 rom_spi_read_id() return (0 = ROM thinks a device is present)
 *     +2 JEDEC word read from SPI_RXD after 0x9F (raw, as one u32)
 *     +3 four sequential byte reads packed: id[0]|id[1]<<8|id[2]<<16|id[3]<<24
 *     +4 SPI_CTL snapshot
 *     +5 SPI_STAT snapshot
 *   [20] ROM_CFG+0x68, [21] +0x6c, [22] +0x74 (addr-mode globals)
 *   [23] 0x454E4400 ('\0DNE') end marker
 */
#include "spi_rom.h"

#define DATA ((volatile uint32_t *)0x00120100u)
struct result { void *addr; unsigned size; };
#define RESULT ((volatile struct result *)0x00120010u)

/* Bounded FIFO wait (ROM func_3c8c: two bounded loops on SPI_STAT, ~0x2aa4
 * iterations each via func_4ca0). Calling it keeps timing ROM-identical. */
static int (* const rom_spi_wait)(void) = (int (*)(void))(0x3c8cu | 1);

/* Mirror of ROM func_31ac's command/read register choreography, but captures
 * the data instead of only a pass/fail. Read-only. */
static void spi_begin_cmd(uint32_t cmd)
{
    REG(SPI_BASE + SPI_CTL) |= 8;                 /* fifo reset pulse */
    REG(SPI_BASE + SPI_CTL) &= ~8u;
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 2u; /* cmd phase */
    REG(SPI_BASE + SPI_TXD) = cmd;
    rom_spi_wait();
}

static uint32_t spi_read_word(void)
{
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) &= ~0x30u;
    REG(SPI_BASE + SPI_CTL) |= 0x30u;             /* read enable */
    REG(SPI_BASE + SPI_LEN) = 1;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 1u; /* read phase */
    rom_spi_wait();
    return REG(SPI_BASE + SPI_RXD);
}

static uint8_t spi_read_byte(void)
{
    REG(SPI_BASE + SPI_LEN) = 1;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 1u;
    rom_spi_wait();
    return (uint8_t)REG(SPI_BASE + SPI_RXD);
}

static void spi_end(void)
{
    REG(SPI_BASE + SPI_CTL) &= ~3u;               /* deassert / idle */
    REG(SPI_BASE + SPI_CTL) &= ~0x200u;
}

void *entry_main(void)
{
    unsigned b, i;

    wd();
    rom_spi_init();                               /* func_1ab4 */

    DATA[0] = 0x53504944u;                        /* 'SPID' */
    DATA[1] = SPI_BASE;

    for (b = 0; b < 3; b++) {
        volatile uint32_t *o = &DATA[2 + b * 6];
        uint32_t idw, packed = 0;

        wd();
        rom_spi_pinmux((int)b);                   /* func_383c */

        /* wake: 0xAB release-power-down (read-only) */
        spi_begin_cmd(0xABu);
        spi_end();

        /* JEDEC 0x9F */
        spi_begin_cmd(0x9Fu);
        idw = spi_read_word();
        for (i = 0; i < 4; i++)
            packed |= (uint32_t)spi_read_byte() << (i * 8);
        o[4] = REG(SPI_BASE + SPI_CTL);
        o[5] = REG(SPI_BASE + SPI_STAT);
        spi_end();

        o[0] = b;
        o[1] = (uint32_t)rom_spi_read_id(0);      /* func_31ac verdict */
        o[2] = idw;
        o[3] = packed;
    }

    DATA[20] = REG(ROM_CFG + CFG_F68);
    DATA[21] = REG(ROM_CFG + CFG_F6C);
    DATA[22] = REG(ROM_CFG + CFG_ADDR4);
    DATA[23] = 0x454E4400u;                        /* end marker */

    RESULT->addr = (void *)DATA;
    RESULT->size = 24 * 4;
    wd();
    return (void *)RESULT;
}
