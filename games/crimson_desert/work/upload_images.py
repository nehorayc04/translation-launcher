"""Process + upload the Crimson Desert catalog artwork to the public `covers` bucket.

Targets match every sibling game row:
    covers/crimson-desert.webp          600x900   cover (box art)
    covers/banners/crimson-desert.webp  <=1600w   wide banner
    covers/logos/crimson-desert.png     <=360w    transparent logo

The logo is CONTAIN-fitted and never stretched.
Sources (supplied by the user, mapped by measured dimensions, not by filename):
    600x900   RGB   -> cover (already the exact target size)
    3840x1240 RGB   -> banner (~3.10 aspect, matches the 1600x517 target)
    444x138   RGBA  -> logo (real alpha transparency)
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
GID = "crimson-desert"

SRC = {
    "cover":  DL / "16d0e5565572c83e0bc429147524b465.png",
    "banner": DL / "11af2e35fe0228ff4a349714f3dde3d3.png",
    "logo":   DL / "ee59427f4dfe7f8aff37e71c0e63b5e6.png",
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
            print(f"  src {k:6s} {im.size[0]}x{im.size[1]}  {im.mode}  {p.name[:44]}")

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
