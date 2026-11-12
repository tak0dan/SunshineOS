#!/usr/bin/env bash
# Headless QEMU boot with monitor socket for screenshots. Usage: headless.sh uefi|bios [disk]
cd "$(dirname "$0")/.."
mode=${1:-uefi}; disk=${2:-test/tmp/disk.qcow2}
iso=$(ls -t out/*.iso | head -1)
[ -f "$disk" ] || qemu-img create -f qcow2 "$disk" 30G >/dev/null
args=(-enable-kvm -cpu host -smp 4 -m 4096 -machine q35 -name sunshine-$mode
  -drive file="$disk",if=virtio -cdrom "$iso" -boot d
  -vga virtio -display none -monitor unix:test/tmp/mon-$mode.sock,server,nowait
  -serial file:test/tmp/serial-$mode.log
  -device qemu-xhci -device usb-tablet -device usb-kbd
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0)
if [ "$mode" = uefi ]; then
  cp -n /usr/share/edk2/x64/OVMF_VARS.4m.fd test/tmp/OVMF_VARS-$mode.fd
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS-$mode.fd)
fi
exec qemu-system-x86_64 "${args[@]}"
