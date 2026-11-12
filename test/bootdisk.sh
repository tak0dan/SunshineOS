#!/usr/bin/env bash
# Boot an installed disk (no ISO), headless. Usage: bootdisk.sh uefi|bios [disk]
cd "$(dirname "$0")/.."
mode=${1:-uefi}; disk=${2:-test/tmp/disk.qcow2}
args=(-enable-kvm -cpu host -smp 4 -m 4096 -machine q35 -name sunshine-inst-$mode
  -drive file="$disk",if=virtio
  -vga virtio -display none -monitor unix:test/tmp/mon-$mode.sock,server,nowait
  -serial file:test/tmp/serial-inst-$mode.log
  -device qemu-xhci -device usb-tablet -device usb-kbd
  -netdev user,id=n0,hostfwd=tcp::2223-:22 -device virtio-net,netdev=n0)
[ "$mode" = uefi ] && args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS-uefi.fd)
exec qemu-system-x86_64 "${args[@]}"
