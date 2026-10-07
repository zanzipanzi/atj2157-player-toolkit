#!/bin/bash
# apply_font_fix.sh - write the two font-fix sectors (0xEE000 font data, then 0x11000 LFI head/dir)
# to the ATJ2157 SPI NOR through the validated scrambler path, verify, and roll back on any mismatch.
#
# Run on a Linux host inside your actions_flash checkout with the player in ADFU and adfus running.
# Needs: spiwrite.bin spiread.bin spistat.bin spi_4m.bin(raw) spi_plain.bin spi_plain_mod.bin
#
#   DRY=1 ./apply_font_fix.sh      all checks + payload dry run, NO flash command sent
#   ./apply_font_fix.sh            real write (asks for "yes" before each sector)
#   ROLLBACK=1 ./apply_font_fix.sh restore the ORIGINAL raw bytes of both sectors (scrambler off)
set -uo pipefail
DUMP=./actions_dump
CODE=0x11e000; ARGS=0x120000; DATA=0x120100; SRC=0x121000
ORIG_RAW=${ORIG_RAW:-spi_4m.bin}            # factory raw, used only by ROLLBACK
RAW=${CUR_RAW:-spi_4m.bin}; PLAIN=${CUR_PLAIN:-spi_plain.bin}   # what the flash holds NOW (verified before writing)
MOD=${MOD:-spi_plain_mod.bin}
UNPROT=0x554E5052
read -r -a SECTORS <<< "${SECTORS:-0xEE000 0x11000}"   # data first, directory/head (0x11000) last
DRY=${DRY:-0}; ROLLBACK=${ROLLBACK:-0}

le32(){ printf '\\x%02x\\x%02x\\x%02x\\x%02x' $(($1&255)) $((($1>>8)&255)) $((($1>>16)&255)) $((($1>>24)&255)); }
args(){ printf "$(le32 $1)$(le32 $2)$(le32 $3)$(le32 $4)$(le32 $5)$(le32 $6)$(le32 $7)" > args.bin; }
slice(){ dd if="$1" bs=4096 skip=$(($2/4096)) count=1 2>/dev/null of="$3"; }
rd(){ args $1 4096 0 $2 0 0 0
  timeout 30 $DUMP chip 2157 write_mem $CODE 0 0 spiread.bin write_mem $ARGS 0 0 args.bin \
    exec_ret $CODE 0 read_mem2 $DATA 4096 "$3" >/dev/null 2>&1; }
word(){ python3 -c "import struct,sys;d=open('$1','rb').read();print(struct.unpack_from('<I',d,4*$2)[0])"; }

wr(){ # addr scramble dry file -> writes status to wstat.bin
  args $1 4096 0 $2 $3 0 $UNPROT
  timeout 60 $DUMP chip 2157 write_mem $SRC 0 0 "$4" write_mem $CODE 0 0 spiwrite.bin \
    write_mem $ARGS 0 0 args.bin exec_ret $CODE 0 read_mem2 $DATA 56 wstat.bin >/dev/null 2>&1; }

show(){ python3 - <<EOF
import struct
d=open('wstat.bin','rb').read()
w=struct.unpack_from('<14I',d)
print("    magic %08x err=%d SR1 before=%#x after=%#x | erase_loops=%d prog_loops=%d bytes=%d to=%d addr=%#x" % (w[0],w[1],w[2],w[3],w[4],w[5],w[6],w[7],w[8]))
print("    SR during write: SR1=%#x SR2=%#x | SR restored: SR1=%#x SR2=%#x" % (w[10],w[11],w[12],w[13]))
EOF
}

if [ "$ROLLBACK" = 1 ]; then
  for S in "${SECTORS[@]}"; do
    slice $ORIG_RAW $S orig_raw_$S.bin
    echo "[rollback] $S: writing ORIGINAL RAW (scrambler off)"
    wr $S 0 0 orig_raw_$S.bin; show
    rd $S 0 rb_$S.bin; cmp -s rb_$S.bin orig_raw_$S.bin && echo "    raw == original: OK" || echo "    MISMATCH"
  done
  exit 0
fi

echo "[0] spistat"; timeout 30 $DUMP chip 2157 simple_exec $CODE spistat.bin -1 2>&1 | tail -4
echo "[1] verify the flash still equals the reference images (raw and descrambled)"
for S in "${SECTORS[@]}"; do
  rd $S 0 cur_raw.bin; slice $RAW $S exp_raw.bin; cmp -s cur_raw.bin exp_raw.bin || { echo "ABORT: raw $S differs"; exit 1; }
  rd $S 1 cur_pl.bin;  slice $PLAIN $S exp_pl.bin; cmp -s cur_pl.bin exp_pl.bin || { echo "ABORT: plain $S differs"; exit 1; }
done
echo "    ok"

for S in "${SECTORS[@]}"; do
  slice $MOD $S tgt_$S.bin
  echo "[2] DRY RUN $S (no flash command sent)"
  wr $S 1 1 tgt_$S.bin; show
  [ "$(word wstat.bin 1)" = 16 ] || { echo "ABORT: dry-run error code"; exit 1; }
done
[ "$DRY" = 1 ] && { echo "DRY=1: stopping before any write."; exit 0; }

for S in "${SECTORS[@]}"; do
  read -r -p "[3] REAL WRITE $S (unprotect-volatile, erase, program, restore). type yes: " a
  [ "$a" = yes ] || { echo aborted; exit 1; }
  wr $S 1 0 tgt_$S.bin; show
  err=$(word wstat.bin 1)
  rd $S 1 back_pl_$S.bin
  if [ "$err" != 0 ] || ! cmp -s back_pl_$S.bin tgt_$S.bin; then
    echo "FAIL on $S (err=$err or readback differs) -> ROLLBACK=1 ./apply_font_fix.sh"; exit 2
  fi
  echo "    $S verified: descrambled read-back == target"
done

echo "[4] both sectors written and verified. Next, still in ADFU, run the whole-flash check:"
echo "    SIZE=4194304 F68=1 OUT=../dump/after_plain.bin ./dump_spi.sh   (expect == spi_plain_mod.bin)"
echo "    SIZE=4194304 F68=0 OUT=../dump/after_raw.bin   ./dump_spi.sh   (expect == spi_4m.bin except 2 sectors)"
