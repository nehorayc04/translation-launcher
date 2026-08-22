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
//   steam-hebrew   -> hebrew-translation-hub/steam-hebrew-mods
//   cp2077-hebrew  -> hebrew-translation-hub/cp2077-hebrew-mods

const REPOS = {
  "steam-hebrew":     "hebrew-translation-hub/steam-hebrew-mods",
  "cp2077-hebrew":    "hebrew-translation-hub/cp2077-hebrew-mods",
  "spiderman2-hebrew": "hebrew-translation-hub/spiderman2-hebrew-mods",
  "watchdogs2-hebrew": "hebrew-translation-hub/watchdogs2-hebrew-mods",
  "anno1800-hebrew":  "hebrew-translation-hub/anno1800-hebrew-mods",
  "godofwar-ragnarok-hebrew": "hebrew-translation-hub/godofwar-ragnarok-hebrew-mods",
  "virtualdj-hebrew": "hebrew-translation-hub/virtualdj-hebrew-mods",
  "witcher3-hebrew": "hebrew-translation-hub/witcher3-hebrew-mods",
  "gtav-hebrew":     "hebrew-translation-hub/gtav-hebrew-mods",
  "borderless-gaming-hebrew": "hebrew-translation-hub/borderless-gaming-hebrew-mods",
  "signalrgb-hebrew": "hebrew-translation-hub/signalrgb-hebrew-mods",
  "hogwarts-legacy-hebrew": "hebrew-translation-hub/hogwarts-legacy-hebrew-mods",
  "rdr2-hebrew":      "hebrew-translation-hub/rdr2-hebrew-mods",
  "corsair-cove-hebrew": "hebrew-translation-hub/corsair-cove-hebrew-mods",
};

// The website's "offline package" builder fetches these manifests + archives
// from the BROWSER (it assembles the store client-side), which is cross-origin
// to this worker - without CORS the browser blocks it before the request is even
// sent. Everything served here is already public (the launcher fetches it with no
// credentials), so a permissive origin costs nothing and adds no new exposure.
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Max-Age": "86400",
};

// The ONE-FILE offline installer is assembled in the browser by appending the
// translations to the real launcher setup. GitHub's release CDN sends NO
// Access-Control-Allow-Origin, so a page cannot fetch the setup itself - this
// route streams it with CORS instead. The URL is NOT taken from the caller
// (that would be an open proxy / SSRF): it is read from our own public
// /api/launcher and then hard-validated against this exact repo.
const LAUNCHER_REPO = "hebrew-translation-hub/translation-launcher";
const LAUNCHER_INFO = "https://hebrew-translation-hub.com/api/launcher";

async function serveLauncherSetup() {
  let info;
  try {
    const r = await fetch(LAUNCHER_INFO, { headers: { "User-Agent": "hebrew-mods-proxy" } });
    if (!r.ok) return new Response(`launcher info: ${r.status}`, { status: 502, headers: CORS });
    info = await r.json();
  } catch {
    return new Response("launcher info unreachable", { status: 502, headers: CORS });
  }
  const url = String(info?.downloadUrl || "");
  const ok = url.startsWith(`https://github.com/${LAUNCHER_REPO}/releases/download/`);
  if (!ok) return new Response("launcher url not allowed", { status: 502, headers: CORS });

  const a = await fetch(url, { headers: { "User-Agent": "hebrew-mods-proxy" }, redirect: "follow" });
  if (!a.ok) return new Response(`setup: ${a.status}`, { status: 502, headers: CORS });
  return new Response(a.body, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      ...(a.headers.get("content-length") ? { "Content-Length": a.headers.get("content-length") } : {}),
      "Content-Disposition": `attachment; filename="${info?.filename || "TranslationManager-Setup.exe"}"`,
      "Cache-Control": "no-store",
      "X-Launcher-Version": String(info?.version || ""),
      // so the page can read the version/size it just streamed
      "Access-Control-Expose-Headers": "Content-Length, X-Launcher-Version",
      ...CORS,
    },
  });
}

// ── pool query dispatcher — backed by TURSO (libSQL, SQLite, 5GB free) ────
// POST /pool/query   header x-pool-secret: <POOL_SECRET>
//   body {sql, params}                 -> {results, meta}
//   body {batch: [{sql, params}, ...]} -> {results: [{results, meta}, ...]}
// The community /translate POOL lives on Turso (TURSO_URL + TURSO_TOKEN Worker
// secrets) — free 5GB + 25M writes/mo, vs D1's 100K writes/day. Same SQLite
// dialect, so api/translate.ts + the python importer are unchanged (they still
// POST {sql,params}/{batch} here). A D1 binding may remain in wrangler.toml but
// is unused. Turso's HTTP "pipeline" protocol returns typed cells — coerced
// back to plain JSON here so callers see the same {results,meta} shape as D1.

// One param -> a typed Turso arg.
function tursoArg(v) {
  if (v === null || v === undefined) return { type: "null" };
  if (typeof v === "number") return Number.isInteger(v)
    ? { type: "integer", value: String(v) } : { type: "float", value: v };
  if (typeof v === "boolean") return { type: "integer", value: v ? "1" : "0" };
  return { type: "text", value: String(v) };
}
// One typed cell -> a plain JS value.
function tursoCell(c) {
  if (!c || c.type === "null") return null;
  if (c.type === "integer") return Number(c.value);
  if (c.type === "float")   return typeof c.value === "number" ? c.value : Number(c.value);
  return c.value; // text / blob
}
// A pipeline execute result -> {results:[rowObj...], meta:{changes,last_row_id}}.
function tursoShape(execResult) {
  const cols = (execResult.cols || []).map((c) => c.name);
  const rows = (execResult.rows || []).map((row) => {
    const o = {};
    row.forEach((cell, i) => { o[cols[i]] = tursoCell(cell); });
    return o;
  });
  return {
    results: rows,
    meta: {
      changes: Number(execResult.affected_row_count || 0),
      last_row_id: execResult.last_insert_rowid != null ? Number(execResult.last_insert_rowid) : 0,
    },
  };
}

// Run N statements in ONE Turso pipeline request. Returns per-statement shapes.
async function tursoRun(env, stmts) {
  const base = String(env.TURSO_URL || "").replace(/\/+$/, "").replace(/^libsql:\/\//, "https://");
  const requests = stmts.map((s) => ({
    type: "execute",
    stmt: { sql: s.sql, args: (s.params || []).map(tursoArg) },
  }));
  requests.push({ type: "close" });
  const r = await fetch(base + "/v2/pipeline", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.TURSO_TOKEN}` },
    body: JSON.stringify({ requests }),
  });
  const text = await r.text();
  let j;
  try { j = JSON.parse(text); } catch { throw new Error(`turso: bad JSON (${r.status})`); }
  if (!r.ok) throw new Error(`turso: HTTP ${r.status} ${text.slice(0, 300)}`);
  const out = [];
  const results = j.results || [];
  for (let i = 0; i < stmts.length; i++) {
    const res = results[i];
    if (!res) throw new Error("turso: missing result");
    if (res.type === "error") throw new Error(res.error?.message || "turso error");
    out.push(tursoShape(res.response.result));
  }
  return out;
}

async function handlePool(request, env, parts) {
  const j = (obj, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });

  if (!env.TURSO_URL || !env.TURSO_TOKEN) return j({ error: "pool db not configured (TURSO_URL/TURSO_TOKEN)" }, 500);
  if (!env.POOL_SECRET) return j({ error: "worker misconfigured: POOL_SECRET missing" }, 500);
  if ((request.headers.get("x-pool-secret") || "") !== env.POOL_SECRET) {
    return j({ error: "unauthorized" }, 401);
  }
  if (request.method !== "POST") return j({ error: "method not allowed" }, 405);
  if (parts[1] !== "query") return j({ error: "not found" }, 404);

  let body;
  try { body = await request.json(); } catch { return j({ error: "bad json" }, 400); }

  try {
    if (Array.isArray(body.batch)) {
      const shaped = await tursoRun(env, body.batch);
      return j({ results: shaped });
    }
    if (typeof body.sql !== "string") return j({ error: "missing sql" }, 400);
    const [shaped] = await tursoRun(env, [{ sql: body.sql, params: body.params }]);
    return j({ results: shaped.results, meta: shaped.meta });
  } catch (e) {
    console.error("pool error:", e && e.message ? e.message : e);
    return j({ error: String(e && e.message ? e.message : e) }, 500);
  }
}

// ── /cc/* — Community-Compute queue (Turso, isolated cc_* tables). ──────────
// BYOK volunteer devices pull work + submit Hebrew; SEPARATE from the site's
// Supabase/AUTH (never touched). Per-worker lease + LIVE cc_config (5-min
// heartbeat). Device routes gated by CC_SECRET (soft app secret embedded in the
// app); operator ops (config-set / block) by CC_ADMIN_SECRET. No PII, no IP, no
// key stored. Returned Hebrew is UNTRUSTED -> the operator's collect step runs
// the QA gate + admin approval before anything ships.
// Rows-read guard: `stats` and `detail` are POLLED by several clients and each
// one is a full pass over cc_lines. Module scope survives between requests on a
// Worker isolate, so all callers in a window share ONE query. Deliberately short
// - stale numbers are fine here, a blown quota is not.
const CC_CACHE = {};
const CC_CACHE_MS = 20000;

// Two layers on purpose: module scope is the fast path but is per-ISOLATE, and
// Cloudflare spreads requests across isolates - measured, two consecutive calls
// missed each other. The Cache API is shared across the whole colo, so every
// client in a region really does collapse onto one query.
const CC_CACHE_KEY = (k) => new Request("https://cc-cache.local/" + k);

async function ccCacheGet(key) {
  const e = CC_CACHE[key];
  if (e && (Date.now() - e.t) < CC_CACHE_MS) return e.v;
  try {
    const r = await caches.default.match(CC_CACHE_KEY(key));
    if (r) {
      const v = await r.json();
      CC_CACHE[key] = { t: Date.now(), v };
      return v;
    }
  } catch { /* cache unavailable -> just query */ }
  return null;
}

async function ccCachePut(key, value) {
  CC_CACHE[key] = { t: Date.now(), v: value };
  try {
    await caches.default.put(CC_CACHE_KEY(key), new Response(JSON.stringify(value), {
      headers: { "Content-Type": "application/json",
                 "Cache-Control": `max-age=${Math.round(CC_CACHE_MS / 1000)}` } }));
  } catch { /* best effort */ }
  return value;
}

async function ccConfig(env) {
  const [c] = await tursoRun(env, [{ sql: "SELECT k, v FROM cc_config" }]);
  const cfg = { heartbeat_seconds: 300, lease_ttl_seconds: 1200, batch_size: 50, max_inflight: 300 };
  for (const row of c.results) cfg[row.k] = Number(row.v);
  return cfg;
}

async function handleCc(request, env, parts) {
  const j = (obj, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
  if (!env.TURSO_URL || !env.TURSO_TOKEN) return j({ error: "cc db not configured" }, 500);
  if (!env.CC_SECRET) return j({ error: "worker misconfigured: CC_SECRET missing" }, 500);

  const op = parts[1] || "";
  const isAdminOp = (op === "config" && request.method === "POST") || op === "block" || op === "unblock" || op === "detail";
  const secret = request.headers.get("x-cc-secret") || "";
  if (isAdminOp) {
    if (!env.CC_ADMIN_SECRET || secret !== env.CC_ADMIN_SECRET) return j({ error: "unauthorized (admin)" }, 401);
  } else if (secret !== env.CC_SECRET && !(env.CC_ADMIN_SECRET && secret === env.CC_ADMIN_SECRET)) {
    return j({ error: "unauthorized" }, 401);
  }

  const now = Math.floor(Date.now() / 1000);
  let body = {};
  if (request.method === "POST") { try { body = await request.json(); } catch { return j({ error: "bad json" }, 400); } }
  const w = String(body.worker || "");

  try {
    if (op === "stats") {
      // Cached: every COUNT here is a full pass over cc_lines (~185k rows), and
      // this is POLLED - a dashboard, the website pusher and every volunteer app
      // all ask for the same number. One query per window serves them all; the
      // figures move slowly and each consumer already shows its own age.
      const hit = await ccCacheGet("stats");
      if (hit) return j(hit);
      const cfg = await ccConfig(env);
      const active = now - cfg.lease_ttl_seconds;
      const [s] = await tursoRun(env, [{ sql:
        "SELECT (SELECT COUNT(*) FROM cc_lines WHERE status='open' AND collected=0) AS open," +
        "(SELECT COUNT(*) FROM cc_lines WHERE status='claimed') AS claimed," +
        "(SELECT COUNT(*) FROM cc_lines WHERE status='done' AND collected=0) AS done," +
        "(SELECT COUNT(*) FROM cc_workers WHERE last_seen>=? AND blocked=0) AS workers," +
        "(SELECT COUNT(DISTINCT game) FROM cc_lines WHERE collected=0) AS games", params: [active] }]);
      return j(await ccCachePut("stats", { ...s.results[0], config: cfg }));
    }

    // Operator-only breakdown for a fleet dashboard: which game(s) are active and which devices
    // are working on them. Not exposed to the (soft) device secret -- admin-gated like config/block.
    if (op === "detail") {
      const hitD = await ccCacheGet("detail");
      if (hitD) return j(hitD);
      const cfg = await ccConfig(env);
      const active = now - cfg.lease_ttl_seconds;
      const [games, workers, byWorker] = await tursoRun(env, [
        { sql:
          "SELECT game," +
          " SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open," +
          " SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) AS claimed," +
          " SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done" +
          " FROM cc_lines WHERE collected=0 GROUP BY game ORDER BY game" },
        { sql: "SELECT id, platform, last_seen, done FROM cc_workers WHERE last_seen>=? AND blocked=0 ORDER BY last_seen DESC",
          params: [active] },
        { sql: "SELECT worker_id, game, COUNT(*) AS n FROM cc_lines WHERE status='claimed' AND worker_id IS NOT NULL GROUP BY worker_id, game" },
      ]);
      const gameByWorker = {};
      for (const r of byWorker.results) {
        const cur = gameByWorker[r.worker_id];
        if (!cur || Number(r.n) > cur.n) gameByWorker[r.worker_id] = { game: r.game, n: Number(r.n) };
      }
      const outWorkers = workers.results.map((w2) => ({
        id: w2.id, platform: w2.platform, last_seen: w2.last_seen, done: w2.done,
        game: (gameByWorker[w2.id] && gameByWorker[w2.id].game) || null,
        claimed: (gameByWorker[w2.id] && gameByWorker[w2.id].n) || 0,
      }));
      return j(await ccCachePut("detail",
        { games: games.results, workers: outWorkers, config: cfg }));
    }

    if (op === "config") {
      if (request.method !== "POST") return j({ config: await ccConfig(env) });
      const set = body.set || {};
      const allow = { heartbeat_seconds: [60, 3600], lease_ttl_seconds: [120, 86400], batch_size: [1, 200], max_inflight: [10, 5000] };
      const stmts = [];
      for (const [k, v] of Object.entries(set)) {
        if (!(k in allow)) continue;
        const n = Math.max(allow[k][0], Math.min(allow[k][1], Math.floor(Number(v))));
        stmts.push({ sql: "INSERT INTO cc_config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", params: [k, n] });
      }
      if (stmts.length) await tursoRun(env, stmts);
      return j({ config: await ccConfig(env) });
    }

    if (op === "block" || op === "unblock") {
      if (!w) return j({ error: "missing worker" }, 400);
      const b = op === "block" ? 1 : 0;
      const stmts = [{ sql: "UPDATE cc_workers SET blocked=? WHERE id=?", params: [b, w] }];
      if (b) stmts.push({ sql: "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? WHERE worker_id=? AND status='claimed'", params: [now, w] });
      const r = await tursoRun(env, stmts);
      return j({ ok: true, worker: w, blocked: !!b, released: b ? r[1].meta.changes : 0 });
    }

    // ---- device routes ----
    if (op === "enroll") {
      if (!w) return j({ error: "missing worker" }, 400);
      await tursoRun(env, [{ sql:
        "INSERT INTO cc_workers(id,platform,last_seen,enrolled_at) VALUES(?,?,?,?) " +
        "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, platform=COALESCE(cc_workers.platform,excluded.platform)",
        params: [w, body.platform || null, now, now] }]);
      const [bl] = await tursoRun(env, [{ sql: "SELECT blocked FROM cc_workers WHERE id=?", params: [w] }]);
      return j({ worker: w, blocked: !!(bl.results[0] && bl.results[0].blocked), config: await ccConfig(env) });
    }

    if (op === "renew") { // the CHEAP heartbeat: exactly 1 write
      if (!w) return j({ error: "missing worker" }, 400);
      const [r] = await tursoRun(env, [{ sql: "UPDATE cc_workers SET last_seen=? WHERE id=?", params: [now, w] }]);
      if (!r.meta.changes) return j({ ok: false, reenroll: true, config: await ccConfig(env) });
      const [bl] = await tursoRun(env, [{ sql: "SELECT blocked FROM cc_workers WHERE id=?", params: [w] }]);
      return j({ ok: true, blocked: !!(bl.results[0] && bl.results[0].blocked), config: await ccConfig(env) });
    }

    if (op === "release") {
      if (!w) return j({ error: "missing worker" }, 400);
      const [r] = await tursoRun(env, [{ sql: "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? WHERE worker_id=? AND status='claimed'", params: [now, w] }]);
      return j({ released: r.meta.changes });
    }

    if (op === "submit") { // commits ONLY lines the worker still HOLDS (poison-safe)
      if (!w) return j({ error: "missing worker" }, 400);
      const out = body.out || {};
      const ids = Object.keys(out);
      if (!ids.length) return j({ accepted: 0, rejected: 0 });
      const stmts = ids.map((id) => ({ sql: "UPDATE cc_lines SET out=?, status='done', updated_at=? WHERE id=? AND worker_id=? AND status='claimed'", params: [String(out[id]), now, id, w] }));
      const res = await tursoRun(env, stmts);
      let accepted = 0; for (const r of res) accepted += r.meta.changes;
      if (accepted) await tursoRun(env, [{ sql: "UPDATE cc_workers SET done=done+? WHERE id=?", params: [accepted, w] }]);
      return j({ accepted, rejected: ids.length - accepted });
    }

    if (op === "claim") {
      if (!w) return j({ error: "missing worker" }, 400);
      const cfg = await ccConfig(env);
      const r1 = await tursoRun(env, [
        { sql: "UPDATE cc_workers SET last_seen=? WHERE id=?", params: [now, w] },
        { sql: "SELECT blocked FROM cc_workers WHERE id=?", params: [w] },
        { sql: "SELECT COUNT(*) AS n FROM cc_lines WHERE worker_id=? AND status='claimed'", params: [w] },
      ]);
      if (!r1[0].meta.changes) return j({ lines: [], reenroll: true, config: cfg });
      if (r1[1].results[0] && r1[1].results[0].blocked) {
        await tursoRun(env, [{ sql: "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? WHERE worker_id=? AND status='claimed'", params: [now, w] }]);
        return j({ lines: [], blocked: true, config: cfg });
      }
      const inflight = Number(r1[2].results[0].n || 0);
      const n = Math.min(cfg.batch_size, Math.max(0, cfg.max_inflight - inflight));
      if (n <= 0) return j({ lines: [], config: cfg });
      const stale = now - cfg.lease_ttl_seconds;
      // 🔴 ROWS-READ: the old single statement preferred open rows with
      // `ORDER BY (l.status='open') DESC, l.created_at`. That expression cannot
      // use an index, so SQLite materialised + sorted EVERY matching row
      // (USE TEMP B-TREE, ~72k of them) just to take 50 - on every claim, from
      // every worker. Turso billed all of it and the org hit 75% of its
      // rows-read quota. Same preference, two statements: OPEN first as an
      // index-ordered range scan that stops at n rows (cc_lines_open_idx on
      // status, collected, created_at), and the expensive steal scan ONLY when
      // the open pool cannot fill the batch - i.e. almost never.
      const [c] = await tursoRun(env, [{ sql:
        "UPDATE cc_lines SET worker_id=?1, status='claimed', lease_until=?2, updated_at=?3 " +
        "WHERE id IN (SELECT l.id FROM cc_lines l WHERE l.status='open' AND l.collected=0 " +
        "ORDER BY l.created_at LIMIT ?4) RETURNING id, target, sys, src",
        params: [w, now + cfg.lease_ttl_seconds, now, n] }]);
      let lines = c.results;
      if (lines.length < n) {
        const [s2] = await tursoRun(env, [{ sql:
          "UPDATE cc_lines SET worker_id=?1, status='claimed', lease_until=?2, updated_at=?3 " +
          "WHERE id IN (SELECT l.id FROM cc_lines l WHERE l.collected=0 AND l.status='claimed' " +
          "AND NOT EXISTS (SELECT 1 FROM cc_workers x WHERE x.id=l.worker_id AND x.blocked=0 " +
          "AND x.last_seen>=?4) ORDER BY l.created_at LIMIT ?5) RETURNING id, target, sys, src",
          params: [w, now + cfg.lease_ttl_seconds, now, stale, n - lines.length] }]);
        lines = lines.concat(s2.results);
      }
      return j({ lines, config: cfg });
    }

    return j({ error: "not found" }, 404);
  } catch (e) {
    console.error("cc error:", op, w, e && e.message ? e.message : e);
    return j({ error: String(e && e.message ? e.message : e) }, 500);
  }
}

export default {
  async fetch(request, env) {
    const parts = new URL(request.url).pathname.split("/").filter(Boolean);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ── /pool/query — the community /translate POOL, on D1 (5GB free). ──────
    // Server-to-server ONLY (Vercel api/translate.ts + the python importer),
    // gated by POOL_SECRET. Never called from a browser, so no CORS. The DB
    // holds only public, re-importable pool data (no auth/PII), and the secret
    // is server-only, so a generic parametrised-SQL endpoint is acceptable
    // here and keeps all query logic in the (typechecked) api/translate.ts.
    if (parts[0] === "pool") {
      return handlePool(request, env, parts);
    }

    // ── /cc/* — Community-Compute volunteer queue (Turso, isolated cc_*). ────
    // Devices (BYOK 3 providers) enroll/claim/renew/submit; operator does
    // stats/config/block. SEPARATE from the site's Supabase — can never break
    // AUTH. See handleCc for the gate + the per-worker lease design.
    if (parts[0] === "cc") {
      return handleCc(request, env, parts);
    }

    if (parts[0] === "launcher" && parts[1] === "setup") {
      return serveLauncherSetup();
    }

    const repo = REPOS[parts[0]];
    if (!repo) {
      return new Response("not found", { status: 404, headers: CORS });
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
      return new Response(`github releases: ${relResp.status}`, { status: 502, headers: CORS });
    }
    let rel;
    try {
      rel = await relResp.json();
    } catch {
      // A GitHub glitch returning 200 with a non-JSON body must not throw
      // an uncaught SyntaxError out of the fetch handler → clean 502.
      return new Response("github releases: malformed JSON body", { status: 502, headers: CORS });
    }
    const assets = Object.fromEntries((rel.assets || []).map((a) => [a.name, a]));

    // ── manifest.json drives everything ─────────────────────
    const manifestAsset = assets["manifest.json"];
    if (!manifestAsset) {
      return new Response("release has no manifest.json asset", { status: 502, headers: CORS });
    }
    let manifest;
    try {
      manifest = await (
        await fetch(manifestAsset.url, {
          headers: { ...gh, Accept: "application/octet-stream" },
        })
      ).json();
    } catch {
      // A malformed manifest.json asset (or a fetch/JSON glitch) must not
      // throw an uncaught SyntaxError out of the handler → clean 502.
      return new Response("manifest.json: malformed or unreachable", { status: 502, headers: CORS });
    }

    // ── Normalize the manifest ──────────────────────────────
    // The contract is {archive_name, sha256, version} - mod_source.fetch_manifest
    // REJECTS a manifest without `archive_name`, and the /archive route below
    // looks the asset up by it. But each game has its own packer, and some write
    // `archive` (+ `size`/`name`) instead - the Witcher 3 release did, which made
    // /archive answer "release has no asset 'undefined'" AND the launcher throw
    // "manifest missing 'archive_name'". Accept both spellings so one packer's
    // wording can never take a published mod offline.
    if (!manifest.archive_name && manifest.archive) {
      manifest.archive_name = manifest.archive;
    }

    // ── GET /<slug>/manifest ────────────────────────────────
    if (parts[1] === "manifest") {
      return Response.json(manifest, { headers: { "Cache-Control": "no-store", ...CORS } });
    }

    // ── GET /<slug>/archive ─────────────────────────────────
    if (parts[1] === "archive") {
      const archiveAsset = assets[manifest.archive_name];
      if (!archiveAsset) {
        return new Response(
          `release has no asset '${manifest.archive_name}'`,
          { status: 502, headers: CORS },
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
          ...CORS,
        },
      });
    }

    return new Response("not found", { status: 404, headers: CORS });
  },
};
