/*
 * spistat.c - READ-ONLY SPI-NOR status reader for ATJ2157.
 *
 * Runs after adfus (0x118000) via adfus CMD_ADFU_EXEC at 0x11e000.
 * args: ARGS[0]=bank (0..2, default 0). No writes of any kind.
 *
 * Returns a block at DATA=0x120100 (u32 words):
 *   [0] magic 'STAT' 0x53544154
 *   [1] JEDEC byte0 (manufacturer), [2] JEDEC byte1, [3] JEDEC byte2 (density)
 *   [4] JEDEC as one 32-bit RXD word (for cross-check)
 *   [5] SR1 (0x05)  [6] SR2 (0x35)  [7] SR3 (0x15)
 *   [8] end marker 'DEND' 0x444e4544
 *
 * Only opcodes transmitted: 0x9F, 0x05, 0x35, 0x15 (all read-only).
 */
#include "spi_cmd.h"

#define ARGS ((volatile uint32_t *)0x00120000u)
#define DATA ((volatile uint32_t *)0x00120100u)
struct result { void *addr; unsigned size; };
#define RESULT ((volatile struct result *)0x00120010u)

void *entry_main(void)
{
    uint32_t bank, idw, i;
    uint8_t id[3];

    wd();
    bank = ARGS[0];
    if (bank > 2) bank = 0;

    rom_spi_init();                 /* func_1ab4 */
    rom_spi_pinmux((int)bank);      /* func_383c */
    spi_scramble(0);                /* raw command path for id/status */

    /* wake, then JEDEC 0x9F -> 3 id bytes */
    spi_cmd0(0xABu);
    spi_begin_cmd(0x9Fu);
    idw = 0;
    for (i = 0; i < 3; i++) { id[i] = spi_rx_byte(); idw |= (uint32_t)id[i] << (i * 8); }
    spi_end();

    DATA[0] = 0x53544154u;
    DATA[1] = id[0];
    DATA[2] = id[1];
    DATA[3] = id[2];
    DATA[4] = idw;
    DATA[5] = spi_read_sr(0x05u);   /* SR1 */
    DATA[6] = spi_read_sr(0x35u);   /* SR2 */
    DATA[7] = spi_read_sr(0x15u);   /* SR3 */
    DATA[8] = 0x444e4544u;

    RESULT->addr = (void *)DATA;
    RESULT->size = 9 * 4;
    wd();
    return (void *)RESULT;
}
