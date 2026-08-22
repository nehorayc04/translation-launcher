"""Offline-validate the deploy WITHOUT touching the real game: copy the real toc
into a temp 'game_root', run spiderman2_mod.apply() there, then re-read the
mutated toc and confirm all 3 assets (loc + 2 fonts) were redirected to our
tm_he_* files with the correct sizes, and the toc re-parses cleanly."""
import os, sys, shutil, tempfile, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
STAGE = os.path.join(HERE, "menu_proof", "rc_hebrew_menuproof.stage")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1 as _d1
import spiderman2_mod as sm

LOC_AID, FONT_REG, FONT_BLD = 0xBE55D94F171BF8DE, 0xA2197874D2B7B1AC, 0xB5F411285669C55D
EXPECT = {LOC_AID: "loc", FONT_REG: "font_reg", FONT_BLD: "font_bld"}

tmp = tempfile.mkdtemp(prefix="rc_deploy_")
try:
    shutil.copy2(os.path.join(GAME, "toc"), os.path.join(tmp, "toc"))
    print(f"[*] temp game_root: {tmp}  (toc copied)")
    r = sm.apply(tmp, [STAGE], cb=lambda p,pct,m: None)
    print("[apply]", r)
    assert r.get("ok"), "apply failed"
    # re-read mutated temp toc
    with open(os.path.join(tmp, "toc"), "rb") as f:
        t = dat1lib.read(f)
    t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
    assets = t.get_assets_section(); ids = getattr(assets,"ids",None) or getattr(assets,"values",None)
    sizes = t.get_sizes_section(); archs = t.get_archives_section()
    spans = t.get_spans_section()
    # our new archives
    n_arch = len(archs.archives)
    print(f"[*] archives after apply: {n_arch}")
    # for each expected asset in span 0, check the redirect
    sp0 = spans.entries[0]; lo, cnt = sp0.asset_index, sp0.count
    seen = {}
    for i in range(lo, lo+cnt):
        if ids[i] in EXPECT:
            se = sizes.entries[i]
            arc = archs.archives[se.archive_index]
            nm = bytes(arc.filename).split(b"\x00")[0].decode("ascii","ignore")
            seen[EXPECT[ids[i]]] = (i, se.archive_index, nm, se.offset, se.value, se.header_offset)
    print("\n=== redirected size-entries (span 0) ===")
    ok = True
    for tag in ("loc","font_reg","font_bld"):
        if tag not in seen:
            print(f"  [MISSING] {tag}"); ok = False; continue
        i, ai, nm, off, val, ho = seen[tag]
        pointsto_ours = nm.startswith("d\\mods\\tm_he_")
        f = os.path.join(tmp, nm.replace("\\","/"))
        real = os.path.getsize(f) if os.path.exists(f) else -1
        good = pointsto_ours and off == 0 and val == real
        ok = ok and good
        print(f"  [{'OK' if good else 'BAD'}] {tag:9} idx={i} -> archive[{ai}]='{nm}' offset={off} value={val} file={real} header_offset={ho}")
    # confirm toc re-serializes/re-reads without exception (already read above)
    print(f"\n[*] toc re-read OK, {len(ids)} assets, {n_arch} archives")
    print(f"\n[{'PASS' if ok else 'FAIL'}] offline deploy validation")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
