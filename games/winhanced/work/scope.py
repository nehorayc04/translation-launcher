"""Scope report for the Winhanced UI corpus, measured from the PRI (the superset).

Reports the three numbers that matter -- records / per-file uniques / GLOBAL
uniques -- and splits identifiers from real UI copy, because translating an
identifier (x:Name, resource key, type or property name, URI) breaks the app.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pri_xbf
import xbf

ROOT = Path(r"C:\Program Files\Winhanced")

# --- things that are CODE, never text -------------------------------------
RE_URI = re.compile(r"^(https?|ms-appx|ms-appdata|using|urn|file|mailto):", re.I)
RE_SCHEMA = re.compile(r"schemas\.(microsoft|openxmlformats)\.com|/markup-compatibility/")
RE_COLOR = re.compile(r"^#[0-9A-Fa-f]{3,8}$")
RE_NUMERIC = re.compile(r"^[\d\s.,;:+\-*/()%]*$")
RE_MARKUP = re.compile(r"^\{.*\}$", re.S)  # {Binding ...} {StaticResource ...}
RE_DOTTED = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)+$")  # Winhanced.Foo.Bar
RE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # RootGrid, IsActive, SemiBold
RE_PATHY = re.compile(r"^[A-Za-z]:\\|^\\\\|^/|\.(png|jpg|jpeg|webp|gif|svg|json|db|xaml|xbf|dll|exe|mp4)$", re.I)
RE_GEOM = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz\d\s.,\-]+$")  # path geometry data


def kind(s: str) -> str:
    t = s.strip()
    if not t:
        return "empty"
    if RE_SCHEMA.search(t):
        return "schema"
    if RE_URI.match(t):
        return "uri"
    if RE_PATHY.search(t):
        return "path"
    if RE_MARKUP.match(t):
        return "markup"
    if RE_COLOR.match(t):
        return "color"
    if RE_NUMERIC.match(t):
        return "numeric"
    if RE_DOTTED.match(t):
        return "dotted"          # namespace / type / property path
    if len(t) > 12 and RE_GEOM.match(t):
        return "geometry"
    if RE_IDENT.match(t):
        return "identifier"      # single token: x:Name, enum, resource key... AND
                                 # also short UI words like "Settings" -> ambiguous
    return "text"                # has a space or punctuation -> real UI copy


def main() -> None:
    emb = pri_xbf.carve(ROOT / "Winhanced.pri")

    records = 0
    per_file_unique = 0
    counts: Counter[str] = Counter()
    occurrences: Counter[str] = Counter()
    for e in emb:
        records += len(e.obj.strings)
        u = set(e.obj.strings)
        per_file_unique += len(u)
        for s in u:
            occurrences[s] += 1
    glob = set(occurrences)

    print("=== Winhanced UI corpus (source: Winhanced.pri) ===")
    print(f"  XBF payloads          : {len(emb)}")
    print(f"  records (all entries) : {records}")
    print(f"  per-file uniques (sum): {per_file_unique}")
    print(f"  GLOBAL uniques        : {len(glob)}   <-- the real translation unit")
    print()

    for s in glob:
        counts[kind(s)] += 1
    print("  by kind:")
    for k, n in counts.most_common():
        print(f"    {k:<12} {n:>6}")

    text = sorted(s for s in glob if kind(s) == "text")
    ident = sorted(s for s in glob if kind(s) == "identifier")
    chars = sum(len(s) for s in text)
    print()
    print(f"  >> translatable prose ('text'): {len(text)} strings, {chars} chars")
    print(f"  >> ambiguous single tokens    : {len(ident)}  (UI word vs x:Name -- needs care)")

    out = Path(__file__).resolve().parents[1] / "extract"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ui_text.txt").write_text("\n".join(text), encoding="utf-8")
    (out / "ambiguous_tokens.txt").write_text("\n".join(ident), encoding="utf-8")
    print(f"\n  wrote {out/'ui_text.txt'} and {out/'ambiguous_tokens.txt'}")


if __name__ == "__main__":
    main()
