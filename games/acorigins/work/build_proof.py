#!/usr/bin/env python3
r"""
build_proof.py — the AC Origins Phase-1 menu+subtitle proof.

ONE deploy closes every remaining gate, on BOTH surfaces, and runs a LADDER over
the two UI candidates so a single session answers which one the engine wins with
([[measure-with-a-ladder]], [[test-both-candidates-in-one-proof]]).

🔴 ORIGINS IS A TWO-SURFACE GAME, and the surfaces are independent:
      ACO.ini [Language]  Text=en-US   Subtitles=ar-AR   Sound=en-US
  • UI        -> `LocalizationPackage_English`  (the Arabic UI package is a
                 457-byte / 20-record STUB, so there is no Arabic UI locale)
  • SUBTITLES -> `LocalizationPackage_Arabic_Subtitles` (full, 12,844 records)
  bidi is therefore decided PER SURFACE ([[bidi-per-surface-not-per-product]]).

THE LADDER — both UI candidates ship in the same build, each with its OWN Latin
marker, so whichever marker appears names the live package:
  A  `LocalizationPackage_English`  marker ZZ-AOR-ENUI-ZZ   (Text=en-US, default,
                                                             costs the user NOTHING)
  B  `LocalizationPackage_Arabic`   marker ZZ-AOR-ARUI-ZZ   (Text=ar-AR — filled
                                     with all 8,223 English ids so the UI stays
                                     usable; if it loads we get the engine's own
                                     RTL menu layout for free)

Every proof row is deliberate:
  • a pure-LATIN marker            -> the file MOUNTED (independent of font+bidi)
  • the SAME word VISUAL vs LOGICAL -> the bidi mode, per surface
  • `אבגד` (4 non-confusable)       -> direction control
  • all 27 letters                  -> glyph coverage / tofu
  • punctuation+parens+digits+Latin -> layout, in BOTH modes
  • ONE deliberately-WRONG row      -> turns "looks right" into "exactly one of
                                       these can be right" (costs one string)

    python work/build_proof.py --build      # blobs only
    python work/build_proof.py --deploy     # build + write into the game
    python work/build_proof.py --verify     # read the live forge back
    python work/build_proof.py --revert
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "..", "acunity", "work"))

import aor_cfd                                          # noqa: E402
import aor_deploy                                       # noqa: E402
import aor_loc                                          # noqa: E402
import aor_rtl                                          # noqa: E402
from acu_loc import encode_payload                      # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("AOR_GAME", r"F:\Games\Assassin's Creed Origins")
FORGE = os.path.join(GAME, "DataPC.forge")
BLOBS = os.path.join(HERE, "_blobs")

PKG_EN_UI = "LocalizationPackage_English"
PKG_AR_UI = "LocalizationPackage_Arabic"
PKG_AR_SUB = "LocalizationPackage_Arabic_Subtitles"

V = aor_rtl.to_visual
L = aor_rtl.to_logical

ALEFBET = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
PARA = 'סימני פיסוק: (סוגריים) "מרכאות" — מקף, נקודה. שאלה? 12.5% ואז Origins 1234. סוף!'


def _i(d):
    """Normalise a {str|int: str} map to the INT keys the payload codec uses."""
    return {int(k): v for k, v in d.items()}


def ui_rows(marker):
    """The UI proof. Same ids in both candidates; only the marker differs.

    🔴 KEYS ARE `int` — `decode_payload` returns INT ids, and a JSON round-trip
    turns them into strings, so a str-keyed update() silently adds 20 NEW ids and
    changes nothing ([[json-roundtrip-hides-key-type]]). `_i()` normalises."""
    return _i({
        # ---- mount marker on a GUARANTEED-VISIBLE main-menu row --------------
        # 🔴 Round 1 put it on CREDITS, which is NOT a main-menu item in Origins,
        # so the marker never showed and only the id-lookup below saved the run.
        # LOOK THE ID UP BY ITS ENGLISH VALUE — never guess it from a sibling game.
        "1083812": marker,                                   # Discovery Tour
        "456221": marker,                                    # CREDITS (options page)
        # ---- the REAL main menu (ids resolved from base_english.json) --------
        "1011740": V("שחק"),                                 # Play
        "1011737": V("חנות"), "1012623": V("חנות"), "1012625": V("חנות"),
        "1011739": V("מועדון יוביסופט"),                     # Ubisoft Club
        "1014351": V("יציאה לשולחן העבודה"),                 # Quit to Desktop
        "60000099": V("יציאה לשולחן העבודה"),
        "663085": V("אפשרויות"), "532106": V("אפשרויות"),    # Options / OPTIONS (CONFIRMED live)
        "1080251": V("משחק חדש"),                            # New Game
        "1011733": V("טען משחק"),                            # Load Game
        "1043183": V("המשך משחק"), "1043184": V("המשך"),     # CONTINUE / Continue
        "1006284": V("שפה"),                                 # Language
        # ---- bidi A/B — CONFIRMED VISUAL on the UI, kept as the stale-deploy control
        "456219": V("שלום"),                                 # Controls   VISUAL
        "456223": L("שלום") + "  ZZ-LOGICAL",                # Sound      LOGICAL (wrong on purpose)
        "456235": V("אבגד"),                                 # Brightness direction control
        # ---- glyph coverage --------------------------------------------------
        "456233": V(ALEFBET),                                # Menu Language
        # ---- layout, both modes ---------------------------------------------
        "456237": V(PARA),                                   # Subtitle Display
        "456230": L(PARA),                                   # Music volume
        "456215": V("עמוד אפשרויות"),                        # Option Page
        "456238": V("שפת הכתוביות"),                         # Subtitle Language
        "456239": V("שחק לא מקוון"),                         # Play offline
        "456226": V("כן"), "456229": V("לא"),                # Yes / No
        "456227": V("פועל"), "456228": V("כבוי"),            # On / Off
    })


# 🔴 ROUND 2 PROVED THE SUBTITLE SURFACE IS **VISUAL** — and the paragraph row
# exposed the store-VISUAL wrap trap (§8b rule 4): the engine wraps in STORAGE
# order, so a long VISUAL line renders with its LINE ORDER INVERTED (`סימני פיסוק:`,
# the logical START, came out on the BOTTOM line). Measured exposure: **34 % of
# subtitle lines are >60 chars** and the shipped Arabic pre-wraps only 11 of
# 12,844 rows (Arabic gets engine bidi, so it never needed to). ⇒ Phase 2 MUST
# pre-wrap, and a pre-wrapper needs a BUDGET.
#
# RULER (the RDR2 method, §8b rule 5): each row is `W‹n›` + filler + `W‹n›`, sized
# so the WHOLE string is exactly n chars. The largest n whose TWO tags stay on ONE
# line is the usable width; that exact string is then measured in Heebo advances,
# which makes the answer FACE-INDEPENDENT (Heebo is injected into all 9 faces, so
# the Hebrew advances are Heebo's whichever face draws the subtitle).
#
# 🔴🔴 ROUND 3 USED `[n]` AND THE ENGINE ATE IT. Verified from both sides: 4,268
# rows carry a `[N]` in the LIVE forge, and not one bracket or digit reached the
# screen. Origins parses `[...]` as a control-name substitution and renders an
# unknown name as NOTHING. The trap is that I picked `[n]` *because* `aor_rtl`
# protects an all-digit bracket as an atomic token — but "my transform must not
# touch it" and "the engine claims it" are the SAME property read from two sides.
# **A proof marker must be a string the ENGINE has no meaning for.** `W44` is
# plain Latin+digits: no bracket, no token namespace, and Latin is already proven
# to render (`ZZ-SUB-V-ZZ`).
RULER_WIDTHS = (36, 40, 44, 46, 48, 50, 54)
_RULER_FILL = "אבגדהוזחט "


def _ruler(n):
    tag = f"W{n}"
    fill = n - 2 * len(tag) - 2          # two tags + the two spaces around the body
    body = (_RULER_FILL * (fill // len(_RULER_FILL) + 1))[:fill]
    return V(f"{tag} {body} {tag}")


def sub_rows(ids):
    """The SUBTITLE proof. Rotate three variants by id so ANY line the player
    triggers shows one, and adjacent lines of one conversation show DIFFERENT
    modes -> the A/B lands on a single screen without hunting for a scene.

    m==0/1 = the bidi A/B (ANSWERED: VISUAL wins). It is KEPT on purpose — the
    deliberately-wrong LOGICAL row is what makes a stale deploy impossible to
    mistake for a fix. m==2 now carries the width ruler."""
    out = {}
    for i in ids:
        m = int(i) % 3
        if m == 0:
            out[i] = V("שלום עברית") + "  ZZ-SUB-V-ZZ"
        elif m == 1:
            out[i] = L("שלום עברית") + "  ZZ-SUB-L-ZZ"
        else:
            out[i] = _ruler(RULER_WIDTHS[(int(i) // 3) % len(RULER_WIDTHS)])
    return out


def build():
    os.makedirs(BLOBS, exist_ok=True)
    fg = aor_loc.open_forge(FORGE)
    od = aor_cfd.oodle()
    plan = []

    # ---------------- candidate A: the English UI package -------------------
    p = aor_loc.find(fg, PKG_EN_UI, od)
    st = p.strings()
    st.update(ui_rows("ZZ-AOR-ENUI-ZZ"))
    blob = aor_cfd.encode_resource(
        [(d, ci) for d, ci, _ in p.parts][:-1] + [(p.rebuild(encode_payload(st)), p.parts[-1][1])],
        compressor=p.parts[-1][2] or aor_cfd.OODLE_KRAKEN, od=od)
    plan.append((p.entry.id, PKG_EN_UI, len(st), blob))

    # ---------------- candidate B: the Arabic UI stub, FILLED ---------------
    # Seed it with the full English id set so the UI stays usable if the engine
    # accepts Text=ar-AR; the 20 shipped Arabic strings are kept where present.
    pa = aor_loc.find(fg, PKG_AR_UI, od)
    base = dict(aor_loc.find(fg, PKG_EN_UI, od).strings())
    base.update(pa.strings())
    base.update(ui_rows("ZZ-AOR-ARUI-ZZ"))
    blob = aor_cfd.encode_resource(
        [(d, ci) for d, ci, _ in pa.parts][:-1] + [(pa.rebuild(encode_payload(base)), pa.parts[-1][1])],
        compressor=pa.parts[-1][2] or aor_cfd.OODLE_KRAKEN, od=od)
    plan.append((pa.entry.id, PKG_AR_UI, len(base), blob))

    # ---------------- the subtitle surface ----------------------------------
    ps = aor_loc.find(fg, PKG_AR_SUB, od)
    sst = ps.strings()
    sst.update(sub_rows(list(sst)))
    blob = aor_cfd.encode_resource(
        [(d, ci) for d, ci, _ in ps.parts][:-1] + [(ps.rebuild(encode_payload(sst)), ps.parts[-1][1])],
        compressor=ps.parts[-1][2] or aor_cfd.OODLE_KRAKEN, od=od)
    plan.append((ps.entry.id, PKG_AR_SUB, len(sst), blob))

    man = []
    for rid, name, n, blob in plan:
        path = os.path.join(BLOBS, f"{rid}.bin")
        open(path, "wb").write(blob)
        man.append({"id": rid, "name": name, "strings": n, "bytes": len(blob)})
        print(f"  {name:38s} id={rid:<14} {n:>6,d} strings -> {len(blob):>9,d} B")

    # the 9 Hebrew-injected fonts were written by aor_font.py into the same dir
    fonts = [f for f in os.listdir(BLOBS)
             if f.endswith(".bin") and int(f[:-4]) not in {r["id"] for r in man}]
    print(f"  + {len(fonts)} Hebrew-injected font blobs already staged")
    json.dump(man, open(os.path.join(BLOBS, "manifest.json"), "w"), indent=1)
    return man


def all_blobs():
    return sorted(int(f[:-4]) for f in os.listdir(BLOBS)
                  if f.endswith(".bin") and f[:-4].isdigit())


def deploy():
    ids = all_blobs()
    print(f"deploying {len(ids)} resources into {FORGE}")
    for rid in ids:
        blob = open(os.path.join(BLOBS, f"{rid}.bin"), "rb").read()
        aor_deploy.apply(FORGE, rid, blob)
    print("done — backup at", aor_deploy.backup_path(FORGE))


def verify():
    """Read the LIVE forge back — never trust the builder ([[patch-every-copy-verify-winner]])."""
    fg = aor_loc.open_forge(FORGE)
    od = aor_cfd.oodle()
    ok = True
    for name, marker in ((PKG_EN_UI, "ZZ-AOR-ENUI-ZZ"), (PKG_AR_UI, "ZZ-AOR-ARUI-ZZ")):
        p = aor_loc.find(fg, name, od)
        st = p.strings()
        # INT keys — see _i(). 1083812 = Discovery Tour, the main-menu marker slot;
        # 456221 = CREDITS, the options-page one.
        hits = {k: st.get(k) for k in (1083812, 456221)}
        good = all(v == marker for v in hits.values())
        ok &= good
        print(f"  {name:38s} {len(st):>6,d} strings · "
              f"markers={ {k: (v == marker) for k, v in hits.items()} } "
              f"{'OK' if good else 'MISMATCH ' + repr(hits)}")
    p = aor_loc.find(fg, PKG_AR_SUB, od)
    st = p.strings()
    # Match on tokens that survive BOTH storage modes verbatim — the `ZZ-SUB-*`
    # tags and the ruler's `W‹n›` (a Latin+digit island the UBA keeps intact).
    # Matching Hebrew here would re-run trap #2: an `id%3==2` row is stored
    # pre-reversed, so the literal form is NOT a substring and a correct build
    # reports two-thirds failure.
    tags = tuple(f"W{n_}" for n_ in RULER_WIDTHS)
    n = sum(1 for v in st.values()
            if "ZZ-SUB-" in v or any(t in v for t in tags))
    print(f"  {PKG_AR_SUB:38s} {len(st):>6,d} strings · {n:,d}/{len(st):,d} carry the proof")
    ok &= n == len(st)
    # fonts
    import aor_font
    heb = 0
    for e, blob in aor_font.font_entries(fg, od):
        fr = aor_font.FontRes(e, blob, od)
        _, _, h = aor_font.describe(fr.ttf)
        heb += (h == 27)
    print(f"  fonts with 27/27 Hebrew in the LIVE forge: {heb}/9")
    ok &= heb == 9
    print("VERIFY", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        aor_deploy.revert(FORGE)
        return 0
    if a.build or a.deploy:
        build()
    if a.deploy:
        deploy()
    if a.verify:
        return verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
