# -*- coding: utf-8 -*-
"""DEEP investigation of the game's OWN font metric policy (vanilla, read-only).

The user's instruction: "take the game's VANILLA Arabic font and replace it with Hebrew".
The principled way to do that is NOT to invent a box policy of my own, but to MEASURE the
policy the shipped Arabic uses and reproduce it, so the engine treats Hebrew exactly the
way it treats the Arabic it replaces -> the on-screen size is automatically what the game
intended.

Answers, from the PRISTINE backup only (nothing is written):
  1. every Fonts_Z object in FONT/ENGLISH.DPC (which fonts exist, how many glyphs)
  2. BIG_ARABIC: is the declared box UNIFORM or TIGHT around the ink?  where is the baseline?
  3. the same for the Latin BIG_FONT / SMALL_FONT (the size the player compares against)
  4. the resulting ink/box ratio == the multiplier the engine applies to the requested size
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, is_ar

VAN = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC.he_backup"
FONT_CLASS = 0x87218B06F6FE91FD


def load(path):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    return D, byid


def page_cache(byid):
    pages = {}

    def pg(t):
        if t not in pages:
            pages[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        return pages[t]
    return pg


def measure(fz, m2t, pg, pick, label, limit=None):
    rows = []
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and pick(ord(c))):
            continue
        if e.mat not in m2t:
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        bw, bh = x1 - x0, y1 - y0
        if bw < 4 or bh < 4:
            continue
        a = pg(m2t[e.mat])
        box = a[y0:y1, x0:x1]
        ys, xs = np.where(box > 60)
        if len(ys) < 8:
            continue
        it, ib = int(ys.min()), int(ys.max())        # ink top/bottom RELATIVE to box top
        ih = ib - it + 1
        rows.append(dict(ch=c, bw=bw, bh=bh, ih=ih, it=it, ib=ib,
                         adv=e.adv, bx=e.bx, by=e.by,
                         asc=e.adv - it, desc=(ib + 1) - e.adv))
        if limit and len(rows) >= limit:
            break
    if not rows:
        print(f"  {label}: (no glyphs)")
        return rows

    def st(k):
        v = np.array([r[k] for r in rows], dtype=float)
        return v.min(), v.max(), v.mean(), len(set(np.round(v, 2)))

    print(f"\n  --- {label}   n={len(rows)} ---")
    for k in ("bh", "ih", "it", "adv", "by"):
        lo, hi, mu, nd = st(k)
        tag = "UNIFORM" if nd == 1 else ("near-uniform" if nd <= 3 else "per-glyph")
        print(f"    {k:>4}: min={lo:7.1f} max={hi:7.1f} mean={mu:7.1f}  distinct={nd:<4} {tag}")
    fill = np.array([r["ih"] / r["bh"] for r in rows])
    print(f"    ink_h/box_h : min={fill.min():.3f} max={fill.max():.3f} mean={fill.mean():.3f}")
    # how far the ink sits from the box edges
    gap_t = np.array([r["it"] for r in rows], dtype=float)
    gap_b = np.array([r["bh"] - 1 - r["ib"] for r in rows], dtype=float)
    print(f"    gap top={gap_t.mean():.1f} (max {gap_t.max():.0f})   "
          f"gap bottom={gap_b.mean():.1f} (max {gap_b.max():.0f})")
    # baseline coherence: is (box_top + adv) the same line for every glyph?
    print(f"    baseline-in-box (adv): {sorted(set(round(r['adv'], 1) for r in rows))[:12]}")
    tall = sorted(rows, key=lambda r: -r["ih"])[:6]
    short = sorted(rows, key=lambda r: r["ih"])[:6]
    print("    tallest:", "  ".join(f"{r['ch']} box{r['bw']}x{r['bh']} ink{r['ih']} top{r['it']}" for r in tall))
    print("    shortest:", "  ".join(f"{r['ch']} box{r['bw']}x{r['bh']} ink{r['ih']} top{r['it']}" for r in short))
    return rows


def main():
    D, byid = load(VAN)
    fonts = [o for o in byid.values() if o.otype == FONT_CLASS]
    print(f"=== Fonts_Z objects in the VANILLA FONT/ENGLISH.DPC: {len(fonts)} ===")
    infos = []
    for o in sorted(fonts, key=lambda x: -len(x.body)):
        try:
            fz = FontsZ(o.body)
        except Exception as ex:
            print(f"  0x{o.oid:016X}  (unparsable: {ex})")
            continue
        chars = [cid_to_char(e.cid) for e in fz.entries]
        n_ar = sum(1 for c in chars if c and len(c) == 1 and is_ar(ord(c)))
        n_lat = sum(1 for c in chars if c and len(c) == 1 and 0x20 <= ord(c) < 0x17F)
        bh = [int(e.y1 - e.y0) for e in fz.entries if e.y1 - e.y0 > 3]
        print(f"  0x{o.oid:016X}  entries={fz.count:<5} arabic={n_ar:<5} latin={n_lat:<4} "
              f"box_h min/max/mean={min(bh) if bh else 0}/{max(bh) if bh else 0}/"
              f"{(sum(bh)/len(bh)) if bh else 0:.0f}  distinct_box_h={len(set(bh))}")
        infos.append((o, fz))

    pg = page_cache(byid)
    lat = lambda cp: 0x41 <= cp <= 0x5A or 0x61 <= cp <= 0x7A
    dig = lambda cp: 0x30 <= cp <= 0x39
    for o, fz in infos:
        m2t = resolve_mat_textures(byid, fz)
        if not m2t:
            continue
        print(f"\n=== 0x{o.oid:016X} ===")
        measure(fz, m2t, pg, is_ar, "ARABIC glyphs", limit=60)
        measure(fz, m2t, pg, lat, "LATIN A-Za-z", limit=60)
        measure(fz, m2t, pg, dig, "DIGITS 0-9")


main()
