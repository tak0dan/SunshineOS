#!/usr/bin/env bash
# Boot an installed disk in legacy BIOS mode (no ISO), std VGA, monitor socket mon-bios.sock, ssh on 2222. Usage: boot-bios-disk.sh disk
cd "$(dirname "$0")/.."
exec qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m ${MEM:-4608} -machine q35 -drive file="$1",if=virtio -vga std -display none \
  -monitor unix:test/tmp/mon-bios.sock,server,nowait -serial file:test/tmp/serial-bios-disk.log -device qemu-xhci -device usb-tablet -device usb-kbd \
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0
