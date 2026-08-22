# -*- coding: utf-8 -*-
"""Codec for The Witcher 3 motion-comic subtitle files (movies.bundle *.subs).

A .subs file = UTF-16LE + BOM, CRLF-separated:
    <header_id>\r\n
    <start_ms>, <end_ms>, <text>\r\n
    ...
The launch RECAP (recap_wip_*.subs) + the STORYBOOK cutscenes (storybook/altsubs/st_*_*.subs)
each ship one file per language (en/ar/ru/es/it/fr/de/pl/…). We hijack the *_ar.subs slot
(the Arabic locale the mod uses) with Hebrew, exactly like the .w3strings Arabic-slot trick.

parse()  -> (header, [(start,end,text), ...])   (blank/'...' timing rows preserved)
build()  -> bytes (UTF-16LE+BOM, CRLF)          round-trips parse() byte-identically
"""
import re

_ROW = re.compile(r'^(\d+)\s*,\s*(\d+)\s*,\s*(.*)$', re.S)


def parse(raw: bytes):
    t = raw.decode("utf-16-le")
    if t and t[0] == "﻿":
        t = t[1:]
    # normalise to \n for splitting; remember rows verbatim
    lines = t.replace("\r\n", "\n").split("\n")
    header = lines[0]
    rows = []
    for ln in lines[1:]:
        m = _ROW.match(ln)
        if m:
            rows.append([m.group(1), m.group(2), m.group(3)])
        else:
            # a non-timed line (rare) — keep as a raw passthrough row
            rows.append([None, None, ln])
    # drop a single trailing empty passthrough (the file's terminal CRLF)
    while rows and rows[-1][0] is None and rows[-1][2] == "":
        rows.pop()
    return header, rows


def build(header: str, rows) -> bytes:
    out = [header]
    for r in rows:
        if r[0] is None:
            out.append(r[2])
        else:
            out.append(f"{r[0]}, {r[1]}, {r[2]}")
    text = "\r\n".join(out) + "\r\n"
    return "﻿".encode("utf-16-le") + text.encode("utf-16-le")


if __name__ == "__main__":
    import os, sys
    sys.stdout.reconfigure(encoding="utf-8")
    import potato_bundle as PB
    GAME = r"D:\Games\The Witcher 3 - Complete Edition"
    p = os.path.join(GAME, "content", "content0", "bundles", "movies.bundle")
    d, entries = PB.list_entries(p)
    byn = {e["name"].lower(): e for e in entries}
    e = byn[r"movies\cutscenes\gamestart\subs\recap_wip_ar.subs".lower()]
    raw = PB.extract(d, e)
    h, rows = parse(raw)
    rebuilt = build(h, rows)
    print("round-trip identical:", rebuilt == raw, "| header:", repr(h), "| rows:", len(rows))
