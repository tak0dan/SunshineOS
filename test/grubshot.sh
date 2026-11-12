#!/usr/bin/env bash
# Boot an installed disk (UEFI, std VGA) and capture the GRUB menu at a few moments. Usage: grubshot.sh disk out-prefix
cd "$(dirname "$0")/.."
pkill -f "[q]emu-system-x86_64"; sleep 3
cp /usr/share/edk2/x64/OVMF_VARS.4m.fd test/tmp/OVMF_VARS-uefi.fd
(MEM=3072 nohup test/headless-disk.sh "$1" >/dev/null 2>&1 &)
for t in 1 2 3 4; do sleep $((t==1?4:1)); echo "screendump $2-$t.ppm" | socat - UNIX-CONNECT:test/tmp/mon-uefi.sock >/dev/null 2>&1; done
sleep 1; magick $2-3.ppm -resize 50% $2.png 2>/dev/null; echo captured
