"""
Merge UI Hebrew translations into the WD2 main_arabic.loc string set.

The WD2 frontend/menu renderer does NOT apply bidi (it draws glyphs in storage
order), so Hebrew must be stored in VISUAL (pre-reversed) order — Latin/brand
runs and [TOKEN]/{VALUE}/%d specs are kept intact, Hebrew runs reversed, run
order reversed (RTL base), per line. Subtitles (a different, bidi renderer) are
left untouched here.

  python wd2_ui_merge.py <translations.json {id: he_logical}>  ->  C:/tmp/ui_he_strings.txt
then: wd2_loc.py encode <orig.loc> C:/tmp/ui_he_strings.txt <out.loc> ; wd2_archive deploy
"""
import json, io, re, sys

try:
    from bidi.algorithm import get_display      # real Unicode Bidi Algorithm (RTL base)
    _HAVE_BIDI = True
except Exception:
    _HAVE_BIDI = False

SRC = "C:/tmp/main_arabic.loc.txt"      # clean AR skeleton (UTF-16, [CR]/[LF] markers)
OUT = "C:/tmp/ui_he_strings.txt"

# the main-menu labels already chosen (logical Hebrew), kept in lockstep with menu_he.py
MENU_LOGICAL = {
    "Continue": "המשך", "New Game": "משחק חדש", "Load Game": "טען משחק",
    "Premium Content": "תוכן פרימיום", "Ubisoft Club": "מועדון Ubisoft",
    "Settings": "הגדרות", "Credits": "קרדיטים", "Options": "אפשרויות",
    "Quit to Desktop": "יציאה לשולחן העבודה", "Online": "מקוון",
    "[PC_ACCESS] ACCESS": "[PC_ACCESS] גישה",
}

HE = re.compile(r'[֐-׿]')
# preserved tokens kept as ATOMIC LTR islands across the bidi pass (never split,
# never bracket-mirrored): [TOKEN] / {VALUE} / %d-specs / &entity;
_TOKEN = re.compile(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[diufslxeDIUFSLXE]+|%%|&#?[A-Za-z0-9]+;')


def _visual_line(s):
    """logical Hebrew -> VISUAL (storage) order for WD2's NON-bidi frontend, via the
    real Unicode Bidi Algorithm (RTL base). Each preserved token is swapped for a
    single PUA placeholder (strong-LTR, atomic) so bidi keeps it whole and in the
    right place, then restored verbatim. This (vs the old naive run-reverse) keeps
    Latin/brand WORD ORDER correct ("Old Glory" not "Glory Old") and MIRRORS real
    punctuation brackets ( ) [ ] { } the way RTL needs."""
    if not s.strip():
        return s
    if not _HAVE_BIDI:
        raise RuntimeError("python-bidi required for correct RTL visual order — run "
                           "the build under the repo .venv (.venv\\Scripts\\python.exe).")
    toks = []

    def grab(m):
        toks.append(m.group(0)); return chr(0xE000 + len(toks) - 1)

    prot = _TOKEN.sub(grab, s)
    vis = get_display(prot, base_dir='R')
    return ''.join(toks[ord(c) - 0xE000] if 0xE000 <= ord(c) < 0xE000 + len(toks)
                   else c for c in vis)


def visual(s):
    """logical -> stored visual order, reversing each line independently so the
    non-bidi menu renderer shows correct RTL Hebrew. [CR]/[LF] kept as separators."""
    s = s.replace("\r", "[CR]").replace("\n", "[LF]")
    parts = re.split(r'(\[CR\]|\[LF\])', s)
    return ''.join(p if p in ("[CR]", "[LF]") else _visual_line(p) for p in parts)


def main():
    trans = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else {}
    trans = {int(k): v for k, v in trans.items()}
    raw = open(SRC, "rb").read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    out = io.StringIO()
    menu = ui = 0
    for line in raw.decode(enc, "replace").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if not k.isdigit():
            out.write(line + "\n"); continue
        kid = int(k)
        if v in MENU_LOGICAL:
            out.write(f"{kid}={visual(MENU_LOGICAL[v])}\n"); menu += 1
        elif kid in trans and trans[kid].strip():
            out.write(f"{kid}={visual(trans[kid])}\n"); ui += 1
        else:
            out.write(line + "\n")
    open(OUT, "w", encoding="utf-8").write(out.getvalue())
    print(f"merged menu={menu} ui={ui} -> {OUT}")


if __name__ == "__main__":
    main()
