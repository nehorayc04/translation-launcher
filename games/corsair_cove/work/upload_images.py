"""Process + upload the Corsair Cove catalog artwork to the public `covers` bucket.

Targets match every sibling game row:
    covers/corsair-cove.webp          600x900   cover (box art)
    covers/banners/corsair-cove.webp  <=1600w   wide banner
    covers/logos/corsair-cove.png     <=360w    transparent logo

The logo is CONTAIN-fitted and never stretched -- a stretched wordmark is instantly visible.
Sources (supplied by the user, mapped by measured aspect ratio, not by filename):
    3840x1240 (3.10)  -> banner
    1440x2160 (0.67)  -> cover, already a clean 2:3 so the 600x900 resize is not a crop
    1280x720  RGBA    -> logo (transparent; the real ink is a sub-rect, so it is bbox-trimmed)
"""
from __future__ import annotations

import io
import pathlib
import re
import sys
import urllib.request

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(r"c:/Users/Nehoray_Cohen/Projects/Game translator")
DL = pathlib.Path(r"C:/Users/Nehoray_Cohen/Downloads")
GID = "corsair-cove"

SRC = {
    "banner": DL / "library_hero_2x.jpg",
    "cover":  DL / "apps.57612.14230424027872647.ab6270a0-0d1f-4913-b718-32112ae966e2 העתק.jpg",
    "logo":   DL / "logo_2x.png",
}


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / "website" / ".env").read_text("utf-8").splitlines():
        m = re.match(r'^([A-Z_]+)\s*=\s*"?([^"\r\n]*)"?', line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def put(path: str, data: bytes, ctype: str) -> None:
    e = env()
    key = e.get("SUPABASE_SERVICE_ROLE_KEY") or e["SUPABASE_SERVICE_KEY"]
    req = urllib.request.Request(
        f"{e['SUPABASE_URL']}/storage/v1/object/{path}", data=data, method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": ctype, "x-upsert": "true"})
    with urllib.request.urlopen(req) as r:
        print(f"  {r.status}  {path}  ({len(data):,} B)")


def main() -> int:
    for k, p in SRC.items():
        if not p.exists():
            print("MISSING source: " + str(p))
            return 1
        with Image.open(p) as im:
            print(f"  src {k:6s} {im.size[0]}x{im.size[1]}  {p.name[:44]}")

    cover = Image.open(SRC["cover"]).convert("RGB").resize((600, 900), Image.LANCZOS)
    buf = io.BytesIO(); cover.save(buf, "WEBP", quality=86)
    put(f"covers/{GID}.webp", buf.getvalue(), "image/webp")

    ban = Image.open(SRC["banner"]).convert("RGB")
    if ban.width > 1600:
        ban = ban.resize((1600, round(ban.height * 1600 / ban.width)), Image.LANCZOS)
    buf = io.BytesIO(); ban.save(buf, "WEBP", quality=86)
    put(f"covers/banners/{GID}.webp", buf.getvalue(), "image/webp")

    logo = Image.open(SRC["logo"]).convert("RGBA")
    bb = logo.getbbox()                                    # trim the transparent margin
    if bb:
        logo = logo.crop(bb)
    if logo.width > 360:
        logo = logo.resize((360, round(logo.height * 360 / logo.width)), Image.LANCZOS)
    buf = io.BytesIO(); logo.save(buf, "PNG", optimize=True)
    put(f"covers/logos/{GID}.png", buf.getvalue(), "image/png")
    print(f"\n  logo final {logo.size[0]}x{logo.size[1]} (contain-fitted, aspect preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
