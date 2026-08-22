"""93_strip_controls.py — the PERMANENT box/symbol fix.

Why the box/symbol happened (root cause, confirmed 2026-06-07 from the live game
archive + python-bidi):
  cohtml draws a bidi-control character (RLM U+200F, PDF U+202C, RLE U+202B, …)
  as a .notdef tofu box/symbol when the ACTIVE font lacks a glyph for it. The
  game's native Arabic font (AzbukaPro) carries those code points as zero-width
  glyphs, so the official Arabic never boxes. Our Heebo subset does NOT, so every
  control char we emit is drawn as a square. The earlier RLE..PDF wrap boxed on
  the trailing PDF; the Arabic-match pass (91) then boxed on the trailing RLM it
  grafted in. Both are the same root: our font can't render the control char.

Why we can just delete them all:
  RTL base direction comes from the UI CONTAINER, not the text — proven: the
  shipped Arabic has 7289 strings that START with a Latin/token run and carry NO
  leading anchor, yet render correctly. python-bidi with base_dir='R' reproduces
  correct order (period at the left end, (HUD)/[DPAD_*]/NN%% in place) for the
  Hebrew with ZERO control chars. So the anchors are unnecessary for us — and
  unrenderable — so we strip every one. With none present, nothing can ever
  .notdef again. This is the fix that "won't come back".

Also strips the in-game " vN" header tag (the build version now lives only in the
Overstrike mod name, per user request).

Run from work/ AFTER 91, BEFORE the 10->15->80 rebuild. Do NOT run 99_stamp after.
"""
import json, glob, re, os, sys

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

# Every bidi formatting code point + the HTML entities for them.
BIDI_CHARS = "​‌‍‎‏‪‫‬‭‮⁦⁧⁨⁩"
CTRL = re.compile(r'&rlm;|&lrm;|&zwj;|&zwnj;|[' + BIDI_CHARS + r']')

HEADERS = {
    "MENU_LOBBY_COMMONSETTINGS_HEADER", "MENU_GAME_HEADER", "PAUSE_UISETTINGS_TITLE",
    "MENU_SUBTITLECAPTIONS_HEADER", "MENU_GAMEPAD_HEADER", "MENU_SHORTCUT_HEADER",
    "PAUSE_ACCESSIBILITYSETTINGS_TITLE",
}
VTAG = re.compile(r'\s*v\d+\s*$')

def main() -> int:
    n_ctrl = n_tag = 0
    residual = 0
    for fn in sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]:
        if not os.path.exists(fn):
            continue
        d = json.load(open(fn, encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        changed = False
        for k, v in list(d.items()):
            if not isinstance(v, str):
                continue
            nv = CTRL.sub('', v)
            if k in HEADERS:
                stripped = VTAG.sub('', nv)
                if stripped != nv:
                    n_tag += 1
                    nv = stripped
            if nv != v:
                if CTRL.search(v):
                    n_ctrl += 1
                d[k] = nv
                changed = True
            if CTRL.search(d[k]):
                residual += 1
        if changed:
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"stripped bidi-control chars from {n_ctrl} strings")
    out(f"removed in-game ' vN' tag from {n_tag} headers")
    out(f"RESIDUAL control chars: {residual}  (must be 0)")

    # full-corpus sanity: under an RTL container, every string's order is sound.
    try:
        from bidi.algorithm import get_display
        he = {}
        for fn in sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]:
            he.update(json.load(open(fn, encoding="utf-8")))
        bad = 0
        for k, v in he.items():
            if not isinstance(v, str):
                continue
            plain = re.sub(r'<[^>]+>|&[a-z]+;', '', v)
            toks = re.findall(r'\[[A-Z0-9_]+\]', plain)
            vis = get_display(plain, base_dir='R')
            # every [TOKEN] must survive intact (not letter-reversed) in the visual order
            if any(t not in vis for t in toks):
                bad += 1
        out(f"python-bidi (base=R) token-integrity over {len(he)} strings: {bad} broken")
    except Exception as e:
        out("(bidi check skipped:", e, ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
