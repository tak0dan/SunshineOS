#!/usr/bin/env bash
# Publishes the Sunshine tools to the tools repository (default tak0dan/sunshine-tools): the files are committed there (bin/, lib/, share/ ...
# laid out as they are installed) and a signed release `tools` is made, which `sunshine-toolsync` on every Sunshine OS system pulls from.
#   tools/publish-tools.sh            build the release, commit + push the repository, replace the release assets
#   tools/publish-tools.sh --dry      only build into /tmp and show what would be published
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=${SUNSHINE_TOOLS_REPO:-tak0dan/sunshine-tools}; TAG=tools
WORK=${SUNSHINE_TOOLS_CLONE:-$HOME/sunshineos-build/scratch/tools}
GH=${SUNSHINE_SIGNING_HOME:-$HOME/sunshineos-build/signing}; KEY=$(cat "$GH/key-fingerprint")
DRY=0; [ "${1:-}" = --dry ] && DRY=1
VERSION=$(date +%Y.%m.%d).$(git rev-list --count HEAD)
S=$(mktemp -d); trap 'rm -rf "$S"' EXIT; mkdir -p "$S/files"
# overlay/system is canonical; the profile holds the tools that exist only in the image (installer, welcome, ...)
for root in profile/airootfs overlay/system; do
  for sub in usr/local/bin usr/local/lib/sunshine usr/share/sunshine/i18n usr/share/sunshine/migrations usr/share/sunshine/logo-anim usr/share/libalpm/hooks usr/share/applications; do
    [ -d "$root/$sub" ] || continue
    (cd "$root" && find "$sub" -type f \( -path 'usr/local/bin/sunshine-*' -o -path 'usr/local/lib/sunshine/*' -o -path 'usr/share/sunshine/i18n/*' -o -path 'usr/share/sunshine/migrations/*' -o -path 'usr/share/sunshine/logo-anim/*' -o -path 'usr/share/libalpm/hooks/*sunshine-*' -o -path 'usr/share/applications/sunshine-*.desktop' \) ! -name '*.pyc' ! -path '*__pycache__*') | while read -r f; do
      mkdir -p "$S/files/$(dirname "$f")"; cp -p "$root/$f" "$S/files/$f"
    done
  done
  for pl in "$root"/usr/share/plasma/plasmoids/com.sunshineos.* "$root"/usr/share/plasma/look-and-feel/com.sunshineos.*; do
    [ -d "$pl" ] || continue; rel=${pl#"$root"/}; mkdir -p "$S/files/$(dirname "$rel")"; cp -a "$pl" "$S/files/$(dirname "$rel")/"
  done
  [ -f "$root/usr/share/sunshine/catalogue.toml" ] && { mkdir -p "$S/files/usr/share/sunshine"; cp -p "$root/usr/share/sunshine/catalogue.toml" "$S/files/usr/share/sunshine/"; }
done
python3 - "$S" "$VERSION" <<'EOF'
import hashlib, json, os, sys
root, version = sys.argv[1], sys.argv[2]
files = {}
base = os.path.join(root, "files")
for d, _, fs in os.walk(base):
    for f in fs:
        p = os.path.join(d, f); rel = os.path.relpath(p, base)
        if os.path.islink(p): continue
        files[rel] = {"sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "mode": "755" if (os.access(p, os.X_OK) or rel.startswith("usr/local/bin/") or rel.startswith("usr/share/sunshine/migrations/")) else "644"}
json.dump({"version": version, "files": files}, open(os.path.join(root, "manifest.json"), "w"), indent=1, sort_keys=True)
print(len(files), "files")
EOF
tar -C "$S/files" --owner=0 --group=0 -czf "$S/sunshine-tools.tar.gz" .
gpg --homedir "$GH" --batch --yes --detach-sign --no-armor --local-user "$KEY" -o "$S/manifest.json.sig" "$S/manifest.json" 2>/dev/null
gpg --homedir "$GH" --batch --yes --detach-sign --no-armor --local-user "$KEY" -o "$S/sunshine-tools.tar.gz.sig" "$S/sunshine-tools.tar.gz" 2>/dev/null
echo "version $VERSION: $(du -h "$S/sunshine-tools.tar.gz" | cut -f1)"
[ $DRY = 1 ] && { cp -r "$S" /tmp/sunshine-tools-dry; echo "dry run: /tmp/sunshine-tools-dry"; exit 0; }

gh repo view "$REPO" >/dev/null 2>&1 || gh repo create "$REPO" --public --description "Tools of Sunshine OS: rescue, doctor, update, gaming, kernel, desktops. Pulled by sunshine-update (sunshine-toolsync)." >/dev/null
if [ ! -d "$WORK/.git" ]; then rm -rf "$WORK"; mkdir -p "$(dirname "$WORK")"; git clone -q "https://github.com/$REPO.git" "$WORK" 2>/dev/null || { mkdir -p "$WORK"; git -C "$WORK" init -q -b main; git -C "$WORK" remote add origin "https://github.com/$REPO.git"; }; fi
(cd "$WORK" && git ls-files -z | xargs -0 -r rm -f; find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +)
cp -a "$S/files/." "$WORK/"; cp "$S/manifest.json" "$WORK/manifest.json"
[ -f docs/TOOLS-README.md ] && cp docs/TOOLS-README.md "$WORK/README.md"
(cd "$WORK" && git add -A && { git diff --cached --quiet || git commit -q -m "tools $VERSION" ; } && git push -q -u origin HEAD:main 2>&1 | tail -1)
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  gh release view "$TAG" --repo "$REPO" --json assets --jq '.assets[].name' | while read -r a; do gh release delete-asset "$TAG" "$a" --repo "$REPO" -y; done
else gh release create "$TAG" --repo "$REPO" --title "Sunshine tools" --notes "Signed tool release pulled by sunshine-toolsync. Replaced on every publish." --latest=false; fi
gh release upload "$TAG" "$S/manifest.json" "$S/manifest.json.sig" "$S/sunshine-tools.tar.gz" "$S/sunshine-tools.tar.gz.sig" --repo "$REPO" --clobber
echo "published $VERSION: https://github.com/$REPO"
