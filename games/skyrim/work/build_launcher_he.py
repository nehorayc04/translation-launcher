"""Hebrew for SkyrimSELauncher.exe — menu bitmaps + the English string block.

TWO surfaces, and they need OPPOSITE treatment:

  * the 4 main-menu buttons are pre-rendered 275x50 BITMAPS, so there is no bidi
    question at all -- we rasterise Hebrew ourselves in visual order and match the
    original's right edge, cap height, brightness and anti-aliasing profile;
  * everything else is an RT_STRING drawn by Win32, where the bidi behaviour is
    unknown until a screenshot says so -> the proof stores the SAME word both ways
    on adjacent rows of the Options dialog.

Nothing is guessed: every geometric number below was MEASURED off the shipped
English bitmaps (`--measure`).

usage: python build_launcher_he.py [--deploy] [--revert] [--verify] [--measure]
       python build_launcher_he.py --preview     # PNG contact sheet, no game needed
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import launcher_res as LR          # noqa: E402
from skyrim_rtl import to_visual   # noqa: E402

GAME = Path(r"D:\Games\TES - Skyrim - Anniversary Edition")
EXE = GAME / "SkyrimSELauncher.exe"
BACKUP = GAME / "SkyrimSELauncher.exe.he_backup"

# id -> (english, state)   MEASURED from the shipped bitmaps; every English entry
# is right-aligned with a 29 px right margin, dim peak 85 / bright peak 168.
MENU = {
    105: ("PLAY", "bright"), 114: ("PLAY", "dim"),
    119: ("OPTIONS", "bright"), 259: ("OPTIONS", "dim"),
    261: ("SUPPORT", "dim"), 265: ("SUPPORT", "bright"),
    107: ("EXIT", "dim"), 116: ("EXIT", "bright"),
}
MENU_HE = {"PLAY": "שחק", "OPTIONS": "אפשרויות", "SUPPORT": "תמיכה", "EXIT": "יציאה"}

FONT = "C:/Windows/Fonts/Heebo-Medium.ttf"
CONDENSE = 0.78          # the launcher face is condensed; Heebo needs pulling in
SS = 4                   # supersample

# === RT_STRING is stored LOGICAL ===========================================
# PROVEN in the Options dialog: "shalom" stored LOGICAL read CORRECTLY while the
# VISUAL copy on the adjacent checkbox read reversed. Win32/Uniscribe runs the bidi
# algorithm for dialog controls, so this surface is the OPPOSITE of the game engine
# (Scaleform, which does none and needs VISUAL). NEVER pass a string through
# to_visual() on its way into a resource.
MARKER = "ZZ-SKYL-OK-ZZ"

# scaffolding -- only for the gate proof, never shipped
PROOF_ONLY = {
    10007: MARKER,                         # "Graphics Adapter and Resolution" -> MOUNT
    10009: "שלום",                          # "Windowed Mode"  -> LOGICAL   \  bidi A/B
    10061: to_visual("שלום"),               # "Borderless"     -> VISUAL    /
    10004: "אבגד",                          # "Antialiasing"   -> direction control
    10006: "אבגדהוזחטיכךלמםנןסעפףצץקרשת",     # "Detail"         -> glyph coverage
}

# ALL 64 English launcher strings, LOGICAL. Decided against the panel of the eight
# languages the launcher already ships (extract/launcher_panel.json) rather than
# from the English alone -- e.g. "Adapters" is "Karten"/"Cartes graphiques"/
# "Адаптер" = the graphics CARD, and "Object Fade" is "Дальность отрисовки" = a
# draw DISTANCE, not a fade effect. German is the length budget: if DE fits the
# control, Hebrew of similar length fits.
# Brands / technique acronyms stay Latin (FXAA, TAA, SSAO, INI, DVD-ROM, setup.exe,
# Skyrim Special Edition). Leading spaces on 10024/10026 are LOAD-BEARING: the
# launcher appends them to a number.
REAL_STRINGS = {
    10000: "אישור",
    10001: "ביטול",
    10002: "כרטיס מסך",
    10003: "רזולוציות",
    10004: "החלקת קצוות",
    10005: "כבוי (ביצועים מיטביים)",
    10006: "רמת פירוט",
    10007: "כרטיס מסך ורזולוציה",
    10008: "הצג את כל הרזולוציות",
    10009: "מצב חלון",
    10010: "מתקדם",
    10011: "נמוכה מאוד",
    10012: "נמוכה",
    10013: "בינונית",
    10014: "גבוהה",
    10015: "גבוהה מאוד",
    10016: "אולטרה",
    10017: "איפוס",
    10018: "הגדרות הווידאו נקבעו לאיכות נמוכה.",
    10019: "הגדרות הווידאו נקבעו לאיכות בינונית.",
    10020: "הגדרות הווידאו נקבעו לאיכות גבוהה.",
    10021: "הגדרות הווידאו נקבעו לאיכות אולטרה.",
    10022: "אפשרויות",
    10023: "הגדרות וידאו",
    10024: " דגימות",
    10025: "כבוי (ביצועים מיטביים)",
    10026: " [ליטרבוקס]",
    10027: "רגיל (נמוך)",
    10028: "מסך רחב",
    10029: "רמת פירוט",
    10030: "טווח ראייה",
    10031: "קבצי נתונים",
    10032: "טעינת קבצים חופשיים",
    10033: ("נראה ש-Skyrim Special Edition אינו מותקן ולא נמצאה תוכנית ההתקנה.\n"
            "נסו לפתוח את כונן ה-DVD-ROM ולבחור את setup.exe כדי להתקין את המשחק."),
    10034: "לא זוהה התקן שמע. Skyrim Special Edition אינו יכול לפעול.",
    10035: "FXAA (נמוך)",
    10036: "TAA (איכות מיטבית)",
    10037: "איכות צללים",
    10038: "טווח צללים",
    10039: "כמות דקאלים",
    10040: "ללא",
    10041: "איכות קרני אור",
    10042: "השתקפויות מסך",
    10043: "הצללת סביבה",
    10044: "עומק שדה",
    10045: "הצללת גשם",
    10046: "שיידר שלג",
    10047: "סנוור עדשה",
    10048: "יעדי רינדור 64 סיביות",
    10049: "טווח עצמים",
    10050: "טווח דמויות",
    10051: "טווח עשב",
    10052: "טווח חפצים",
    10053: "טווח עצמים גדולים",
    10054: "פירוט עצמים רחוקים",
    10055: "טווח פירוט עצמים",
    10056: "מזהה את חומרת הווידאו",
    10057: ("Skyrim Special Edition יזהה כעת את חומרת הווידאו שלך "
            "ויקבע את הגדרות הווידאו בהתאם."),
    10058: "SSAO (גבוה)",
    10059: "כרטיס מסך לא מזוהה",
    10060: "לא הצלחנו לזהות את חומרת הווידאו שלך. הגדרות הווידאו נקבעו לאיכות נמוכה.",
    10061: "ללא מסגרת",
    10062: "יחס גובה-רוחב",
    10063: "לא נמצא קובץ INI. נא להתקין מחדש את Skyrim Special Edition.",
}


# ---------------------------------------------------------------- measurement
def ink_mask(a: np.ndarray, thr: int = 25):
    g = a.mean(axis=2)
    return g > np.median(g) + thr, g


def measure(data: bytes) -> dict:
    a = LR.bmp_to_array(data)
    m, g = ink_mask(a)
    ys, xs = np.where(m)
    return {"w": a.shape[1], "h": a.shape[0],
            "x0": int(xs.min()), "x1": int(xs.max()),
            "y0": int(ys.min()), "y1": int(ys.max()),
            "cap": int(ys.max() - ys.min() + 1),
            "peak": int(g[m].max()), "mean_ink": float(g[m].mean()),
            "right_margin": int(a.shape[1] - 1 - xs.max())}


# ------------------------------------------------------------------ rendering
def render_word(word_he: str, ref: dict, base: np.ndarray) -> np.ndarray:
    """Draw `word_he` into a copy of `base`, matching ref's box + brightness."""
    h, w = base.shape[:2]
    cap = ref["cap"]
    # 1. erase the original ink -> per-column background (the bg is near-black but
    #    has a faint left-edge gradient, so a per-column median keeps it seamless)
    m, _g = ink_mask(base)
    out = base.astype(np.float32).copy()
    for x in range(w):
        col = base[:, x][~m[:, x]]
        if len(col):
            out[m[:, x], x] = col.mean(axis=0)
    # 2. rasterise the Hebrew, supersampled, condensed on X only.
    #    Size from a FLAT letter ("ה": no ascender, no descender) -- measuring the
    #    whole alphabet inflates the reference by lamed's ascender and the final
    #    letters' descenders and silently under-sizes the word by ~40%.
    visual = to_visual(word_he)                 # PIL has no bidi (raqm absent)
    probe = ImageFont.truetype(FONT, 100)
    _, y0p, _, y1p = probe.getbbox("ה")
    body100 = y1p - y0p
    size = max(8, int(round(100 * cap * SS / body100)))
    f = ImageFont.truetype(FONT, size)
    ascent, _descent = f.getmetrics()
    PAD = 20 * SS
    tmp = Image.new("L", (w * SS * 3, h * SS * 4), 0)
    ImageDraw.Draw(tmp).text((PAD, PAD), visual, font=f, fill=255)
    bb = tmp.getbbox()
    if bb is None:
        return base
    baseline_ss = PAD + ascent                  # absolute baseline row, supersampled
    glyphs = tmp.crop(bb)
    base_in_crop = (baseline_ss - bb[1]) / SS   # baseline, in FINAL pixels
    gw = max(1, int(round(glyphs.width * CONDENSE)))
    glyphs = glyphs.resize((gw, glyphs.height), Image.LANCZOS)
    glyphs = glyphs.resize((max(1, gw // SS), max(1, glyphs.height // SS)), Image.LANCZOS)
    # 3. place: right edge matched, and the BASELINE aligned to the original ink
    #    bottom (the English is ALL-CAPS, so its ink bottom IS the baseline).
    #    Aligning the glyph-run bottom instead would float any word containing a
    #    descender (qof / final kaf-nun-pe-tsadi) upward.
    gx = ref["x1"] - glyphs.width + 1
    gy = int(round(ref["y1"] + 1 - base_in_crop))
    gx = max(0, min(gx, w - glyphs.width))
    gy = max(0, min(gy, h - glyphs.height))
    al = np.asarray(glyphs, dtype=np.float32) / 255.0
    # 4. brightness: match the original's PEAK so dim/bright states stay in step
    peak = ref["peak"]
    sub = out[gy:gy + glyphs.height, gx:gx + glyphs.width]
    out[gy:gy + glyphs.height, gx:gx + glyphs.width] = (
        sub * (1 - al[..., None]) + al[..., None] * peak)
    return np.clip(out, 0, 255).astype(np.uint8)


def build() -> dict[int, bytes]:
    src = BACKUP if BACKUP.exists() else EXE          # always build from PRISTINE
    bmps = LR.read_bitmaps(src)
    out: dict[int, bytes] = {}
    print("== menu bitmaps ==")
    for bid, (en, state) in MENU.items():
        ref = measure(bmps[bid])
        base = LR.bmp_to_array(bmps[bid])
        arr = render_word(MENU_HE[en], ref, base)
        out[bid] = LR.array_to_bmp(arr, bmps[bid])
        chk = measure(out[bid])
        print(f"  id={bid:<4} {en:<8}({state:<6}) -> {MENU_HE[en]:<9} "
              f"cap {ref['cap']}->{chk['cap']:<3} rightMargin {ref['right_margin']}->"
              f"{chk['right_margin']:<3} peak {ref['peak']}->{chk['peak']}")
    return out


# --------------------------------------------------------------------- deploy
def qa(strings: dict[int, str]) -> int:
    """Gate the launcher translation. Every check below caught a real defect class
    somewhere in this project before it reached a screen."""
    import re
    src = BACKUP if BACKUP.exists() else EXE
    en = {k: v for k, v in LR.read_strings(src).items() if 10000 <= k <= 10063}
    de = {k - 3000: v for k, v in LR.read_strings(src).items() if 13000 <= k <= 13063}
    HEB = re.compile(r"[֐-׿]")
    NIQ = re.compile(r"[֑-ׇ]")
    FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ぀-ヿ一-鿿]")
    KEEP = ("Skyrim Special Edition", "FXAA", "TAA", "SSAO", "INI",
            "DVD-ROM", "setup.exe", "64")
    bad = 0
    missing = sorted(set(en) - set(strings))
    if missing:
        print(f"  MISSING {len(missing)} ids: {missing}")
        bad += len(missing)
    for sid, he in sorted(strings.items()):
        src_en = en.get(sid, "")
        tag = f"  {sid}"
        if NIQ.search(he):
            print(f"{tag} NIQQUD"); bad += 1
        if FOREIGN.search(he):
            print(f"{tag} FOREIGN SCRIPT"); bad += 1
        if not HEB.search(he):
            print(f"{tag} NO HEBREW: {he!r}"); bad += 1
        if he == src_en:
            print(f"{tag} UNTRANSLATED (== English)"); bad += 1
        # leading/trailing space is load-bearing where the launcher concatenates
        if src_en[:1] == " " and he[:1] != " ":
            print(f"{tag} LOST LEADING SPACE: {he!r}"); bad += 1
        if src_en.count("\n") != he.count("\n"):
            print(f"{tag} NEWLINE COUNT {src_en.count(chr(10))} -> {he.count(chr(10))}")
            bad += 1
        for k in KEEP:
            if k in src_en and k not in he:
                print(f"{tag} DROPPED {k!r}"); bad += 1
        # every number in the source must survive
        ns, nh = re.findall(r"\d+", src_en), re.findall(r"\d+", he)
        if sorted(ns) != sorted(nh):
            print(f"{tag} NUMBERS {ns} -> {nh}"); bad += 1
        # length budget: German is the widest shipped language for these controls
        budget = max(len(src_en), len(de.get(sid, "")))
        if len(he) > budget * 1.35 + 6:
            print(f"{tag} TOO LONG {len(he)} vs budget {budget}: {he!r}"); bad += 1
    print(f"QA: {'PASS' if bad == 0 else f'{bad} DEFECTS'}  ({len(strings)}/{len(en)} ids)")
    return bad


def deploy(strings: dict[int, str], bitmaps: dict[int, bytes]) -> None:
    if not BACKUP.exists():
        shutil.copy2(EXE, BACKUP)
        print(f"  pristine backup -> {BACKUP.name}")
    LR.patch(BACKUP, EXE, strings=strings, bitmaps=bitmaps)
    print(f"  patched {EXE.name}  ({EXE.stat().st_size} B)")


def revert() -> None:
    if BACKUP.exists():
        shutil.copy2(BACKUP, EXE)
        BACKUP.unlink()
        print(f"restored {EXE.name} from the pristine backup")
    else:
        print("no backup -- nothing to revert")


def verify(expect: dict[int, str]) -> None:
    """Read the DEPLOYED exe back, never trust the builder."""
    s = LR.read_strings(EXE)
    b = LR.read_bitmaps(EXE)
    print(f"strings={len(s)} bitmaps={len(b)}")
    for sid in sorted(expect):
        got = s.get(sid, "")
        print(f"  {sid}  {'OK   ' if got == expect[sid] else 'DRIFT'} {got!r}")
    for bid in sorted(MENU):
        m = measure(b[bid])
        print(f"  bmp {bid:<4} ink x={m['x0']}..{m['x1']} cap={m['cap']} peak={m['peak']}")


def preview(bitmaps: dict[int, bytes]) -> None:
    src = BACKUP if BACKUP.exists() else EXE
    orig = LR.read_bitmaps(src)
    ids = sorted(MENU)
    W, H = 275, 50
    sheet = Image.new("RGB", (W * 2 + 18, len(ids) * (H + 14)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, bid in enumerate(ids):
        y = i * (H + 14)
        sheet.paste(Image.fromarray(LR.bmp_to_array(orig[bid])), (0, y + 12))
        sheet.paste(Image.fromarray(LR.bmp_to_array(bitmaps[bid])), (W + 18, y + 12))
        d.text((2, y + 1), f"{bid} {MENU[bid][0]} ({MENU[bid][1]})  ORIGINAL | HEBREW",
               fill=(255, 220, 120))
    p = HERE / "_launcher_menu_preview.png"
    sheet.save(p)
    print(f"-> {p}  {sheet.size}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--qa", action="store_true", help="run the gate only")
    ap.add_argument("--proof", action="store_true",
                    help="also deploy the gate-proof scaffolding strings")
    a = ap.parse_args()
    if a.revert:
        revert(); return 0
    if a.qa:
        return 1 if qa(REAL_STRINGS) else 0
    if a.verify:
        verify(REAL_STRINGS); return 0
    if a.measure:
        src = BACKUP if BACKUP.exists() else EXE
        for bid, (en, st) in sorted(MENU.items()):
            print(f"  {bid:<4} {en:<8} {st:<6} {measure(LR.read_bitmaps(src)[bid])}")
        return 0
    bmps = build()
    if a.preview:
        preview(bmps)
    if a.deploy:
        strings = dict(REAL_STRINGS)
        if a.proof:
            strings.update(PROOF_ONLY)
        if qa(REAL_STRINGS):
            print("REFUSING to deploy on a failing QA gate")
            return 1
        print(f"== deploy ({'proof + real' if a.proof else 'real only'}) ==")
        deploy(strings, bmps)
        print()
        verify(strings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
