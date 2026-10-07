#!/bin/bash
# test_free_sector.sh - validate the SPI write path on an ERASED, UNUSED sector (after the LFI end
# 0x3d8600, raw FF in the original dump). Firmware never reads it, so this cannot affect boot.
# Run on a Linux host inside your actions_flash checkout, player in ADFU with adfus running.
# Needs: spiwrite.bin spiread.bin spistat.bin spi_4m.bin spi_plain.bin
set -uo pipefail
DUMP=./actions_dump
CODE=0x11e000; ARGS=0x120000; DATA=0x120100; SRC=0x121000
T=${T:-0x3dd000}
MAGIC=0x414C4C57
REF=0xEE000            # plaintext source for the scrambler test (the real font sector)

le32(){ printf '\\x%02x\\x%02x\\x%02x\\x%02x' $(($1&255)) $((($1>>8)&255)) $((($1>>16)&255)) $((($1>>24)&255)); }
args(){ printf "$(le32 $1)$(le32 $2)$(le32 $3)$(le32 $4)$(le32 $5)$(le32 $6)" > args.bin; }
slice(){ dd if="$1" bs=4096 skip=$(($2/4096)) count=1 2>/dev/null of="$3"; }

rd(){ # addr f68 out
  args $1 4096 0 $2 0 0
  timeout 30 $DUMP chip 2157 write_mem $CODE 0 0 spiread.bin write_mem $ARGS 0 0 args.bin \
    exec_ret $CODE 0 read_mem2 $DATA 4096 "$3" >/dev/null 2>&1; }

wr(){ # addr scramble file
  args $1 4096 0 $2 0 $MAGIC
  timeout 30 $DUMP chip 2157 write_mem $SRC 0 0 "$3" write_mem $CODE 0 0 spiwrite.bin \
    write_mem $ARGS 0 0 args.bin exec_ret $CODE 0 read_mem2 $DATA 40 wstat.bin >/dev/null 2>&1
  echo "    spiwrite status: $(xxd -p -c 40 wstat.bin)"; }

echo "[0] spistat (read-only)"
timeout 30 $DUMP chip 2157 simple_exec $CODE spistat.bin -1 2>&1 | tail -4

echo "[1] precheck: target $T must be raw FF now"
rd $T 0 pre_raw.bin
python3 -c "import sys; d=open('pre_raw.bin','rb').read(); sys.exit(0 if d==b'\xff'*4096 else 1)" \
  || { echo "ABORT: $T is not erased"; exit 1; }
echo "    ok"

echo "[2] T1: raw write (scramble=0) of a random pattern"
head -c 4096 /dev/urandom > pat.bin
wr $T 0 pat.bin
rd $T 0 t1_raw.bin
cmp -s t1_raw.bin pat.bin && echo "    T1 PASS: raw read-back == pattern" || { echo "    T1 FAIL"; T1FAIL=1; }

echo "[3] T2: scrambled write (scramble=1) of the plaintext font sector"
slice spi_plain.bin $REF ref_plain.bin; slice spi_4m.bin $REF ref_raw.bin
wr $T 1 ref_plain.bin
rd $T 1 t2_plain.bin; rd $T 0 t2_raw.bin
cmp -s t2_plain.bin ref_plain.bin && echo "    T2a PASS: descrambled read-back == plaintext" || echo "    T2a FAIL: descrambled read-back differs"
cmp -s t2_raw.bin ref_raw.bin && echo "    T2b PASS: raw == original raw font sector (scrambler symmetric)" || echo "    T2b FAIL: raw differs from original raw"
python3 - <<'EOF'
a=open('t2_plain.bin','rb').read(); b=open('ref_plain.bin','rb').read()
d=[i for i in range(4096) if a[i]!=b[i]]
print('    plaintext diff bytes: %d; first diff at %s; per-512 diff counts %s' % (len(d), hex(d[0]) if d else None, [sum(1 for i in d if k*512<=i<(k+1)*512) for k in range(8)]))
EOF

echo "[4] cleanup: back to erased (scramble=0, all FF)"
python3 -c "open('ff.bin','wb').write(b'\xff'*4096)"
wr $T 0 ff.bin
rd $T 0 post_raw.bin
cmp -s post_raw.bin ff.bin && echo "    cleanup PASS: $T is raw FF again" || echo "    cleanup FAIL"
