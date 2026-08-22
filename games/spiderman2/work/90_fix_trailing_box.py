"""90_fix_trailing_box.py — kill the trailing tofu-box on RTL descriptions.

Root cause (verified 2026-06-07 against the live build + 29 in-game shots):
cohtml renders the closing PDF (U+202C) of an RLE...PDF-wrapped string as a
.notdef box (a tofu square) when the string ENDS with an inline-element close
`</span>` (regardless of the span's script — Hebrew OR Latin) or with a strong
LTR char/digit. Strings that end on a plain Hebrew word do NOT box, because the
PDF then sits right after a strong-RTL char and is absorbed.

Fix: give the trailing PDF a strong-RTL anchor — insert `&rlm;` (U+200F) right
before the closing U+202C. This is the SAME mechanism the source data already
uses on dozens of strings (e.g. HELP_FOCUS_GENERATE_*, *_REWARD, POP2/POP3 all
end `...&rlm;‬`). `&rlm;` is zero-width, so on a string that does NOT box
it is a harmless no-op; it can only help, never hurt.

Surgical: only touches wrapped strings (ending in U+202C) that are box-prone
(end with `</span>` or an ASCII letter/digit, ignoring trailing `.`/spaces) and
are NOT already RLM-anchored. Hebrew-ending strings and `(…)` Hebrew-in-parens
are left byte-identical.

Run from games/spiderman2/work/.  Backs up each file to <name>.bak.box before
writing.
"""
from __future__ import annotations
import json, glob, shutil, string, os

PDF  = "‬"
RLM  = "‏"
RLM_ENT = "&rlm;"
LATIN = set(string.ascii_letters)
DIGIT = set("0123456789")


def is_box_prone(body: str) -> bool:
    """body = the value WITHOUT its trailing PDF char. True if its visible tail
    would make the closing PDF render as a tofu box."""
    t = body.rstrip()
    # peel trailing sentence punctuation that is itself neutral
    while t and t[-1] in ".  \t":
        t = t[:-1].rstrip()
    if not t:
        return False
    if t.endswith("</span>"):
        return True
    last = t[-1]
    return last in LATIN or last in DIGIT


def already_anchored(body: str) -> bool:
    tail = body[-8:]
    return tail.endswith(RLM_ENT) or body.endswith(RLM)


def main() -> int:
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    grand = 0
    per_file = {}
    samples = []
    for fn in files:
        if not os.path.exists(fn):
            continue
        with open(fn, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            continue
        fixed = 0
        for k, v in list(d.items()):
            if not (isinstance(v, str) and v.endswith(PDF)):
                continue
            body = v[:-1]
            if already_anchored(body):
                continue
            if not is_box_prone(body):
                continue
            d[k] = body + RLM_ENT + PDF
            fixed += 1
            if len(samples) < 12:
                samples.append((fn, k))
        if fixed:
            shutil.copyfile(fn, fn + ".bak.box")
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        per_file[fn] = fixed
        grand += fixed

    print(f"[+] trailing-box anchor inserted on {grand} strings")
    for fn, n in per_file.items():
        if n:
            print(f"      {fn:22} {n}")
    print("    sample keys:")
    for fn, k in samples:
        print(f"      [{fn}] {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
