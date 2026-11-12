#!/usr/bin/env bash
# Type text into the VM via QEMU monitor sendkey. Usage: type.sh uefi|bios "text" [enter]
cd "$(dirname "$0")/.."
mode=$1; text=$2
{ for ((i=0;i<${#text};i++)); do c=${text:$i:1}
    case "$c" in [a-z0-9]) k=$c;; " ") k=spc;; ".") k=dot;; "-") k=minus;; "/") k=slash;; "_") k=shift-minus;; "(") k=shift-9;; ")") k=shift-0;; "@") k=shift-2;; ",") k=comma;; "=") k=equal;; "$") k=shift-4;; ":") k=shift-semicolon;; ";") k=semicolon;; [A-Z]) k=shift-${c,,};; *) k=;; esac
    [ -n "$k" ] && echo "sendkey $k" && sleep 0.15; done
  [ "${3:-}" = enter ] && echo "sendkey ret"; sleep 1; } | socat - UNIX-CONNECT:test/tmp/mon-$mode.sock >/dev/null
