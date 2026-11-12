#!/usr/bin/env bash
# Push the working-tree installer into the running live VM and start an auto install. Usage: push-install.sh [fs]
cd "$(dirname "$0")/.."
test/vmssh.sh 'sudo tee /usr/local/bin/sunshine-install >/dev/null && sudo chmod 755 /usr/local/bin/sunshine-install' < profile/airootfs/usr/local/bin/sunshine-install
test/vmssh.sh "sudo env SUNSHINE_AUTO=1 SUNSHINE_DISK=/dev/vda SUNSHINE_USER=tester SUNSHINE_PASS=testpass123 SUNSHINE_HOSTNAME=sunshine-test SUNSHINE_TZ=Europe/Madrid SUNSHINE_FS=${1:-ext4} nohup /usr/local/bin/sunshine-install > /tmp/inst.out 2>&1 &"
