#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="sunshineos"
iso_label="SUNSHINE_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Sunshine OS <https://github.com/tak0dan>"
iso_application="Sunshine OS Live/Install"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="arch"
bootmodes=('bios.syslinux'
           'uefi.grub')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86,arm64' '-b' '1M' '-Xdict-size' '1M' '-processors' '6' '-mem' '2G')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
kernel_params_aarch64="clk_ignore_unused pd_ignore_unused arm64.nopauth"
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/etc/sudoers.d/20-sunshine"]="0:0:440"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/etc/gshadow"]="0:0:400"
  ["/home/sunshine"]="1000:1000:750"
  ["/home/sunshine/Desktop"]="1000:1000:755"
  ["/home/sunshine/Desktop/sunshine-install.desktop"]="1000:1000:755"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/sunshine-install"]="0:0:755"
  ["/usr/local/bin/sunshine-welcome"]="0:0:755"
  ["/usr/local/bin/sunshine-update"]="0:0:755"
  ["/usr/local/bin/awww-daemon"]="0:0:755"
  ["/usr/local/bin/sunshine-live-setup"]="0:0:755"
  ["/usr/bin/sunshine-store"]="0:0:755"
  ["/usr/bin/sunshine-store-index"]="0:0:755"
  ["/usr/bin/sunshine-store-appimage"]="0:0:755"
  ["/usr/bin/sunshine-store-windows"]="0:0:755"
  ["/usr/local/bin/sunshine-post-install"]="0:0:755"
  ["/usr/local/bin/sunshine-firstlogin"]="0:0:755"
  ["/usr/local/bin/sunshine-update-run"]="0:0:755"
  ["/usr/local/bin/sunshine-update-notifier"]="0:0:755"
)

# archiso resets the modes of every airootfs file that is not listed in file_permissions, which stripped the executable
# bit from the Hyprland dots' scripts (Permission denied: no bar, no wallpaper, no first-boot). List every executable
# file automatically so scripts stay runnable.
_ar="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/airootfs"
while IFS= read -r -d '' _f; do
  file_permissions["${_f#"$_ar"}"]="0:0:755"
done < <(find "$_ar" -type f -perm -u+x -print0)
unset _ar _f
