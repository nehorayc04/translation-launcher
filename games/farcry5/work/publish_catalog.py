"""Create the Supabase catalog row for Far Cry 5 — the website + launcher card.

DB-only: both the website (`/api/games`) and the launcher (`_try_supabase_catalog`, `select=*`)
read this row LIVE, so no `vercel --prod` and no launcher rebuild are needed.

The mod is NOT published (Phase 1 is done, the 25k-string translation is not) -> the row is
`in-progress` / `locked` / free, exactly like the Far Cry 6 sibling. It becomes purchasable at
publish time per [[mod-price-53-default]].

    python work/publish_catalog.py            # dry run
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
GID = "farcry5"
COVERS = "https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers"

ROW = {
    "id": GID,
    "title_en": "Far Cry 5",
    "title_he": "פאר קריי 5",
    "version": "-",
    "version_label": "",
    "status": "locked",
    "release_stage": "stable",
    # ⚠️ availability is ADMIN-OWNED (the admin panel sets planned/in-progress/paused/…).
    # Matched to the Far Cry 6 sibling; a re-run must not fight an admin edit.
    "availability": "planned",
    "progress": 0,
    "cover_url": f"{COVERS}/{GID}.webp",
    "banner_url": f"{COVERS}/banners/{GID}.webp",
    "logo_url": f"{COVERS}/logos/{GID}.png",
    "theme_key": "default",
    "download_url": None,
    "tagline": "כת יום־הדין השתלטה על מונטנה — ואתם השריף שנשאר לבד",
    "description": (
        "פאר קריי 5 מציב אתכם כסגן שריף צעיר במחוז הופ שבמונטנה, שנשלח לעצור את ג'וזף סיד — "
        "מטיף כריזמטי שהפך כת יום־דין חמושה לשליטת האזור. המעצר משתבש, המחוז נסגר, ואתם "
        "נותרים לבדכם לבנות התנגדות מבית לבית: לשחרר בני ערובה, לגייס לוחמים וחיות לוויה, "
        "ולהפיל אחד־אחד את שלושת בני משפחת סיד ששולטים באזורים. עולם פתוח שאפשר לשחק בו "
        "בסדר חופשי לגמרי, לבד או בשיתוף פעולה."
    ),
    "changelog": "",
    "price_cents": 0,
    "is_software": False,
    "featured": False,
    "next_up": False,
    "sort_order": 10009,          # right after Far Cry 6 (10008)
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
    for k in ("title_he", "availability", "status", "price_cents",
              "show_on_website", "show_on_launcher", "sort_order"):
        print(f"  {k:18s} = {ROW[k]!r}")
    # the artwork must already be in the bucket, or the card renders empty
    for u in (ROW["cover_url"], ROW["banner_url"], ROW["logo_url"]):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, method="HEAD")) as r:
                print(f"  art {r.status}  {u.rsplit('/', 2)[-2]}/{u.rsplit('/', 1)[-1]}")
        except Exception as e:                                   # noqa: BLE001
            print(f"  art FAIL {u}  {e}")
            return 1
    if not apply:
        print("\ndry run - pass --apply to write")
        return 0

    if exists:
        st, res = call("PATCH", f"games?id=eq.{GID}",
                       {k: v for k, v in ROW.items() if k != "id"})
    else:
        st, res = call("POST", "games", ROW, prefer="return=representation")
    print(f"\n  games -> HTTP {st}" + ("" if st < 300 else f"  {res}"))
    return 0 if st < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
