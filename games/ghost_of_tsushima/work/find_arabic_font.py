#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""find_arabic_font.py — LOCATE the Arabic-slot glyph table in Ghost of Tsushima DC.

Round 1 found only Latin 64-byte glyph tables (core_common/core_tsu/core_iki/m_lm_menu),
cp <= 0x1a6. The Arabic-covering table (cp 0x600-0x6ff), the true Hebrew-injection target,
is elsewhere. This tool scans KCAP .xpps packages for it.

DETECTORS (all require the 64-byte stride + cp ASCENDING + cp-hi u16@+2 == 0):
  STRUCT  — font-kind-AGNOSTIC glyph record: +16 u32 == 0xffffffff AND +62 u16 == 0xffff.
            (Round 1's got_fonk keyed on +8==4; the Arabic font MIGHT use a different +8
             "font kind", so we DON'T assume +8. +16==0xffffffff & +62==0xffff are the
             layout invariants proven on the Latin tables — see notes/arabic_font_table.md.)
  CMAP    — codepoint->id map record: +62 u16 == cp (core_common CMAP layout).
  RELAXED — ascending stride-64 run with only +2==0 (catches ANY variant). Classified so a
            consecutive-integer INDEX array (dense +1, no struct markers) is NOT a false hit.

For every run reaching Arabic (max cp >= 0x600) it reports coverage + the field signature so
a real glyph table is distinguished from a mesh/index false positive.

RESULT (2026-07-08, see notes/arabic_font_table.md): the Arabic-slot font is
`/ghost_title.xpps` in `gapack_misc_g.psarc` — a single multi-script UI/title font (Latin,
Cyrillic, Hebrew 0x5d0-0x5ea, Arabic 0x600-0x6ff+, Indic, CJK), 4553 glyph records, kind
`+8==0` (round 1's `+8==4` detector missed it -> use the RELAXED path). The 27 Hebrew letters
already exist as records (first, ALEF 0x5d0, @0x87ec92, inside sub-table @0x87d7d2 cp 0x584-0x6db)
but are DEGENERATE (only 3 distinct (+16,+18) outline refs for 27 letters) -> that is the in-game
tofu. Real Arabic per-glyph outlines are @0x880dd2 onward. core_common/core_tsu/core_iki/game.sprig/
m_lm_menu have NO Hebrew/Arabic font (verified). Injection = give the 27 0x5d0-0x5ea records real
FontVerts outlines (the remaining crack), or repurpose Arabic-letter records.
"""
import os, sys, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R  # noqa: E402

GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
PD = os.path.join(GAME, "cache_pc", "psarc")
GREC = 64


# ---------------------------------------------------------------- ranges
def _rng(cps, a, b):
    return sum(1 for c in cps if a <= c <= b)


def coverage(cps):
    real = [c for c in cps if c != 0xffff]
    if not real:
        return "empty"
    return (f"n={len(real)} cp[0x{min(real):x}..0x{max(real):x}] "
            f"ASCII={_rng(real, 0x20, 0x7e)} Latin1={_rng(real, 0xa0, 0x2af)} "
            f"Heb={_rng(real, 0x5d0, 0x5ea)} Arabic={_rng(real, 0x600, 0x6ff)} "
            f"ArPF={_rng(real, 0xfb50, 0xfeff)} Cyr={_rng(real, 0x400, 0x4ff)} "
            f"Hira={_rng(real, 0x3040, 0x309f)} CJK={_rng(real, 0x4e00, 0x9fff)}")


# ---------------------------------------------------------------- record predicates
def _u16(d, p):
    return struct.unpack_from("<H", d, p)[0]


def _u32(d, p):
    return struct.unpack_from("<I", d, p)[0]


def is_struct(d, p):
    """Font-kind-agnostic glyph record: cp-hi 0, +16 == 0xffffffff, +62 == 0xffff."""
    if p + GREC > len(d):
        return False
    return (_u16(d, p + 2) == 0 and _u32(d, p + 16) == 0xffffffff
            and _u16(d, p + 62) == 0xffff)


def is_cmap(d, p):
    if p + GREC > len(d):
        return False
    return _u16(d, p + 2) == 0 and _u16(d, p + 62) == _u16(d, p)


# ---------------------------------------------------------------- generic ascending-run walker
def _walk_runs(data, ok, cp_ok=lambda c: 1 <= c <= 0xfffe, minrun=12, allow_sentinel=True):
    """Find maximal stride-64 runs where ok(data,p) holds for each record and cp strictly
    ascends. `ok` is the per-record predicate. Uses a numpy prefilter on +2==+3==0."""
    n = len(data)
    b = np.frombuffer(data, dtype=np.uint8)
    if n < GREC:
        return []
    cand = np.nonzero((b[2:n - 1] == 0) & (b[3:n] == 0))[0]  # p where p+2,p+3 == 0
    candset = cand  # sorted ascending already
    out = []
    used = set()
    for pp in candset:
        p = int(pp)
        if p in used or p + GREC > n:
            continue
        if not ok(data, p):
            continue
        cp0 = _u16(data, p)
        if not cp_ok(cp0) and cp0 != 0xffff:
            continue
        # start-of-run only: predecessor record must not be an ascending match
        if p - GREC >= 0 and ok(data, p - GREC):
            pc = _u16(data, p - GREC)
            if pc == cp0 - 1 or (pc < cp0 and (p - GREC) not in used):
                # could be mid-run; skip so we anchor at true start
                pass
        cps = []
        q = p
        while q + GREC <= n and ok(data, q):
            c = _u16(data, q)
            if c == 0xffff and allow_sentinel:
                used.add(q)
                q += GREC
                break
            if not cp_ok(c):
                break
            if cps and c <= cps[-1]:
                break
            cps.append(c)
            used.add(q)
            q += GREC
        if len(cps) >= minrun:
            out.append((p, cps, q))
    # dedup runs that are sub-runs of a bigger one starting earlier
    out.sort(key=lambda t: t[0])
    return out


def dense_frac(cps):
    if len(cps) < 2:
        return 0.0
    return sum(1 for i in range(1, len(cps)) if cps[i] == cps[i - 1] + 1) / (len(cps) - 1)


def field_sig(data, start, cps):
    """For a run, fraction of records matching each structural marker (excl sentinel)."""
    nn = len(cps)
    if nn == 0:
        return {}
    c8 = c16 = c62s = c62cp = f8 = 0
    for i in range(nn):
        p = start + i * GREC
        if _u32(data, p + 8) == 4:
            c8 += 1
        if _u32(data, p + 16) == 0xffffffff:
            c16 += 1
        if _u16(data, p + 62) == 0xffff:
            c62s += 1
        if _u16(data, p + 62) == _u16(data, p):
            c62cp += 1
        if data[p + 20] == 0xf8:
            f8 += 1
    return dict(c8=c8 / nn, c16=c16 / nn, c62_sent=c62s / nn,
                c62_cp=c62cp / nn, f8=f8 / nn, dense=dense_frac(cps))


# ---------------------------------------------------------------- package scan
def scan_blob(data, minrun=12):
    """Return dict of detector -> list of (start, cps, end)."""
    return {
        "STRUCT": _walk_runs(data, is_struct, minrun=minrun),
        "CMAP": _walk_runs(data, is_cmap, minrun=minrun),
        "RELAXED": _walk_runs(data, lambda d, p: _u16(d, p + 2) == 0, minrun=max(minrun, 24)),
    }


def arabic_tables(res, arabic_min=1):
    """Extract runs reaching Arabic (>=0x600) from a scan result, tagged by detector."""
    hits = []
    for det, runs in res.items():
        for (s, cps, e) in runs:
            real = [c for c in cps if c != 0xffff]
            if real and _rng(real, 0x600, 0x6ff) >= arabic_min:
                hits.append((det, s, cps, e))
    return hits


# ---------------------------------------------------------------- archive helpers
def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    d = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return d


def _report_blob(name, data, minrun=12, arabic_only=True):
    res = scan_blob(data, minrun)
    tot = {k: len(v) for k, v in res.items()}
    print(f"{name}: {len(data):,}B  STRUCT={tot['STRUCT']} CMAP={tot['CMAP']} RELAXED={tot['RELAXED']}")
    hits = arabic_tables(res)
    if hits:
        print(f"  *** {len(hits)} table(s) reaching ARABIC (>=0x600) ***")
        for det, s, cps, e in sorted(hits, key=lambda t: -_rng([c for c in t[2] if c != 0xffff], 0x600, 0x6ff)):
            sig = field_sig(data, s, [c for c in cps if c != 0xffff])
            print(f"  [{det}] @0x{s:x} {coverage(cps)}")
            print(f"        sig: +8==4:{sig['c8']:.2f} +16==FFFFFFFF:{sig['c16']:.2f} "
                  f"+62==sent:{sig['c62_sent']:.2f} +62==cp:{sig['c62_cp']:.2f} "
                  f"+20==f8:{sig['f8']:.2f} dense+1:{sig['dense']:.2f}")
        return True
    if not arabic_only:
        # show biggest STRUCT/CMAP tables for context
        for det in ("STRUCT", "CMAP"):
            for s, cps, e in sorted(res[det], key=lambda t: -len(t[1]))[:3]:
                print(f"  ({det}) @0x{s:x} {coverage(cps)}")
    return False


# ---------------------------------------------------------------- CLI
def cmd_pkg(args):
    archive, name = args[0], args[1]
    minrun = int(args[2]) if len(args) > 2 else 12
    data = get(archive, name)
    if data is None:
        print("NOT FOUND"); return
    _report_blob(name, data, minrun, arabic_only=False)


def cmd_arc(args):
    """Scan every file in an archive; report only files with an Arabic-reaching table."""
    archive = args[0]
    minrun = int(args[1]) if len(args) > 1 else 12
    maxsize = int(args[2]) if len(args) > 2 else 0   # 0 = no cap
    arc = R.Psarc2(os.path.join(PD, archive))
    files = arc.files()
    print(f"=== {archive}: {len(files)} files (cap={maxsize or 'none'}) ===", flush=True)
    found = 0
    for i, e in enumerate(files):
        if maxsize and e.orig_size > maxsize:
            continue
        try:
            data = arc.extract(e)
        except Exception as ex:
            print(f"  ! {e.path}: {ex}"); continue
        res = scan_blob(data, minrun)
        hits = arabic_tables(res)
        if hits:
            found += 1
            print(f"\n>>> {e.path} ({e.orig_size:,}B)", flush=True)
            for det, s, cps, en in hits:
                sig = field_sig(data, s, [c for c in cps if c != 0xffff])
                print(f"    [{det}] @0x{s:x} {coverage(cps)}")
                print(f"        sig: +8==4:{sig['c8']:.2f} +16==FFFFFFFF:{sig['c16']:.2f} "
                      f"+62==sent:{sig['c62_sent']:.2f} +62==cp:{sig['c62_cp']:.2f} dense+1:{sig['dense']:.2f}")
        if (i + 1) % 250 == 0:
            print(f"    ..{i + 1}/{len(files)} scanned, {found} arabic-tables so far", flush=True)
    arc.d.f.close()
    print(f"\n=== {archive}: {found} files with an Arabic-reaching table ===")


def cmd_dump(args):
    archive, name, off = args[0], args[1], int(args[2], 0)
    n = int(args[3]) if len(args) > 3 else 12
    data = get(archive, name)
    for i in range(n):
        p = off + i * GREC
        r = data[p:p + GREC]
        cp = _u16(data, p)
        ch = chr(cp) if 32 <= cp < 127 else "?"
        print(f"slot{i} @0x{p:x} cp=0x{cp:x} '{ch}' +8={_u32(data, p + 8)} "
              f"+16=0x{_u32(data, p + 16):x} +62=0x{_u16(data, p + 62):x}")
        print(f"   {r[:32].hex(' ')}")
        print(f"   {r[32:].hex(' ')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: find_arabic_font.py pkg <arc> <name> [minrun] | "
              "arc <arc> [minrun] [maxsize] | dump <arc> <name> <off> [n]")
        sys.exit(0)
    cmd = sys.argv[1]
    {"pkg": cmd_pkg, "arc": cmd_arc, "dump": cmd_dump}[cmd](sys.argv[2:])
