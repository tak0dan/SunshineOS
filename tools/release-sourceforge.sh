#!/usr/bin/env bash
# Publish the ISO from out/ to SourceForge as ONE file (no size limit), then check that the public download link works.
#   rsync over SSH to frs.sourceforge.net:/home/frs/project/<project>/releases/<version>/<iso>
# The website (tak0dan.github.io/sunshineos-site) reads release.json from its own repo, so with SITE_DIR=<clone of that repo>
# this script also adds the new release to SITE_DIR/release.json (commit and push it yourself).
# Needs an SSH key registered at sourceforge.net/auth/shell_services (SF_KEY, default ~/.ssh/sourceforge_sunshineos).
#   tools/release-sourceforge.sh            DRY=1 only prints; SF_USER / SF_PROJECT / SF_KEY / SITE_DIR override the defaults
set -euo pipefail
cd "$(dirname "$0")/.."
SF_USER=${SF_USER:-tak0}; SF_PROJECT=${SF_PROJECT:-sunshinelinux}; SF_KEY=${SF_KEY:-$HOME/.ssh/sourceforge_sunshineos}
iso=$(ls -t out/*.iso 2>/dev/null | head -1); [ -n "$iso" ] || { echo "no ISO in out/ (run ./make-iso.sh)"; exit 1; }
name=$(basename "$iso"); ver=$(sed -E 's/^sunshineos-([0-9.]+)-.*/\1/' <<<"$name"); arch=$(sed -E 's/^sunshineos-[0-9.]+-(.*)\.iso$/\1/' <<<"$name")
# published name: SunshineOS_<version>_Release_<date>.iso, version from the VERSION file (or SUNSHINE_VERSION), date = build date.
# The website picks the newest file matching SunshineOS_*_Release_*.iso.
rel=${SUNSHINE_VERSION:-$(tr -d '[:space:]' < VERSION)}; day=${ver//./-}
pub="SunshineOS_${rel}_Release_${day}.iso"
size=$(stat -c %s "$iso"); sha=$(sha256sum "$iso" | cut -d' ' -f1)
echo "$sha  $pub" > "out/$pub.sha256"
dest="/home/frs/project/$SF_PROJECT/releases/$ver"
url="https://downloads.sourceforge.net/project/$SF_PROJECT/releases/$ver/$pub"
ssh_cmd="ssh -i $SF_KEY -o IdentitiesOnly=yes -o BatchMode=yes"
run() { if [ -n "${DRY:-}" ]; then echo "DRY: $*"; else "$@"; fi; }

echo "uploading $name as $pub ($(du -h "$iso" | cut -f1)) to $SF_USER@frs.sourceforge.net:$dest (resumes if interrupted) ..."
# create the folders first over SFTP (the rsync server does not reliably support --mkpath); existing folders are fine
printf -- '-mkdir releases\n-mkdir releases/%s\n' "$ver" > "out/.sftp-mkdir"
run sftp -i "$SF_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -b "out/.sftp-mkdir" "$SF_USER@frs.sourceforge.net:/home/frs/project/$SF_PROJECT" >/dev/null 2>&1 || true
run rsync -av --partial --progress -e "$ssh_cmd" "$iso" "$SF_USER@frs.sourceforge.net:$dest/$pub"
run rsync -a -e "$ssh_cmd" "out/$pub.sha256" "$SF_USER@frs.sourceforge.net:$dest/$pub.sha256"

if [ -z "${DRY:-}" ]; then
  echo "checking the public link (SourceForge needs a little while to publish new files) ..."
  ok=0
  for i in $(seq 40); do
    h=$(curl -s -L -r 0-0 -D - -o /dev/null "$url" || true)
    if grep -qi '^content-range: bytes 0-0/'"$size" <<<"$h"; then ok=1; break; fi; sleep 15
  done
  [ $ok = 1 ] || { echo "the link does not serve the expected $size bytes yet: $url"; exit 1; }
  grep -qi '^content-disposition: attachment' <<<"$h" && echo "link ok: serves the file as a download ($size bytes)"
fi

if [ -n "${SITE_DIR:-}" ]; then
  python3 - "$SITE_DIR/release.json" "$rel" "$day" "$ver" "$pub" "$size" "$sha" "$url" <<'PY'
import json,sys,os
p,rel,day,folder,name,size,sha,url=sys.argv[1:]
d=json.load(open(p)) if os.path.exists(p) else {"releases":[]}
d["releases"]=[r for r in d["releases"] if r["file"]!=name]
d["releases"].insert(0,{"version":rel,"date":day,"dir":"releases/"+folder,"file":name,"size":int(size),"sha256":sha,"url":url})
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n")
print("updated",p)
PY
fi
echo "download link: $url"
