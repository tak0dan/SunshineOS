#!/usr/bin/env bash
# Screenshot: shot.sh uefi|bios name  -> test/tmp/name.png
cd "$(dirname "$0")/.."
echo "screendump test/tmp/$2.ppm" | socat - UNIX-CONNECT:test/tmp/mon-$1.sock >/dev/null
sleep 1; python3 -I -c "from PIL import Image; Image.open('test/tmp/$2.ppm').save('test/tmp/$2.png')"
