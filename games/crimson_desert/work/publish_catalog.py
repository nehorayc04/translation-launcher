"""Create/refresh the Crimson Desert `games` catalog row.

⚠️ This row MUST exist BEFORE any `community_translate.py import crimson-desert` --
the pool's foreign key rejects the WHOLE batch otherwise (§17.7 trap).

⚠️ `availability` is ADMIN-OWNED. On a re-run this script does NOT re-assert it, so an
admin flipping the game to `in-progress` from the panel is never clobbered.

PostgREST + the `sb_secret_…` service key must be sent with NO browser User-Agent
(a browser UA gets "Forbidden use of secret API key in browser" 401) -- the inverse of the
Supabase Management API, which requires one.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(r"c:/Users/Nehoray_Cohen/Projects/Game translator")
GID = "crimson-desert"
BUCKET = "storage/v1/object/public/covers"

ROW = {
    "id": GID,
    "title_en": "Crimson Desert",
    "title_he": "מדבר ארגמן",
    "tagline": "הרפתקת פעולה בעולם פתוח - Pearl Abyss",
    "status": "locked",
    "release_stage": "stable",
    "price_cents": 0,
    "show_on_website": True,
    "show_on_launcher": False,
    "is_software": False,
    "sort_order": 10012,          # right after corsair-cove (10011)
    "theme_key": "default",
}


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / "website" / ".env").read_text("utf-8").splitlines():
        m = re.match(r'^([A-Z_]+)\s*=\s*"?([^"\r\n]*)"?', line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _req(method, path, body=None):
    e = env()
    key = e.get("SUPABASE_SERVICE_ROLE_KEY") or e["SUPABASE_SERVICE_KEY"]
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/rest/v1/{path}", data=data, method=method,
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt.strip() else None)
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()


def main() -> int:
    e = env()
    base = e["SUPABASE_URL"]
    row = dict(ROW)
    row["cover_url"] = f"{base}/{BUCKET}/{GID}.webp"
    row["banner_url"] = f"{base}/{BUCKET}/banners/{GID}.webp"
    row["logo_url"] = f"{base}/{BUCKET}/logos/{GID}.png"

    st, cur = _req("GET", f"games?id=eq.{GID}&select=id,availability")
    exists = bool(cur)
    if exists:
        print(f"  row exists (availability={cur[0].get('availability')!r}) -> UPDATE, availability untouched")
        st, out = _req("PATCH", f"games?id=eq.{GID}", row)
    else:
        row["availability"] = "planned"          # only ever set on CREATE
        print("  row absent -> INSERT (availability=planned)")
        st, out = _req("POST", "games", row)
    print(f"  HTTP {st}")
    if st >= 400:
        print(out)
        return 1

    st, chk = _req("GET", f"games?id=eq.{GID}&select=id,title_en,title_he,availability,status,"
                          "price_cents,show_on_website,show_on_launcher,sort_order,cover_url,banner_url,logo_url")
    r = chk[0]
    for k, v in r.items():
        print(f"    {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
