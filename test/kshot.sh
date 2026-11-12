#!/usr/bin/env bash
# Screenshot of the live Plasma session via spectacle over SSH. Usage: kshot.sh name -> test/tmp/name.png
cd "$(dirname "$0")/.."
test/vmssh.sh 'export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; rm -f /tmp/k.png; spectacle -b -n -f -o /tmp/k.png >/dev/null 2>&1; ls /tmp/k.png >/dev/null' 2>&1 | tail -1
sshpass -p sunshine scp -q -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null sunshine@localhost:/tmp/k.png test/tmp/$1.png
