#!/usr/bin/env python3
"""
build_menu_proof.py - the Corsair Cove Phase-1 proof, round 3: STUB REPLACEMENT.

WHY
---
Round 1 (`~mods/pakchunk999-WinGDK_P.pak`) and round 2 (a 3-way ladder over
`pakchunk0-WinGDK_P.pak` / `~mods/pakchunk0_s2-WinGDK_P.pak` /
`pakchunk0_s25-WinGDK_P.pak`) both showed NOTHING in-game -- not even the
pure-Latin marker. This is a Microsoft-Store / GDK build whose `package.manifest`
and `layout_*.xml` ENUMERATE every shipped pak by name, so an ADDED pak is
apparently never mounted, however it is named or wherever it is placed.

THE LEVER
---------
24 of the shipped paks are **339-byte EMPTY STUBS** (`repak info` -> `0 file
entries`): `pakchunk0_s1..s24-WinGDK.pak`. All of their real content went to the
IoStore side (`.ucas`/`.utoc`), so the `.pak` half carries nothing. They are
listed in the manifest, so the engine definitely mounts them -- and overwriting
one loses NOTHING.

So: put our payload INSIDE three of those stubs. Backup = 339 bytes each.
The `.ucas`/`.utoc` of those chunks are never touched.

  S2  pakchunk0_s2-WinGDK.pak   -> en/CoveGame.locres  (the full Hebrew proof)
  S3  pakchunk0_s3-WinGDK.pak   -> UI/ST_Options.csv   (the runtime-CSV surface)
  S4  pakchunk0_s4-WinGDK.pak   -> the 4 Hebrew .ufont

🔴 ROUND-2 LESSON BAKED IN: put the MOUNT MARKER ON A KEY THAT IS ACTUALLY ON THE
SCREEN. Round 2's marker sat on `NewGame`, and this game's main menu has no "New
Game" row at all -- it reads Resume / Story Mode / Uncharted Mode / Load /
Settings / Credits / Quit. Every proof string below is now pinned to a row that
is visible in the screenshot the user already sent.

THE WHOLE PROOF IS ON ONE SCREEN
--------------------------------
  Resume          ZZ-S2-LOCRES-ZZ   MOUNT (pure Latin -> font/bidi independent)
  Story Mode      שלום  LOGICAL     bidi A
  Uncharted Mode  םולש  VISUAL      bidi B  (exactly one of A/B can read שלום)
  Load            ZZ-S3-CSV-ZZ      the OTHER surface, in its OWN pak
  Help            אבגד               direction control
  (Settings + the whole Settings dialog carry the layout paragraph + tab ladders)
  Credits         all 27 letters     glyph coverage
  Quit            1 שלום             digit side (answers bidi even through tofu)

    python build_menu_proof.py            # build only
    python build_menu_proof.py --deploy
    python build_menu_proof.py --revert
    python build_menu_proof.py --status
"""
import os
import shutil
import stat
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GAME_DIR, "..", ".."))
sys.path.insert(0, os.path.join(GAME_DIR, "tools"))

import cc_locres  # noqa: E402
import cc_rtl  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = os.environ.get("CC_GAME", r"E:\Games\Corsair Cove")
PAKS = os.path.join(GAME, "CorsairCove", "Content", "Paks")
MODS = os.path.join(PAKS, "~mods")

REPAK = os.path.join(REPO, "games", "hogwarts_legacy", "tools", "repak.exe")
PRISTINE = os.path.join(GAME_DIR, "extract", "pak0")
FONTS_HE = os.path.join(GAME_DIR, "work", "fonts_he")
WORK = os.path.join(GAME_DIR, "work")
STUB_BAK = os.path.join(WORK, "stub_backups")

LOC_REL = "CorsairCove/Content/Localization/CoveGame/en/CoveGame.locres"
CSV_REL = "CorsairCove/Content/StringTables/UI/ST_Options.csv"

# The empty shipped stubs we hijack. A stub MUST be verified 0-entry before we
# overwrite it, so we can never destroy real content.
STUB_LOC = "pakchunk0_s2-WinGDK.pak"
STUB_CSV = "pakchunk0_s3-WinGDK.pak"
STUB_FNT = "pakchunk0_s4-WinGDK.pak"
STUBS = [STUB_LOC, STUB_CSV, STUB_FNT]

# Paks ADDED by rounds 1-2; --revert deletes them too.
ADDED_ROUND12 = [
    (PAKS, "pakchunk0-WinGDK_P.pak"),
    (PAKS, "pakchunk0_s25-WinGDK_P.pak"),
    (PAKS, "pakchunk999-WinGDK_P.pak"),
    (MODS, "pakchunk0_s2-WinGDK_P.pak"),
    (MODS, "pakchunk999-WinGDK_P.pak"),
]

MARKER_LOC = "ZZ-S2-LOCRES-ZZ"
MARKER_CSV = "ZZ-S3-CSV-ZZ"
ALEPH_TAV = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
PARA = 'בדיקה: (סוגריים) "מרכאות" - מקף, נקודה. 12.5% ואז Corsair Cove!'

# Every key below was READ OFF the user's main-menu screenshot.
PLAN = {
    ("ST_Options", "Menu_Resume"): MARKER_LOC,                # row "Resume"
    ("ST_Options", "StoryMode"): "שלום",                      # row "Story Mode"   LOGICAL
    ("ST_Options", "FreePlay"): cc_rtl.to_visual("שלום"),     # row "Uncharted Mode" VISUAL
    ("ST_Options", "Menu_Help"): "אבגד",                      # direction control
    ("ST_Options", "Credits"): ALEPH_TAV,                     # row "Credits"
    ("ST_HUD", "Quit"): "1 שלום",                             # row "Quit"
    # belt-and-braces: the other plausible key for a quit row
    ("ST_Options", "Menu_ExitToDesktop"): "9 עברית",
    # --- options screen ------------------------------------------------------
    ("ST_Options", "HEADER_Language"): "שפה",
    ("ST_Options", "TextLanguage_LABEL"): "שפת טקסט",
    ("ST_Options", "Back"): "חזרה",
}
CSV_MARKER_KEY = "Menu_Load"                                  # row "Load"

# --- Settings screen ---------------------------------------------------------
# Every key below was resolved by searching the corpus for the exact ENGLISH VALUE
# shown in the user's Settings screenshot ([[resolve-ids-by-value-not-by-sibling]]).
# 🔴 The TABS do NOT use the keys whose names suggest them: the "Graphics" tab is
# `ST_HUD/Graphics`, not `ST_Options/HEADER_Graphics`, and the "Sound" tab is
# `ST_HUD/Sound` while `HEADER_Audio` is the word "Audio". Where two keys share the
# same English, both are patched with a DISTINGUISHING suffix so one screenshot
# names the live one.
PLAN_SETTINGS = {
    # the dialog title is wide + centred -> the best place for the layout paragraph
    ("ST_Options", "Menu_Settings"): PARA,                      # layout LOGICAL
    ("ST_Options", "Section_Color"): cc_rtl.to_visual(PARA),    # layout VISUAL
    # tabs
    ("ST_Options", "HEADER_Accessibility"): "נגישות",
    ("ST_HUD", "Graphics"): "גרפיקה",
    ("ST_HUD", "Sound"): "שמע",
    ("ST_HUD", "Gameplay"): "משחקיות",
    ("ST_HUD", "Controls"): "בקרים",
    # ✅ ladders RESOLVED in-game: the tab showed "מצלמה-O" and the section "כללי-S"
    ("ST_Options", "HEADER_Camera"): "מצלמה",        # <- the LIVE Camera-tab key
    ("ST_Options", "Section_General"): "כללי",       # <- the LIVE section-header key
    # option rows
    ("ST_Options", "AudioLanguage_LABEL"): "שפת שמע",
    ("ST_Options", "Subtitles_LABEL"): "כתוביות",
    ("ST_Options", "UIScalingMode_LABEL"): "מצב קנה-מידה של הממשק",
    ("ST_Options", "Brightness_LABEL"): "תיקון גמא",
    ("ST_Options", "CVD_TypeLabel"): "מצב עיוורון צבעים",
}
PLAN.update(PLAN_SETTINGS)

# --- Graphics tab: the LONG-PARAGRAPH gate -----------------------------------
# The bottom description panel is the widest + tallest text area in the game, so
# it is where a real translated paragraph must be proven: word WRAP over several
# lines, LINE ORDER across an explicit newline, and neutral/bracket/digit
# placement at a line boundary (which a one-line label can never exercise).
LONG_WRAP = (
    'משפר את איכות התמונה על ידי שינוי מידת ההחלקה של הקצוות (anti-aliasing). '
    'השיטה שנבחרה עשויה לעשות זאת תוך רינדור המשחק ברזולוציה נמוכה יותר - '
    'למשל 1920x1080 במקום 2560x1440 - ומעלה את הביצועים ב-30% ולעיתים אף יותר. '
    'שים לב: אפשרויות כגון DLSS, AMD FSR ו-XeSS דורשות חומרה תואמת, '
    'ואיכות התמונה עשויה להשתנות בין "איכות" ל"ביצועים".'
)
# an explicit newline: the two lines MUST stay in this order (line 1 above line 2)
LONG_NEWLINE = (
    'שורה ראשונה: קובעת את שיטת האיכות שבה משתמש AMD FSR (1 מתוך 4).' + "\n" +
    'שורה שנייה: ככל שהאיכות נמוכה יותר, כך הביצועים טובים יותר - עד 60% שיפור.'
)
# the hardest bidi edge case: the paragraph BEGINS and ENDS with a Latin/digit run
LONG_EDGES = (
    'AMD FSR 2.2 קובע עד כמה תהיה התמונה חדה לאחר שדרוג הרזולוציה. '
    'ערך של 50% הוא ברירת המחדל; 100% חד מאוד ועלול להבליט רעש. טווח: 0-100%'
)
# 🔴 ROUND-4 GATE, found in-game: `LONG_EDGES` STARTS with a Latin run, so the UBA's
# first-strong-character rule (P2/P3) gave that paragraph an **LTR base** -- it
# left-aligned and its neutrals (`;`, `טווח:`, `0-100%`) resolved to the wrong side.
# The engine is behaving correctly; the SOURCE text is the problem. Two candidate
# fixes, laddered on two adjacent description panels against the untouched control:
RLM = "‏"   # zero-width strong-RTL; the fonts now carry an EMPTY glyph for it
EDGES_RLM = RLM + LONG_EDGES                       # candidate A: force the RTL base
EDGES_REORDERED = (                                # candidate B: a TRANSLATION fix --
    'קובע עד כמה תהיה התמונה חדה לאחר שדרוג הרזולוציה על ידי AMD FSR 2.2. '   # start Hebrew
    'ערך של 50% הוא ברירת המחדל; 100% חד מאוד ועלול להבליט רעש. הטווח הוא 0-100 אחוז.'
)
PLAN_LONG = {
    ("ST_GraphicsOptions", "AntiAliasing_DESC"): LONG_WRAP,      # ✅ WRAP proven correct
    ("ST_GraphicsOptions", "FSRQuality_DESC"): LONG_NEWLINE,     # ✅ line order proven correct
    ("ST_GraphicsOptions", "FSRSharpness_DESC"): EDGES_RLM,      # A: leading RLM
    ("ST_GraphicsOptions", "FrameRateLimit_DESC"): EDGES_REORDERED,  # B: reordered source
    ("ST_GraphicsOptions", "VSync_DESC"): LONG_EDGES,            # C: control (known wrong)
    # the Graphics tab labels, so the whole screen reads Hebrew
    ("ST_GraphicsOptions", "UpsamplingAntiAliasing_LABEL"): "החלקת קצוות / שדרוג רזולוציה",
    ("ST_GraphicsOptions", "AntiAliasing_LABEL"): "שיטת החלקה / שדרוג",
    ("ST_GraphicsOptions", "FSRQuality_LABEL"): "מצב איכות של AMD FSR",
    ("ST_GraphicsOptions", "FSRSharpness_LABEL"): "אחוז חדות של AMD FSR",
    ("ST_GraphicsOptions", "FrameSynchronization_CATEGORY"): "סנכרון פריימים",
    ("ST_GraphicsOptions", "VSync_LABEL"): "סנכרון אנכי",
    ("ST_GraphicsOptions", "FrameRateLimit_LABEL"): "הגבלת קצב פריימים",
    ("ST_Options", "Off"): "כבוי",
    ("ST_Options", "On"): "פעיל",
}
PLAN.update(PLAN_LONG)



def _force_rmtree(path, tries=8):
    if not os.path.isdir(path):
        return
    for i in range(tries):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            for dp, dns, fns in os.walk(path):
                for n in dns + fns:
                    try:
                        os.chmod(os.path.join(dp, n), stat.S_IWRITE)
                    except OSError:
                        pass
            time.sleep(0.25 * (i + 1))
    os.rename(path, path + ".old%d" % int(time.time()))


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit("command failed: %s" % " ".join(cmd))
    return r.stdout


def _pack(stage, out_pak):
    if os.path.isfile(out_pak):
        os.remove(out_pak)
    _run([REPAK, "pack", "--version", "V11", "--mount-point", "../../../",
          stage, out_pak])
    return out_pak


def _stage(name):
    d = os.path.join(WORK, "_stage_" + name)
    _force_rmtree(d)
    return d


def build_locres():
    stage = _stage("loc")
    parsed = cc_locres.load(os.path.join(PRISTINE, LOC_REL))
    index = {(ns["name"], e["key"]): e
             for ns in parsed["namespaces"] for e in ns["entries"]}
    missing = [k for k in PLAN if k not in index]
    if missing:
        raise SystemExit("keys not in the locres: %r" % missing)
    for k, v in PLAN.items():
        index[k]["value"] = v
    dst = os.path.join(stage, LOC_REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cc_locres.save(parsed, dst)
    return _pack(stage, os.path.join(WORK, "S2_locres.pak"))


def build_csv():
    stage = _stage("csv")
    dst = os.path.join(stage, CSV_REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(os.path.join(PRISTINE, CSV_REL), encoding="utf-8-sig", newline="") as f:
        lines = f.read().split("\n")
    hit = 0
    for i, ln in enumerate(lines):
        if ln.startswith('"%s",' % CSV_MARKER_KEY):
            head, _, rest = ln.partition('","')
            _old, _, tail = rest.partition('","')
            lines[i] = '%s","%s","%s' % (head, MARKER_CSV, tail)
            hit += 1
    if hit != 1:
        raise SystemExit("CSV key %r matched %d rows (expected 1)" % (CSV_MARKER_KEY, hit))
    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        f.write("\n".join(lines))
    return _pack(stage, os.path.join(WORK, "S3_csv.pak"))


def build_fonts():
    stage = _stage("fnt")
    n = 0
    for dirpath, _dirs, files in os.walk(FONTS_HE):
        for fn in files:
            if not fn.lower().endswith(".ufont"):
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, FONTS_HE).replace("\\", "/")
            dst = os.path.join(stage, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    if n != 4:
        raise SystemExit("expected 4 injected fonts, found %d" % n)
    return _pack(stage, os.path.join(WORK, "S4_fonts.pak"))


def _entry_count(pak):
    return len(_run([REPAK, "list", pak]).split())


def verify(loc, csv, fnt):
    tmp = os.path.join(WORK, "_verify")
    _force_rmtree(tmp)
    _run([REPAK, "unpack", "-o", tmp, loc])
    d = cc_locres.load(os.path.join(tmp, LOC_REL))
    idx = {(ns["name"], e["key"]): e["value"]
           for ns in d["namespaces"] for e in ns["entries"]}
    bad = [k for k, v in PLAN.items() if idx.get(k) != v]
    if bad:
        raise SystemExit("locres pak missing %r" % bad)
    if idx[("ST_Options", CSV_MARKER_KEY)] == MARKER_CSV:
        raise SystemExit("the CSV key must stay English inside the locres pak")
    print("  S2 locres : %d/%d proof strings, CSV key left English" % (len(PLAN), len(PLAN)))
    _force_rmtree(tmp)
    _run([REPAK, "unpack", "-o", tmp, csv])
    if MARKER_CSV not in open(os.path.join(tmp, CSV_REL), encoding="utf-8-sig").read():
        raise SystemExit("CSV marker missing")
    print("  S3 csv    : marker present")
    _force_rmtree(tmp)
    if _entry_count(fnt) != 4:
        raise SystemExit("font pak entry count != 4")
    print("  S4 fonts  : 4 entries")


def _assert_stub_is_empty(path):
    """NEVER overwrite a pak that actually holds files."""
    if not os.path.isfile(path):
        raise SystemExit("stub missing: %s" % path)
    n = _entry_count(path)
    if n != 0:
        raise SystemExit("REFUSING to overwrite %s -- it holds %d entries, not a stub"
                         % (os.path.basename(path), n))


def deploy(loc, csv, fnt):
    # 1. clean up rounds 1-2 so nothing competes for the same file paths
    removed = _remove_added(quiet=True)
    if removed:
        print("  removed %d pak(s) added by earlier rounds" % removed)
    os.makedirs(STUB_BAK, exist_ok=True)
    for src, stub in ((loc, STUB_LOC), (csv, STUB_CSV), (fnt, STUB_FNT)):
        live = os.path.join(PAKS, stub)
        bak = os.path.join(STUB_BAK, stub + ".orig")
        if not os.path.isfile(bak):          # back up the PRISTINE stub, once
            _assert_stub_is_empty(live)
            shutil.copy2(live, bak)
            print("  backed up %-30s %5d B" % (stub, os.path.getsize(bak)))
        shutil.copy2(src, live)
        print("  wrote     %-30s %9d B" % (stub, os.path.getsize(live)))
    print("\nRUN THE GAME. Nothing to change in the settings.")
    print("On the MAIN MENU, the 7 rows should read:")
    print("   Resume          -> %s      (MOUNT: locres surface works)" % MARKER_LOC)
    print("   Story Mode      -> שלום           (bidi A, LOGICAL)")
    print("   Uncharted Mode  -> םולש           (bidi B, VISUAL)")
    print("   Load            -> %s        (the CSV surface works)" % MARKER_CSV)
    print("   Settings        -> אבגד           (direction control)")
    print("   Credits         -> 27 Hebrew letters (glyph coverage)")
    print("   Quit            -> 1 שלום         (digit side)")


def _remove_added(quiet=False):
    n = 0
    for folder, name in ADDED_ROUND12:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            os.remove(p)
            n += 1
            if not quiet:
                print("removed", p)
    try:
        if os.path.isdir(MODS) and not os.listdir(MODS):
            os.rmdir(MODS)
    except OSError:
        pass
    return n


def revert():
    n = _remove_added()
    for stub in STUBS:
        bak = os.path.join(STUB_BAK, stub + ".orig")
        live = os.path.join(PAKS, stub)
        if os.path.isfile(bak):
            shutil.copy2(bak, live)
            print("restored %-30s %5d B" % (stub, os.path.getsize(live)))
            n += 1
    if n == 0:
        print("nothing to revert")


def status():
    print("game :", GAME, "(exists)" if os.path.isdir(GAME) else "(MISSING)")
    for stub in STUBS:
        live = os.path.join(PAKS, stub)
        bak = os.path.join(STUB_BAK, stub + ".orig")
        sz = os.path.getsize(live) if os.path.isfile(live) else -1
        print("  %-30s live=%-10s backup=%s"
              % (stub, sz, "yes" if os.path.isfile(bak) else "NO"))
    for folder, name in ADDED_ROUND12:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            print("  leftover added pak:", p)


def main(argv):
    if "--revert" in argv:
        revert()
        return 0
    if "--status" in argv:
        status()
        return 0
    loc, csv, fnt = build_locres(), build_csv(), build_fonts()
    for p in (loc, csv, fnt):
        print("built %-20s %9d B" % (os.path.basename(p), os.path.getsize(p)))
    verify(loc, csv, fnt)
    if "--deploy" in argv:
        deploy(loc, csv, fnt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
