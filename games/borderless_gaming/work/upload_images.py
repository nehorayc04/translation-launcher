"""Process + upload the catalog artwork to the public `covers` bucket.

Targets match the sibling software entry (VirtualDJ):
    covers/borderless-gaming.webp          600x900  cover
    covers/banners/borderless-gaming.webp  <=1600w  banner
    covers/logos/borderless-gaming.png     <=360w   transparent logo
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
GID = "borderless-gaming"

SRC = {
    "logo":   DL / "9c10d235bc6941125446942ec2c0d999.png",
    "cover":  DL / "06e792caa5532d8e7417c1c7c0389a43.png",
    "banner": DL / "af17b9d72632cf538b191472d83eceeb.png",
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
