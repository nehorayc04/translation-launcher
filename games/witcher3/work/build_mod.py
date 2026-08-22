"""Build + deploy the FULL Witcher 3 Hebrew mod (base + all DLC).

Reads the fleet's hebrew.json ({str_id: LOGICAL hebrew}) and, for every
ar.w3strings file (13 base content + 21 DLC), overrides each present str_id
with visual_line(he) (VISUAL bake — the W3 surface is NON-BIDI for Hebrew,
proven by the menu/dialogue proofs), re-encodes (Arabic slot = keyid 0
cleartext), backs up the original once (.he_backup), and writes.

Reversible: --revert restores every .he_backup. Font is separate (already
proven via repack_bundle.py). LOCAL build — never publishes.

Usage:  py build_mod.py            # dry-run: report per-file override counts, write nothing
        py build_mod.py --deploy   # backup + overwrite all 34 ar.w3strings (GAME MUST BE CLOSED)
        py build_mod.py --revert   # restore every ar.w3strings from its .he_backup
"""
import os, sys, json, glob, shutil, re
import w3strings as W
from bidi.algorithm import get_display

# --logical : store Hebrew in LOGICAL order (NO visual pre-reversal) — for a game
# engine that DOES bidi Hebrew script (later Next-Gen patches appear to; the shipped
# build is VISUAL because patch 4.00 does NOT). See the pre-launch section in CLAUDE.md.
LOGICAL = "--logical" in sys.argv

# CJK/Hangul/PUA in an English value = a corrupted extraction (mojibake); never
# fall back to it — keep the original Arabic instead (translated later from Arabic).
_MOJI = re.compile("[　-퟿-]")

# Tags / placeholders shielded from the bidi pass so it never scrambles their internals
# (e.g. "</i>" must stay "</i>", not become "<i/>"): <..>, {..}, %d/%s, &ent;.
_TOK = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]|&[a-zA-Z#0-9]+;')
# strip any stray explicit bidi controls from the source (our visual bake carries none)
_BIDI_STRIP = dict.fromkeys(
    [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
     0x2066, 0x2067, 0x2068, 0x2069, 0x061C], None)

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
HERE = os.path.dirname(os.path.abspath(__file__))
HEB_JSON = os.path.join(HERE, "..", "fleet", "hebrew.json")


def is_heb(ch):
    return "֐" <= ch <= "׿"


# Hebrew-prefix + ASCII hyphen + Latin word  (e.g. "ה-NPC", "ל-GWENT", "ב-nits").
# On the 4.04 bidi engine the neutral hyphen mis-resolves and lands on the visual
# LEFT (after the Latin), so "ה-NPC" renders "הNPC-". Candidate B: insert an RLM
# (U+200F) right AFTER the hyphen -> the hyphen is now flanked by two RTL-strong
# contexts (the Hebrew letter + the RLM) so it stays on the Hebrew side. The RLM is
# a zero-width bidi control (the Arabic-locale font renders it invisibly). Toggle a
# different candidate with the env HYPHEN_FIX = rlm(default) | maqaf | none.
_HYPH = re.compile(r'([֐-ת])-(?=[A-Za-z])')
_HYPHEN_FIX = os.environ.get("HYPHEN_FIX", "rlm")


def _fix_prefix_hyphen(s):
    if _HYPHEN_FIX == "rlm":
        return _HYPH.sub("\\1-‏", s)        # ה-<RLM>NPC
    if _HYPHEN_FIX == "maqaf":
        return _HYPH.sub("\\1־", s)         # ה־NPC  (Hebrew maqaf, strong RTL)
    return s                                     # "none": leave raw (baseline)


def logical_line(s):
    """LOGICAL storage: keep memory order, strip stray explicit bidi controls, then
    anchor the <heb>-<Latin> hyphen so the bidi engine keeps it on the Hebrew side.
    For an engine that bidi's Hebrew script itself."""
    return "\n".join(_fix_prefix_hyphen(ln.translate(_BIDI_STRIP)) for ln in s.split("\n"))


def visual_line(s):
    """VISUAL pre-bake for the NON-BIDI Hebrew renderer, via the Unicode Bidi Algorithm
    (python-bidi, base RTL) — per physical line. Correctly MIRRORS brackets ([..]→[..],
    (..)→(..)), keeps LTR islands ('Ray Tracing') and numbers/percent in their own order,
    and lays Hebrew right-to-left. Tags/placeholders (<..>, {..}, %d, &ent;) are shielded
    as single atoms so bidi never scrambles their internals (e.g. '</i>' stays '</i>').
    A line with NO Hebrew (keybind / English fallback / number) is returned AS-IS."""
    out = []
    for line in s.split("\n"):
        if not any(is_heb(c) for c in line):
            out.append(line)
            continue
        line = line.translate(_BIDI_STRIP)
        toks = []

        def _sub(m):
            toks.append(m.group(0))
            return chr(0xE000 + len(toks) - 1)

        prot = _TOK.sub(_sub, line)
        vis = get_display(prot, base_dir="R")
        if toks:
            vis = "".join(
                toks[ord(c) - 0xE000] if 0xE000 <= ord(c) < 0xE000 + len(toks) else c
                for c in vis)
        out.append(vis)
    return "\n".join(out)


def ar_files():
    files = glob.glob(os.path.join(GAME, "content", "content*", "ar.w3strings"))
    files += glob.glob(os.path.join(GAME, "dlc", "*", "content", "ar.w3strings"))
    return sorted(files)


# The boot epilepsy/health warning is a PRE-RENDERED VIDEO per language
# (movies/.../gamestart/epilepsy/epilepsy_<lang>.usm) — not text, so it can't be
# translated. On the hijacked Arabic slot the game plays epilepsy_ar.usm (Arabic
# text baked in). Swap it for the English video so nothing shows in Arabic.
_EPI = os.path.join(GAME, "content", "content0", "movies", "cutscenes",
                    "gamestart", "epilepsy")
_EPI_AR = os.path.join(_EPI, "epilepsy_ar.usm")
_EPI_EN = os.path.join(_EPI, "epilepsy_en.usm")


def swap_epilepsy_video():
    if not (os.path.exists(_EPI_AR) and os.path.exists(_EPI_EN)):
        print("  epilepsy video: not found — skipped"); return
    bak = _EPI_AR + ".he_backup"
    if not os.path.exists(bak):
        shutil.copy2(_EPI_AR, bak)          # preserve the original Arabic once
    if os.path.getsize(_EPI_AR) != os.path.getsize(_EPI_EN):
        shutil.copy2(_EPI_EN, _EPI_AR)      # boot warning now shows in English
        print("  epilepsy video: ar <- en (boot warning now English)")
    else:
        print("  epilepsy video: already English (skip)")


def revert():
    n = 0
    for f in ar_files():
        bak = f + ".he_backup"
        if os.path.exists(bak):
            shutil.copy2(bak, f); n += 1
    bak = _EPI_AR + ".he_backup"
    if os.path.exists(bak):
        shutil.copy2(bak, _EPI_AR); n += 1
        print("  epilepsy video restored to Arabic")
    print(f"reverted {n} files from .he_backup")


def build(deploy=False):
    heb = json.load(open(HEB_JSON, encoding="utf-8"))
    # full English source: any untranslated str_id falls back to ENGLISH (Latin),
    # never the game's original Arabic. All untranslated-with-English are junk
    # (numbers / key names / codes) whose correct display IS the Latin value.
    en_path = os.path.join(HERE, "..", "extract", "en.json")
    en = json.load(open(en_path, encoding="utf-8")) if os.path.exists(en_path) else {}
    bake = logical_line if LOGICAL else visual_line
    print(f"hebrew.json: {len(heb)} translated str_ids | en.json: {len(en)} fallback ids")
    print(f"bidi mode: {'LOGICAL (no pre-reversal)' if LOGICAL else 'VISUAL (pre-reversed)'}")
    files = ar_files()
    print(f"ar.w3strings files: {len(files)}\n")

    total_over = total_fb = total_str = 0
    per_file = []
    for f in files:
        src = f + ".he_backup" if os.path.exists(f + ".he_backup") else f
        d = W.decode(open(src, "rb").read())
        over = fb = 0
        for e in d["entries"]:
            sid = str(e["str_id"])
            if sid in heb:
                e["text"] = bake(heb[sid]); over += 1
            elif sid in en and en[sid].strip() and not _MOJI.search(en[sid]):
                # not translated -> show ENGLISH (Latin), not the original Arabic.
                # (skip garbled/mojibake English -> keep Arabic, translated later)
                e["text"] = bake(en[sid]); fb += 1
        rebuilt = W.encode(d["entries"], d["block2"], version=d["version"])
        # verify round-trip
        d2 = W.decode(rebuilt)
        assert len(d2["entries"]) == len(d["entries"]), f"entry-count drift in {f}"
        total_over += over; total_fb += fb; total_str += len(d["entries"])
        rel = f.replace(GAME, "").lstrip("\\/")
        per_file.append((rel, over, fb, len(d["entries"]), rebuilt))

    for rel, over, fb, tot, _ in per_file:
        print(f"  {rel:<34} he:{over:>6}  en-fallback:{fb:>4}  / {tot}")
    print(f"\nTOTAL: {total_over} Hebrew + {total_fb} English-fallback across {total_str} strings")
    print(f"       (remaining Arabic = {total_str - total_over - total_fb} = Arabic-only, no English source)")

    if not deploy:
        print("\n(dry-run) nothing written. Re-run with --deploy (GAME MUST BE CLOSED).")
        return

    written = 0
    for (rel, over, fb, tot, rebuilt), f in zip(per_file, files):
        bak = f + ".he_backup"
        if not os.path.exists(bak):
            shutil.copy2(f, bak)
        with open(f, "wb") as fh:
            fh.write(rebuilt)
        written += 1
    swap_epilepsy_video()
    print(f"\nDEPLOYED {written} files (each original backed up to .he_backup).")
    print("In-game: Options -> Language -> Text = Arabic (العربية); Speech = English.")
    print("Font: run repack_bundle.py deploy (David) if not already applied.")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        build(deploy="--deploy" in sys.argv)
