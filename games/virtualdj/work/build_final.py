r"""Build + deploy the FINAL Hebrew Languages\Arabic.xml.

Wraps every line of every value in RLE (U+202B) ... PDF (U+202C) so VirtualDJ's
renderers force RTL base direction (the engine bidi's Arabic correctly but leaves
Hebrew LTR-base without this; RLE makes Hebrew behave like Arabic). Proven in-game
2026-07-12 (dialog A/B/C test -> RLE = perfect).

  python build_final.py            # build to work/_hebrew_full_Arabic.xml
  python build_final.py --deploy   # + copy to %LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml
"""
import sys, os, json, re, shutil
from pathlib import Path
sys.argv0 = sys.argv[0]
HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))
import vdj_lang as V

RLE = "‫"   # RIGHT-TO-LEFT EMBEDDING
PDF = "‬"   # POP DIRECTIONAL FORMATTING


def wrap_rtl(value):
    """Wrap each (non-empty) line in RLE..PDF; preserve empty lines + newlines."""
    out = []
    for line in value.split("\n"):
        out.append(RLE + line + PDF if line.strip() != "" else line)
    return "\n".join(out)


def main():
    deploy = "--deploy" in sys.argv
    he = json.load(open(GAME / "agent_handoff" / "hebrew.json", encoding="utf-8"))
    wrapped = {k: wrap_rtl(v) for k, v in he.items()}
    arabic = (GAME / "extract" / "langs_orig" / "Arabic.xml").read_bytes()
    # show "עברית" (not "Arabic") in the Options language dropdown; keep iso="ar"
    # so the engine still selects the RTL locale.
    out = V.build_hebrew(arabic, wrapped, lang_attrib_override={"lang": "עברית"})
    built = HERE / "_hebrew_full_Arabic.xml"
    built.write_bytes(out)
    # sanity: re-parse, verify RLE present + Hebrew coverage
    _, secs = V.parse(out)
    flat = dict(V.flatten(secs))
    heb = sum(1 for v in flat.values() if re.search(r"[א-ת]", v))
    rle = sum(1 for v in flat.values() if RLE in v)
    print(f"built {built} : {len(out)} bytes, {len(flat)} keys, {heb} with-hebrew, {rle} RLE-wrapped")
    if deploy:
        lang = Path(os.environ["LOCALAPPDATA"]) / "VirtualDJ" / "Languages"
        lang.mkdir(parents=True, exist_ok=True)
        dep = lang / "Arabic.xml"
        bak = lang / "Arabic.xml.he_backup"
        if dep.exists() and not bak.exists():
            shutil.copy(dep, bak)
        shutil.copy(built, dep)
        print(f"deployed -> {dep}")


if __name__ == "__main__":
    main()
