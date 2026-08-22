#!/usr/bin/env python3
r"""
build_menu_proof.py — the AC Odyssey Phase-1 menu proof: ONE deploy that closes
every remaining gate at once.

WHAT IT PROVES, and how to read the screenshot
──────────────────────────────────────────────
1. MOUNT (font-independent) — a pure-Latin marker. If you see `ZZ-ACO-A22-ZZ` or
   `ZZ-ACO-A24-ZZ`, the rebuilt LocalizationPackage loaded. Latin renders in the
   vanilla font, so this separates "the file didn't load" from "the font has no
   Hebrew glyphs" — otherwise both look like nothing/boxes.

2. WHICH ARABIC PACKAGE IS LIVE (a LADDER — the game ships TWO full Arabic sets):
       LocalizationPackage_Arabic      (language 22)  -> marker ZZ-ACO-A22-ZZ
       LocalizationPackage_Arabe_MTM   (language 24)  -> marker ZZ-ACO-A24-ZZ
   Whichever marker appears names the slot `ar-AA` resolves to. Don't guess it —
   one screenshot answers it ([[measure-with-a-ladder]]).

3. BIDI MODE — an A/B pair of the SAME word on adjacent rows plus a control:
       row `1` holds שלום stored LOGICAL
       row `2` holds שלום stored VISUAL (i.e. the bytes םולש)
       row `3` holds אבגד (4 non-confusable letters, LOGICAL)
   EXACTLY ONE of rows 1/2 can read שלום.
       row 1 correct  -> engine does bidi  -> store LOGICAL   (predicted)
       row 2 correct  -> engine does none  -> store VISUAL
   Row 3 must read אבגד right-to-left; if it reads דגבא the engine is not
   reordering. ⚠️ Read the ORDER off the picture, do not "translate" it —
   [[hebrew-screenshot-transcription-trap]].

4. GLYPH COVERAGE — a row with all 27 letters incl. the 5 finals. Any tofu box
   means that face missed the injection.

5. LAYOUT — a real sentence with punctuation, parentheses, quotes, digits and a
   Latin island, shipped in BOTH modes, so wrapping/neutral placement is visible.

DEPLOY TARGETS (§8e — patch EVERY copy, verify the winner)
    text  : ids 99519690106 (Arabic) + 10202694787 (Arabe_MTM)
            written into BOTH DataPC.forge AND DataPC_patch_01.forge
            (the same ids live in both, with DIFFERENT payloads — the patch wins,
             but patching only one is how AC Mirage lost a day)
    fonts : the base and patch forges hold 15 fonts EACH under DIFFERENT ids with
            byte-identical TTFs, so both sets are injected.

ACTIVATION (one registry string, no menu navigation):
    HKCU\SOFTWARE\Ubisoft\Assassins Creed Odyssey\Language = ar-AA
  `--deploy` sets it and records the previous value; `--revert` restores it.

    python work/build_menu_proof.py --deploy
    python work/build_menu_proof.py --verify
    python work/build_menu_proof.py --revert
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "..", "acunity", "work"))

import aco_forge                                        # noqa: E402
import aco_cfd                                          # noqa: E402
import aco_loc                                          # noqa: E402
import aco_rtl                                          # noqa: E402
import aco_font                                         # noqa: E402
from acu_loc import encode_payload                      # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("ACO_GAME", r"F:\Games\Assassin's Creed Odyssey")
BASE = os.path.join(GAME, "DataPC.forge")
PATCH = os.path.join(GAME, "DataPC_patch_01.forge")
STATE = os.path.join(ROOT, "work", "_proof_state.json")
BLOBS = os.path.join(ROOT, "work", "_blobs")

# 🔴 ACTIVATION — settled by reading the game's OWN config, not by guessing.
# `Documents\Assassin's Creed Odyssey\ACOdyssey.ini` is plain text:
#     [Language]
#     Text=ar-AR      <- the UI/text locale  (THE lever)
#     Subtitles=ar-AR
#     Sound=en-US     <- INDEPENDENT -> English VO is preserved for free
#     Client=ar-AR
# The code is **ar-AR**, NOT `ar-AA`. `uplay_install.state` pairs them
# (`…\Language` + `ar-AA` + `ar-AR`): `ar-AA` is Ubisoft's language-PACK id and
# `ar-AR` is the value the game actually reads. Every other locale has the pair
# identical (`en-US`/`en-US`), which is exactly why the difference is easy to miss.
# ⚠️ `expanduser("~")` / %USERPROFILE% resolve to the Antigravity SANDBOX profile
# here, so the ini read comes back EMPTY and looks like "the file has no
# [Language] section" ([[env-redirection-real-home]]). Resolve the REAL profile
# via FOLDERID_Profile, and honour a OneDrive-redirected Documents.
def _real_home():
    try:
        import ctypes
        from ctypes import wintypes
        FOLDERID_Profile = ctypes.create_string_buffer(
            b"\x1a\x4c\xdb\x5e\x25\x0f\xf3\x4f\xaf\x43\xa2\x4f\x25\x0c\xba\x18")
        # {5E4B23DB-...} built from bytes to avoid a GUID literal typo
        buf = ctypes.c_wchar_p()
        # SHGetKnownFolderPath(REFKNOWNFOLDERID, DWORD, HANDLE, PWSTR*)
        guid = (ctypes.c_byte * 16).from_buffer_copy(bytes.fromhex(
            "db234b5e" "0f25" "f34f" "a24fa243250cba18"))  # FOLDERID_Profile
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0:
            p = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
            if p and os.path.isdir(p):
                return p
    except Exception:
        pass
    for cand in (os.environ.get("USERPROFILE"), os.path.expanduser("~")):
        if cand and os.path.isdir(os.path.join(cand, "Documents")):
            return cand
    return os.path.expanduser("~")


def _find_ini():
    if os.environ.get("ACO_INI"):
        return os.environ["ACO_INI"]
    home = _real_home()
    cands = [os.path.join(home, "Documents"),
             os.path.join(home, "OneDrive", "Documents"),
             os.path.join(home, "OneDrive", "מסמכים")]
    try:                                    # the authoritative Documents location
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion"
                            r"\Explorer\Shell Folders") as k:
            cands.insert(0, os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
    except Exception:
        pass
    for d in cands:
        p = os.path.join(d, "Assassin's Creed Odyssey", "ACOdyssey.ini")
        if os.path.exists(p):
            return p
    return os.path.join(cands[0] if cands else home,
                        "Assassin's Creed Odyssey", "ACOdyssey.ini")


INI_PATH = _find_ini()
LANG_TARGET = "ar-AR"
LANG_KEYS = ("Text", "Subtitles", "Client")      # NOT `Sound` — keep English VO

REG_KEY = r"HKCU\SOFTWARE\Ubisoft\Assassins Creed Odyssey"
REG_VAL = "Language"

# The two full Arabic packages — the ladder.
AR_PACKAGES = {
    99519690106: ("A22", "LocalizationPackage_Arabic"),
    10202694787: ("A24", "LocalizationPackage_Arabe_MTM"),
}

ALEF_TAV = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"          # all 27, incl. the 5 finals
PARA = 'בדיקה: (סוגריים) "מרכאות" — מקף, 12.5 ו-Odyssey. סוף!'

# 🔴 SETTLED IN-GAME 2026-07-27: the engine's RTL pipeline is gated to the ARABIC
# script, so Hebrew is drawn in STORAGE order -> ship VISUAL (pre-reversed).
# The first build shipped LOGICAL and the user reported "עברית ראי".
SHIP = "visual"


def _key(strings, sid):
    """🔴 `decode_payload` returns **int** keys. A `str(sid)` lookup silently
    matches NOTHING and the build reports "0 edits applied", which reads exactly
    like "this package doesn't carry the menu". It was masked because dumping the
    dict to JSON turns int keys into strings. Accept either type."""
    if sid in strings:
        return sid
    s = str(sid)
    if s in strings:
        return s
    try:
        i = int(sid)
    except (TypeError, ValueError):
        return None
    return i if i in strings else None


def ship(s):
    """The SHIPPING transform — VISUAL, settled in-game (see the SHIP note)."""
    return aco_rtl.to_visual(s) if SHIP == "visual" else aco_rtl.to_logical(s)


def plan(tag):
    """id -> the bytes to store. Now that bidi is settled, the proof is a REAL
    Hebrew menu stored VISUAL: the decisive question is simply "does it read
    correctly?", which a native reader answers at a glance. One LOGICAL control
    row is kept so the contrast stays visible in the same screenshot."""
    S = ship
    L = aco_rtl.to_logical
    p = {}

    # ---- title screen: a real Hebrew menu, stored VISUAL ---------------
    p[2034381] = S("משחק חדש")                 # New Game
    p[2034382] = S("המשך משחק")                # Continue
    p[2163274] = S("המשך")                     # CONTINUE
    p[2163275] = S("המשך")                     # Continue

    # ---- pause menu (Character/Store/Options/Quit/Credits, one screen) --
    p[880583] = S("דמות")                      # Character
    p[880587] = S("חנות")                      # Store
    p[880588] = S("אפשרויות")                  # Options
    p[880590] = S("יציאה למסך הפתיחה")         # Quit to Title Screen
    p[880591] = S("קרדיטים")                   # Credits

    # ---- options page: layout + coverage + the control -----------------
    p[456215] = S(PARA)                        # Option Page -> punctuation/digits
    p[456219] = S("פקדים")                     # Controls
    p[456221] = S(ALEF_TAV)                    # Credits     -> all 27 letters
    # the ONE control row: stored LOGICAL, so it MUST look mirrored while every
    # other row reads correctly. Prefixed with a Latin tag that also doubles as
    # the build marker, so a stale deploy is impossible to mistake for a fix.
    p[456223] = f"ZZ-{tag}-LOGICAL " + L("שלום")
    return p


# ------------------------------------------------------------------ registry
def reg_get():
    try:
        out = subprocess.run(["reg", "query", REG_KEY, "/v", REG_VAL],
                             capture_output=True, text=True, timeout=20)
        for line in out.stdout.splitlines():
            if REG_VAL in line:
                return line.split()[-1]
    except Exception:
        pass
    return None


def reg_set(value):
    subprocess.run(["reg", "add", REG_KEY, "/v", REG_VAL, "/t", "REG_SZ",
                    "/d", value, "/f"], capture_output=True, text=True, timeout=20)


# ----------------------------------------------------------------- ACOdyssey.ini
def ini_read():
    """-> {key: value} of the [Language] section (empty if the ini is absent)."""
    out = {}
    if not os.path.exists(INI_PATH):
        return out
    sec = None
    for line in open(INI_PATH, encoding="utf-8", errors="replace"):
        t = line.strip()
        if t.startswith("[") and t.endswith("]"):
            sec = t[1:-1]
        elif sec == "Language" and "=" in t:
            k, v = t.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def ini_set(values):
    """Surgically rewrite only the given [Language] keys, preserving the file's
    exact line order, spacing and line endings. Never adds a key."""
    if not os.path.exists(INI_PATH):
        print(f"[warn] no {INI_PATH} — the game writes it on first launch")
        return
    with open(INI_PATH, "rb") as fh:
        raw = fh.read()
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    lines = raw.split(nl)
    sec, changed = None, 0
    for i, b in enumerate(lines):
        t = b.strip().decode("utf-8", "replace")
        if t.startswith("[") and t.endswith("]"):
            sec = t[1:-1]
            continue
        if sec != "Language" or "=" not in t:
            continue
        k = t.split("=", 1)[0].strip()
        if k in values:
            lines[i] = f"{k}={values[k]}".encode("utf-8")
            changed += 1
    with open(INI_PATH, "wb") as fh:
        fh.write(nl.join(lines))
    print(f"  ACOdyssey.ini: {changed} [Language] key(s) set "
          f"-> {', '.join(f'{k}={v}' for k, v in values.items())}")


# --------------------------------------------------------------------- build
def build_text(forge_path, od):
    """Rebuild both Arabic UI packages in one forge. Returns [(res_id, blob)]."""
    fg = aco_forge.Forge(forge_path)
    out = []
    for res_id, (tag, name) in AR_PACKAGES.items():
        ents = [e for e in fg.entries if e.id == res_id]
        if not ents:
            print(f"  [skip] {name}: id {res_id} not in {os.path.basename(forge_path)}")
            continue
        e = ents[0]
        pkg = aco_loc.Package(e, aco_cfd.decode_resource(fg.read(e), od))
        strings = pkg.strings()
        edits = plan(tag)
        applied, missing = 0, []
        for sid, text in edits.items():
            k = _key(strings, sid)
            if k is not None:
                strings[k] = text
                applied += 1
            else:
                missing.append(sid)
        # The BASE forge's Arabic package is an older, SMALLER set (23,519 strings
        # vs the patch's 25,401) — but it DOES carry the menu ids, so both copies
        # get patched (§8e). A package where nothing applies is skipped rather
        # than rewritten, since rewriting what we cannot edit only adds risk.
        if applied == 0:
            print(f"  {name:<32} lang={pkg.language:<3} SKIPPED — none of the "
                  f"{len(edits)} proof ids exist here ({len(strings):,} strings; "
                  f"this copy is not the one carrying the menu)")
            continue
        payload = encode_payload(strings)
        content = pkg.rebuild(payload)
        parts = [(d, ci) for d, ci, _ in pkg.parts]
        parts[-1] = (content, parts[-1][1])
        codec = next((c for _, _, c in pkg.parts if c), aco_cfd.OODLE_KRAKEN)
        blob = aco_cfd.encode_resource(parts, compressor=codec, od=od)
        print(f"  {name:<32} lang={pkg.language:<3} edits={applied}/{len(edits)}"
              f"{' MISSING ' + str(missing) if missing else ''}  "
              f"payload {len(pkg.payload):,}->{len(payload):,}  blob {len(blob):,}")
        out.append((res_id, blob))
    fg.close()
    return out


def build_fonts(forge_path, od, include_cjk=False):
    """Inject Hebrew into every UI font of one forge. Returns [(res_id, blob)]."""
    import io
    from fontTools.ttLib import TTFont
    from anno_font import _add_hebrew
    fg = aco_forge.Forge(forge_path)
    out = []
    for e, blob in aco_font.font_entries(fg, od):
        fr = aco_font.FontRes(e, blob, od)
        nm, _, heb = aco_font.describe(fr.ttf)
        if not include_cjk and nm in aco_font.CJK_FACES:
            continue
        if aco_font.is_cff(fr.ttf):
            print(f"  font #{e.index:<7} {nm:<22} SKIPPED (CFF/OTTO — glyf merge "
                  f"is a no-op; needs a whole-font replace)")
            continue
        src = (aco_font.DEFAULT_DONOR_BOLD if "bold" in nm.lower()
               else aco_font.DEFAULT_DONOR_MED if ("medium" in nm.lower()
                                                   or "cond" in nm.lower())
               else aco_font.DEFAULT_DONOR)
        f = TTFont(io.BytesIO(fr.ttf), fontNumber=0)
        added, _ = _add_hebrew(f, aco_font.donor_font(src))
        buf = io.BytesIO()
        f.save(buf)
        new_ttf = buf.getvalue()
        _, _, heb2 = aco_font.describe(new_ttf)
        res = aco_cfd.encode_resource(fr.cfd_parts(new_ttf),
                                      compressor=fr.codec, od=od)
        print(f"  font #{e.index:<7} {nm:<22} HEB {heb}->{heb2}/27 (+{added})  "
              f"ttf {fr.ttf_len:,}->{len(new_ttf):,}  blob {len(res):,}")
        out.append((e.id, res))
    fg.close()
    return out


# -------------------------------------------------------------------- deploy
def deploy(include_cjk=False):
    import aco_deploy
    od = aco_cfd.oodle()
    os.makedirs(BLOBS, exist_ok=True)
    state = {"lang_before": reg_get(), "ini_before": ini_read(), "forges": {}}

    for forge in (PATCH, BASE):                 # patch first: it is the winner
        if not os.path.exists(forge):
            print(f"[skip] missing {forge}")
            continue
        tagname = os.path.basename(forge)
        print(f"\n=== {tagname} ===")
        print("-- text --")
        items = build_text(forge, od)
        print("-- fonts --")
        items += build_fonts(forge, od, include_cjk)

        print(f"-- deploy {len(items)} resource(s) --")
        for res_id, blob in items:
            path = os.path.join(BLOBS, f"{tagname}.{res_id}.bin")
            open(path, "wb").write(blob)
            aco_deploy.apply(forge, res_id, blob)
        state["forges"][tagname] = [r for r, _ in items]
        aco_deploy.verify(forge)

    print("\n-- activation --")
    ini_set({k: LANG_TARGET for k in LANG_KEYS})
    reg_set(LANG_TARGET)
    state["lang_after"] = reg_get()
    state["ini_after"] = ini_read()
    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=1)
    print(f"  registry Language: {state['lang_before']!r} -> {state['lang_after']!r}")
    print(f"  ini [Language]   : {state['ini_after']}")
    print("\nDEPLOYED. Launch the game, look at the title screen, then press Esc "
          "in-game for the pause menu, and screenshot both.")
    return 0


def verify():
    od = aco_cfd.oodle()
    rc = 0
    for forge in (PATCH, BASE):
        if not os.path.exists(forge):
            continue
        print(f"\n=== {os.path.basename(forge)} ===")
        fg = aco_forge.Forge(forge)
        for res_id, (tag, name) in AR_PACKAGES.items():
            ents = [e for e in fg.entries if e.id == res_id]
            if not ents:
                continue
            pkg = aco_loc.Package(ents[0], aco_cfd.decode_resource(fg.read(ents[0]), od))
            s = pkg.strings()
            want = plan(tag)
            hit = sum(1 for sid, t in want.items()
                      if (k := _key(s, sid)) is not None and s[k] == t)
            print(f"  {name:<32} {hit}/{len(want)} edits present "
                  f"({len(s):,} strings)")
            if hit != len(want):
                rc = 1
        # font coverage, read back OUT of the live forge
        heb_ok = heb_bad = cff = 0
        for e, blob in aco_font.font_entries(fg, od):
            fr = aco_font.FontRes(e, blob, od)
            nm, _, heb = aco_font.describe(fr.ttf)
            if nm in aco_font.CJK_FACES:
                continue
            if aco_font.is_cff(fr.ttf):      # DINCond-Medium / -Bold: known gap
                cff += 1
                continue
            (heb_ok := heb_ok + 1) if heb == 27 else (heb_bad := heb_bad + 1)
        print(f"  fonts injected 27/27: {heb_ok}   failed: {heb_bad}   "
              f"CFF not-injectable (known): {cff}")
        if heb_bad:
            rc = 1
        print(f"  contiguity-violations: {fg.validate()} "
              f"(one per relocated resource is expected)")
        fg.close()
    ini = ini_read()
    lang_ok = all(ini.get(k) == LANG_TARGET for k in LANG_KEYS)
    print(f"\nactivation: ini [Language] {ini}  registry {reg_get()!r}")
    print(f"  [{'ok  ' if lang_ok else 'FAIL'}] text locale is {LANG_TARGET} "
          f"(Sound stays {ini.get('Sound')!r} -> English VO preserved)")
    return rc or (0 if lang_ok else 1)


def revert():
    import aco_deploy
    for forge in (PATCH, BASE):
        if os.path.exists(forge + ".he_backup") or os.path.exists(
                forge + ".he_journal.json"):
            print(f"=== {os.path.basename(forge)} ===")
            aco_deploy.revert(forge)
    if os.path.exists(STATE):
        st = json.load(open(STATE, encoding="utf-8"))
        ini_before = st.get("ini_before") or {}
        if ini_before:
            ini_set({k: v for k, v in ini_before.items() if k in LANG_KEYS})
        before = st.get("lang_before")
        if before:
            reg_set(before)
            print(f"registry Language restored -> {before!r}")
        else:
            subprocess.run(["reg", "delete", REG_KEY, "/v", REG_VAL, "/f"],
                           capture_output=True, text=True)
            print("registry Language removed (was absent before)")
        os.remove(STATE)
    if os.path.isdir(BLOBS):
        shutil.rmtree(BLOBS, ignore_errors=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--plan", action="store_true", help="print the proof plan only")
    ap.add_argument("--cjk", action="store_true", help="also inject the CJK fallbacks")
    a = ap.parse_args()

    if a.plan:
        for tag in ("A22", "A24"):
            print(f"--- {tag} ---")
            for sid, t in plan(tag).items():
                print(f"  {sid}: {t!r}")
        return 0
    if a.revert:
        return revert()
    if a.verify:
        return verify()
    if a.deploy:
        return deploy(a.cjk)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
