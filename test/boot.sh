#!/usr/bin/env bash
# Boot the newest ISO in QEMU. Usage: test/boot.sh [uefi|bios] [disk.qcow2] [--headless]
# Uses only project-local files (test/tmp); never touches host disks.
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-uefi}; disk=${2:-test/tmp/disk.qcow2}; extra=${3:-}
iso=$(ls -t out/*.iso | head -1)
mkdir -p test/tmp
[ -f "$disk" ] || qemu-img create -f qcow2 "$disk" 30G >/dev/null
args=(-enable-kvm -cpu host -smp 4 -m 4096 -machine q35
      -drive file="$disk",if=virtio -cdrom "$iso" -boot d
      -device virtio-vga-gl -display gtk,gl=on
      -device qemu-xhci -device usb-tablet
      -audiodev none,id=a -device intel-hda -device hda-duplex,audiodev=a
      -netdev user,id=n0 -device virtio-net,netdev=n0)
if [ "$mode" = uefi ]; then
  cp -n /usr/share/edk2/x64/OVMF_VARS.4m.fd test/tmp/OVMF_VARS.fd
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS.fd)
fi
[ "$extra" = --headless ] && args+=(-display none -serial mon:stdio)
exec qemu-system-x86_64 "${args[@]}"
