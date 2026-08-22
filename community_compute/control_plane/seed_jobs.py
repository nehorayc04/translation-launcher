# -*- coding: utf-8 -*-
"""OPERATOR-ONLY — push a translation/review corpus into the community-compute queue.

Line-model: inserts ONE `cc_lines` row per source line. Volunteer worker apps
claim up to 50 at a time, run the job's own `sys` prompt over the line's `src`,
and submit. Collect with `collect_results.py`.

Two insert backends (the API is identical; pick what your network allows):
  * default = PostgREST /rest/v1/cc_lines with the SERVICE key (works on a normal
    operator machine; NO browser UA).
  * --mgmt  = the Supabase Management API query endpoint with a PAT
    (SUPABASE_ACCESS_TOKEN). Use this where Cloudflare 403s the service key over
    PostgREST (e.g. some datacenter IPs). Browser UA required there.

Accepts either corpus shape:
  * {"items": {id: text}, "sys": "..."}                 (the New-Era / review builder output)
  * {"<id>": "<english>", ...}
  * [{"string_key": "...", "source_en": "...", ...}]    (the /translate ct_upload shape)

Usage:
  python seed_jobs.py <corpus.json> --game <id> [--target <label>] [--limit N] [--section "..."] [--mgmt]
"""
import argparse, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SUPABASE_URL = "https://mfudkftrluabqlrpkvtj.supabase.co"
PROJECT_REF  = "mfudkftrluabqlrpkvtj"
_BROWSER_UA  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"

DEFAULT_SYS = (
    "You are a professional game translator, English to Hebrew. Return natural, "
    "fluent Hebrew. NO niqqud. Keep every [TOKEN], {value}, %s/%d and <tag> EXACTLY "
    "as in the source. Proper names of people/places stay as-is. "
    "Return ONLY a JSON object {id: hebrew_translation} and nothing else."
)


def _env(name):
    v = os.environ.get(name, "").strip()
    if not v:
        envf = os.path.join(REPO, "website", ".env")
        if os.path.exists(envf):
            for line in open(envf, encoding="utf-8"):
                if line.strip().startswith(name):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'"); break
    return v


def _dollar_tag(base, *texts):
    """A dollar-quote tag guaranteed absent from every text."""
    tag = f"${base}$"
    i = 0
    while any(tag in t for t in texts):
        i += 1; tag = f"${base}{i}$"
    return tag


def _insert_postgrest(rows, key):
    data = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        SUPABASE_URL + "/rest/v1/cc_lines", data=data, method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal",
                 "User-Agent": "cc-seed/1"})
    urllib.request.urlopen(req, timeout=120).read()


def _insert_mgmt(pairs, sysmsg, game, tok):
    """pairs = [(target, src), ...]. Inserts via the Management API."""
    arr = json.dumps([{"t": t, "s": s} for t, s in pairs], ensure_ascii=False)
    jt = _dollar_tag("CCJ", arr)
    st = _dollar_tag("CCS", sysmsg)
    gt = _dollar_tag("CCG", game)
    sql = (f"insert into public.cc_lines (game, sys, target, src)\n"
           f"select {gt}{game}{gt}, {st}{sysmsg}{st}, x->>'t', x->>'s'\n"
           f"from jsonb_array_elements({jt}{arr}{jt}::jsonb) as x;")
    body = json.dumps({"query": sql}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                 "User-Agent": _BROWSER_UA})
    urllib.request.urlopen(req, timeout=120).read()


def _load(path, section):
    raw = json.load(open(path, encoding="utf-8"))
    sysmsg, pairs = DEFAULT_SYS, []
    if isinstance(raw, dict) and "items" in raw:
        sysmsg = raw.get("sys", DEFAULT_SYS)
        pairs = [(str(k), str(v)) for k, v in raw["items"].items()]
    elif isinstance(raw, dict):
        pairs = [(str(k), str(v)) for k, v in raw.items()]
    elif isinstance(raw, list):
        for r in raw:
            if section and str(r.get("section", "")) != section:
                continue
            k = r.get("string_key") or r.get("id")
            v = r.get("source_en") or r.get("en") or r.get("value")
            if k and v:
                pairs.append((str(k), str(v)))
    return sysmsg, pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--game", default="")
    ap.add_argument("--target", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--section", default="")
    ap.add_argument("--mgmt", action="store_true", help="seed via the Management API (PAT) instead of PostgREST")
    ap.add_argument("--chunk", type=int, default=400, help="rows per Management-API insert (413 on huge panels -> lower this)")
    ap.add_argument("--skip", type=int, default=0, help="skip the first N pairs (resume after a partial/failed run)")
    a = ap.parse_args()

    sysmsg, pairs = _load(a.corpus, a.section)
    pairs = [(k, v) for k, v in pairs if v.strip()]
    if a.skip > 0:
        pairs = pairs[a.skip:]
    if a.limit > 0:
        pairs = pairs[:a.limit]
    if not pairs:
        sys.exit("no lines to seed")

    if a.mgmt:
        tok = _env("SUPABASE_ACCESS_TOKEN")
        if not tok:
            sys.exit("SUPABASE_ACCESS_TOKEN not set (env or website/.env)")
        n = 0
        for i in range(0, len(pairs), a.chunk):
            chunk = [(a.target or k, v) for k, v in pairs[i:i + a.chunk]]
            _insert_mgmt(chunk, sysmsg, a.game, tok)
            n += len(chunk); print(f"  ...{n}/{len(pairs)}", flush=True)
        print(f"seeded {n} lines via Management API  game={a.game!r}")
        return

    key = _env("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        sys.exit("SUPABASE_SERVICE_ROLE_KEY not set (env or website/.env)")
    rows, n = [], 0
    for k, v in pairs:
        rows.append({"game": a.game, "sys": sysmsg, "target": (a.target or k), "src": v})
        if len(rows) >= 500:
            _insert_postgrest(rows, key); n += len(rows); rows = []
    if rows:
        _insert_postgrest(rows, key); n += len(rows)
    print(f"seeded {n} lines via PostgREST  game={a.game!r}")


if __name__ == "__main__":
    main()
