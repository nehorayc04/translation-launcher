"""Merge BOTH the UI Hebrew (visual order) AND the SUBTITLE Hebrew (logical order)
into one main_arabic.loc strings file for encode+deploy.

Two renderers, two storage orders (this is the whole subtlety):
  * UI / frontend / menu / settings / HUD  -> NON-bidi  -> store VISUAL (pre-reversed)
    (wd2_ui_merge.visual()).
  * Spoken SUBTITLE / dialogue (the Arabic-slot narrative path) -> the Disrupt engine
    DOES bidi-reorder -> store LOGICAL (as translated). NO reversal. The forced line
    break (literal "\\n" from the oasis source) is written as the skeleton's [LF] marker.

Any id NOT in either set keeps the skeleton's original line (Arabic for untranslated
barks — readable RTL — until it gets translated).

  python wd2_sub_merge.py <ui_combined.json {id:he_logical}> <sub_he.json {id:he_logical}>
      -> C:/tmp/ui_he_strings.txt
then: wd2_loc.py encode C:/tmp/ar.loc C:/tmp/ui_he_strings.txt <out.loc> ; wd2_archive deploy
"""
import json, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wd2_ui_merge as UI            # reuse visual() + MENU_LOGICAL (one source of truth)

SRC = "C:/tmp/main_arabic.loc.txt"
OUT = "C:/tmp/ui_he_strings.txt"
OASIS = os.path.join(os.path.dirname(HERE), "extract", "en_oasis", "languages",
                     "english", "oasisstrings_converted.xml")
_SOUND = re.compile(r'enum="soundbinary[^"]*"\s+LineId="(\d+)"')

def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}

def soundbinary_ids():
    """ids whose oasis enum is soundbinary\\*.bnk = the SPOKEN-subtitle / narrative
    path, which the Disrupt engine renders WITH bidi -> store LOGICAL. EVERY other
    id is frontend/HUD (menus, descriptions, missions, messages, email, profiler) =
    NON-bidi -> store VISUAL. Misrouting named content to logical is exactly what
    made it render REVERSED in-game."""
    try:
        return {int(m.group(1)) for m in _SOUND.finditer(open(OASIS, encoding="utf-8").read())}
    except OSError:
        return set()

def norm_breaks(s):
    """normalize every line-break representation (entity / literal backslash-n /
    real newline) to a real newline so UI.visual() marks it [LF] for the encoder."""
    s = s.replace("&#xA;", "\n").replace("&#xa;", "\n")
    s = s.replace("&#xD;", "\r").replace("&#xd;", "\r")
    return s.replace("\\n", "\n").replace("\\r", "\r")

def sub_logical(s):
    """Subtitle storage: LOGICAL (engine bidi-reorders). Normalize EVERY line-break
    representation to the loc skeleton's [LF]/[CR] markers — the source/agent output
    can carry the literal two-char "\\n", an HTML entity "&#xA;", OR a real newline
    (line-based format must not contain raw newlines). Match the skeleton exactly so
    wd2_loc.py encode turns them back into real line breaks (not literal "&#xA;" text)."""
    s = s.replace("&#xA;", "[LF]").replace("&#xa;", "[LF]")
    s = s.replace("&#xD;", "[CR]").replace("&#xd;", "[CR]")
    s = s.replace("\\n", "[LF]").replace("\\r", "[CR]")
    s = s.replace("\r", "[CR]").replace("\n", "[LF]")
    return s

def main():
    ui  = {int(k): v for k, v in jload(sys.argv[1] if len(sys.argv) > 1 else "").items()}
    sub = {int(k): v for k, v in jload(sys.argv[2] if len(sys.argv) > 2 else "").items()}
    sound = soundbinary_ids()

    raw = open(SRC, "rb").read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    out = io.StringIO()
    n_vis = n_log = 0
    for line in raw.decode(enc, "replace").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if not k.isdigit():
            out.write(line + "\n"); continue
        kid = int(k)
        # pick the translated value (menu label > UI set > subtitle set)
        if v in UI.MENU_LOGICAL:
            val = UI.MENU_LOGICAL[v]
        elif kid in ui and str(ui[kid]).strip():
            val = ui[kid]
        elif kid in sub and str(sub[kid]).strip():
            val = sub[kid]
        else:
            out.write(line + "\n"); continue
        # ORIENTATION IS DECIDED BY THE ENUM, not by which file it came from:
        # soundbinary -> bidi narrative renderer -> LOGICAL; everything else -> VISUAL.
        if kid in sound:
            out.write(f"{kid}={sub_logical(val)}\n"); n_log += 1
        else:
            out.write(f"{kid}={UI.visual(norm_breaks(val))}\n"); n_vis += 1
    open(OUT, "w", encoding="utf-8").write(out.getvalue())
    print(f"merged visual(frontend)={n_vis} logical(subtitle)={n_log} -> {OUT}  "
          f"(soundbinary ids={len(sound)})")

if __name__ == "__main__":
    main()
