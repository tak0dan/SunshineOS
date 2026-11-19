#!/usr/bin/env bash
# Publish the ISO from out/ as a GitHub Release. GitHub refuses release files of 2 GiB or more, so the ISO is uploaded in parts
# (default 1900 MiB); the Cloudflare Worker in worker/iso-download.js streams them back as ONE file named
#   SunshineOS_<D>.<M>.<months>.<big>.<small>_<Release|Beta|Testing>_<date>.iso     (naming: see below)
# and the website's release.json lists the parts, so the download button always serves the newest release.
#   tools/release-github.sh                      split + upload (DRY=1 only prints what it would do)
#   (the site updates itself, see docs/RELEASING.md; SITE_DIR=<clone> DOWNLOAD_URL=<Worker URL> still writes SITE_DIR/release.json by hand)
#   JSON_ONLY=1 SITE_DIR=... DOWNLOAD_URL=... tools/release-github.sh                       only rewrite release.json from the release
#   ISO=/path/to/file.iso tools/release-github.sh   publish that file instead of the newest ISO in out/
# Needs: gh (logged in), rsync not required.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=${GH_REPO:-tak0dan/SunshineOS}; PART_MIB=${PART_MIB:-1900}
iso=${ISO:-$(ls -t out/*.iso 2>/dev/null | head -1)}; [ -n "$iso" ] && [ -f "$iso" ] || { echo "no ISO in out/ (run ./make-iso.sh, or give ISO=/path/to.iso)"; exit 1; }
name=$(basename "$iso"); ver=$(sed -E 's/^sunshineos-([0-9.]+)-.*/\1/' <<<"$name")
# Release name: SunshineOS_<D>.<M>.<months>.<big>.<small>_<Release|Beta|Testing>_<date>.iso
#   <D>.<M>     day.month of the numbering anchor date          (ANCHOR file, kept local and out of git; SUNSHINE_ANCHOR=YYYY-MM-DD overrides)
#   <months>    whole months from the anchor date to the release date
#   <big>.<small>  generation counters from the VERSION file (or SUNSHINE_VERSION)
#   channel     Release (default), Beta or Testing (SUNSHINE_CHANNEL); only Release files are served by the download button
#   <date>      release date, today unless RELEASE_DATE=YYYY-MM-DD is set
# Edition: Sol is the main distribution (default, no tag in the file name); other editions are branches such as Sirius (declarative).
# Each edition has its own version counter: VERSION for Sol, VERSION.<edition in lower case> for the others (or SUNSHINE_VERSION).
edition=${SUNSHINE_EDITION:-Sol}; [[ "$edition" =~ ^[A-Za-z]+$ ]] || { echo "SUNSHINE_EDITION must be letters only (Sol, Sirius, ...)"; exit 1; }
vfile=VERSION; [ "$edition" = Sol ] || vfile="VERSION.${edition,,}"
gen=${SUNSHINE_VERSION:-$(tr -d '[:space:]' < "$vfile")}
channel=${SUNSHINE_CHANNEL:-Release}; case "$channel" in Release|Beta|Testing) ;; *) echo "SUNSHINE_CHANNEL must be Release, Beta or Testing"; exit 1;; esac
day=${RELEASE_DATE:-$(date +%F)}
anchor=${SUNSHINE_ANCHOR:-$(tr -d '[:space:]' < ANCHOR 2>/dev/null || true)}
[ "$channel" != Release ] || [ "$edition" != Sol ] || [ -n "$anchor" ] || { echo "no numbering anchor: put a date (YYYY-MM-DD) in the ANCHOR file or set SUNSHINE_ANCHOR"; exit 1; }
# Only a Sol Release uses the anchor scheme; everything else is numbered in plain order (0.1, 0.2, ...)
if [ "$channel" != Release ] || [ "$edition" != Sol ]; then rel=$gen; else rel=$(python3 - "$anchor" "$day" "$gen" <<'PY'
import sys,datetime
a=datetime.date.fromisoformat(sys.argv[1]); r=datetime.date.fromisoformat(sys.argv[2]); gen=sys.argv[3]
m=(r.year-a.year)*12+(r.month-a.month)-(1 if r.day<a.day else 0)
if m<0: sys.exit("the release date is before the anchor date")
print("%d.%d.%d.%s"%(a.day,a.month,m,gen))
PY
) || exit 1; fi
if [ "$edition" = Sol ]; then prefix=SunshineOS; tag="v${rel}-${channel,,}-${day}"; else prefix="SunshineOS-${edition}"; tag="v${rel}-${edition,,}-${channel,,}-${day}"; fi
pub="${prefix}_${rel}_${channel}_${day}.iso"
run() { if [ -n "${DRY:-}" ]; then echo "DRY: $*"; else "$@"; fi; }

if [ -z "${JSON_ONLY:-}" ]; then
  work=out/release-$day; rm -rf "$work"; mkdir -p "$work"
  echo "splitting $name into parts of $PART_MIB MiB ..."
  split -b "${PART_MIB}M" -d -a 1 --numeric-suffixes=1 "$iso" "$work/$pub.part"
  echo "$(sha256sum < "$iso" | cut -d' ' -f1)  $pub" > "$work/$pub.sha256"
  ls -l "$work" | tail -n +2
  run gh release create "$tag" "$work"/* --repo "$REPO" $([ "$channel" = Release ] || echo --prerelease) --title "Sunshine OS $([ "$edition" = Sol ] || echo "$edition ")$rel ($channel, $day)" \
    --notes "Sunshine OS $rel ($channel), released $day. Download it from https://tak0dan.github.io/sunshineos-site/ . The ISO is stored here in parts (GitHub's 2 GiB file limit) and served as one file \`$pub\`; to join the parts by hand: \`cat $pub.part* > $pub\` and check it with \`sha256sum -c $pub.sha256\`."
fi

# The website follows the releases by itself (workflow "release-json" in the site repository, every 15 minutes). Ask it to run right now, so the
# page shows the new release within a minute or two. Best effort: when this fails, the scheduled run does it later.
if [ -z "${DRY:-}" ] && [ -z "${JSON_ONLY:-}" ] && [ -n "${SITE_REPO:-tak0dan/sunshineos-site}" ]; then
  gh workflow run release-json.yml --repo "${SITE_REPO:-tak0dan/sunshineos-site}" >/dev/null 2>&1 && echo "site: release-json workflow started" || echo "site: could not start the workflow (the scheduled run will pick the release up)"
fi

# Optional and no longer needed: write release.json into a local clone of the site by hand (SITE_DIR). The workflow above overwrites it with the same content.
if [ -n "${SITE_DIR:-}" ] && [ -z "${DRY:-}" ]; then
  gh release view "$tag" --repo "$REPO" --json assets > out/.assets.json
  python3 - "$SITE_DIR/release.json" "$rel" "$day" "$pub" "$tag" "${DOWNLOAD_URL:-}" "out/.assets.json" "$(sha256sum < "$iso" | cut -d' ' -f1)" "$channel" "$edition" <<'PY'
import json,sys,os
p,rel,day,pub,tag,dl,assets,sha,channel,edition=sys.argv[1:]
parts=sorted([a for a in json.load(open(assets))["assets"] if ".part" in a["name"]],key=lambda a:a["name"])
if not parts: sys.exit("the release has no parts")
d=json.load(open(p)) if os.path.exists(p) else {"releases":[]}
d["releases"]=[r for r in d["releases"] if r.get("file")!=pub]
d["releases"].insert(0,{"version":rel,"edition":edition,"channel":channel,"date":day,"tag":tag,"file":pub,"size":sum(a["size"] for a in parts),"sha256":sha,
  "url":dl,"parts":[{"url":a["url"],"size":a["size"]} for a in parts]})
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n"); print("updated",p,"-",len(parts),"parts")
PY
fi
echo "release: https://github.com/$REPO/releases/tag/$tag"
