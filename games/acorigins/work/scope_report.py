#!/usr/bin/env python3
r"""
scope_report.py — the honest Phase-2 scope for AC Origins.

Reports THREE counts, never one (§17.1): records · per-file uniques · GLOBAL
uniques — only the last is the translation workload. Also runs the
dedup-safety measurement ([[dedup-safety-from-game-langs]]): before keying a
pool by the English string, MEASURE how often the game's OWN professional
locales give one English string two different translations.

🔴 ORIGINS SHAPE (differs from Odyssey): the Arabic **UI** package is a 457-byte
STUB while Arabic **Subtitles** ships full. So the surfaces are split:
  subtitles -> Arabic-slot hijack ·  UI -> LTR (English) slot hijack.

    python work/scope_report.py [--out extract/scope.txt]
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "..", "acunity", "work"))

import aor_forge                                        # noqa: E402
import aor_cfd                                          # noqa: E402
import aor_loc                                          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("AOR_GAME", r"F:\Games\Assassin's Creed Origins")

# (label, forge relative path, package-name prefix)
SOURCES = [
    ("base", "DataPC.forge", "LocalizationPackage_"),
    ("dlc", "DataPC_22_dlc_patch_01.forge", "DLC22-30_LocalizationPackage_"),
]

# suffix -> logical language key
LANGS = {
    "English": "en",
    "Arabic": "ar",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Spanish(Spain)": "es",
    "Spanish": "es",            # the Subtitles package drops the "(Spain)"
    "Russian": "ru",
    "Polish": "pl",
    "Czech": "cs",
    "Dutch": "nl",
    "Brazil": "br",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese(Trad)": "zt",
    "Chinese(Simp)": "zs",
}

TOKEN = re.compile(r"<[^>]{1,80}>|\{[^}]{1,60}\}|\[[^\]]{1,60}\]|%[sd]|\\n")


def load_all():
    """-> {(src, kind, lang): {id: text}}  kind in {'ui','subs'}"""
    out = {}
    for src, rel, prefix in SOURCES:
        path = os.path.join(GAME, rel)
        if not os.path.exists(path):
            print(f"  [skip] {rel} missing")
            continue
        fg = aor_loc.open_forge(path)
        od = aor_cfd.oodle()
        for pkg in aor_loc.iter_packages(fg, od):
            name = pkg.name
            if not name.startswith(prefix):
                continue
            tail = name[len(prefix):]
            kind = "subs" if tail.endswith("_Subtitles") else "ui"
            langname = tail[:-len("_Subtitles")] if kind == "subs" else tail
            lang = LANGS.get(langname)
            if lang is None:
                continue
            st = pkg.strings()
            if not st:
                continue
            out[(src, kind, lang)] = st
    return out


def tokstats(strings):
    c = collections.Counter()
    for v in strings.values():
        for t in TOKEN.findall(v):
            c[t] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "extract", "scope.txt"))
    a = ap.parse_args()

    data = load_all()
    L = []

    def p(s=""):
        print(s)
        L.append(s)

    p("AC ORIGINS — SCOPE REPORT")
    p("=" * 72)

    # ---- per-package record counts -------------------------------------
    p("\n[1] PACKAGES FOUND (records per package)")
    for k in sorted(data, key=lambda k: (k[0], k[1], k[2])):
        src, kind, lang = k
        p(f"  {src:5s} {kind:5s} {lang:3s}  {len(data[k]):>7,d} records")

    # ---- the three counts, English source ------------------------------
    p("\n[2] THE THREE COUNTS (English = the translation source)")
    total_records = 0
    per_file_uniques = 0
    global_texts = set()
    ui_ids, sub_ids = set(), set()
    for (src, kind, lang), st in data.items():
        if lang != "en":
            continue
        total_records += len(st)
        per_file_uniques += len(set(st.values()))
        global_texts |= set(st.values())
        (ui_ids if kind == "ui" else sub_ids).add((src, kind))
    p(f"  records (all English packages)      : {total_records:>8,d}")
    p(f"  sum of per-package uniques (WRONG)  : {per_file_uniques:>8,d}")
    p(f"  GLOBAL unique English strings       : {len(global_texts):>8,d}   <- the workload")
    chars = sum(len(s) for s in global_texts)
    p(f"  characters (global unique)          : {chars:>8,d}")

    # ---- UI vs subtitles, by the engine's OWN metadata ------------------
    p("\n[3] UI vs SUBTITLES (split by the package's own Type field)")
    for kind in ("ui", "subs"):
        recs, uniq = 0, set()
        for (src, k, lang), st in data.items():
            if lang == "en" and k == kind:
                recs += len(st)
                uniq |= set(st.values())
        lens = sorted(len(s) for s in uniq)
        med = lens[len(lens) // 2] if lens else 0
        p(f"  {kind:5s}  records {recs:>7,d} · unique {len(uniq):>7,d} · "
          f"median {med:>4d} ch · max {max(lens) if lens else 0:,d} ch")

    # ---- id overlap between UI and subtitles ---------------------------
    ui_all, sub_all = {}, {}
    for (src, k, lang), st in data.items():
        if lang != "en":
            continue
        (ui_all if k == "ui" else sub_all).update({(src, i): v for i, v in st.items()})
    p(f"\n[4] ID SPACES  ui {len(ui_all):,d} · subs {len(sub_all):,d} · "
      f"overlap {len(set(ui_all) & set(sub_all)):,d}")

    # ---- oracle-language parity ----------------------------------------
    p("\n[5] ORACLE PANEL — key parity vs English (per source+kind)")
    for src, _rel, _pfx in SOURCES:
        for kind in ("ui", "subs"):
            en = data.get((src, kind, "en"))
            if not en:
                continue
            row = []
            for lang in ("ar", "fr", "de", "it", "es", "ru", "pl", "cs", "nl", "br", "ja", "ko"):
                st = data.get((src, kind, lang))
                if not st:
                    continue
                shared = len(set(en) & set(st))
                row.append(f"{lang} {100.0 * shared / len(en):5.1f}%")
            p(f"  {src:5s} {kind:5s} (n={len(en):,d}): " + " · ".join(row))

    # ---- tokens ---------------------------------------------------------
    p("\n[6] TOKENS TO PRESERVE (English, all packages)")
    c = collections.Counter()
    for (src, kind, lang), st in data.items():
        if lang == "en":
            c += tokstats(st)
    shapes = collections.Counter()
    for t, n in c.items():
        if t.startswith("<"):
            shapes["<...>"] += n
        elif t.startswith("{"):
            shapes["{...}"] += n
        elif t.startswith("["):
            shapes["[...]"] += n
        else:
            shapes[t] += n
    for s, n in shapes.most_common():
        p(f"  {s:10s} {n:>7,d}")
    p("  distinct token literals: %d" % len(c))
    p("  top 25: " + ", ".join(t for t, _ in c.most_common(25)))

    # ---- dedup safety ----------------------------------------------------
    p("\n[7] DEDUP SAFETY — does one English string get two translations?")
    p("    (measured against the game's OWN professional locales)")
    for kind in ("ui", "subs"):
        en = {}
        for src, _r, _p in SOURCES:
            for i, v in (data.get((src, kind, "en")) or {}).items():
                en[(src, i)] = v
        groups = collections.defaultdict(list)
        for k, v in en.items():
            groups[v].append(k)
        dup = {v: ks for v, ks in groups.items() if len(ks) > 1}
        p(f"  {kind}: {len(dup):,d} duplicate-English groups "
          f"({sum(len(k) for k in dup.values()):,d} ids)")
        for lang in ("ar", "ru", "fr", "de", "it", "es", "pl"):
            tot = div = 0
            for _v, ks in dup.items():
                vals = set()
                for (src, i) in ks:
                    st = data.get((src, kind, lang))
                    if st and i in st:
                        vals.add(st[i])
                if len(vals) >= 1:
                    tot += 1
                    if len(vals) > 1:
                        div += 1
            if tot:
                p(f"      {lang}: {div:,d}/{tot:,d} groups diverge = {100.0*div/tot:4.1f}%")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    p(f"\nwritten -> {a.out}")


if __name__ == "__main__":
    main()
