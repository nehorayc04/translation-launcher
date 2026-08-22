#!/usr/bin/env python3
"""Joint donor selection: match advance AND keep height uniform, with a fit constraint.
READ-ONLY. Quantifies the achievable spacing + size evenness. Also renders the CURRENT
deployed Hebrew glyphs to ASCII to confirm they are readable letters (size aside)."""
import os, sys, struct
import numpy as np
from PIL import ImageFont

REPO = r"c:\Users\Nehoray_Cohen\Projects\Game translator"
os.environ["ACS_OODLE_DLL"] = os.path.join(REPO, "Game Lab", "Battlefield 6", "oo2core_9_win64.dll")
sys.path.insert(0, os.path.join(REPO, "games", "acshadows", "tools"))
sys.path.insert(0, os.path.join(REPO, "games", "acshadows", "work"))
import acs_cfd as C
import acs_atlas_inject as AI

HEB = [chr(0x05D0+i) for i in range(27)]

def load_weight_backup(idx):
    with open(AI.BAK % idx, "rb") as g:
        off, size = struct.unpack("<QQ", g.read(16)); rest = g.read()
    blob = rest if len(rest)==size else rest[rest.index(b"\x00")+1:]
    cfds,_ = C.decode_resource(blob, C._oodle())
    return max((x for x,_ in cfds), key=len)

def load_weight_live(forge, idx):
    import acs_forge as F
    info = F.parse(forge); r = info["recs"][idx]
    with open(forge,"rb") as f: f.seek(r["offset"]); blob=f.read(r["size"])
    cfds,_ = C.decode_resource(blob, C._oodle())
    return max((x for x,_ in cfds), key=len)

def hungarian_ish(cost):
    """Small greedy min-cost assignment (27 x N). Good enough; pool is large."""
    N = cost.shape[1]
    assigned = [-1]*27
    used = set()
    # assign most-constrained letters first: those with the fewest low-cost donors
    order = sorted(range(27), key=lambda i: np.partition(cost[i],5)[:5].sum())
    for i in order:
        j = min((jj for jj in range(N) if jj not in used), key=lambda jj: cost[i][jj])
        assigned[i]=j; used.add(j)
    return assigned

def main():
    idx = 20630
    dec = load_weight_backup(idx)
    _g,_c,_s,recs = AI._records(dec)
    donors = [r for r in recs if 0xFB50 <= r["cp"] <= 0xFEFF and r["W"]*r["H"]>0]
    dadv = np.array([r["m"][0] for r in donors])
    dW   = np.array([float(r["W"]) for r in donors])
    dH   = np.array([float(r["H"]) for r in donors])

    font = ImageFont.truetype(AI.HEB_FONT, 100)
    nat = np.array([font.getlength(ch) for ch in HEB])
    # natural letter height class (px @100) to know which need tall slots (lamed) / descenders
    heights=[]
    for ch in HEB:
        m=font.getmask(ch, mode="L")
        heights.append(m.size[1] if m.size[1] else 60)
    heights=np.array(heights, float)

    # TARGET: pick a body height the donors can supply uniformly. Use donor median H.
    Ht = float(np.median(dH))               # ~50
    scale = Ht/np.median(nat)               # scale natural advances to donor-advance units? no:
    # advance target: scale natural advances so Hebrew MEDIAN advance == donor median advance
    scale_adv = np.median(dadv)/np.median(nat)
    ideal_adv = nat*scale_adv

    # Joint cost: normalized advance error + height-uniformity (want donor H all ~Ht) + fit.
    # fit: donor must be tall enough to render a body-height glyph -> H >= Ht (hard).
    lam = 2.0                               # weight on height-uniformity vs advance
    cost = np.zeros((27, len(donors)))
    for i in range(27):
        ae = np.abs(dadv - ideal_adv[i]) / max(1.0, np.median(dadv))
        he = np.abs(dH - Ht) / Ht
        fit = np.where(dH >= Ht*0.9, 0.0, 5.0)     # penalize too-short slots
        cost[i] = ae + lam*he + fit

    assign = hungarian_ish(cost)
    a_adv = np.array([donors[assign[i]]["m"][0] for i in range(27)])
    a_H   = np.array([float(donors[assign[i]]["H"]) for i in range(27)])
    a_W   = np.array([float(donors[assign[i]]["W"]) for i in range(27)])
    a_err = np.abs(a_adv - ideal_adv)

    # current v2: 27 largest-area, letter i -> i-th largest
    cur = sorted(donors, key=lambda r:-(r["W"]*r["H"]))[:27]
    c_adv=np.array([r["m"][0] for r in cur]); c_H=np.array([float(r["H"]) for r in cur])
    c_err=np.abs(c_adv-ideal_adv)

    print(f"weight {idx}: pool={len(donors)} donors  target body H={Ht:.0f}  ideal advance spread stdev={np.std(ideal_adv):.1f}")
    print(f"\n  ADVANCE (spacing):")
    print(f"    current v2 : mean|err|={c_err.mean():5.1f}  advance stdev={np.std(c_adv):5.1f}  max advance={c_adv.max():.0f}")
    print(f"    JOINT pick : mean|err|={a_err.mean():5.1f}  advance stdev={np.std(a_adv):5.1f}  max advance={a_adv.max():.0f}")
    print(f"\n  HEIGHT (letter size uniformity):")
    print(f"    current v2 : H mean={c_H.mean():5.1f}  H stdev={np.std(c_H):5.1f}  range {c_H.min():.0f}..{c_H.max():.0f}")
    print(f"    JOINT pick : H mean={a_H.mean():5.1f}  H stdev={np.std(a_H):5.1f}  range {a_H.min():.0f}..{a_H.max():.0f}")
    print(f"\n  FIT: all joint-picked donors W>=needed? minW={a_W.min():.0f} minH={a_H.min():.0f}  (all >= {Ht*0.9:.0f}? {bool((a_H>=Ht*0.9).all())})")

    print(f"\n  {'let':<4}{'ideal':>7}{'joint_adv':>10}{'err':>6}{'donorH':>8}{'donorW':>8}")
    for i in range(27):
        print(f"  {HEB[i]:<4}{ideal_adv[i]:>7.1f}{a_adv[i]:>10.1f}{a_err[i]:>6.1f}{a_H[i]:>8.0f}{a_W[i]:>8.0f}")

    # --- render a few CURRENTLY DEPLOYED glyphs to ASCII (validate readability) ---
    print("\n== CURRENTLY DEPLOYED glyph rasters (live patch_02 idx 20630) ==")
    live = load_weight_live(os.path.join(r"C:\Games\Assassin's Creed Shadows","DataPC_boot_patch_02.forge"), 20630)
    for ch in ("א","ב","ש","ל","ם"):
        print(f"\n  {ch} (U+{ord(ch):04X}):")
        print(AI._ascii(live, ord(ch)))

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
