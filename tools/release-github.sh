#!/usr/bin/env bash
# Publish the ISO from out/ as a GitHub Release. GitHub refuses release files of 2 GiB or more, so the ISO is uploaded in parts
# (default 1900 MiB); the Cloudflare Worker in worker/iso-download.js streams them back as ONE file named
#   SunshineOS_<version>_Release_<date>.iso        (version from the VERSION file or SUNSHINE_VERSION, date = build date)
# and the website's release.json lists the parts, so the download button always serves the newest release.
#   tools/release-github.sh                      split + upload (DRY=1 only prints what it would do)
#   SITE_DIR=<clone of the site repo> DOWNLOAD_URL=<Worker URL> tools/release-github.sh     also write SITE_DIR/release.json
#   JSON_ONLY=1 SITE_DIR=... DOWNLOAD_URL=... tools/release-github.sh                       only rewrite release.json from the release
# Needs: gh (logged in), rsync not required.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=${GH_REPO:-tak0dan/SunshineOS}; PART_MIB=${PART_MIB:-1900}
iso=$(ls -t out/*.iso 2>/dev/null | head -1); [ -n "$iso" ] || { echo "no ISO in out/ (run ./make-iso.sh)"; exit 1; }
name=$(basename "$iso"); ver=$(sed -E 's/^sunshineos-([0-9.]+)-.*/\1/' <<<"$name")
rel=${SUNSHINE_VERSION:-$(tr -d '[:space:]' < VERSION)}; day=${ver//./-}
pub="SunshineOS_${rel}_Release_${day}.iso"; tag="v${rel}-${day}"
run() { if [ -n "${DRY:-}" ]; then echo "DRY: $*"; else "$@"; fi; }

if [ -z "${JSON_ONLY:-}" ]; then
  work=out/release-$day; rm -rf "$work"; mkdir -p "$work"
  echo "splitting $name into parts of $PART_MIB MiB ..."
  split -b "${PART_MIB}M" -d -a 1 --numeric-suffixes=1 "$iso" "$work/$pub.part"
  echo "$(sha256sum < "$iso" | cut -d' ' -f1)  $pub" > "$work/$pub.sha256"
  ls -l "$work" | tail -n +2
  run gh release create "$tag" "$work"/* --repo "$REPO" --title "Sunshine OS $rel ($day)" \
    --notes "Sunshine OS $rel, built $day. Download it from https://tak0dan.github.io/sunshineos-site/ . The ISO is stored here in parts (GitHub's 2 GiB file limit) and served as one file \`$pub\`; to join the parts by hand: \`cat $pub.part* > $pub\` and check it with \`sha256sum -c $pub.sha256\`."
fi

if [ -n "${SITE_DIR:-}" ] && [ -z "${DRY:-}" ]; then
  gh release view "$tag" --repo "$REPO" --json assets > out/.assets.json
  python3 - "$SITE_DIR/release.json" "$rel" "$day" "$pub" "$tag" "${DOWNLOAD_URL:-}" "out/.assets.json" "$(sha256sum < "$iso" | cut -d' ' -f1)" <<'PY'
import json,sys,os
p,rel,day,pub,tag,dl,assets,sha=sys.argv[1:]
parts=sorted([a for a in json.load(open(assets))["assets"] if ".part" in a["name"]],key=lambda a:a["name"])
if not parts: sys.exit("the release has no parts")
d=json.load(open(p)) if os.path.exists(p) else {"releases":[]}
d["releases"]=[r for r in d["releases"] if r.get("file")!=pub]
d["releases"].insert(0,{"version":rel,"date":day,"tag":tag,"file":pub,"size":sum(a["size"] for a in parts),"sha256":sha,
  "url":dl,"parts":[{"url":a["url"],"size":a["size"]} for a in parts]})
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n"); print("updated",p,"-",len(parts),"parts")
PY
fi
echo "release: https://github.com/$REPO/releases/tag/$tag"
