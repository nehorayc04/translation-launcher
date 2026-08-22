#!/usr/bin/env python3
"""pack_and_release.py — build the shippable RDR2 Hebrew drop-in zip (+ manifest).

🔑 THE BYTES COME OUT OF THE LIVE GAME FOLDER, not out of the build's staging dir. The whole
point of a release package is that it contains exactly what was TESTED, and what was tested is
what sits in the game folder the user just played. Reading the staging copy would let a stale
or mid-build artifact ship while every check still passes (the "verify the ARTIFACT, never the
source tree" lesson from the Witcher 3 launch).

The user extracts the zip into the game folder and launches. Revert = delete `dinput8.dll`.

    python pack_and_release.py 1.0.0-beta.1                 # pack + verify only  (default)
    python pack_and_release.py 1.0.0-beta.1 --release       # ALSO create the GitHub release
                                                            # -- only on an explicit "פרסם"
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "work"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"
OUTD = os.path.join(HERE, "release")
FILES_D = os.path.join(HERE, "release_files")
REPO = "hebrew-translation-hub/rdr2-hebrew-mods"
ARCHIVE = "rdr2_hebrew.zip"

# Loader infrastructure, taken verbatim from the working install. NOT our IP — the same public
# files the community already runs for the Arabic mod. Credited in the readme.
LOADER_ROOT = [
    "dinput8.dll",                     # the ASI proxy: deleting THIS is the whole uninstall
    "ScriptHookRDR2.dll",
    "vfs.asi",                         # the LML engine
    "ModManager.Core.dll",
    "ModManager.NativeInterop.dll",
    "NLog.dll",
    "lml.ini",
]
LOADER_LML = [
    "mods.xml",
    "patterns.dat",
    "KGF/install.xml",                 # font replacement descriptor
    "tranar/install.xml",              # DataFile (text) descriptor
]
CONTENT = [
    ("lml/KGF/asset_replace/font_lib_efigs.gfx", "lml/KGF/asset_replace/font_lib_efigs.gfx"),
    ("lml/tranar/Ko Games Studio.gxt2", "lml/tranar/Ko Games Studio.gxt2"),
]


def g(rel: str) -> str:
    return os.path.join(GAME, rel.replace("/", os.sep))


def preflight() -> dict:
    """Refuse to package a build that would ship a defect. Every check reads the LIVE file."""
    import rdr2_text

    gxt2 = g("lml/tranar/Ko Games Studio.gxt2")
    recs = rdr2_text.parse(open(gxt2, encoding="utf-8").read())
    entries = [r for r in recs if r["kind"] == "entry"]
    d = {r["key"]: r["val"] for r in entries}
    vals = list(d.values())

    HEB = re.compile(r"[\u05d0-\u05ea]")
    NIQ = re.compile(r"[\u0591-\u05c7]")
    FOR = re.compile(r"[\u0400-\u04ff\u0600-\u06ff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af"
                     r"\u0370-\u03ff]")
    LONG = re.compile(r"[\u2010-\u2015\u2212\u2e3a\u2e3b\ufe58\ufe63\uff0d]")
    MARK = re.compile(r"ZZ-|__MARK|@@TS")

    cov = set(json.load(open(os.path.join(HERE, "work", "_fontinspect",
                                          "covered_codes.json"), encoding="utf-8")))
    uncov = sorted({c for v in vals for c in v if c != "~" and ord(c) not in cov})

    checks = {
        "entries": len(entries),
        "duplicate keys": len(entries) - len(d),
        "hebrew %": round(100 * sum(1 for v in vals if HEB.search(v)) / len(vals), 1),
        "'=' in a value": sum(1 for v in vals if "=" in v),
        "niqqud": sum(1 for v in vals if NIQ.search(v)),
        "foreign script": sum(1 for v in vals if FOR.search(v)),
        "long dash": sum(1 for v in vals if LONG.search(v)),
        "proof markers": sum(1 for v in vals if MARK.search(v)),
        "empty values": sum(1 for v in vals if not v.strip()),
        "uncovered codepoints": len(uncov),
    }
    print("=== pre-flight (live game files) ===")
    for k, v in checks.items():
        print(f"  {k:22} {v}")
    if uncov:
        print(f"  !! uncovered: {uncov}")

    fatal = [k for k in ("duplicate keys", "'=' in a value", "niqqud", "foreign script",
                         "long dash", "proof markers", "empty values", "uncovered codepoints")
             if checks[k]]
    if fatal:
        sys.exit(f"\n!! REFUSING TO PACK — failed: {', '.join(fatal)}")
    if checks["hebrew %"] < 99.0:
        sys.exit(f"\n!! REFUSING TO PACK — only {checks['hebrew %']}% of values carry Hebrew")
    print("  -> PASS\n")
    return checks


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    version = sys.argv[1]
    do_release = "--release" in sys.argv

    checks = preflight()
    os.makedirs(OUTD, exist_ok=True)
    zpath = os.path.join(OUTD, ARCHIVE)

    missing = [f for f in LOADER_ROOT if not os.path.exists(g(f))] + \
              [f"lml/{f}" for f in LOADER_LML if not os.path.exists(g(f"lml/{f}"))] + \
              [s for s, _ in CONTENT if not os.path.exists(g(s))]
    if missing:
        sys.exit(f"!! missing from the game folder: {missing}")

    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in LOADER_ROOT:
            z.write(g(f), f)
        for f in LOADER_LML:
            z.write(g(f"lml/{f}"), f"lml/{f}")
        for src, dst in CONTENT:
            # ⚠️ never glob asset_replace/ — it also holds *.prescale_backup / *.stencil_backup,
            # 6.6 MB of dead weight that must not reach a user.
            z.write(g(src), dst)
        for name in sorted(os.listdir(FILES_D)):
            z.write(os.path.join(FILES_D, name), name)

    size = os.path.getsize(zpath)
    sha = hashlib.sha256(open(zpath, "rb").read()).hexdigest()
    manifest = {
        "version": version,
        "archive_name": ARCHIVE,     # the Worker + mod_source contract key; NOT "archive"
        "archive": ARCHIVE,          # tolerated spelling, kept so no consumer can miss it
        "sha256": sha,
        "size_bytes": size,
        "entries": checks["entries"],
    }
    mpath = os.path.join(OUTD, "manifest.json")
    json.dump(manifest, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=== package ===")
    with zipfile.ZipFile(zpath) as z:
        for i in z.infolist():
            print(f"  {i.filename:52} {i.file_size:>10,} B")
    print(f"\n  {ARCHIVE}  {size:,} B")
    print(f"  sha256      {sha}")
    print(f"  manifest    {mpath}")

    if not do_release:
        print("\n(pack only — pass --release to create the GitHub release)")
        return

    tag = f"v{version}"
    subprocess.run(["gh", "release", "create", tag, zpath, mpath,
                    "--repo", REPO, "--title", f"RDR2 Hebrew {version}",
                    "--notes", f"Red Dead Redemption 2 Hebrew translation {version}"],
                   check=True)
    print(f"\nreleased {tag} on {REPO}")


if __name__ == "__main__":
    main()
