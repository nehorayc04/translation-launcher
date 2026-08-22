# -*- coding: utf-8 -*-
"""Patch the Hebrew intro-recap subtitle INTO recap_wip.usm's embedded @SBT stream.

THE real mechanism (the .subs files are vestigial — the engine ignores them for this cinematic):
the launch recap plays `content0\...\gamestart\recap_wip.usm`, a CRI Sofdec USM whose subtitles are
MULTIPLEXED into the video as `@SBT` chunks — 15 language channels x ~24 lines, text stored UTF-8 in
PRESENTATION forms (i.e. VISUAL, the renderer does NO bidi). The game shows the subtitle for the
channel of the selected Text Language. **Channel 14 = Arabic** (the slot we hijack).

Each @SBT chunk:  '@SBT' + u32be size + payload[size]
  payload = subheader[8] + fields[36] + text[textlen] + zero-padding
  fields: start(u32be)@0 dur(u32be)@4 .. channel(u32le)@32 .. textlen(u32le)@36
  (so within payload: channel @ +8+32=40, textlen @ +8+36=44, text @ +8+40=48-? -> measured 44)
Actually measured: payload[40:44]=channel, payload[40? ] — we use the offsets proven in analysis:
  channel   = u32le at payload+8+16      (=+24)  -> NO; use the verified constants below.

Verified layout (from a real chunk):  subheader=payload[0:8], fields=payload[8:44],
  channel  = u32le payload[8+16 : 8+20]        (=payload[24:28])
  textlen  = u32le payload[8+32 : 8+36]        (=payload[40:44])
  text     = payload[44 : 44+textlen]
  capacity = size - 44   (text may grow up to here; the rest is zero padding)

We replace channel-14 (Arabic) text with the Hebrew VISUAL bake, IN PLACE: same chunk size, same USM
size, same bundle offset -> a pure byte overwrite of the recap_wip.usm region, no re-mux, no TOC change.

Backup: movies.bundle.he_backup. Revert: --revert. GAME MUST BE CLOSED.
"""
import os, sys, json, struct, shutil
import potato_bundle as PB
import subs_codec as SC
from build_mod import visual_line

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "movies.bundle")
BAK = BUNDLE + ".he_backup"
HERE = os.path.dirname(os.path.abspath(__file__))
USM_NAME = r"movies\cutscenes\gamestart\recap_wip.usm".lower()
AR_CHANNEL = 14


def hebrew_by_start():
    """{start_ms: hebrew VISUAL} for the recap lines, from subs_plan + subs_hebrew + reuse."""
    plan = json.load(open(os.path.join(HERE, "subs_plan.json"), encoding="utf-8"))
    hp = os.path.join(HERE, "subs_hebrew.json")
    hebmap = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else {}
    rows = plan[r"movies\cutscenes\gamestart\subs\recap_wip_ar.subs"]
    out = {}
    for rec in rows:
        he = rec.get("reuse_he") or (hebmap.get(rec.get("tkey", "")) if rec.get("tkey") else None)
        if he:
            out[int(rec["start"])] = visual_line(he)
    return out


def patch_usm(data: bytes, he_by_start: dict):
    """Return (patched_bytes, replaced, skipped_over) — same length as `data`."""
    buf = bytearray(data)
    pos = 0
    replaced = over = 0
    while True:
        pos = buf.find(b"@SBT", pos)
        if pos == -1:
            break
        size = struct.unpack_from(">I", buf, pos + 4)[0]
        p0 = pos + 8                        # payload start
        chan = struct.unpack_from("<I", buf, p0 + 8 + 16)[0]
        if chan == AR_CHANNEL:
            start = struct.unpack_from(">I", buf, p0 + 8 + 0)[0]
            he = he_by_start.get(start)
            if he is not None:
                hb = he.encode("utf-8")
                cap = size - 44             # text region capacity
                if len(hb) <= cap:
                    struct.pack_into("<I", buf, p0 + 40, len(hb))          # new textlen
                    buf[p0 + 44:p0 + 44 + len(hb)] = hb                    # new text
                    for i in range(p0 + 44 + len(hb), p0 + size):         # zero the rest
                        buf[i] = 0
                    replaced += 1
                else:
                    over += 1
        pos += 4
    return bytes(buf), replaced, over


def _usm_entry(src):
    d, ents = PB.list_entries(src)
    e = next(x for x in ents if x["name"].lower() == USM_NAME)
    return d, e


def deploy():
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK); print(f"backed up -> {os.path.basename(BAK)}")
    # start from a PRISTINE bundle so offsets are the shipping ones, then overwrite ONLY the usm bytes
    shutil.copy2(BAK, BUNDLE)
    d, e = _usm_entry(BAK)
    off, zsize = e["offs"], e["zsize"]
    with open(BAK, "rb") as f:
        f.seek(off); usm = f.read(zsize)

    he = hebrew_by_start()
    print(f"hebrew recap lines: {len(he)}")
    patched, n, over = patch_usm(usm, he)
    assert len(patched) == len(usm), "usm length changed — must be identical for in-place"
    if over:
        print(f"  WARNING: {over} lines exceeded chunk capacity (left Arabic)")
    with open(BUNDLE, "r+b") as f:
        f.seek(off); f.write(patched)
    print(f"patched {n} channel-14 @SBT chunks IN PLACE (usm {zsize} B, offset {off} unchanged)")

    # verify: re-read the usm from the deployed bundle and confirm Hebrew on channel 14
    d2, e2 = _usm_entry(BUNDLE)
    with open(BUNDLE, "rb") as f:
        f.seek(e2["offs"]); back = f.read(e2["zsize"])
    HE = lambda s: any('֐' <= c <= '׿' for c in s)
    pos = 0; heb = 0; ar = 0
    while True:
        pos = back.find(b"@SBT", pos)
        if pos == -1:
            break
        size = struct.unpack_from(">I", back, pos + 4)[0]
        p0 = pos + 8
        if struct.unpack_from("<I", back, p0 + 8 + 16)[0] == AR_CHANNEL:
            tl = struct.unpack_from("<I", back, p0 + 40)[0]
            t = back[p0 + 44:p0 + 44 + tl].decode("utf-8", "replace")
            if HE(t): heb += 1
            elif any('؀' <= c <= 'ۿ' for c in t): ar += 1
        pos += 4
    print(f"verify: channel-14 chunks now hebrew={heb} arabic={ar}")
    print("DEPLOYED. Fully restart the game (Text Language = Arabic).")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted movies.bundle from .he_backup")
    else:
        print("no backup found")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        he = hebrew_by_start()
        d, e = _usm_entry(BAK if os.path.exists(BAK) else BUNDLE)
        with open(BAK if os.path.exists(BAK) else BUNDLE, "rb") as f:
            f.seek(e["offs"]); usm = f.read(e["zsize"])
        _, n, over = patch_usm(usm, he)
        print(f"(dry-run) would patch {n} channel-14 chunks; {over} over-capacity")
