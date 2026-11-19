# Releasing Sunshine OS and how the website follows

The ISO is stored on GitHub Releases in parts (GitHub refuses release files of 2 GiB or more). A Cloudflare Worker joins the parts into one download. The website's download button and the Worker read one file, `release.json`, which lists every release with its parts. **Nobody edits `release.json`**: it is generated from the GitHub releases.

```
build ISO ─► tools/release-github.sh ─► GitHub Release (parts + .sha256)
                                              │
        site repo workflow "release-json" (every 15 minutes, and started by the script)
                                              ▼
                 release.json in the site repo  ─►  download button (page)  and  Cloudflare Worker (one file download)
```

## Publishing a release (the normal way)

1. Bump the counter: `VERSION` for Sol (`VERSION.sirius` for Sirius, and so on). The file name follows from it:
   `SunshineOS_<D>.<M>.<months>.<big>.<small>_<Release|Beta|Testing>_<date>.iso` for Sol (`<D>.<M>` and `<months>` come from the local, git-ignored `ANCHOR` file), `SunshineOS-<Edition>_<version>_<channel>_<date>.iso` for other editions.
2. Build: `ZSTD_LEVEL=15 ./make-iso.sh` (add `FAST=1 ./build.sh` + `test/smoke.sh` for a quick trial first).
3. Check the ISO in a VM (boot, installer, tools) and write the build report in `docs/team/reports/`.
4. Publish: `ISO=out/<file>.iso tools/release-github.sh` (`SUNSHINE_EDITION=Sirius SUNSHINE_CHANNEL=Testing` for other editions; `DRY=1` only prints what would happen).
5. Done. The script starts the site workflow; the page and the download button show the new release a minute or two later. Without that trigger the scheduled run finds it within 15 minutes.

Which release the button serves: the newest **Sol / Release** (by date, then version). Other editions and channels are reachable with `?edition=Sirius&channel=Testing` on the Worker address. Deleting a GitHub release removes it from the site at the next run.

## What the site repository does

- `tools/gen-release-json.py` reads the releases of `tak0dan/SunshineOS` through the GitHub API, takes the parts (`*.iso.partN`) with their sizes and the checksum from `*.iso.sha256`, and writes `release.json` in the format the page and the Worker expect.
- `.github/workflows/release-json.yml` runs it every 15 minutes, on demand (`gh workflow run release-json.yml --repo tak0dan/sunshineos-site`) and on a `sunshine-release` dispatch, and commits the file when it changed. GitHub Pages then publishes it.
- Why not let every visitor's browser ask GitHub directly: the API allows only 60 requests an hour per address without a token, so the list is generated once, with the workflow's own token.

## Declaring an ISO by hand (no GitHub Release needed)

An ISO hosted anywhere can be listed by adding it to `releases/declared.json` in the site repository:

```json
{
  "releases": [
    {
      "file": "SunshineOS_13.4.7.1.7_Release_2026-12-01.iso",
      "parts": ["https://example.org/iso/SunshineOS_13.4.7.1.7_Release_2026-12-01.iso.part1",
                "https://example.org/iso/SunshineOS_13.4.7.1.7_Release_2026-12-01.iso.part2"],
      "sha256": "<64 hex digits>",
      "link": "https://example.org/release-page"
    }
  ]
}
```

- `file` (required) must follow the naming scheme above; edition, channel, version and date are read from it.
- `parts` (required) are `https` URLs in the order they must be joined; a single URL is fine when the ISO is one file. Sizes are read from the hosts (`Content-Length`), so the hosts must answer HEAD requests and allow range requests for resumable downloads.
- `sha256` or `sha256_url` (a file whose first word is the checksum) is optional but recommended; the page shows it.
- `link` (optional) is the page the "All files" link opens. Without it, declared entries have no such link.
- The same rules apply as for the others: the newest Sol / Release wins the button. A declared entry whose `file` equals the name of a GitHub release is ignored in favour of the release. An entry that cannot be read (wrong name, unreachable host) is skipped with a warning in the workflow log and never breaks the others.
- To publish: edit the file in the site repository (it is a normal commit), then wait for the next run or start it: `gh workflow run release-json.yml --repo tak0dan/sunshineos-site`.

## Checking that the page is right

```sh
curl -s https://tak0dan.github.io/sunshineos-site/release.json | python3 -m json.tool | head -30      # newest entry first
curl -sI https://sunshineos-download.sunshineos.workers.dev/ | grep -iE 'content-(length|disposition)'  # file name and size of the download
google-chrome-stable --headless=new --virtual-time-budget=12000 --dump-dom https://tak0dan.github.io/sunshineos-site/ | grep -E 'dlbtntext|dlinfo'
```

`content-length` must equal the size of the ISO file; the button text shows the version and size; the SHA-256 on the page must match `sha256sum` of the ISO.

## When something is wrong

| Symptom | Cause and fix |
|---|---|
| Page still shows the old release | The workflow has not run yet or failed: open the Actions tab of the site repository (`release-json`), or run it by hand. GitHub Pages can take a minute to publish. |
| `release.json` lacks the release | The release has no `*.iso.partN` assets, or the name does not match the scheme (the workflow log lists skipped entries). |
| Download starts but is cut off | The Worker streams the parts from GitHub; look at the Worker log in Cloudflare. Part sizes in `release.json` must be exact (they are read from the real files). |
| API rate limit in a local run of the generator | Set `GITHUB_TOKEN` (for example `GITHUB_TOKEN=$(gh auth token)`); the workflow always has one. |

The Worker (`worker/iso-download.js`) is deployed by hand in the Cloudflare dashboard and only changes when its own code does; a new release never needs a Worker change.
