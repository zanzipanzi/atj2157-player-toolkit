# Build the ATJ2157 SPI-NOR read-only payloads.
# Convention copied from actions_flash/payload_arm: thumb, armv7-m, linked at
# 0x11e000, .bin produced with objcopy -O binary -R .bss.
#
#   make                 -> builds spiid.bin and spiread.bin
#   make NAME=spiid      -> builds spiid.bin only
#
# Toolchain: arm-none-eabi-gcc / arm-none-eabi-objcopy (WSL Ubuntu).

OBJDIR  = obj
LDSCRIPT = simple.ld
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy

CFLAGS  = -Os -Wall -Wextra -std=c99 -pedantic
CFLAGS += -fPIE -ffreestanding -march=armv7-m -mthumb -fno-strict-aliasing
LFLAGS  = -nostartfiles -nodefaultlibs -nostdlib -Wl,-T,$(LDSCRIPT) -Wl,-z,notext
LFLAGS += -Wl,--defsym,IMAGE_START=0x11e000

PAYLOADS = spiid spiread spistat spiwrite

.PHONY: all clean
all: $(PAYLOADS:%=%.bin)

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(OBJDIR)/start.o: start.s | $(OBJDIR)
	$(CC) $< -c -o $@

$(OBJDIR)/%.o: %.c spi_rom.h spi_cmd.h | $(OBJDIR)
	$(CC) $(CFLAGS) $< -c -o $@

$(OBJDIR)/%.elf: $(OBJDIR)/start.o $(OBJDIR)/%.o
	$(CC) $(LFLAGS) $^ -o $@

%.bin: $(OBJDIR)/%.elf
	$(OBJCOPY) -O binary -R .bss $< $@

clean:
	$(RM) -r $(OBJDIR) $(PAYLOADS:%=%.bin)
