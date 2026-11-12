#!/usr/bin/env bash
# Headless QEMU boot WITH 3D (virtio-gpu + virgl via egl-headless) for Hyprland tests.
# Usage: headless-gl.sh uefi|bios [disk]   (ISO is attached unless NOISO=1)
cd "$(dirname "$0")/.."
mode=${1:-uefi}; disk=${2:-test/tmp/disk.qcow2}
iso=$(ls -t out/*.iso | head -1)
[ -f "$disk" ] || qemu-img create -f qcow2 "$disk" 30G >/dev/null
args=(-enable-kvm -cpu host -smp 4 -m ${MEM:-6144} -machine q35 -name sunshine-gl-$mode
  -drive file="$disk",if=virtio
  -device virtio-vga-gl -display egl-headless,rendernode=/dev/dri/renderD128
  -monitor unix:test/tmp/mon-$mode.sock,server,nowait -qmp unix:test/tmp/qmp-$mode.sock,server,nowait -serial file:test/tmp/serial-gl-$mode.log
  -device qemu-xhci -device usb-tablet -device usb-kbd
  -netdev user,id=n0,hostfwd=tcp::2222-:22 -device virtio-net,netdev=n0)
[ -z "${NOISO:-}" ] && args+=(-cdrom "$iso" -boot d)
if [ "$mode" = uefi ]; then
  cp -n /usr/share/edk2/x64/OVMF_VARS.4m.fd test/tmp/OVMF_VARS-$mode.fd
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive if=pflash,format=raw,file=test/tmp/OVMF_VARS-$mode.fd)
fi
exec qemu-system-x86_64 "${args[@]}"
