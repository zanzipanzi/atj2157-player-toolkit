/*
 * spi_rom.h - ATJ2157 boot-ROM SPI-NOR driver, addresses and helpers.
 *
 * All facts below are taken from static analysis of rom.bin (reset=0x189).
 * The on-board firmware storage is SPI NOR on controller base 0xC00A0000.
 * The boot ROM contains a complete, validated read path; this payload CALLS
 * those ROM functions rather than re-implementing the controller, so the
 * exact timing/handshake is guaranteed identical to a real boot.
 *
 * READ-ONLY GUARANTEE: this payload issues only
 *   0x9F (JEDEC ID), 0xAB (release power-down / read ID), 0x0B (fast read).
 * It never issues 0x06 (WREN), 0x01/0x05 write-status, 0x02 page-program,
 * 0x20/0x52/0xD8/0xC7/0x60 erase, or any other state-changing command.
 */
#ifndef SPI_ROM_H
#define SPI_ROM_H
#include <stdint.h>

#define REG(a)   (*(volatile uint32_t *)(a))

/* ---- peripheral bases referenced by the ROM SPI path ------------------- */
#define SPI_BASE   0xC00A0000u   /* SPI-NOR controller (word0 of ROM obj @0x50a8) */
#define GPIO_BASE  0xC01C0000u   /* pad mux (0xC01C0004 + 4*pin)                  */
#define CMU_BASE   0xC0001000u
#define RTC_BASE   0xC0030000u   /* watchdog ctl at +0x1C                         */

/* SPI controller register offsets (from func_2224 / func_31ac / func_3c8c) */
#define SPI_CTL    0x00   /* bits0-1 phase, bit3 fifo-reset pulse, 0x30 read/dma,
                             0x40|0x80000 dma start, 0x200/0x1000 cfg        */
#define SPI_STAT   0x04   /* bit2(0x4) busy, bit4(0x10) tx-ready, bit6(0x40) rx */
#define SPI_TXD    0x08   /* FIFO write: command/address/dummy bytes         */
#define SPI_RXD    0x0C   /* FIFO read: ID / data bytes                      */
#define SPI_LEN    0x10   /* transfer byte count                             */

/* ---- ROM function pointers (Thumb, low bit set for blx) ----------------
 * func_1ab4  spi_init():   pin-save+clear (func_3500), CMU/clock (func_337c),
 *                          controller reset (func_21f8); zeroes 0x100034+0x64/68.
 * func_383c  spi_pinmux(bank): 0..2 -> writes pad function to GPIO pads.
 * func_31ac  spi_read_id(mode): 0x9F, returns 0 if a valid (non 00/FF) id byte.
 * func_2224  spi_read_sector(byteAddr, 512, ramBuf, flag=0): 0x0B fast read
 *            of one 512-byte sector via DMA ch1 (0xC0070100). Bounded waits.
 * func_28d8  wd_feed(): writes 0x1d to 0xC003001C (watchdog).
 */
typedef void (*rom_void_fn)(void);
typedef int  (*rom_int_i_fn)(int);
typedef int  (*rom_read_fn)(uint32_t addr, uint32_t len, void *buf, int flag);

#define rom_spi_init   ((rom_void_fn)(0x1ab4u | 1))
#define rom_spi_pinmux ((rom_int_i_fn)(0x383cu | 1))   /* arg = bank 0..2 */
#define rom_spi_read_id ((rom_int_i_fn)(0x31acu | 1))  /* arg = mode (0)   */
#define rom_spi_read_sec ((rom_read_fn)(0x2224u | 1))
#define rom_wd_feed    ((rom_void_fn)(0x28d8u | 1))

/* ROM scratch struct base used by func_1ab4/func_2224 (in SRAM, set by boot) */
#define ROM_CFG    0x00100034u
#define CFG_ADDR4  0x74   /* 4-byte-address flag (0 = 24-bit)                */
#define CFG_F68    0x68
#define CFG_F6C    0x6C

/* Bounded busy-wait feeding the watchdog (never hangs the chip). */
static inline void wd(void) { rom_wd_feed(); }

#endif /* SPI_ROM_H */
