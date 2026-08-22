#!/usr/bin/env python3
"""Community-translation pipeline bridge — import EN source strings into the
community POOL, and export APPROVED Hebrew back out for the per-game apply/bake/
deploy scripts.

The pool lives on **Cloudflare D1** (5GB free) so it can never fill the Supabase
DB that AUTH lives in. All access goes through the secret-gated /pool/query route
on the mod Worker (same endpoint api/translate.ts uses).

Game-agnostic by design. The contract is a NORMALIZED strings file: a JSON
array of objects, one per line to translate:

    [
      {"string_key": "39166",            # EXACT spine key (pk / stringId) — required
       "source_en":  "Talk to Jackie.",  # English source — required
       "current_he": "דבר עם ג'קי.",      # existing translation ('' = untranslated)
       "context":    "quest objective",  # optional hint shown to the translator
       "section":    "onscreens",        # optional grouping
       "char_limit": 40,                  # optional length cap (UI overflow)
       "order_index": 12},                # optional sort
      ...
    ]

Keep `string_key` byte-exact — export maps the approved Hebrew back onto it.

Commands:
    import <game_id> <strings.json>     upsert the pool (on game_id+string_key)
    export <game_id> [--out FILE]       approved → {string_key: hebrew} JSON
    stats  <game_id>                    progress counts

Reads POOL_QUERY_URL + POOL_SECRET from website/.env. No third-party deps.
"""
import sys, json, argparse, uuid, re, urllib.request, urllib.error
from pathlib import Path

WEBSITE = Path(__file__).resolve().parent.parent / "website"

# Upsert one string, preserving contributor progress (status/claimed_by/
# approved_text/he_* are NOT in the DO UPDATE, so a re-import refreshes the seed
# without losing claims or approvals).
_UPSERT = (
    "INSERT INTO translation_strings "
    "(id,game_id,string_key,source_en,current_he,context,char_limit,section,order_index,category,updated_at) "
    "VALUES (?,?,?,?,?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%fZ','now')) "
    "ON CONFLICT(game_id,string_key) DO UPDATE SET "
    "source_en=excluded.source_en, current_he=excluded.current_he, context=excluded.context, "
    "char_limit=excluded.char_limit, section=excluded.section, order_index=excluded.order_index, "
    "category=excluded.category, updated_at=excluded.updated_at"
)

# Recompute + upsert one game's progress-cache row (mirrors api/_lib/pool.ts).
_REFRESH = (
    "INSERT INTO translation_progress_cache "
    "(game_id,total,approved,pending,had_existing,untranslated_open,stale,refreshed_at) "
    "SELECT ?, count(*), "
    "sum(CASE WHEN status='approved' THEN 1 ELSE 0 END), "
    "sum(CASE WHEN status='translated' THEN 1 ELSE 0 END), "
    "sum(CASE WHEN current_he <> '' THEN 1 ELSE 0 END), "
    "sum(CASE WHEN current_he = '' AND status <> 'approved' THEN 1 ELSE 0 END), "
    "0, strftime('%Y-%m-%dT%H:%M:%fZ','now') "
    "FROM translation_strings WHERE game_id = ? "
    "ON CONFLICT(game_id) DO UPDATE SET total=excluded.total, approved=excluded.approved, "
    "pending=excluded.pending, had_existing=excluded.had_existing, "
    "untranslated_open=excluded.untranslated_open, stale=0, refreshed_at=excluded.refreshed_at"
)


def _env():
    names = ("POOL_QUERY_URL", "POOL_SECRET")
    v = {}
    for line in (WEBSITE / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")          # tolerant of `NAME = value` (spaces round =)
        key = key.strip()
        if key in names:
            v[key] = val.strip().strip('"').strip("'")
    url, secret = v.get("POOL_QUERY_URL"), v.get("POOL_SECRET")
    if not url or not secret:
        sys.exit("ERROR: POOL_QUERY_URL / POOL_SECRET missing in website/.env")
    return url, secret


def _post(body):
    req = urllib.request.Request(
        _URL, data=json.dumps(body).encode(), method="POST",
        headers={
            "Content-Type": "application/json", "x-pool-secret": _SECRET,
            # Cloudflare bot-blocks the default Python-urllib UA with a 403 "error
            # code: 1010" before the request even reaches the Worker — send a real
            # browser UA (the same gotcha as the Supabase Management API).
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/125.0.0.0 Safari/537.36"),
        })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")


def _query(sql, params=None):
    j = _post({"sql": sql, "params": params or []})
    if isinstance(j, dict) and j.get("error"):
        sys.exit("ERROR pool: " + str(j["error"]))
    return j.get("results", [])


def _batch(stmts):
    j = _post({"batch": stmts})
    if isinstance(j, dict) and j.get("error"):
        sys.exit("ERROR pool: " + str(j["error"]))
    return j.get("results", [])


_HEB = re.compile(r"[א-ת]")

def _category_for(section):
    # Mirrors the Postgres ts_category_for: a Hebrew section passes through
    # VERBATIM (so a game's curated Hebrew categories become the /translate chips);
    # a raw English section maps to the 4 fixed buckets.
    s = (section or "").strip()
    if not s:
        return "other"
    if _HEB.search(s):
        return s
    low = s.lower()
    if any(k in low for k in ("subtitle", "dialog", "voice", "bark", "caption", "cinemat")):
        return "subtitles"
    if any(k in low for k in ("ui", "menu", "hud", "setting", "interface", "tooltip", "button")):
        return "ui"
    if "credit" in low:
        return "credits"
    return "other"


# One 11-column VALUES group (updated_at is a literal strftime, the other 10 are bound).
_VALS = "(?,?,?,?,?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
_COLS = ("(id,game_id,string_key,source_en,current_he,context,char_limit,"
         "section,order_index,category,updated_at)")
_ON_CONFLICT = (
    " ON CONFLICT(game_id,string_key) DO UPDATE SET "
    "source_en=excluded.source_en, current_he=excluded.current_he, context=excluded.context, "
    "char_limit=excluded.char_limit, section=excluded.section, order_index=excluded.order_index, "
    "category=excluded.category, updated_at=excluded.updated_at")


def cmd_import(game_id, strings_path):
    rows = json.loads(Path(strings_path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        sys.exit("ERROR: strings file must be a JSON array")

    # Dedup by string_key (last wins) — a multi-row INSERT..ON CONFLICT cannot
    # touch the same (game_id,string_key) twice in one statement.
    seen, order = {}, []
    for i, r in enumerate(rows):
        sk = str(r.get("string_key", "")).strip()
        en = r.get("source_en")
        if not sk or en is None:
            sys.exit(f"ERROR: row {i} missing string_key/source_en")
        section = r.get("section") or ""
        if sk not in seen:
            order.append(sk)
        seen[sk] = [str(uuid.uuid4()), game_id, sk, en, r.get("current_he") or "",
                    r.get("context") or "", r.get("char_limit"), section,
                    int(r.get("order_index", i)), _category_for(section)]
    recs = [seen[sk] for sk in order]

    # Multi-row INSERT: ROWS rows per statement (one fast bulk op in the DB),
    # STMTS statements per Turso pipeline request. ~100× faster than one exec/row.
    ROWS, STMTS = 150, 10
    stmts = []
    for i in range(0, len(recs), ROWS):
        chunk = recs[i:i + ROWS]
        sql = "INSERT INTO translation_strings " + _COLS + " VALUES " + \
              ",".join([_VALS] * len(chunk)) + _ON_CONFLICT
        stmts.append({"sql": sql, "params": [p for rec in chunk for p in rec]})

    done = 0
    for i in range(0, len(stmts), STMTS):
        _batch(stmts[i:i + STMTS])
        done = min(len(recs), (i + STMTS) * ROWS)
        print(f"  upserted {done}/{len(recs)}")
    print(f"DONE: imported {len(recs)} strings for game '{game_id}'")

    # Recompute the precomputed progress cache the /translate picker reads.
    _query(_REFRESH, [game_id, game_id])
    print(f"  progress cache refreshed for '{game_id}'")


def cmd_export(game_id, out_path):
    rows, offset = [], 0
    while True:
        page = _query(
            "SELECT string_key,approved_text FROM translation_strings "
            "WHERE game_id=? AND status='approved' ORDER BY order_index LIMIT 1000 OFFSET ?",
            [game_id, offset])
        if not page:
            break
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    mapping = {r["string_key"]: r["approved_text"] for r in rows if r.get("approved_text")}
    out_path = out_path or f"approved_{game_id}.json"
    Path(out_path).write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE: exported {len(mapping)} approved translations → {out_path}")
    print("Feed this into the game's apply script keyed by string_key.")


def cmd_stats(game_id):
    p = _query(
        "SELECT total,approved,pending,had_existing,untranslated_open "
        "FROM translation_progress_cache WHERE game_id=?", [game_id])
    if not p:
        print(f"No strings imported for game '{game_id}' yet.")
        return
    r = p[0]
    print(f"Game: {game_id}")
    print(f"  total:             {r['total']}")
    print(f"  approved:          {r['approved']}")
    print(f"  pending review:    {r['pending']}")
    print(f"  had existing he:   {r['had_existing']}")
    print(f"  untranslated open: {r['untranslated_open']}")


def main():
    global _URL, _SECRET
    _URL, _SECRET = _env()
    ap = argparse.ArgumentParser(description="Community-translation pipeline bridge (D1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("import"); pi.add_argument("game_id"); pi.add_argument("strings_json")
    pe = sub.add_parser("export"); pe.add_argument("game_id"); pe.add_argument("--out")
    ps = sub.add_parser("stats");  ps.add_argument("game_id")
    a = ap.parse_args()
    if a.cmd == "import":
        cmd_import(a.game_id, a.strings_json)
    elif a.cmd == "export":
        cmd_export(a.game_id, a.out)
    elif a.cmd == "stats":
        cmd_stats(a.game_id)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
