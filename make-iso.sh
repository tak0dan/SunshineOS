#!/usr/bin/env bash
# One command from a clean checkout to an ISO in ./out:
#   1. builder image (Docker)
#   2. AUR-only packages -> ./repo               (tools/aur-list.sh decides which; build-aur.sh builds them)
#   3. Hyprland payload  -> profile/airootfs/... (tools/import-end4.sh: dots, offline package repo; tools/build-venv.sh: Python venv)
#   4. the ISO                                    (build.sh)
# Every step is idempotent: finished work is skipped, so re-running resumes where a failure stopped.
# Common failures are resolved automatically (retries, dead AUR dependencies, stale repo database, file ownership).
# Usage: ./make-iso.sh [--clean]     --clean rebuilds the image, the AUR packages and the payload
set -uo pipefail
cd "$(dirname "$0")"
export SUNSHINE_CACHE=${SUNSHINE_CACHE:-$PWD/cache}
LOG=${SUNSHINE_LOGS:-$PWD/logs}; mkdir -p "$LOG"
TRIES=3
PAY=profile/airootfs/usr/share/sunshine/hyprland

# AUR dependencies that disappeared upstream -> replacement (space separated; empty = drop). Add to this when a new one shows up.
declare -A DEAD_DEP=( [qt6-avif-image-plugin]="kimageformats libavif" )

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mXX %s\033[0m\n' "$*"; exit 1; }
retry() { local n=$1; shift; local t; for t in $(seq "$n"); do "$@" && return 0; warn "'$1' failed (try $t/$n)"; sleep 10; done; return 1; }

# Containers write as root/uid 1000: hand every output tree back to the invoking user (needs only docker, no sudo).
fix_owner() {
  docker run --rm -v "$PWD:/w" sunshineos-builder bash -c \
    "for d in repo aur out build logs cache $PAY; do [ -e /w/\$d ] && chown -R $(id -u):$(id -g) /w/\$d; done; chmod -R a+rwX /w/cache/pacman 2>/dev/null; true" >/dev/null 2>&1
}

# A missing dependency reported by pacman/makepkg: patch the local PKGBUILD(s) if we know a replacement.
resolve_dead_deps() {
  local logf=$1 changed=1 dep repl f
  for dep in $(grep -ohP 'target not found: \K[^ )]+' "$logf" | sort -u); do
    [[ -v DEAD_DEP[$dep] ]] || continue
    repl=${DEAD_DEP[$dep]}
    for f in pkgs/*/PKGBUILD; do
      grep -qE "^\s*['\"]?$dep['\"]?\s*$" "$f" || continue
      sed -i -E "s/^(\s*)['\"]?$dep['\"]?\s*$/\1${repl// /\\n\\1}/" "$f"
      warn "dependency $dep no longer exists: replaced by '${repl:-nothing}' in $f"; changed=0
    done
  done
  return $changed
}

CLEAN=0; [ "${1:-}" = --clean ] && CLEAN=1

log "Preflight"
command -v docker >/dev/null || die "docker is not installed"
docker info >/dev/null 2>&1 || die "cannot reach the docker daemon (start it, and add yourself to the docker group: sudo usermod -aG docker \$USER, then log in again)"
for t in git rsync; do command -v $t >/dev/null || die "$t is required on the host"; done
mkdir -p "$SUNSHINE_CACHE/pacman" repo aur out build
chmod -R a+rwX "$SUNSHINE_CACHE/pacman" 2>/dev/null
avail=$(df -BG --output=avail . | tail -1 | tr -dc 0-9); [ "${avail:-0}" -ge 25 ] || warn "only ${avail}G free; a full build wants 25G+"

log "1/4 builder image"
if [ $CLEAN = 1 ] || ! docker image inspect sunshineos-builder >/dev/null 2>&1; then
  retry $TRIES docker build -t sunshineos-builder . >"$LOG/image.log" 2>&1 || { tail -20 "$LOG/image.log"; die "image build failed"; }
else echo "present"; fi
fix_owner

log "2/4 AUR packages"
[ $CLEAN = 1 ] && export FORCE=1
for t in $(seq $TRIES); do
  ./build-aur.sh >"$LOG/aur.log" 2>&1; rc=$?; fix_owner
  tail -3 "$LOG/aur.log"
  [ $rc = 0 ] && break
  grep -h "FAILED" "$LOG/aur.log" | sort -u
  resolve_dead_deps "$LOG/aur.log" && warn "retrying with the patched PKGBUILD"
  grep -qiE "Could not resolve host|timed out|Connection reset|error: 50[23]" "$LOG/aur.log" && { warn "network trouble, waiting 20 s"; sleep 20; }
  [ $t = $TRIES ] && die "AUR packages failed (see $LOG/aur.log)"
  unset FORCE   # on retries only build what is still missing
done
unset FORCE

log "3/4 Hyprland payload"
if [ $CLEAN = 1 ] || [ ! -d "$PAY/root/etc/skel" ]; then
  retry $TRIES tools/import-end4.sh >"$LOG/import-end4.log" 2>&1 || { tail -20 "$LOG/import-end4.log"; die "tools/import-end4.sh failed"; }
  grep -E "payload repo|skeleton ready|LUA SYNTAX" "$LOG/import-end4.log"
else echo "skeleton present"; fi
if [ $CLEAN = 1 ] || [ ! -d "$PAY/root/opt/illogical-impulse-venv" ]; then
  retry $TRIES tools/build-venv.sh >"$LOG/venv.log" 2>&1 || { tail -20 "$LOG/venv.log"; die "tools/build-venv.sh failed"; }
else echo "venv present"; fi
fix_owner

log "4/4 ISO"
rm -f out/*.iso
for t in $(seq $((TRIES + 2))); do
  ./build.sh >"$LOG/iso.log" 2>&1; fix_owner
  ls out/*.iso >/dev/null 2>&1 && break
  warn "no ISO produced (round $t); last lines:"; tail -5 "$LOG/iso.log" | cut -c1-200
  grep -q "No space left" "$LOG/iso.log" && die "out of disk space"
  missing=$(grep -ohE 'target not found: [^ )]+' "$LOG/iso.log" | awk '{print $NF}' | sort -u | tr '\n' ' ')
  if [ -n "$missing" ]; then
    warn "not in any repo: $missing -> trying the AUR"
    ./build-aur.sh $missing >"$LOG/aur-extra.log" 2>&1; fix_owner
    resolve_dead_deps "$LOG/aur-extra.log" && ./build-aur.sh $missing >>"$LOG/aur-extra.log" 2>&1; fix_owner
  fi
  sleep 10
done
ls out/*.iso >/dev/null 2>&1 || die "no ISO after several rounds (see $LOG/iso.log)"

log "Done"
ls -lh out/*.iso; (cd out && sha256sum ./*.iso | tee SHA256SUMS)
