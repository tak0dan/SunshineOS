#!/usr/bin/env bash
cd "$(dirname "$0")/.."
for i in $(seq 1 100); do
  out=$(test/vmssh.sh 'grep -c SUNSHINE_INSTALL_OK /tmp/inst.out; grep -m1 "^ERROR" /tmp/inst.out' 2>&1)
  echo "$out" | grep -q ERROR && break
  echo "$out" | grep -qx 1 && { echo INSTALL_OK; break; }
  sleep 15
done
test/vmssh.sh 'tail -c 1500 /tmp/inst.out | tr "\r" "\n" | tail -15'
