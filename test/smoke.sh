#!/usr/bin/env bash
# Fast boot check of an ISO (about 2 minutes, no installation, throwaway VM). Run it on a FAST=1 build before spending an hour on
# the release build.   Usage: test/smoke.sh [iso]     (default: newest of out/fast/*.iso, out/*.iso)
#
# The VM has NO network on purpose: an ISO must boot to a login prompt on an offline machine. Checks:
#   - reaches the login prompt (a boot that waits for a time server for ever fails here)
#   - no failed systemd units (a broken dbus-broker/polkit/networkd shows up here)
#   - installed binaries are runnable by non-root services (host umask / ACL leaking into the image)
#   - dbus, NetworkManager and the display manager are active
# The kernel is started directly from the ISO, so GRUB is not exercised (see test/headless.sh for that).
set -uo pipefail
cd "$(dirname "$0")/.."
iso=${1:-$(ls -t out/fast/*.iso out/*.iso 2>/dev/null | head -1)}
[ -f "$iso" ] || { echo "no ISO found (FAST=1 ./build.sh first)"; exit 2; }
for t in qemu-system-x86_64 bsdtar blkid python3; do command -v $t >/dev/null || { echo "missing tool: $t"; exit 2; }; done
T=test/tmp/smoke; rm -rf "$T"; mkdir -p "$T"
label=$(blkid -o value -s LABEL "$iso")
bsdtar -xf "$iso" -C "$T" arch/boot/x86_64/vmlinuz-linux arch/boot/x86_64/initramfs-linux.img || { echo "cannot read kernel from $iso"; exit 2; }
accel=(); [ -w /dev/kvm ] && accel=(-enable-kvm -cpu host) || accel=(-cpu max)
qemu-system-x86_64 "${accel[@]}" -smp 4 -m 4096 -machine q35 -name sunshine-smoke \
  -cdrom "$iso" -kernel "$T/arch/boot/x86_64/vmlinuz-linux" -initrd "$T/arch/boot/x86_64/initramfs-linux.img" \
  -append "archisobasedir=arch archisolabel=$label console=tty0 console=ttyS0" \
  -vga virtio -display none -nic none -monitor "unix:$T/mon.sock,server,nowait" -serial "unix:$T/ser.sock,server,nowait" \
  -daemonize -pidfile "$T/qemu.pid" >"$T/qemu.out" 2>&1 || { cat "$T/qemu.out"; exit 2; }
trap 'kill $(cat "$T/qemu.pid" 2>/dev/null) 2>/dev/null' EXIT
echo "booting $(basename "$iso") ($label), no network ..."
SMOKE_BOOT_TIMEOUT=${SMOKE_BOOT_TIMEOUT:-240} SMOKE_IGNORE=${SMOKE_IGNORE:-} python3 -I - "$T/ser.sock" <<'PY'
import os,re,socket,sys,time
sock,boot_to,ignore=sys.argv[1],int(os.environ["SMOKE_BOOT_TIMEOUT"]),os.environ.get("SMOKE_IGNORE","")
for _ in range(50):
    try:
        s=socket.socket(socket.AF_UNIX); s.connect(sock); break
    except OSError: time.sleep(0.2)
else: print("FAIL  cannot reach the VM serial console"); sys.exit(1)
s.settimeout(1); ansi=re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b[()][B0]")
def read_until(pat,timeout):
    end=time.time()+timeout; buf=""
    while time.time()<end:
        try: d=s.recv(65536)
        except socket.timeout: d=b""
        buf+=ansi.sub("",d.decode(errors="replace"))
        if re.search(pat,buf): return buf
    return None
t0=time.time(); res=[]
def check(name,ok,detail=""):
    res.append(ok); print(("PASS  " if ok else "FAIL  ")+name+(("  -> "+detail) if detail and not ok else ""))
out=read_until(r"login: ",boot_to)
check("boots to a login prompt without network (%ds)"%(time.time()-t0) if out else "boots to a login prompt without network (not reached in %ds)"%boot_to,out is not None,
      "still waiting for something at boot; look at the VM screen / journal (a time-sync wait is the usual cause)")
if out is None: sys.exit(1)
s.sendall(b"root\n"); o=read_until(r"Password|# ",8)
if o and "Password" in o: s.sendall(b"\n"); read_until(r"# ",8)
# plain shell without line editing, so the captured output has no terminal escape codes
s.sendall(b"exec env -i TERM=dumb HOME=/root PATH=/usr/bin:/bin bash --norc --noprofile\n"); time.sleep(2)
s.sendall(b"stty -echo; PS1=; PS2=\n"); time.sleep(1)
try: s.recv(65536)
except socket.timeout: pass
n=[0]
def run(cmd,timeout=40):
    """Output of cmd, or None if it did not finish in time (a timeout must never look like 'nothing wrong')."""
    s.settimeout(0.3)
    try:
        while s.recv(65536): pass          # drop anything left over from the previous command
    except socket.timeout: pass
    s.settimeout(1)
    n[0]+=1; tag="@@E%d@@"%n[0]
    s.sendall(("%s; echo %s\n"%(cmd,tag)).encode())
    o=read_until(r"(^|\n)"+re.escape(tag)+r"\r?\n",timeout)
    if o is None:
        read_until(r"(^|\n)"+re.escape(tag)+r"\r?\n",150)   # let the slow command finish, so its output cannot leak into the next one
        return None
    return o.split(tag)[0].replace("\r","").strip()
run("true")
# did the boot finish? (a start job that never ends, e.g. a wait for a time server, keeps the state at 'starting')
t1=time.time(); state=""
while time.time()-t1<float(os.environ.get("SMOKE_SETTLE","90")):
    state=run("systemctl is-system-running")
    if state in ("running","degraded"): break
    time.sleep(3)
jobs=run("systemctl list-jobs --no-legend | head -4 | tr -s ' ' | tr '\\n' ';'") if state not in ("running","degraded") else ""
check("boot settles without network (system state: %s)"%(state or "unknown"),state in ("running","degraded"),"unfinished jobs: "+jobs)
failed_out=run("systemctl --failed --no-legend --plain | awk '{print $1}'")
failed=[u for u in (failed_out or "").split() if not (ignore and re.search(ignore,u))]
check("no failed systemd units",failed_out is not None and not failed,", ".join(failed) or "command timed out")
# Host umask/ACL damage hits every file, so a sample of packages is enough (the whole system takes minutes in the VM).
# Files the profile changes on purpose (shadow, sudoers.d, ...) are not in the sample.
sample="dbus-broker polkit networkmanager sddm systemd openssh imagemagick coreutils util-linux libutempter"
# known and harmless: libutempter's setgid bit is dropped while the image is built (only utmp records of terminals are affected)
ignore_perm=os.environ.get("SMOKE_PERM_IGNORE","libutempter")
bad=run("pacman -Qkk %s 2>&1 | grep -i 'permissions' | grep -Ev '%s' | head -6"%(sample,ignore_perm),timeout=180)
check("file permissions match what the packages ship (sample of %d packages)"%len(sample.split()),bad=="",("command timed out" if bad is None else bad.replace("\n"," | ")))
bad=run("find /etc/dbus-1 /etc/polkit-1 /etc/pam.d /etc/NetworkManager /usr/share/dbus-1 /usr/share/polkit-1 -xdev -type f ! -perm -004 2>/dev/null | head -5",timeout=120)
check("service config files are readable by other users",bad=="",("command timed out" if bad is None else bad.replace("\n"," ")))
for unit in ("dbus-broker","NetworkManager","sddm"):
    st=run("systemctl is-active %s"%unit)
    check("%s is active"%unit,st=="active",st or "no answer")
# graphical session: the live user is logged in automatically; wait for the desktop, then look at the screen
t2=time.time(); up=""
while time.time()-t2<float(os.environ.get("SMOKE_GUI","150")):
    up=run("pgrep -x plasmashell >/dev/null && echo yes")
    if up=="yes": break
    time.sleep(5)
check("graphical session starts (plasmashell running, %ds)"%(time.time()-t2) if up=="yes" else "graphical session starts (plasmashell not running)",up=="yes",
      "sddm: "+(run("systemctl is-active sddm") or "?")+"; session processes: "+(run("pgrep -a 'kwin|sddm|startplasma' | cut -c1-60 | head -3 | tr '\\n' ';'") or "?"))
time.sleep(12)
m=socket.socket(socket.AF_UNIX); m.connect(os.path.join(os.path.dirname(sock),"mon.sock")); m.settimeout(2)
ppm=os.path.abspath(os.path.join(os.path.dirname(sock),"screen.ppm"))   # QEMU is daemonized and runs from /
m.sendall(("screendump %s\n"%ppm).encode())
for _ in range(20):
    if os.path.exists(ppm) and os.path.getsize(ppm)>1000: break
    time.sleep(0.5)
mon=""
try: mon=ansi.sub("",m.recv(4096).decode(errors="replace")).strip().replace("\n"," | ")[-200:]
except Exception: pass
if not os.path.exists(ppm): print("      monitor said: "+mon)
try:
    from PIL import Image
    im=Image.open(ppm).convert("RGB"); im.save(ppm.replace(".ppm",".png"))
    px=list(im.resize((160,100)).getdata()); lit=sum(1 for p in px if max(p)>24)/len(px); colours=len(set((p[0]//32,p[1]//32,p[2]//32) for p in px))
    check("the screen shows a desktop (%.0f%% lit, %d colours; test/tmp/smoke/screen.png)"%(lit*100,colours),lit>0.25 and colours>6,"screen is (almost) black")
except Exception as e:
    check("screenshot readable",False,str(e))
print("\n%d/%d checks passed"%(sum(res),len(res))); sys.exit(0 if all(res) else 1)
PY
rc=$?
echo "(VM serial log: $T/ser.sock closed; rerun with a longer SMOKE_BOOT_TIMEOUT if the boot is only slow)"
exit $rc
