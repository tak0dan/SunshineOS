#!/usr/bin/env bash
# Screenshot the Wayland session inside the live VM (grim over SSH). Usage: vmshot.sh name
cd "$(dirname "$0")/.."
test/vmssh.sh 'export XDG_RUNTIME_DIR=/run/user/1000; for s in $XDG_RUNTIME_DIR/wayland-*; do case $s in *.lock) ;; *) export WAYLAND_DISPLAY=$(basename $s);; esac; done; grim /tmp/vm.png && echo ok' >/dev/null 2>&1
sshpass -p sunshine scp -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR sunshine@localhost:/tmp/vm.png test/tmp/$1.png
