# -*- coding: utf-8 -*-
"""Build + deploy the full Hebrew r_lang_ar.wad for God of War: Ragnarök.

Usage:
  python build_wad.py            # pack hebrew.json + inject font -> out/ -> deploy
  python build_wad.py --no-font  # skip font injection (text only, for testing)
  python build_wad.py --deploy   # also copy to C:\\Games copy
  python build_wad.py --verify   # verify an existing out/r_lang_ar.wad

Reads:  arabic.json  (AR fallback for untranslated IDs)
        hebrew.json  (translated output from gowr_translate.py)
Writes: out/r_lang_ar.wad

Deploy targets:
  (1) Game Lab copy  — exec/wad/pc_le/r_lang_ar.wad  (always, our work copy)
  (2) C:\\Games copy — exec/wad/pc_le/r_lang_ar.wad  (--deploy flag)
"""
import sys, os, json, shutil, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.normpath(os.path.join(HERE, ".."))
REPO  = os.path.normpath(os.path.join(ROOT, "..", ".."))

SRC_WAD   = os.path.join(ROOT, "extract", "r_lang_ar.wad")
HE_JSON   = os.path.join(HERE, "hebrew.json")
AR_JSON   = os.path.join(HERE, "arabic.json")
OUT_DIR   = os.path.join(ROOT, "out")
OUT_WAD   = os.path.join(OUT_DIR, "r_lang_ar.wad")

GAME_LAB  = r"C:\Game Lab\God of War - Ragnarok"
GAMES_DIR = r"C:\Games\God of War - Ragnarok"
WAD_REL   = os.path.join("exec", "wad", "pc_le", "r_lang_ar.wad")


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def backup_if_needed(wad_path):
    bak = wad_path + ".he_backup"
    if not os.path.exists(bak) and os.path.exists(wad_path):
        shutil.copy2(wad_path, bak)
        print(f"  backup -> {bak}")


def deploy(out_wad, target_dir, label):
    dst = os.path.join(target_dir, WAD_REL)
    if not os.path.exists(os.path.dirname(dst)):
        print(f"  {label}: target dir not found, skipping")
        return
    backup_if_needed(dst)
    shutil.copy2(out_wad, dst)
    print(f"  deployed -> {dst}  ({os.path.getsize(dst):,} B)")


def main():
    sys.path.insert(0, HERE)
    import gowr_wad as W
    import gowr_font as F

    no_font = "--no-font" in sys.argv
    do_deploy_games = "--deploy" in sys.argv
    verify_only = "--verify" in sys.argv

    if verify_only:
        print(f"verify {OUT_WAD}")
        re_ext = W.extract(OUT_WAD)
        he = load_json(HE_JSON)
        correct = sum(1 for k, v in he.items() if re_ext.get(k) == v)
        print(f"  translated IDs: {len(he):,}  in-WAD correct: {correct:,}")
        blob = bytearray(W.decompress(OUT_WAD))
        STREAM_BASE_SMF = 2266599
        smf43_wtoc = struct.unpack_from('<I', blob, 0x40 + 43 * 0x90 + 0x78)[0]
        smf43_blob = STREAM_BASE_SMF + smf43_wtoc
        smf_data = bytearray(blob[smf43_blob:smf43_blob + 40520])
        heb_cps = [cp for _, cp in F.smf_records(smf_data) if 0x5D0 <= cp <= 0x5EA]
        print(f"  Hebrew SMF records: {len(heb_cps)}/27")
        return 0

    he_dict = load_json(HE_JSON)
    print(f"hebrew.json: {len(he_dict):,} translated IDs")

    if not he_dict:
        print("ERROR: hebrew.json is empty — run gowr_translate.py first"); return 1

    # BIDI FIX (2026-07-04, confirmed in-game): the Zouna engine does a SIMPLISTIC bidi — it keeps a
    # SPACE-separated English run together (LTR) but SPLITS + REVERSES an English run at an internal
    # HYPHEN ("anti-aliasing" rendered "aliasing) anti("; "NVIDIA DLSS" was fine). It also IGNORES
    # Unicode directional marks (LRI/LRE tested — no effect). So the reliable fix is to replace a
    # hyphen BETWEEN TWO LATIN letters with a space; the Hebrew-to-Latin connector (e.g. "ל-PLAYSTATION"
    # = a Hebrew ל prefix) is UNTOUCHED because its left side is Hebrew, not Latin.
    import re as _re

    # ITALIC MARKUP STRIP (2026-07-04, from a subtitle screenshot report): the engine applies a
    # SYNTHETIC italic SLANT to the [i]...[/i] run. On the injected Hebrew glyphs (metrics differ from
    # the native Arabic font) the slant SHIFTS the italic run — the user saw the italic word pushed
    # right with a gap ("[i]זה[/i] מה" -> gap after זה) and the adjacent space eaten ("אוכל [i]להשתמש[/i]—"
    # -> "אוכללהשתמש"). The official Arabic renders [i]...[/i] fine at ANY spacing, so it is NOT a spacing
    # bug — it is Hebrew-glyph-slant specific and no spacing rule fixes it. Removing the italic tags
    # (pure Hebrew, which renders correctly) is the reliable fix; italic emphasis on a word is cosmetic
    # and synthetic-sheared Hebrew reads poorly anyway. [style=...] highlights are LEFT (different visual,
    # not reported). Strip is literal (tags are glued to their content) so surrounding spaces stay
    # natural and no double space is created: "אוכל [i]x[/i]—" -> "אוכל x—", "[i]זה[/i] מה" -> "זה מה".
    _ITAL = _re.compile(r"\[/?i\]")
    _nital = 0
    for _k, _v in list(he_dict.items()):
        if isinstance(_v, str) and "[i]" in _v:
            _nv = _ITAL.sub("", _v)
            if _nv != _v:
                he_dict[_k] = _nv; _nital += 1
    print(f"bidi: stripped [i]/[/i] italic markup in {_nital} strings")

    _ENG_HYPHEN = _re.compile(r'(?<=[A-Za-z])-(?=[A-Za-z])')
    _nfix = 0
    for _k, _v in list(he_dict.items()):
        if isinstance(_v, str) and _ENG_HYPHEN.search(_v):
            he_dict[_k] = _ENG_HYPHEN.sub(' ', _v); _nfix += 1
    print(f"bidi: replaced English-English hyphens with spaces in {_nfix} strings")

    # BIDI FIX #2 (2026-07-04, PROVEN in-game via an Arabic-context A/B test): the Zouna engine
    # mishandles a parenthetical wrapping a Latin term in RTL context. A SINGLE Latin token
    # "(upscaling)" renders "upscaling))" (both parens collapse to one side as the same glyph), and NO
    # spacing/splitting fixes it (tested "(upscaling )", "( upscaling)", "( upscaling )" — all cluster).
    # A multi-word Latin parenthetical is also unreliable. Since the parenthetical English is a
    # translator-added GLOSS (the game's own Arabic drops it and translates the term), the robust,
    # uniform fix is to UNWRAP the parens around any Latin-only term -> the term stays inline, which
    # ALWAYS renders clean (exactly like every other inline Latin term, e.g. "NVIDIA DLSS"). Runs
    # AFTER hyphen->space. Only unwraps content that is Latin/ASCII (no Hebrew), has a real letter,
    # and is not a %-placeholder -> so "(מתפוצץ)", "(92%)", "(%d)", "(3.1)" are all LEFT untouched.
    _PAREN = _re.compile(r"\(([^()]{1,60})\)")
    def _unwrap_lat(m):
        s = m.group(1)
        if (_re.search(r"[A-Za-z]", s)
                and not _re.search(r"[֐-׿؀-ۿ]", s)
                and _re.fullmatch(r"[A-Za-z0-9 .,\-'&/]+", s)):
            return s
        return m.group(0)
    _npar = 0
    for _k, _v in list(he_dict.items()):
        if isinstance(_v, str) and "(" in _v:
            _nv = _PAREN.sub(_unwrap_lat, _v)
            if _nv != _v:
                he_dict[_k] = _nv; _npar += 1
    print(f"bidi: unwrapped Latin-term parentheticals in {_npar} strings")

    # DECIMAL-NUMBER BIDI (2026-07-04). PROVEN in-game: with the literal "." kept, the engine splits the
    # number at the "." and the ".1" ESCAPES to the LEFT (the user saw "the period and the 1 fled left").
    # No trick keeps the period in place (it is a hard engine bidi split at the "." separator). Turning
    # the "." into a SPACE keeps the digits in ORDER ("AMD FSR 3 1") with no escape — the best achievable
    # render (user earlier: "3 1 is very good"). Pure-Latin standalone values (no Hebrew) keep "3.1".
    _HEB = _re.compile(r"[֐-׿]")
    _DECIMAL = _re.compile(r"(?<=\d)\.(?=\d)")
    _ndec = 0
    for _k, _v in list(he_dict.items()):
        if isinstance(_v, str) and _HEB.search(_v) and _DECIMAL.search(_v):
            _nv = _DECIMAL.sub(" ", _v)
            if _nv != _v:
                he_dict[_k] = _nv; _ndec += 1
    print(f"bidi: decimal '.'->space in {_ndec} Hebrew-context strings (period escapes otherwise)")

    # SPACING FIX (2026-07-04, FINAL — ASYMMETRIC, root-caused from in-game screenshots). The engine
    # treats the two edges of an embedded Latin island DIFFERENTLY: at a Hebrew->Latin boundary (the
    # island's logical START = its RIGHT visual edge) it TRIMS one space, so a single source space
    # renders as ZERO -> the English abuts/"rides onto" the Hebrew on the right. At a Latin->Hebrew
    # boundary (the island's END = LEFT visual edge) it KEEPS the space -> a single space renders normal.
    # So NORMALIZE each boundary type to a DIFFERENT target: Hebrew->Latin gets GOWR_GAP_HL spaces
    # (default 3 -> ~2 after the trim -> English sits clear/"far" of the right Hebrew, no overlap);
    # Latin->Hebrew gets GOWR_GAP_LH (default 1 = the minimum, so it stays "close" to the ו on the left).
    # ` *` fully normalizes any existing 0/1/2/n spaces at each boundary.
    # Per user (2026-07-04): a BIG gap ONLY before an English COMMA-LIST (e.g. "NVIDIA DLSS, AMD FSR 3 1"),
    # to push the long enumeration LEFT, away from the Hebrew "את" on its right. A 3-word TITLE with no
    # comma ("GOD OF WAR") or a phrase ("anti aliasing") gets the NORMAL gap — the earlier 3-word rule
    # wrongly widened the main-menu title. The LEFT edge (Latin->Hebrew) is a normal single space.
    _sp = 0
    _GAP_HL_BIG = " " * int(os.environ.get("GOWR_GAP_HL_BIG", "6"))   # comma-list island RIGHT -> ~5 visible after trim
    _GAP_HL     = " " * int(os.environ.get("GOWR_GAP_HL", "2"))       # ordinary English RIGHT -> ~1 visible
    _GAP_LH     = " " * int(os.environ.get("GOWR_GAP_LH", "1"))       # LEFT edge -> normal single
    # Hebrew -> a Latin island that CONTAINS A COMMA (an enumeration). The class excludes Hebrew so it
    # stays within the island; the middle "," proves it's a list.
    _ML = _re.compile(r"([֐-׿]) *([A-Za-z][A-Za-z0-9 .'&/-]*,[A-Za-z0-9 .'&/-]*[A-Za-z0-9])")
    _MARK = "\x00" * 6   # big-gap placeholder (protects it from the single-word pass below)
    for _k, _v in list(he_dict.items()):
        if isinstance(_v, str):
            _nv = _ML.sub(r"\1" + _MARK + r"\2", _v)                                 # 3+ word island -> mark (big)
            _nv = _re.sub(r"([֐-׿]) *([A-Za-z0-9])", r"\1" + _GAP_HL + r"\2", _nv)    # 1-2 word right -> normal
            _nv = _nv.replace(_MARK, _GAP_HL_BIG)                                     # unmark -> big
            _nv = _re.sub(r"([A-Za-z0-9]) *([֐-׿])", r"\1" + _GAP_LH + r"\2", _nv)    # left edge -> normal
            if _nv != _v:
                he_dict[_k] = _nv; _sp += 1
    print(f"spacing: big(3+word)={len(_GAP_HL_BIG)} / small={len(_GAP_HL)} / left={len(_GAP_LH)} in {_sp} strings")

    # --letter-h N : override the Hebrew body target (diagnostic: 2x res test = 60).
    letter_h = 34          # user: shrink the Hebrew more to match the English (44->40->34).
    for a in sys.argv:
        if a.startswith("--letter-h="):
            letter_h = int(a.split("=", 1)[1])
    print(f"letter_h target = {letter_h}px")

    font_injector = None
    if not no_font:
        font_path = F.pick_font()
        def font_injector(blob):
            F.inject_hebrew(blob, font_path, letter_h=letter_h, log=lambda m: print(f"  [font] {m}"))

    print(f"packing -> {OUT_WAD}")
    dec_size, delta = W.pack(he_dict, SRC_WAD, OUT_WAD, font_injector=font_injector)
    print(f"  decompressed: {dec_size:,} B  msgs_txt_delta: {delta:+,} B")

    # quick sanity
    re_ext = W.extract(OUT_WAD)
    spot = list(he_dict.keys())[:5]
    spot_ok = all(re_ext.get(k) == he_dict[k] for k in spot)
    print(f"  spot-check {len(spot)} IDs: {'OK' if spot_ok else 'FAIL'}")

    # deploy ONLY to the project's Game Lab copy — the one the user runs
    # (C:\Games is intentionally left untouched per user request 2026-07-03).
    deploy(OUT_WAD, GAME_LAB, "Game Lab")
    if do_deploy_games:
        print("  (--deploy ignored: C:\\Games deploy disabled — project-folder only)")

    if "--launch" in sys.argv:      # user: do NOT auto-launch (2026-07-03) — opt-in only now
        relaunch_game()
    else:
        print("  (not launching — pass --launch to close+relaunch the game)")

    print("done")
    return 0


def force_windowed():
    """User standing rule (2026-07-04): ALWAYS open GoWR as a proper on-screen WINDOW, never
    fullscreen (fullscreen -> a black screen here) and never at the int16-underflow off-screen
    position a crash leaves behind (taskbar-only, no visible window). Force DisplayMode=Windowed +
    a valid TOP-RIGHT WindowPosition in settings.ini before every launch. This edits only the game's
    display config — NOT Saved Games."""
    ini = os.path.join(GAME_LAB, "settings.ini")
    if not os.path.exists(ini):
        return
    try:
        import re
        txt = open(ini, encoding="utf-8", errors="replace").read()
        # top-right for a ~1264x681 window on a 1920x1080 screen (x = 1920-1264-20, y = 20)
        txt = re.sub(r'(?m)^(DisplayMode=).*$', r'\1Windowed', txt)
        txt = re.sub(r'(?m)^(WindowPosition=).*$', r'\g<1>636, 20', txt)
        open(ini, "w", encoding="utf-8").write(txt)
        print("  settings.ini -> Windowed @ top-right (636, 20)")
    except Exception as e:
        print(f"  (settings.ini patch skipped: {e})")


def relaunch_game():
    """After every build: close GoWR.exe if running, force a proper window, then relaunch it (user
    standing rule 2026-07-03/04) so the fresh atlas is reloaded without a manual restart. Detached
    launch via os.startfile so the game survives this process exiting."""
    import subprocess, time
    exe = os.path.join(GAME_LAB, "GoWR.exe")
    try:
        r = subprocess.run(["taskkill", "/F", "/IM", "GoWR.exe"],
                           capture_output=True, text=True)
        if "SUCCESS" in (r.stdout or ""):
            print("  closed running GoWR.exe")
            time.sleep(2.0)   # let the file locks + process fully release
    except Exception as e:
        print(f"  (taskkill skipped: {e})")
    force_windowed()                 # ensure a proper on-screen window (never fullscreen/off-screen black)
    try:
        # CRITICAL: launch with cwd = the GAME dir. os.startfile inherits OUR cwd (work/), and the game
        # resolves settings.ini relative to the working directory -> from work/ it finds no settings.ini
        # and falls back to FULLSCREEN (the user's black screen); a user's double-click has cwd = the
        # game dir so it reads settings.ini and opens WINDOWED. subprocess.Popen(cwd=GAME_LAB) reproduces
        # the double-click. DETACHED so the game survives this script exiting.
        subprocess.Popen([exe], cwd=GAME_LAB,
                         creationflags=0x00000008 | 0x00000200,   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                         close_fds=True)
        print(f"  launched {exe}  (cwd={GAME_LAB})")
    except Exception as e:
        print(f"  ERROR launching game: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
