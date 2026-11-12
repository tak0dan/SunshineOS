"""Make initial-boot.sh robust: never run awww-daemon in the foreground (it blocks the whole first-boot setup)."""
import re, sys
p = sys.argv[1]
s = open(p).read()
old = "$WWW query || $DAEMON && $swww $wallpaper $effect"
new = ('$WWW query >/dev/null 2>&1 || { $DAEMON >/dev/null 2>&1 & for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do sleep 0.4; $WWW query >/dev/null 2>&1 && break; done; }\n'
       '\t\t$swww "$wallpaper" $effect')
if old not in s:
    print("pattern not found (already patched?)"); sys.exit(0)
open(p, "w").write(s.replace(old, new, 1)); print("patched", p)
