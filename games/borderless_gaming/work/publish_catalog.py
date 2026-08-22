"""Create/update the Supabase catalog rows for the Borderless Gaming mod.

FREE software entry (the user asked for חינם), shown on BOTH the website and the
launcher. Mirrors the VirtualDJ row shape; writes `games` + `mod_version_history`.

    python work/publish_catalog.py           # show what would be written
    python work/publish_catalog.py --apply
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJ = Path(r"c:/Users/Nehoray_Cohen/Projects/Game translator")
GID = "borderless-gaming"
VERSION = "1.0.0-beta.1"
TAG = f"v{VERSION}"
REPO = "hebrew-translation-hub/borderless-gaming-hebrew-mods"
ARCHIVE = "borderless_gaming_hebrew.zip"
COVERS = "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers"

ROW = {
    "id": GID,
    "title_en": "Borderless Gaming",
    "title_he": "בורדרלס גיימינג",
    "version": VERSION,
    "version_label": "",
    "status": "beta",
    "release_stage": "beta",
    "availability": "available",
    "cover_url": f"{COVERS}/{GID}.webp",
    "banner_url": f"{COVERS}/banners/{GID}.webp",
    "logo_url": f"{COVERS}/logos/{GID}.png",
    "theme_key": "default",
    "progress": None,
    "download_url": f"https://github.com/{REPO}/releases/download/{TAG}/{ARCHIVE}",
    "tagline": "חלון ללא מסגרת ומסנני שדרוג תמונה — עכשיו בעברית מלאה",
    "description": (
        "תרגום מלא לעברית של Borderless Gaming — הכלי שהופך כל משחק לחלון ללא מסגרת "
        "ומוסיף מסנני שדרוג תמונה (FSR, Anime4K, CRT ועוד). מתורגמים גם ממשק התוכנה "
        "וגם עורך האפקטים כולו: הקטגוריות, תיאורי האפקטים, תוויות הפרמטרים וההסברים "
        "שלהם. ההתקנה כותבת רק לתיקיית המשתמש, ולכן אימות הקבצים של Steam לא מוחק "
        "את התרגום ואין צורך בהרשאות מנהל."
    ),
    "changelog": (
        "גרסה ראשונה — 878 מחרוזות בעברית: ממשק התוכנה (343) ועורך האפקטים "
        "(535 מחרוזות ב-106 אפקטים). כיוון RTL מלא, בלי צורך בהתקנת גופן."
    ),
    "price_cents": 0,
    "is_software": True,
    "featured": False,
    "next_up": False,
    "sort_order": 2,
    "show_on_website": True,
    "show_on_launcher": True,
    "interface_only_notice": False,
    "payment_only": False,
    "locked_fields": {},
}


def env() -> dict[str, str]:
    out = {}
    for line in (PROJ / "website" / ".env").read_text("utf-8").splitlines():
        m = re.match(r'^([A-Z_]+)\s*=\s*"?([^"\r\n]*)"?', line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


E = env()
BASE = E["SUPABASE_URL"] + "/rest/v1"
KEY = E.get("SUPABASE_SERVICE_ROLE_KEY") or E["SUPABASE_SERVICE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def call(method: str, path: str, body=None, prefer: str | None = None):
    hdr = dict(H)
    if prefer:
        hdr["Prefer"] = prefer
    req = urllib.request.Request(f"{BASE}/{path}", method=method, headers=hdr,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def main() -> int:
    apply = "--apply" in sys.argv
    _, existing = call("GET", f"games?id=eq.{GID}&select=id")
    exists = bool(existing)
    print(f"games row {GID}: {'EXISTS -> update' if exists else 'NEW -> insert'}")
    print(f"  price_cents = {ROW['price_cents']}  (FREE)")
    print(f"  website={ROW['show_on_website']}  launcher={ROW['show_on_launcher']}  "
          f"is_software={ROW['is_software']}")
    if not apply:
        print("\ndry run - pass --apply to write")
        return 0

    if exists:
        st, res = call("PATCH", f"games?id=eq.{GID}", {k: v for k, v in ROW.items() if k != "id"})
    else:
        st, res = call("POST", "games", ROW, prefer="return=representation")
    print(f"  games -> HTTP {st}" + ("" if st < 300 else f"  {res}"))
    if st >= 300:
        return 1

    hist = {
        "game_id": GID, "version": VERSION, "stage": "beta",
        "changelog": ROW["changelog"], "is_current": True,
    }
    call("PATCH", f"mod_version_history?game_id=eq.{GID}", {"is_current": False})
    st, res = call("POST", "mod_version_history", hist, prefer="return=representation")
    if st >= 300 and "duplicate" in str(res).lower():
        st, res = call("PATCH", f"mod_version_history?game_id=eq.{GID}&version=eq.{VERSION}", hist)
    print(f"  mod_version_history -> HTTP {st}" + ("" if st < 300 else f"  {res}"))
    return 0 if st < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
