/*
 * spi_cmd.h - low-level C00A0000 SPI command primitives shared by spistat.c
 * and spiwrite.c. Mirrors the register choreography of the proven ROM read
 * path (func_31ac @0x31ac, func_2224 @0x2224) and uses the ROM's bounded FIFO
 * wait (func_3c8c @0x3c8c), so timing matches a real boot.
 *
 * Register model (SPI_BASE=0xC00A0000):
 *   +0x00 CTL : phase bits1-0 (0 idle,1 read,2 command); bit3 fifo-reset pulse;
 *               0x30 read-enable; bit 0x1000 = HARDWARE SCRAMBLER enable (the
 *               bit func_2224 sets from CFG_F68 @0x2254; de-scrambles on read,
 *               and - the write hypothesis - re-scrambles on program TX).
 *   +0x04 STAT: bit4(0x10) tx-ready, bit6(0x40) busy.
 *   +0x08 TXD : FIFO write (command / address / program-data bytes).
 *   +0x0C RXD : FIFO read.
 *   +0x10 LEN : transfer byte count.
 */
#ifndef SPI_CMD_H
#define SPI_CMD_H
#include "spi_rom.h"

static int (* const rom_spi_wait)(void) = (int (*)(void))(0x3c8cu | 1);

/* Set/clear the hardware scrambler (CTL bit 0x1000). We set it via the ROM
 * config word too (ROM_CFG+0x68), exactly as the boot probe / func_2224 do. */
static inline void spi_scramble(int on)
{
    REG(ROM_CFG + CFG_F68) = on ? 1u : 0u;
    if (on) REG(SPI_BASE + SPI_CTL) |= 0x1000u;
    else    REG(SPI_BASE + SPI_CTL) &= ~0x1000u;
}

/* TX-direction scrambler. The ROM generic SPI library (func_3c56 @0x3c56) selects the data
 * mode with CTL mask 0xF000: 0x1000 for RX (read, descramble) and 0x2000 for TX (program),
 * and only sets either when the transfer's flag 0x10 is given (func_4098 @0x413a-0x4146). */
static inline void spi_tx_scramble(int on)
{
    uint32_t v = REG(SPI_BASE + SPI_CTL) & ~0xF000u;
    REG(SPI_BASE + SPI_CTL) = on ? (v | 0x2000u) : v;
}

/* Begin a command: assert, write the opcode byte. */
static inline void spi_begin_cmd(uint32_t cmd)
{
    REG(SPI_BASE + SPI_CTL) |= 8;
    REG(SPI_BASE + SPI_CTL) &= ~8u;
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 2u; /* cmd phase */
    REG(SPI_BASE + SPI_TXD) = cmd & 0xffu;
    rom_spi_wait();
}

/* Push one more TX byte (address or program data) in the current command phase. */
static inline void spi_tx_byte(uint32_t b)
{
    REG(SPI_BASE + SPI_TXD) = b & 0xffu;
    rom_spi_wait();
}

/* Read one byte (read phase). */
static inline uint8_t spi_rx_byte(void)
{
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) &= ~0x30u;
    REG(SPI_BASE + SPI_CTL) |= 0x30u;
    REG(SPI_BASE + SPI_LEN) = 1;
    REG(SPI_BASE + SPI_CTL) = (REG(SPI_BASE + SPI_CTL) & ~3u) | 1u; /* read phase */
    rom_spi_wait();
    return (uint8_t)REG(SPI_BASE + SPI_RXD);
}

static inline void spi_end(void)
{
    REG(SPI_BASE + SPI_CTL) &= ~3u;
    REG(SPI_BASE + SPI_CTL) &= ~0x200u;
}

/* One opcode, no data (e.g. 0x06 WREN). */
static inline void spi_cmd0(uint32_t op) { spi_begin_cmd(op); spi_end(); }

/* Read a status register: opcode then one byte (e.g. 0x05/0x35/0x15). */
static inline uint8_t spi_read_sr(uint32_t op)
{
    uint8_t v;
    spi_begin_cmd(op);
    v = spi_rx_byte();
    spi_end();
    return v;
}

/* Poll RDSR(0x05) until WIP(bit0)==0 or bound reached. Returns loops used;
 * sets *timed_out. NEVER an unbounded loop. */
static inline uint32_t spi_wait_wip(uint32_t bound, int *timed_out)
{
    uint32_t i;
    for (i = 0; i < bound; i++) {
        wd();                              /* feed watchdog */
        if (!(spi_read_sr(0x05u) & 1u)) { *timed_out = 0; return i; }
    }
    *timed_out = 1;
    return i;
}

#endif /* SPI_CMD_H */
