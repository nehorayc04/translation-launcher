"""Spider-Man Remastered — the SAME menu proof as 20_build_menu_proof.py, but
deployed via apply_inplace() instead of apply().

Round 4 root-cause work (2026-08-11): on the OFFICIALLY-UPDATED v3.618 exe, the
append-new-archive-entry deploy from 20_build_menu_proof.py causes a reliable boot
stall (user-confirmed 2/2), even though every byte-level structural check on the toc
(chunkmap uniqueness, whole-toc identity round-trip, all 6 DAT1 sections compared
before/after) comes back clean. The one thing genuinely NEW about that deploy vs a
stock asset load is the brand-new archive/chunkmap/filename entry the updated exe has
never seen before.

This variant tests the alternative: append our blobs onto the END of an EXISTING,
already-trusted archive file (g00s000, archive_index=0) and redirect into THAT SAME
archive_index. No new Archives-section row is created at all. Everything else
(the loc/font content, the markers, the bidi A/B) is byte-identical to the proven-
correct build in 20_build_menu_proof.py — only the DEPLOY MECHANISM differs.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "games" / "spiderman_remastered" / "tools"
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import msmr_loc      # noqa: E402
import msmr_deploy    # noqa: E402

# reuse the proven build() / CANDIDATES / markers from the append-archive proof
proof20 = __import__("20_build_menu_proof")

GAME = Path(os.environ.get("MSMR_GAME", r"D:\Games\Spider-man Remastered"))
EN_ASSET_ID = proof20.EN_ASSET_ID
FONT_ASSET_ID = proof20.FONT_ASSET_ID
FONT_SPAN = proof20.FONT_SPAN
CANDIDATES = proof20.CANDIDATES
build_patch = proof20.build_patch
TARGET_ARCHIVE_INDEX = 0  # g00s000, a base always-loaded game archive


def deploy():
    assets, new_font = proof20.build()
    print(f"[*] built {len(assets)} loc candidates + font asset ({len(new_font)} B)")
    all_assets = assets + [(FONT_SPAN, FONT_ASSET_ID, new_font)]
    total_size = sum(len(b) for _, _, b in all_assets)
    print(f"[*] appending {total_size:,} B into archive_index={TARGET_ARCHIVE_INDEX} (in-place, no new archive entry)")

    res = msmr_deploy.apply_inplace(GAME, all_assets, target_archive_index=TARGET_ARCHIVE_INDEX)
    print("[*] deploy (in-place) ->", res)
    if not res.get("ok"):
        raise SystemExit(res.get("error"))

    t = msmr_deploy.read_toc(msmr_deploy.toc_path(GAME))
    n_arch = len(t.get_archives_section().archives)
    print(f"[*] archive count after deploy: {n_arch} (must be UNCHANGED from pristine)")

    t.set_archives_dir(str(msmr_deploy.arch_dir(GAME)))
    all_ok = True
    for span, fname, marker, full in CANDIDATES:
        slot = msmr_deploy.find_asset_index(t, span, EN_ASSET_ID)
        raw = bytes(t.extract_asset(slot))
        L = msmr_loc.Loc(raw)
        d = L.as_dict()
        patch = build_patch(marker, full)
        ok = all(d.get(k) == v for k, v in patch.items())
        all_ok &= ok
        print(f"[{'PASS' if ok else 'FAIL'}] span {span} read-back: "
              f"{sum(1 for k, v in patch.items() if d.get(k) == v)}/{len(patch)} keys correct "
              f"(marker={d.get('TEXT_SPLASHSCREEN_CONTINUE')!r})")

    fslot = msmr_deploy.find_asset_index(t, FONT_SPAN, FONT_ASSET_ID)
    fraw = bytes(t.extract_asset(fslot))
    import gfx_inspect as G  # noqa
    import swf_font as S     # noqa
    heb = 0
    for code, length, off in G.list_tags(fraw):
        if code == 75:
            f = S.parse_definefont3(fraw[off:off + length])
            heb += sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
    print(f"[{'PASS' if heb == 135 else 'FAIL'}] font read-back: {heb} Hebrew glyphs (expect 135)")

    print(f"\n[{'PASS' if all_ok and n_arch == 46 else 'FAIL'}] all candidates written+verified, "
          f"ZERO new archive entries.")
    print("\n[+] DEPLOYED IN-PLACE (no new archive/chunkmap entry). Launch Spider-Man.exe.")


def revert():
    print(msmr_deploy.revert_inplace(GAME))


def status():
    print(msmr_deploy.status_inplace(GAME))


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--status" in sys.argv:
        status()
    elif "--build-only" in sys.argv:
        proof20.build()
        print("[+] build OK (not deployed)")
    else:
        deploy()
