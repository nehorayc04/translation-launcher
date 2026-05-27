// Cloudflare Worker — proxy for the PRIVATE Hebrew-mod repos.
//
// Holds the GitHub PAT as a server-side secret (env.GITHUB_TOKEN). The
// launcher + website only ever talk to this Worker, so NO token ships
// in any client.
//
// Multi-mod: the first path segment is a mod slug that maps to a private
// GitHub repo. Each mod's payload is the latest GitHub Release of its
// repo (one mod per repo → "latest release" is unambiguous).
//
// Routes (consumed by translation_manager/mod_source.py + the website):
//   GET /<slug>/manifest  -> application/json   (latest release manifest)
//   GET /<slug>/archive   -> application/zip     (the mod archive bytes)
//
// Known slugs:
//   steam-hebrew   -> nehorayc04/steam-hebrew-mods
//   cp2077-hebrew  -> nehorayc04/cp2077-hebrew-mods

const REPOS = {
  "steam-hebrew":  "nehorayc04/steam-hebrew-mods",
  "cp2077-hebrew": "nehorayc04/cp2077-hebrew-mods",
};

export default {
  async fetch(request, env) {
    const parts = new URL(request.url).pathname.split("/").filter(Boolean);

    const repo = REPOS[parts[0]];
    if (!repo) {
      return new Response("not found", { status: 404 });
    }
    if (!env.GITHUB_TOKEN) {
      return new Response("worker misconfigured: GITHUB_TOKEN secret missing", {
        status: 500,
      });
    }

    const gh = {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "User-Agent": "hebrew-mods-proxy",
      "X-GitHub-Api-Version": "2022-11-28",
    };

    // ── Resolve the latest release ──────────────────────────
    const relResp = await fetch(
      `https://api.github.com/repos/${repo}/releases/latest`,
      { headers: { ...gh, Accept: "application/vnd.github+json" } },
    );
    if (!relResp.ok) {
      return new Response(`github releases: ${relResp.status}`, { status: 502 });
    }
    const rel = await relResp.json();
    const assets = Object.fromEntries((rel.assets || []).map((a) => [a.name, a]));

    // ── manifest.json drives everything ─────────────────────
    const manifestAsset = assets["manifest.json"];
    if (!manifestAsset) {
      return new Response("release has no manifest.json asset", { status: 502 });
    }
    const manifest = await (
      await fetch(manifestAsset.url, {
        headers: { ...gh, Accept: "application/octet-stream" },
      })
    ).json();

    // ── GET /<slug>/manifest ────────────────────────────────
    if (parts[1] === "manifest") {
      return Response.json(manifest, { headers: { "Cache-Control": "no-store" } });
    }

    // ── GET /<slug>/archive ─────────────────────────────────
    if (parts[1] === "archive") {
      const archiveAsset = assets[manifest.archive_name];
      if (!archiveAsset) {
        return new Response(
          `release has no asset '${manifest.archive_name}'`,
          { status: 502 },
        );
      }
      const a = await fetch(archiveAsset.url, {
        headers: { ...gh, Accept: "application/octet-stream" },
      });
      return new Response(a.body, {
        status: a.status,
        headers: {
          "Content-Type": "application/zip",
          "Content-Length": String(archiveAsset.size),
          // A real filename so browser downloads from the website land
          // as e.g. cyberpunk_hebrew_translation.zip, not "archive".
          "Content-Disposition": `attachment; filename="${manifest.archive_name}"`,
          "Cache-Control": "no-store",
        },
      });
    }

    return new Response("not found", { status: 404 });
  },
};
