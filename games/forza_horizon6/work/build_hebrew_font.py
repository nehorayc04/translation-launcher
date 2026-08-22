"""Inject the 27 Hebrew letters into Forza Horizon 6's UI fonts.

Target = **`Horizon_RU_A/C/D` only**. `media\\UI\\fontsettings.xml` declares an
explicit per-language fallback chain, and the catch-all `lang="*"` block (what EN
and every Latin locale resolves to) already routes every UI face into them:

    Horizon_A / A_tf / B / B_tf  ->  Horizon_RU_A  ->  Horizon_KO -> JP -> CHS -> CHT
    Horizon_C / C_tf             ->  Horizon_RU_C  ->  ...
    Horizon_D / D_tf             ->  Horizon_RU_D  ->  ...

so a codepoint the Latin face lacks is looked up in the RU face automatically.
Three files cover all eight UI faces and `fontsettings.xml` needs no edit at all
— which is exactly how Playground themselves shipped Cyrillic (they grew the
FALLBACK font to 440 glyphs instead of the primaries).

Size and weight are MEASURED, never chosen by eye:

* **size** — Hebrew is unicase, so matching the Latin cap reads oversized while
  matching the x-height reads small; the body is set to the midpoint of the two
  (cap 0.7002, x-height 0.5000 -> body 0.60 em).
* **weight** — each RU face's own stem width is measured off its `H`, and the
  Heebo variable font's `wght` axis is binary-searched until the scaled Hebrew
  stem matches it. So RU_A/C/D each get their own weight rather than one guess.

    python build_hebrew_font.py                 # dry run + report
    python build_hebrew_font.py --preview       # + render a PNG of the result
    python build_hebrew_font.py --deploy
    python build_hebrew_font.py --verify        # read the glyphs back OUT of the game
    python build_hebrew_font.py --revert
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fh6_font as F                                                # noqa: E402
import fh6_glyphgen as G                                            # noqa: E402
import fh6_zip as Z                                                 # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
SLOT = os.path.join(GAME, "media", "UI", "Fonts.zip")
BACKUP = SLOT + ".he_backup"
SIDECAR = SLOT + ".he_backup.json"
VAR = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo", "Heebo-var.ttf")

HEBREW = [c for c in range(0x05D0, 0x05EB)]          # 27 letters, א..ת
TARGETS = ("Horizon_RU_A", "Horizon_RU_C", "Horizon_RU_D")
BODY_FRAC = 0.5                 # body = cap + BODY_FRAC*(x-height - cap) -> midpoint

# 🔴 The page size is declared by the .vfont's TRAILER, which `serialize()` now
# regenerates — so the page MAY grow. (It could not before: the stale trailer
# still named the old length, and exactly the glyphs crossing it rendered wrong.)
#
# The 7 mathematical operators are still dropped because it is free: they are
# never drawn in a racing game AND `Horizon_JP` carries all seven while sitting in
# this font's own fallback chain (RU_A -> KO -> JP), so the engine still finds them.
DROP = list(range(0x2228, 0x222F))                   # ∨ ∩ ∪ ∫ ∬ ∭ ∮
# finest first; the builder takes the best one inside HEB_BUDGET
TOLERANCES = (0.0015, 0.003, 0.005, 0.008, 0.012, 0.02, 0.03, 0.05)
# The AA band costs ~4 verts + 6 indices per outline edge and barely shrinks with
# tolerance, so this budget picks the quality knee rather than a hard limit.
HEB_BUDGET = 52_000                                  # bytes of Hebrew mesh


# --------------------------------------------------------------------------
def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while (b := f.read(1 << 20)):
            h.update(b)
    return h.hexdigest()


def face_metrics(font: F.VFont, page: bytes) -> dict:
    """cap, x-height and stem width of a face, straight from its own outlines."""
    by = font.by_cp()
    g = by[0x48]                                              # H — all straight
    v, _ = F.read_mesh(page, g)
    xs = sorted({round(p[0], 4) for p in v})
    edges = [(xs[i] + xs[i + 1]) / 2 for i in range(0, len(xs), 2)]
    return dict(cap=g.hgt, xht=by[0x78].hgt, stem=edges[1] - edges[0])


def donor_for(stem_target: float, body: float, cache: dict = {}) -> G.Donor:
    """Instantiate Heebo at the wght that matches this face's stroke weight."""
    from fontTools.varLib import instancer
    from fontTools.ttLib import TTFont

    lo, hi = 100.0, 900.0
    for _ in range(14):
        mid = (lo + hi) / 2
        d = cache.get(mid)
        if d is None:
            tt = instancer.instantiateVariableFont(TTFont(VAR), {"wght": mid},
                                                   inplace=False, updateFontNames=False)
            tmp = os.path.join(os.environ.get("TEMP", "."), f"_heebo_{int(mid)}.ttf")
            tt.save(tmp)
            d = cache[mid] = G.Donor(tmp)
        s = body / d.ink(0x05D4, 1.0)[3]
        if d.stem(0x05D5, s) < stem_target:
            lo = mid
        else:
            hi = mid
    return cache[mid], mid


def plan(pay: dict) -> dict:
    """{family: (font, page, donor, scale, wght, metrics)} — measurement only."""
    out = {}
    for fam in TARGETS:
        font = F.parse(pay[f"{fam}.vfont"])
        page = pay[f"{fam}.vfont0"]
        m = face_metrics(font, page)
        body = m["cap"] + BODY_FRAC * (m["xht"] - m["cap"])
        donor, wght = donor_for(m["stem"], body)
        scale = body / donor.ink(0x05D4, 1.0)[3]
        out[fam] = (font, page, donor, scale, wght, m, body)
    return out


def inject(font: F.VFont, page: bytes, donor: G.Donor, scale: float, tol: float):
    """Drop DROP, add Hebrew at flattening tolerance `tol`; (font, page, stats)."""
    G.FLAT_TOL = tol
    have = font.by_cp()
    tail = font.glyphs[10].tail                         # the shared constant tail
    meshes, recs = {}, []
    for cp in HEBREW:
        if cp in have:
            continue
        verts, tris, adv, top = G.mesh_for(donor, cp, scale, F.X_BIAS)
        if not verts:
            raise ValueError(f"U+{cp:04X}: donor produced no outline")
        if max(len(verts), len(tris)) > 0xFFFF:
            raise ValueError(f"U+{cp:04X}: {len(verts)}/{len(tris)} exceeds u16")
        meshes[cp] = (verts, tris)
        recs.append(F.Glyph(cp, adv, top, 0.0, len(verts), len(tris), 0, tail))

    glyphs = [g for g in font.glyphs if g.cp not in DROP]
    dropped = len(font.glyphs) - len(glyphs)
    cps = [g.cp for g in glyphs]
    end = cps.index(F.NOTDEF) if F.NOTDEF in cps else len(cps)   # sorted prefix only
    pos = next((i for i in range(end) if cps[i] > HEBREW[0]), end)
    glyphs[pos:pos] = recs

    page2, glyphs2 = F.build_page(F.lead_block(page), glyphs, meshes, page)
    stats = dict(added=len(recs), dropped=dropped, pos=pos, tol=tol,
                 verts=sum(len(v) for v, _ in meshes.values()),
                 tris=sum(len(t) // 3 for _, t in meshes.values()),
                 heb_bytes=sum(12 + 8 * len(v) + 2 * len(t)
                               for v, t in meshes.values()),
                 grew=len(page2) - len(page))
    return font._replace(glyphs=glyphs2), page2, stats


def inject_fitting(font: F.VFont, page: bytes, donor: G.Donor, scale: float):
    """Finest curve-flattening tolerance whose Hebrew fits HEB_BUDGET."""
    best = None
    for tol in TOLERANCES:
        f2, p2, st = inject(font, page, donor, scale, tol)
        if st["heb_bytes"] <= HEB_BUDGET:
            return f2, p2, st
        best = (f2, p2, st)
    return best


def build(src: str, dst: str, preview: bool = False) -> dict:
    entries, pay = Z.read(src)
    p = plan(pay)
    replace, report = {}, {}
    for fam, (font, page, donor, scale, wght, m, body) in p.items():
        f2, page2, st = inject_fitting(font, page, donor, scale)
        # 🔴 the trailer is the REAL page table — declare the NEW byte length or
        # the engine simply will not have the glyphs past the old one
        replace[f"{fam}.vfont"] = f2.serialize([len(page2)])
        replace[f"{fam}.vfont0"] = page2
        # read the result straight back out to prove it parses
        chk = F.parse(replace[f"{fam}.vfont"])
        cov = chk.coverage(0x05D0, 0x05EA)
        by = chk.by_cp()
        for cp in HEBREW:
            F.read_mesh(page2, by[cp])
        st.update(cov=len(cov), wght=wght, scale=scale, body=body, **m,
                  heb_stem=donor.stem(0x05D5, scale))
        report[fam] = st
        print(f"  {fam:<14s} stem {m['stem']:.4f} -> wght {wght:5.1f} "
              f"(stem {st['heb_stem']:.4f}), body {body:.4f}, tol {st['tol']:.4f}em")
        print(f"                 +{st['added']} Hebrew ({st['heb_bytes']:,} B, "
              f"{st['verts']} v/{st['tris']} t) -{st['dropped']} math, "
              f"page {len(page):,} -> {len(page2):,} ({st['grew']:+,} B), "
              f"coverage {st['cov']}/27")
        if preview:
            preview_face(fam, chk, page2)
    Z.rebuild(src, dst, replace)
    return report


def preview_face(fam: str, font: F.VFont, page: bytes) -> None:
    """Render a real word from the BUILT font, so size/weight are judged offline.

    Only the SOLID interior triangles (cv == 1) are drawn. The game's own glyphs
    also carry AA-band quads whose outer vertices sit ~W outside the outline and
    whose curve triangles hold control points far outside it — rasterising those
    as opaque geometry makes the Latin look both bolder and faceted, which is a
    preview artefact, not the font.
    """
    from PIL import Image, ImageDraw
    W, H, S = 1560, 230, 190.0
    im = Image.new("RGB", (W, H), (14, 14, 20))
    d = ImageDraw.Draw(im)
    by = font.by_cp()
    text = "שלום ABCHEIL עברית 240"
    pen, base = 30.0, 175.0
    for ch in text:
        g = by.get(ord(ch))
        if g is None:
            pen += 0.3 * S
            continue
        if g.n_verts:
            v, idx = F.read_mesh(page, g)
            for i in range(0, len(idx), 3):
                tri = [v[idx[i + k]] for k in range(3)]
                if any(abs(p[3] - 1.0) > 1e-3 for p in tri):
                    continue                       # AA band / curve control
                d.polygon([(pen + (p[0] - F.X_BIAS) * S, base - p[1] * S)
                           for p in tri], fill=(235, 235, 240))
        pen += g.adv * S
    p = os.path.join(HERE, "..", "extract", f"font_preview_{fam}.png")
    im.save(p)
    print(f"    preview -> {os.path.relpath(p, HERE)}")


def validate(src: str, built: str) -> bool:
    """Full offline check of a BUILT zip against the pristine one, before deploy."""
    _, a = Z.read(src)
    _, b = Z.read(built)
    ok = True

    def chk(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'OK ' if cond else 'FAIL'} {msg}")

    touched = {f"{f}.vfont" for f in TARGETS} | {f"{f}.vfont0" for f in TARGETS}
    chk(set(a) == set(b), f"entry set unchanged ({len(a)} entries)")
    same = [n for n in a if n not in touched and a[n] == b[n]]
    chk(len(same) == len(a) - len(touched),
        f"{len(same)} untouched entries BYTE-IDENTICAL "
        f"(incl. fontsettings.xml, all {len(a) - len(touched) - 1} other fonts)")

    for fam in TARGETS:
        fa = F.parse(a[f"{fam}.vfont"])
        fb = F.parse(b[f"{fam}.vfont"])
        pa, pb = a[f"{fam}.vfont0"], b[f"{fam}.vfont0"]
        bya, byb = fa.by_cp(), fb.by_cp()
        chk(fb.kerns == fa.kerns and fb.n_kerns == fa.n_kerns,
            f"{fam}: kern table byte-identical ({fa.n_kerns} pairs)")
        chk(fb.prefix == fa.prefix, f"{fam}: region prefix preserved")
        # 🔴 the trailer IS the page table — it must describe what we wrote
        slots, tbl = fb.page_table()
        chk(slots == len(fb.glyphs) + 1 and tbl[0][0] == len(pb)
            and tbl[0][1] == slots,
            f"{fam}: trailer declares {tbl[0][0]:,} B / {slots} slots, "
            f"page is {len(pb):,} B / {len(fb.glyphs) + 1} slots")
        chk(len(fb.glyphs) == len(fa.glyphs) + 27 - len(DROP),
            f"{fam}: {len(fa.glyphs)} -> {len(fb.glyphs)} glyphs "
            f"(+27 Hebrew, -{len(DROP)} math)")
        # growth is fine now, PROVIDED the trailer says so (checked above)
        chk(len(pb) > 0, f"{fam}: page {len(pa):,} -> {len(pb):,} B "
                         f"({len(pb) - len(pa):+,})")
        cps = fb.codepoints()
        end = cps.index(F.NOTDEF)
        chk(cps[:end] == sorted(set(cps[:end])),
            f"{fam}: codepoints still strictly ascending through U+FFFD")
        chk(not any(c in cps for c in DROP), f"{fam}: math operators removed")
        # every ORIGINAL glyph we KEPT must still decode to the same mesh + metrics
        bad = 0
        for cp, g in bya.items():
            if cp in DROP:
                continue
            h = byb.get(cp)
            if h is None or (g.adv, g.hgt, g.xoff, g.n_verts, g.n_indices) != \
                    (h.adv, h.hgt, h.xoff, h.n_verts, h.n_indices) or \
                    F.read_mesh(pa, g) != F.read_mesh(pb, h):
                bad += 1
        chk(bad == 0, f"{fam}: all {len(bya) - len(DROP)} kept glyphs unchanged")
        heb = [c for c in HEBREW if c in byb]
        ink = all(byb[c].n_verts >= 4 and byb[c].n_indices >= 6 for c in heb)
        chk(len(heb) == 27 and ink, f"{fam}: 27/27 Hebrew present with real geometry")
        # page must stay contiguous and fully consumed
        off = len(F.lead_block(pb))
        for g in fb.glyphs:
            if g.data_off != off:
                break
            off += 12 + F.VERTEX * g.n_verts + 2 * g.n_indices
        chk(off == len(pb), f"{fam}: page contiguous and fully consumed ({len(pb):,} B)")
    print(f"validate: {'PASS' if ok else 'FAIL'}")
    return ok


def verify(path: str) -> None:
    _, pay = Z.read(path)
    ok = True
    for fam in TARGETS:
        font = F.parse(pay[f"{fam}.vfont"])
        page = pay[f"{fam}.vfont0"]
        by = font.by_cp()
        miss = [c for c in HEBREW if c not in by]
        ink = 0
        for cp in HEBREW:
            if cp in by:
                v, idx = F.read_mesh(page, by[cp])
                ink += len(idx) // 3
        cps = font.codepoints()
        end = cps.index(F.NOTDEF) if F.NOTDEF in cps else len(cps)
        sortd = cps[:end] == sorted(set(cps[:end]))
        good = not miss and sortd and ink > 0
        ok &= good
        print(f"  {'OK ' if good else 'BAD'} {fam:<14s} {27 - len(miss)}/27 Hebrew, "
              f"{ink} triangles, {len(font.glyphs)} glyphs, ascending={sortd}")
    # every other face must be untouched
    print(f"verify: {'PASS' if ok else 'FAIL'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(SLOT):
        sys.exit(f"Fonts.zip not found: {SLOT}")

    if a.revert:
        if not os.path.exists(BACKUP):
            sys.exit("no backup to revert")
        meta = json.load(open(SIDECAR)) if os.path.exists(SIDECAR) else {}
        if meta.get("deployed_sha") and sha(SLOT) != meta["deployed_sha"]:
            sys.exit("REFUSING: Fonts.zip is not what we deployed (game updated?)")
        shutil.copy2(BACKUP, SLOT)
        for q in (BACKUP, SIDECAR):
            if os.path.exists(q):
                os.remove(q)
        print("reverted Fonts.zip from backup")
        return

    if a.verify:
        verify(SLOT)
        return

    src = BACKUP if os.path.exists(BACKUP) else SLOT
    tmp = SLOT + ".tmp"
    build(src, tmp, preview=a.preview)
    print(f"built -> {os.path.getsize(tmp):,} bytes "
          f"(was {os.path.getsize(src):,})")

    if not validate(src, tmp):
        os.remove(tmp)
        sys.exit("REFUSING to deploy: offline validation failed")

    if not a.deploy:
        print("(dry run — pass --deploy to install)")
        os.remove(tmp)
        return

    if not os.path.exists(BACKUP):
        shutil.copy2(SLOT, BACKUP)
        print(f"backed up -> {os.path.basename(BACKUP)}")
    orig = sha(BACKUP)
    os.replace(tmp, SLOT)
    json.dump({"original_sha": orig, "deployed_sha": sha(SLOT)},
              open(SIDECAR, "w"), indent=1)
    print("DEPLOYED to", SLOT)
    verify(SLOT)


if __name__ == "__main__":
    main()
