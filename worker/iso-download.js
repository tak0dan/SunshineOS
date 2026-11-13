// Cloudflare Worker: serves the newest Sunshine OS ISO as ONE file.
// GitHub Releases refuse files of 2 GiB or more, so the ISO is stored there in parts. This Worker looks up the newest
// SunshineOS_<version>_Release_<date>.iso in the website's release.json and streams its parts back to back as a single download
// (nothing is stored or buffered here; the join costs no extra time). Range requests work, so downloads can be resumed.
//
// release.json entry: { "file": "SunshineOS_1.0_Release_2026-11-12.iso", "date": "...", "version": "...", "size": N,
//                       "parts": [ { "url": "https://github.com/.../releases/download/<tag>/<file>.part1", "size": N }, ... ] }
const RELEASES = "https://tak0dan.github.io/sunshineos-site/release.json";
const NAME = /^SunshineOS_.+_Release_.+\.iso$/;

async function newest(ctx) {
  const r = await fetch(RELEASES, { cf: { cacheTtl: 120, cacheEverything: true } });
  if (!r.ok) throw new Error("release.json: HTTP " + r.status);
  const list = ((await r.json()).releases || []).filter(x => NAME.test(x.file || "") && (x.parts || []).length);
  list.sort((a, b) => String(b.date).localeCompare(String(a.date)) ||
    String(b.version).localeCompare(String(a.version), undefined, { numeric: true }));
  if (!list.length) throw new Error("no release with parts");
  return list[0];
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET" && request.method !== "HEAD") return new Response("Method not allowed", { status: 405 });
    let rel;
    try { rel = await newest(ctx); } catch (e) { return new Response("No ISO is published yet (" + e.message + ")", { status: 503 }); }
    const total = rel.parts.reduce((n, p) => n + p.size, 0);
    const headers = {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": 'attachment; filename="' + rel.file + '"',
      "Accept-Ranges": "bytes",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    };
    // Range: only a single "bytes=a-b" range is supported (what browsers and curl use to resume)
    let start = 0, end = total - 1, status = 200;
    const m = /^bytes=(\d*)-(\d*)$/.exec(request.headers.get("Range") || "");
    if (m && (m[1] !== "" || m[2] !== "")) {
      if (m[1] === "") { start = Math.max(0, total - Number(m[2])); }
      else { start = Number(m[1]); if (m[2] !== "") end = Math.min(end, Number(m[2])); }
      if (start > end || start >= total) return new Response("Range not satisfiable", { status: 416, headers: { "Content-Range": "bytes */" + total } });
      status = 206; headers["Content-Range"] = "bytes " + start + "-" + end + "/" + total;
    }
    headers["Content-Length"] = String(end - start + 1);
    if (request.method === "HEAD") return new Response(null, { status, headers });

    // which slices of which parts make up [start, end]
    const slices = []; let off = 0;
    for (const p of rel.parts) {
      const a = Math.max(start, off), b = Math.min(end, off + p.size - 1);
      if (a <= b) slices.push({ url: p.url, from: a - off, to: b - off, whole: a === off && b === off + p.size - 1 });
      off += p.size;
    }
    // The parts are piped into one IdentityTransformStream with pipeTo(): the runtime moves the bytes natively, so no JavaScript runs per
    // chunk (a JS read/enqueue loop exhausts the free plan's CPU budget and the download is cut off after a few MB or a few hundred MB).
    const { readable, writable } = new IdentityTransformStream();
    ctx.waitUntil((async () => {
      try {
        for (const s of slices) {
          const r = await fetch(s.url, { headers: s.whole ? {} : { Range: "bytes=" + s.from + "-" + s.to }, redirect: "follow" });
          if (!r.ok) throw new Error("part answered HTTP " + r.status);
          await r.body.pipeTo(writable, { preventClose: true });
        }
        await writable.close();
      } catch (e) { try { await writable.abort(e); } catch (_) {} }
    })());
    return new Response(readable, { status, headers });
  },
};
