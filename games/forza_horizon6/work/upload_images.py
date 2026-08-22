"""Process + upload the Forza Horizon 6 catalog artwork to the public `covers` bucket.

Targets match every sibling game row:
    covers/forza-horizon6.webp          600x900   cover (box art)
    covers/banners/forza-horizon6.webp  <=1600w   wide banner
    covers/logos/forza-horizon6.png     <=360w    transparent logo

The logo is CONTAIN-fitted, never stretched -- a stretched wordmark is instantly visible.
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
GID = "forza-horizon6"

SRC = {
    "banner": DL / "07561478adc8ca51c9646960a5508186.png",   # aerial cherry-blossom road, wide
    "logo":   DL / "b7dfa45d9d3b5dcbd956357582704365.png",   # FORZA HORIZON 6 wordmark, transparent
    "cover":  DL / "5b8613b547316cf7808db044637edb1c.png",   # box art, portrait
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
        with Image.open(p) as im:
            print(f"  src {k:6s} {im.size[0]}x{im.size[1]}  {p.name}")

    cover = Image.open(SRC["cover"]).convert("RGB").resize((600, 900), Image.LANCZOS)
    buf = io.BytesIO(); cover.save(buf, "WEBP", quality=86)
    put(f"covers/{GID}.webp", buf.getvalue(), "image/webp")

    ban = Image.open(SRC["banner"]).convert("RGB")
    if ban.width > 1600:
        ban = ban.resize((1600, round(ban.height * 1600 / ban.width)), Image.LANCZOS)
    buf = io.BytesIO(); ban.save(buf, "WEBP", quality=86)
    put(f"covers/banners/{GID}.webp", buf.getvalue(), "image/webp")

    logo = Image.open(SRC["logo"]).convert("RGBA")
    logo = logo.crop(logo.getbbox())                       # trim the transparent margin
    if logo.width > 360:
        logo = logo.resize((360, round(logo.height * 360 / logo.width)), Image.LANCZOS)
    buf = io.BytesIO(); logo.save(buf, "PNG", optimize=True)
    put(f"covers/logos/{GID}.png", buf.getvalue(), "image/png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
