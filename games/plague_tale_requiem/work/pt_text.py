#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pt_text.py — codec for A Plague Tale: Requiem (Asobo "Zouna" engine) TRTEXT files.

The localization lives in LOOSE plain-text files in the game's TRTEXT/ folder:

    TRTEXT/tt01.pc   = English  (TSC_ID 01  -> our translation SOURCE)
    TRTEXT/tt23.pc   = Arabic   (TSC_ID 23  -> our target SLOT for Hebrew)
    TRTEXT/tt02.pc   = French, tt04 = German, ... (see LangDef.tsc)

File format (UTF-8, CRLF, NO BOM):

    FreeLanguage
    ResetEnumTT
    TT <index> "<value>" <KEY>
    TT <index> "<value>" <KEY>
    ...
    EndLoadTT

* <index> is a 0-based sequential int (0 .. N-1).
* <value> is the display string. Verified: values NEVER contain a literal
  double-quote, so the `TT N "..." KEY` parse is unambiguous.
* <KEY> is [A-Za-z0-9_]+ (no spaces), SHARED across every language file — so
  English<->Arabic<->Hebrew map 1:1 by KEY (and by index; the order matches).
* Line-breaks inside a value are the pipe char `|` (there are NO literal \n).
* `{STR_...}` = a runtime button/key-bind token (kept verbatim, see pt_rtl.py).

Deploy = OVERWRITE tt23.pc directly (loose file, read at runtime, NOT packed in
COMMON.DPC). No repack, no compression, no anti-cheat. Activation = set the game
language to Arabic (العربية); Hebrew rides the Arabic RTL slot.

This module is READ + surgical-WRITE only. The WRITE path replaces ONLY the value
of keys you pass in and re-emits every other byte identically (identity
round-trip proven in the self-test).
"""

from __future__ import annotations

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
GAME_ROOT = r"D:\Games\A Plague Tale - Requiem"
TRTEXT_DIR = os.path.join(GAME_ROOT, "TRTEXT")

LANG_FILES = {  # TSC_ID -> language name (from LangDef.tsc)
    "00": "JAPANESE",   "01": "ENGLISH",  "02": "FRENCH",   "03": "SPANISH",
    "04": "GERMAN",     "05": "ITALIAN",  "08": "POLISH",   "09": "KOREAN",
    "11": "CZECH",      "14": "BRAZIL",   "17": "RUSSIAN",  "20": "SPANISH_US",
    "21": "TCHINESE",   "22": "SCHINESE", "23": "ARABIC",
}
SOURCE_ID = "01"   # English
SLOT_ID = "23"     # Arabic  (Hebrew goes here)

# Live (PC) extension. `.IGN` is a second, divergent variant that ships alongside
# `.pc`; the engine on PC loads `.pc` (confirm once via the menu proof). We target
# `.pc`; deploy also writes `.IGN` for safety (see build_proof.py).
EXT_LIVE = ".pc"

# Structure-preserving match: g1 = 'TT <idx> "', g2 = value, g3 = '" <KEY><trailing ws>',
# g4 = clean KEY. Splitting this way lets the writer replace ONLY g2 and re-emit g1+g3
# byte-for-byte — so quirks like the ONE line with a trailing space after its key
# (OBJECTIVE__CH14_PROTECTSOPHIAANDLUCAS) round-trip identically AND stay translatable.
_LINE_RE = re.compile(r'^(TT (\d+) ")(.*)(" (\S+)\s*)$')


class Row:
    __slots__ = ("idx", "value", "key")

    def __init__(self, idx: int, value: str, key: str):
        self.idx, self.value, self.key = idx, value, key

    def __repr__(self):
        return f"Row({self.idx}, {self.value!r}, {self.key})"


def lang_path(tsc_id: str, ext: str = EXT_LIVE, root: str = TRTEXT_DIR) -> str:
    return os.path.join(root, f"tt{tsc_id}{ext}")


def _read_raw(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    # No BOM in these files; decode strict UTF-8, preserve exact CRLF structure.
    return data.decode("utf-8")


def parse(path: str) -> list[Row]:
    """Parse a ttNN file into Rows. Only `TT ...` lines become Rows."""
    raw = _read_raw(path)
    rows: list[Row] = []
    for line in raw.split("\r\n"):
        m = _LINE_RE.match(line)
        if m:
            rows.append(Row(int(m.group(2)), m.group(3), m.group(5)))
    return rows


def load_map(path: str) -> dict[str, str]:
    """key -> value for a ttNN file."""
    return {r.key: r.value for r in parse(path)}


def write_overrides(src_path: str, out_path: str, overrides: dict[str, str]) -> int:
    """Re-emit `src_path` to `out_path`, replacing ONLY the value of keys present
    in `overrides`. Every non-overridden byte is preserved EXACTLY (identity
    round-trip when overrides is empty). Returns the number of values replaced.

    `overrides` maps KEY -> the exact stored value string (already RTL-transformed
    by pt_rtl.to_stored). Values must NOT contain a `"` or a CR/LF.
    """
    raw = _read_raw(src_path)
    lines = raw.split("\r\n")
    applied = 0
    for i, line in enumerate(lines):
        m = _LINE_RE.match(line)
        if not m:
            continue
        key = m.group(5)
        if key in overrides:
            new_val = overrides[key]
            if '"' in new_val or "\r" in new_val or "\n" in new_val:
                raise ValueError(f"illegal char in value for {key!r}: {new_val!r}")
            # replace ONLY the value (g3); keep g1 ('TT n "') and g4 ('" KEY<ws>') exact
            lines[i] = m.group(1) + new_val + m.group(4)
            applied += 1
    out = "\r\n".join(lines)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(out.encode("utf-8"))
    return applied


# --------------------------------------------------------------------------- #
# key classification (UI vs subtitle) — the prefix before the first "__"
# --------------------------------------------------------------------------- #
SUBTITLE_PREFIX = "VO"          # VO__<char>__<chapter>__... = spoken dialogue/bark
CREDIT_PREFIX = "CREDIT"        # end credits (translate or leave — user's call)


def category(key: str) -> str:
    head = key.split("__", 1)[0].split("_", 1)[0]
    if head == SUBTITLE_PREFIX:
        return "subtitle"
    if head == CREDIT_PREFIX:
        return "credit"
    return "ui"


def counts(path: str) -> dict[str, int]:
    c = {"subtitle": 0, "credit": 0, "ui": 0}
    for r in parse(path):
        c[category(r.key)] += 1
    c["total"] = sum(c.values())
    return c


# --------------------------------------------------------------------------- #
# self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Plague Tale Requiem TRTEXT codec")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "stats", "dump"])
    ap.add_argument("--root", default=TRTEXT_DIR)
    ap.add_argument("--lang", default=SOURCE_ID)
    args = ap.parse_args()

    if args.cmd == "stats":
        for tid in (SOURCE_ID, SLOT_ID):
            p = lang_path(tid, root=args.root)
            if os.path.exists(p):
                print(f"tt{tid} ({LANG_FILES[tid]}): {counts(p)}")
    elif args.cmd == "dump":
        p = lang_path(args.lang, root=args.root)
        for r in parse(p)[:20]:
            print(r)
    else:
        # identity round-trip: write with NO overrides must reproduce the source bytes.
        failures = []

        def check(name, cond):
            print(f"[{'PASS' if cond else 'FAIL'}] {name}")
            if not cond:
                failures.append(name)

        src = lang_path(SLOT_ID, root=args.root)
        if not os.path.exists(src):
            print(f"[SKIP] game file not found: {src} — run on the machine with the game.")
            sys.exit(0)

        original = open(src, "rb").read()
        tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_rt_test.tmp")
        write_overrides(src, tmp, {})
        rt = open(tmp, "rb").read()
        os.remove(tmp)
        check("identity round-trip (empty overrides) is byte-identical", rt == original)

        rows = parse(src)
        check("parsed all TT lines (>= 20000 rows)", len(rows) >= 20000)
        check("indices are 0..N-1 contiguous",
              [r.idx for r in rows] == list(range(len(rows))))

        en = load_map(lang_path(SOURCE_ID, root=args.root))
        ar = load_map(src)
        check("EN and AR key-sets identical", set(en) == set(ar))

        # surgical single-value replace, byte-diff is exactly the value delta
        k0 = rows[len(rows) // 2].key
        write_overrides(src, tmp, {k0: "TESTVALUE"})
        mod = open(tmp, "rb").read()
        os.remove(tmp)
        check("single override changes the file", mod != original)
        check("single override keeps line count",
              mod.count(b"\r\n") == original.count(b"\r\n"))

        print("\nSTATS:")
        for tid in (SOURCE_ID, SLOT_ID):
            print(f"  tt{tid} ({LANG_FILES[tid]}): {counts(lang_path(tid, root=args.root))}")

        sys.exit(1 if failures else 0)
