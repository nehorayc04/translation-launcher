"""
rdr2_text.py — codec for the RDR2 LML text-override file ("*.gxt2" DataFile).

Red Dead Redemption 2 (RAGE engine, RPF8) ships its UI/subtitle text as .yldb text
databases inside the ENCRYPTED RPF8 archives (update_3/x64/data/lang/). BUT the community
translation path (Lenny's Mod Loader `<DataFile>`) overrides strings at load time from a
PLAIN-TEXT file — no RPF8 crack, no repack. That file (misleadingly named `*.gxt2`) is what
this module reads and writes.

Format (verified against Ko Games' shipping RDR2 Arabic mod, 231,993 unique keys):
    * UTF-8, LF-separated lines.
    * `# ...`              -> comment (kept verbatim, ignored as data).
    * blank line           -> ignored.
    * `KEY = value`        -> one string entry. Split on the FIRST `=`. Exactly one space
                             may sit on each side of the `=` (`KEY = value`); we tolerate
                             `KEY= value` / `KEY =value` on read and normalise to `KEY = `
                             on write. The value runs to end-of-line and MAY itself contain
                             `=` characters (only the first `=` is the separator).
    KEY is either a LABEL (`LEGAL_SPLASH_1`, `RCTXD_UC_PLC`, `[A-Za-z0-9_]+`) or a joaat
    hex id (`0x2B39B2B7`). Both are RAGE text keys; the game resolves either.

Tokens inside a value are RAGE tilde-controls — IDENTICAL to GTA V: `~z~` (dialogue),
`~s~`/`~o~`/`~d~`/`~t~` (colour), `~n~` (newline), `~sl:a:b~` (subtitle timing), `~1~`/`~2~`
(colour slots), `~COLOR_*~`, `~INPUT_*~` (button prompts).

bidi = VISUAL. The engine does NO bidi and NO shaping for this path (proven: the Arabic
mod stores 85:1 presentation-form vs standard-block chars and 17,854 lines begin with the
sentence-final period on the LEFT; confirmed in-game 2026-07-19). So Hebrew is stored
**pre-reversed to visual order** — and Hebrew, unlike Arabic, needs NO letter-shaping.

⚠️ The conversion lives in `rdr2_rtl.to_visual`, NOT in GTA V's `visual_line`. We started
with the GTA function and proof #3 showed it mis-places every multi-character neutral run
(`: (`, `) "`, `, `) because it keeps them FORWARD as if they were a Latin island, when a
neutral run actually belongs to the RTL flow. `rdr2_rtl` runs the real Unicode Bidi
Algorithm with an RTL base instead — identical output on everything already confirmed
in-game, correct on the rest. See that module's docstring.

⚠️ Long values must be PRE-WRAPPED (`rdr2_rtl.wrap_logical`) before conversion: the engine
word-wraps in STORAGE order, so an un-broken VISUAL paragraph renders with its LINE ORDER
INVERTED (proven in-game — markers (1)…(6) ran bottom-up).

This module never touches game files; it only parses/serialises the text override.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdr2_rtl import (to_visual, to_visual_row,  # noqa: E402  (UBA logical->visual + pre-wrap)
                      wrap_logical)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# KEY = value  — first '=' is the separator; the key has no '=' and no leading '#'.
_ENTRY = re.compile(r"^(?P<key>[^=\r\n#][^=\r\n]*?)\s*=\s?(?P<val>.*)$")
_HEXKEY = re.compile(r"^0x[0-9A-Fa-f]{8}$")
_LABELKEY = re.compile(r"^[A-Za-z0-9_]+$")


def parse(text):
    """RDR2 override text -> list of records preserving file order.

    Returns a list of dicts:
        {"kind":"comment"|"blank"|"entry", "raw":..., "key":..., "val":...}
    A round-trip serialise(parse(t)) == t for any well-formed file (see selftest).
    """
    out = []
    for ln in text.split("\n"):
        s = ln.rstrip("\r")
        if s.strip() == "":
            out.append({"kind": "blank", "raw": s})
            continue
        if s.lstrip().startswith("#"):
            out.append({"kind": "comment", "raw": s})
            continue
        m = _ENTRY.match(s)
        if not m:
            # Unparseable (rare continuation/odd line) — keep verbatim so nothing is lost.
            out.append({"kind": "raw", "raw": s})
            continue
        out.append({"kind": "entry", "key": m.group("key"), "val": m.group("val")})
    return out


def to_map(records):
    """entry records -> {key: value} (last write wins, mirroring the game loader)."""
    d = {}
    for r in records:
        if r["kind"] == "entry":
            d[r["key"]] = r["val"]
    return d


def serialise(records):
    """records -> override text (LF). `KEY = value` for entries, verbatim otherwise."""
    lines = []
    for r in records:
        if r["kind"] == "entry":
            lines.append(f'{r["key"]} = {r["val"]}')
        else:
            lines.append(r["raw"])
    return "\n".join(lines)


def key_kind(key):
    if _HEXKEY.match(key):
        return "hash"
    if _LABELKEY.match(key):
        return "label"
    return "other"


def build_hebrew(records, hebrew_logical, *, fallback_records=True, wrap_width=None,
                 row_keys=None):
    """Produce override records with Hebrew, stored VISUAL.

    `hebrew_logical` = {key: logical-order Hebrew string}. For every key present in it we
    emit `key = to_visual(hebrew)`. Keys NOT in the map are kept from `records` unchanged
    when `fallback_records` (so a partial translation still ships a complete, loadable file).
    Comments/blank lines from `records` are preserved.

    `wrap_width` (chars) pre-wraps long values into explicit `~n~` lines BEFORE the visual
    conversion. Required for any surface whose box the value would overflow — the engine
    wraps in storage order and would invert the line order. Pass the width measured for
    that surface; None = no pre-wrap (only safe for values known to fit on one line).

    `row_keys` = keys whose value is a button ROW the engine PARSES (`[glyph] label [glyph]
    label`). Those get `to_visual_row`, which pins every token where the game's own string has
    it and reverses only the labels — a normal visual bake moves the leading glyph and the whole
    row then renders as NOTHING. Never wrapped: a row is short and its line breaks are the
    widget's business.
    """
    rows = set(row_keys or ())

    def _conv(v, key=None):
        if key in rows:
            return to_visual_row(v)
        if wrap_width:
            v = wrap_logical(v, wrap_width)
        return to_visual(v)

    seen = set()
    out = []
    for r in records:
        if r["kind"] != "entry":
            out.append(r)
            continue
        k = r["key"]
        seen.add(k)
        if k in hebrew_logical:
            out.append({"kind": "entry", "key": k, "val": _conv(hebrew_logical[k], k)})
        elif fallback_records:
            out.append(r)
    # keys the map has that weren't in the base file -> append
    for k, v in hebrew_logical.items():
        if k not in seen:
            out.append({"kind": "entry", "key": k, "val": _conv(v, k)})
    return out


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    fails = []

    def ck(name, cond):
        print(("[PASS] " if cond else "[FAIL] ") + name)
        if not cond:
            fails.append(name)

    sample = (
        "# RED DEAD REDEMPTION 2 Hebrew\n"
        "\n"
        "LEGAL_SPLASH_1 = ~o~KG~s~ Studio~n~line2\n"
        "0x2B39B2B7 = Aim carefully.\n"
        "PM_PAUSE = Pause = Menu\n"      # value contains '='
        "RCTXD_UC_PLC = Squirrel Location\n"
    )
    recs = parse(sample)
    ck("round-trip serialise(parse(t)) == t", serialise(recs) == sample)

    m = to_map(recs)
    ck("value keeps embedded '='", m["PM_PAUSE"] == "Pause = Menu")
    ck("hex key parsed", "0x2B39B2B7" in m and m["0x2B39B2B7"] == "Aim carefully.")
    ck("key_kind label", key_kind("LEGAL_SPLASH_1") == "label")
    ck("key_kind hash", key_kind("0x2B39B2B7") == "hash")

    heb = {
        "LEGAL_SPLASH_1": "~o~KG~s~ סטודיו~n~שורה שתיים",
        "0x2B39B2B7": "כוון בזהירות.",
    }
    hb = build_hebrew(recs, heb)
    hm = to_map(hb)
    # tokens preserved, run order flipped (visual)
    ck("token ~o~ preserved after visual", "~o~" in hm["LEGAL_SPLASH_1"])
    ck("token ~s~ preserved after visual", "~s~" in hm["LEGAL_SPLASH_1"])
    ck("newline token kept as line splitter", "~n~" in hm["LEGAL_SPLASH_1"])
    # Hebrew run got reversed (visual != logical)
    ck("hebrew stored visual (reversed)", hm["0x2B39B2B7"] != heb["0x2B39B2B7"]
       and hm["0x2B39B2B7"].startswith("."))
    # untranslated key kept from base (complete file)
    ck("untranslated key falls back to base", hm["PM_PAUSE"] == "Pause = Menu")
    # pure-Latin/ASCII untouched by visual
    ck("ASCII-only value unchanged", to_visual("Just ASCII 123") == "Just ASCII 123")

    # neutral runs are part of the RTL flow (the proof-#3 fix)
    ck("brackets mirrored", "(םיירגוס)" in to_visual("טקסט (סוגריים) כאן"))
    # pre-wrap turns a long value into explicit ~n~ lines, order preserved
    long_he = " ".join(["מילה"] * 40)
    wrapped = to_map(build_hebrew([], {"K": long_he}, wrap_width=30))["K"]
    ck("wrap_width emits ~n~", "~n~" in wrapped)
    ck("wrap_width keeps first line first",
       wrapped.split("~n~")[0] == to_visual(wrap_logical(long_he, 30).split("~n~")[0]))

    print("-" * 50)
    print("RESULT:", "ALL PASS" if not fails else f"FAIL {fails}")
    sys.exit(1 if fails else 0)
