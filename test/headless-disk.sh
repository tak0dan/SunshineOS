#!/usr/bin/env bash
# Boot an installed disk only (no ISO) with a plain VGA display, monitor socket for screenshots. Usage: headless-disk.sh disk
cd "$(dirname "$0")/.."
disk=${1:?disk}
args=(-enable-kvm -cpu host -smp 4 -m ${MEM:-6144} -machine q35 -name sunshine-disk
  -drive file="$disk",if=virtio -vga std -display none -monitor unix:test/tmp/mon-uefi.sock,server,nowait -qmp unix:test/tmp/qmp-uefi.sock,server,nowait
  -serial file:test/tmp/serial-disk.log -device qemu-xhci -device usb-tablet -device usb-kbd
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
  -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS-uefi.fd)
exec qemu-system-x86_64 "${args[@]}"
