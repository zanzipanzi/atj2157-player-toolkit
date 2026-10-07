#!/bin/bash
# dump_spi.sh - READ-ONLY dump of the ATJ2157 SPI NOR via ROM func_2224 (spiread.bin).
# Run on a Linux host inside your actions_flash checkout while the player is in ADFU with adfus running.
# read_mem2 uploads its own copy stub over 0x11e000, so spiread.bin is reloaded before every chunk.
set -euo pipefail
DUMP=./actions_dump
CODE=0x11e000
ARGS=0x120000
DATA=0x120100
BANK=${BANK:-0}
F68=${F68:-1}
F6C=${F6C:-0}
SIZE=${SIZE:-$((16*1024*1024))}
CHUNK=$((16*1024))
OUT=${OUT:-../dump/spi_full.bin}
LOG=${LOG:-../dump/spi_dump.log}

: > "$OUT"
off=0
while [ "$off" -lt "$SIZE" ]; do
  n=$CHUNK
  [ $((off + n)) -gt "$SIZE" ] && n=$((SIZE - off))
  printf "$(printf '\\x%02x' \
    $((off & 255)) $(((off >> 8) & 255)) $(((off >> 16) & 255)) $(((off >> 24) & 255)) \
    $((n & 255)) $(((n >> 8) & 255)) $(((n >> 16) & 255)) $(((n >> 24) & 255)) \
    $((BANK & 255)) 0 0 0 \
    $((F68 & 255)) 0 0 0 \
    $((F6C & 255)) 0 0 0)" > args.bin
  timeout 30 $DUMP chip 2157 \
      write_mem $CODE 0 0 spiread.bin \
      write_mem $ARGS 0 0 args.bin \
      exec_ret $CODE 0 \
      read_mem2 $DATA $n chunk.bin >/dev/null 2>>"$LOG"
  got=$(stat -c%s chunk.bin)
  if [ "$got" -ne "$n" ]; then
    echo "short read at 0x$(printf %x $off): $got of $n" | tee -a "$LOG"
    exit 1
  fi
  cat chunk.bin >> "$OUT"
  off=$((off + n))
  [ $((off % (1024*1024))) -eq 0 ] && echo "read $((off / 1024 / 1024)) MiB" >> "$LOG"
done
echo "done $(stat -c%s "$OUT") bytes sha256 $(sha256sum "$OUT" | cut -d' ' -f1)" >> "$LOG"
