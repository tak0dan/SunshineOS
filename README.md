# Sunshine OS

Standalone Arch-based distribution, built with archiso inside a container.
Nothing here modifies the build host.

- `profile/`  archiso profile (packages, airootfs, boot configs)
- `build.sh`  builds the ISO in a Docker container into `out/`
- `test/`     QEMU (UEFI + BIOS) boot and install tests using throwaway disks
