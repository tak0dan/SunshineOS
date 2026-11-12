#!/usr/bin/env bash
# Boot the live ISO (UEFI) with an already-installed disk attached as a second, non-boot drive, for inspection. Usage: attach-disk.sh disk.qcow2
cd "$(dirname "$0")/.."
iso=$(ls -t out/*.iso | head -1)
cp /usr/share/edk2/x64/OVMF_VARS.4m.fd test/tmp/OVMF_VARS-uefi.fd
exec qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m 3072 -machine q35 \
  -drive file=$iso,media=cdrom,if=none,id=cd -device ide-cd,drive=cd,bootindex=0 \
  -drive file="$1",if=virtio -device virtio-vga -display none \
  -monitor unix:test/tmp/mon-uefi.sock,server,nowait -serial file:test/tmp/serial-x.log \
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS-uefi.fd
