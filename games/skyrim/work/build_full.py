"""Skyrim SE / AE — FULL Hebrew build from the New-Era-2 fleet output.

Source: fleet/corpus.json (99,875 rows) + fleet/hebrew.json (99,472 translated,
403 legitimately empty/markup-only page-break placeholders left as English).

Builds, per plugin, EVERY .STRINGS/.DLSTRINGS/.ILSTRINGS the plugin ships (from the
COMPLETE English base extract/langs/english.json -- 99,229 entries, 79 plugins),
overriding each id with the fleet's VISUAL-baked Hebrew where translated, else
keeping the original English (never a blank slot). Plus the UI table
(translate_english.txt) and the 3 Hebrew-injected font SWFs (same donors/ratio as
the Phase-1 proof).

Deploys LOOSE FILES ONLY under Data\\Strings + Data\\Interface -- nothing inside a
.bsa is touched, so Steam file-verification can never fight it. A manifest of every
deployed path is written so --revert deletes exactly those files and nothing else.

usage:  python build_full.py [--deploy] [--revert] [--verify] [--body 0.86]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                       # games/skyrim
FLEET = ROOT / "fleet"
sys.path.insert(0, str(ROOT / "tools"))

import strings as ST            # noqa: E402
import translate_txt as TT      # noqa: E402
import skyrim_font as SF        # noqa: E402
from skyrim_rtl import to_visual  # noqa: E402

GAME = Path(os.environ.get("SKYRIM_GAME",
                           r"D:\Games\TES - Skyrim - Anniversary Edition"))
DATA = GAME / "Data"
RAW = ROOT / "extract" / "raw"
OUT = HERE / "_full"
MANIFEST = HERE / "_full_deployed.json"

# same donors + body ratio as the accepted, in-game-verified Phase-1 proof
FONTS_EN = {
    3:  "C:/Windows/Fonts/Heebo-Medium.ttf",
    4:  "C:/Windows/Fonts/Heebo-Regular.ttf",
    5:  "C:/Windows/Fonts/Heebo-Light.ttf",
    7:  "C:/Windows/Fonts/Heebo-Medium.ttf",
    9:  "C:/Windows/Fonts/Heebo-Regular.ttf",
    13: "C:/Windows/Fonts/FrankRuhlLibre-Regular.ttf",
    15: "C:/Windows/Fonts/DavidLibre-Regular.ttf",
}
FONTS_CONSOLE = {1: "C:/Windows/Fonts/Heebo-Regular.ttf"}
FONTS_LIB = {
    7:  "C:/Windows/Fonts/Heebo-Regular.ttf",
    8:  "C:/Windows/Fonts/Heebo-Light.ttf",
    9:  "C:/Windows/Fonts/Heebo-Medium.ttf",
    10: "C:/Windows/Fonts/Heebo-Regular.ttf",
    11: "C:/Windows/Fonts/FrankRuhlLibre-Regular.ttf",
}


def load_english_base() -> dict[tuple[str, str], dict[int, str]]:
    """(plugin, kind) -> {sid: english_text}, complete for every plugin/kind."""
    eng = json.load(open(ROOT / "extract" / "langs" / "english.json", encoding="utf-8"))
    out: dict[tuple[str, str], dict[int, str]] = {}
    for key, text in eng.items():
        plug, sid, kind = key.split("|")
        out.setdefault((plug, kind), {})[int(sid)] = text
    return out


def load_hebrew_overrides() -> tuple[dict[tuple[str, str, int], str], dict[str, str]]:
    """-> ( (plugin,kind,sid) -> hebrew LOGICAL text ,  ui_key -> hebrew LOGICAL text )"""
    corpus = json.load(open(FLEET / "corpus.json", encoding="utf-8"))
    hebrew = json.load(open(FLEET / "hebrew.json", encoding="utf-8"))
    strs: dict[tuple[str, str, int], str] = {}
    ui: dict[str, str] = {}
    for rid, meta in corpus.items():
        he = hebrew.get(rid)
        if not he:
            continue
        kind = meta["kind"]
        if kind == "ui":
            ui[rid.split(":", 1)[1]] = he
        else:
            plug = meta["section"]
            sid = int(rid.rsplit("|", 1)[1])
            strs[(plug, kind, sid)] = he
    return strs, ui


def build(body_ratio: float) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "Interface").mkdir(exist_ok=True)
    (OUT / "Strings").mkdir(exist_ok=True)
    report: dict = {"body_ratio": body_ratio, "fonts": {}, "plugins": {}, "ui": {}}
    deployed: list[str] = []

    print("== English base + Hebrew overrides ==")
    base = load_english_base()
    str_overrides, ui_overrides = load_hebrew_overrides()
    print(f"   base: {sum(len(v) for v in base.values())} entries across "
          f"{len(base)} (plugin,kind) groups")
    print(f"   hebrew overrides: {len(str_overrides)} strings, {len(ui_overrides)} ui")

    print("\n== per-plugin .STRINGS/.DLSTRINGS/.ILSTRINGS ==")
    EXT = {"strings": "STRINGS", "dlstrings": "DLSTRINGS", "ilstrings": "ILSTRINGS"}
    n_files = 0
    n_he_total = 0
    for (plug, kind), en_entries in sorted(base.items()):
        entries: dict[int, str] = {}
        n_he = 0
        for sid, en_text in en_entries.items():
            he = str_overrides.get((plug, kind, sid))
            if he:
                entries[sid] = to_visual(he)
                n_he += 1
            else:
                entries[sid] = en_text
        rel = f"Strings/{plug}_english.{EXT[kind]}"
        ST.save(OUT / rel, entries)
        chk = ST.load(OUT / rel)
        assert chk == entries, f"round-trip drift: {rel}"
        deployed.append(rel)
        n_files += 1
        n_he_total += n_he
        report["plugins"].setdefault(plug, {})[kind] = {
            "entries": len(entries), "hebrew": n_he}
    print(f"   {n_files} files written, {n_he_total} Hebrew entries applied")

    print("\n== Interface/translate_english.txt ==")
    raw = (RAW / "interface" / "translate_english.txt").read_bytes()
    assert TT.roundtrip(RAW / "interface" / "translate_english.txt"), "translate codec drift"
    cur = TT.parse(raw)
    ov = {}
    n_ui_he = 0
    for k, he in ui_overrides.items():
        if k not in cur:
            print(f"   WARN ui key not in shipped table: {k!r}")
            continue
        ov[k] = to_visual(he)
        n_ui_he += 1
    out = TT.build(raw, ov)
    (OUT / "Interface" / "translate_english.txt").write_bytes(out)
    back = TT.parse(out)
    for k, v in ov.items():
        assert back[k] == v, f"ui key {k} did not survive rebuild"
    deployed.append("Interface/translate_english.txt")
    report["ui"] = {"keys_total": len(cur), "hebrew": n_ui_he}
    print(f"   {n_ui_he}/{len(cur)} ui keys patched, re-read OK ({len(out)} B)")

    print("\n== fonts ==")
    for src, faces, dst in (
            ("fonts_en.swf", FONTS_EN, "fonts_en.swf"),
            ("fonts_console.swf", FONTS_CONSOLE, "fonts_console.swf"),
            ("gfxfontlib.swf", FONTS_LIB, "gfxfontlib.swf")):
        print(f" {src}:")
        report["fonts"][src] = SF.inject_swf(RAW / "interface" / src,
                                             OUT / "Interface" / dst,
                                             faces, body_ratio=body_ratio)
        deployed.append(f"Interface/{dst}")

    (OUT / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    MANIFEST.write_text(json.dumps(sorted(deployed), ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\nmanifest: {len(deployed)} files -> {MANIFEST}")
    return report


def deploy() -> None:
    deployed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for rel in deployed:
        src = OUT / rel
        dst = DATA / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    print(f"deployed {len(deployed)} files under {DATA}")
    print("NOTHING inside a .bsa was modified. Revert = delete those files (see manifest).")


def revert() -> None:
    if not MANIFEST.exists():
        print("no manifest -- nothing to revert (or run from the dir that built it)")
        return
    deployed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    n = 0
    for rel in deployed:
        dst = DATA / rel
        if dst.exists():
            dst.unlink()
            n += 1
    for d in ("Interface", "Strings"):
        p = DATA / d
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    print(f"removed {n}/{len(deployed)} files")


def verify() -> None:
    """Read a sample back off DISK -- never trust the builder."""
    import swf as SWF
    from swf_font import parse_definefont3
    deployed = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    missing = [rel for rel in deployed if not (DATA / rel).exists()]
    print(f"{len(deployed)} files expected, {len(missing)} missing")
    if missing:
        for m in missing[:10]:
            print("  MISSING:", m)

    # sample a couple of .STRINGS files
    for rel in [r for r in deployed if r.endswith((".STRINGS", ".DLSTRINGS", ".ILSTRINGS"))][:3]:
        p = DATA / rel
        e = ST.load(p)
        heb = sum(1 for v in e.values() if any("\u05d0" <= c <= "\u05ea" for c in v))
        print(f"  {rel}: {len(e)} entries, {heb} contain Hebrew chars")

    cur = TT.load(DATA / "Interface" / "translate_english.txt")
    for k in ("$CONTINUE", "$NEW", "$LOAD"):
        if k in cur:
            print(f"  {k} = {cur[k]!r}")

    for swf_name, faces in (("fonts_en.swf", FONTS_EN),
                            ("fonts_console.swf", FONTS_CONSOLE),
                            ("gfxfontlib.swf", FONTS_LIB)):
        p = DATA / "Interface" / swf_name
        if not p.exists():
            continue
        s = SWF.read(p)
        for t in s.tags:
            if t.code == SWF.DEFINE_FONT3:
                f = parse_definefont3(t.body)
                if f["font_id"] in faces:
                    heb = sum(1 for c in f["codes"] if 0x05D0 <= c <= 0x05EA)
                    print(f"  {swf_name} id={f['font_id']:<3} heb={heb}/27")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--body", type=float, default=0.86)
    a = ap.parse_args()
    if a.revert:
        revert()
        return 0
    if a.verify:
        verify()
        return 0
    build(a.body)
    if a.deploy:
        print("\n== deploy ==")
        deploy()
        print()
        verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
