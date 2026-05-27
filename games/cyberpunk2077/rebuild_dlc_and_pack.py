"""
rebuild_dlc_and_pack.py
=======================
Bakes the Phantom Liberty DLC Hebrew translation into z_hebrew_dlc.archive —
the ep1 analog of rebuild_onscreens_and_pack.py + cp2077_subtitle_batch.py.

The Arabic-slot trick, applied to the DLC: the DLC ships ep1/lang_ar_text.archive
with an Arabic CR2W skeleton. We serialize each CR2W, apply our Hebrew from
dlc_ep1_translated.json, deserialize, and pack the result as a SEPARATE mod
archive — z_hebrew_dlc.archive — so it sits alongside the base mods untouched.

Pipeline (per the base scripts it mirrors):
  Phase 1  extract every CR2W from ep1/lang_ar_text.archive  (one-time, marker)
  Phase 2  for each section in dlc_ep1_translated.json:
             a. serialize CR2W -> text JSON      (WolvenKit CLI)
             b. apply Hebrew  (onscreens match by primaryKey, subtitles by
                stringId — the CR2W carries one or the other)
             c. deserialize text JSON -> CR2W    (WolvenKit CLI)
             d. place into the DLC project tree at ep1/localization/ar-ar/...
  Phase 3  pack the DLC tree -> z_hebrew_dlc.archive, backup, deploy

Section-key -> CR2W path:  dlc_ep1_text.json keys are `ep1/onscreens/<f>` and
`ep1/subtitles/<rel>`; the CR2W lives at `ep1/localization/ar-ar/<the rest>`.

Resumable — Phase 2 skips a file already present in the DLC project tree.
Requires Cyberpunk 2077 closed (the deploy file is overwritten).

Run: python rebuild_dlc_and_pack.py [--force-rebake]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── paths ────────────────────────────────────────────────────────────────────
CLI   = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME  = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
PROJ  = r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים"
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"

DLC_TRANSLATED = os.path.join(PROJ, r"source\resources\dlc_ep1_translated.json")
EP1_AR_ARCH    = os.path.join(GAME, r"archive\pc\ep1\lang_ar_text.archive")

WORK        = r"C:\Users\nc528\AppData\Local\Temp\dlc_rebuild"
EXTRACT_DIR = os.path.join(WORK, "ar_pristine")
TEXT_DIR    = os.path.join(WORK, "text")
ENCODED_DIR = os.path.join(WORK, "encoded")

# Separate DLC project tree so the pack contains ONLY ep1 paths.
PROJ_DLC_SRC = os.path.join(WORK, "project", "source", "archive")
PROJ_PACKED  = os.path.join(WORK, "project", "packed", "archive", "pc", "mod",
                             "archive.archive")
DEPLOY       = os.path.join(GAME, r"archive\pc\mod\z_hebrew_dlc.archive")

LOG_FILE = os.path.join(SCRIPTS_DIR, "rebuild_dlc.log")

HEBREW_RE = re.compile(r"[֐-׿]")
WOLVENKIT_TIMEOUT = 180


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def fatal(msg: str) -> None:
    log(f"FATAL: {msg}")
    sys.exit(1)


def run_cli(args, timeout=WOLVENKIT_TIMEOUT):
    try:
        r = subprocess.run([CLI] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:                                  # noqa: BLE001
        return False, f"EXCEPTION: {e}"


def section_to_relpath(section: str) -> str:
    """`ep1/onscreens/onscreens.json` -> `ep1/localization/ar-ar/onscreens/onscreens.json`."""
    rest = section[len("ep1/"):] if section.startswith("ep1/") else section
    return f"ep1/localization/ar-ar/{rest}"


# ── Phase 1 — extract the Arabic DLC skeleton ────────────────────────────────
def phase1_extract() -> None:
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    marker = os.path.join(EXTRACT_DIR, ".extracted_done")
    if os.path.exists(marker):
        log("Phase 1: already extracted (marker present), skipping")
        return
    log("Phase 1: extracting ep1/lang_ar_text.archive (Arabic DLC skeleton)")
    ok, out = run_cli(["extract", EP1_AR_ARCH, "-o", EXTRACT_DIR], timeout=900)
    if not ok:
        fatal(f"extract failed: {out[-500:]}")
    n = sum(1 for _ in Path(EXTRACT_DIR).rglob("*.json"))
    log(f"  extracted {n:,} CR2W files")
    Path(marker).touch()


# ── Phase 2 — per-section serialize -> apply -> deserialize -> place ─────────
def apply_hebrew(text_json_path: str, trans_entries: list) -> tuple[int, int]:
    """Apply Hebrew into a WolvenKit text JSON. The CR2W entry carries either
    `primaryKey` (onscreens) or `stringId` (subtitles); the translated entry is
    keyed the same way. Returns (fv_updated, mv_updated)."""
    with open(text_json_path, "r", encoding="utf-8") as f:
        wkit = json.load(f)
    lookup: dict = {}
    for e in trans_entries:
        if not isinstance(e, dict):
            continue
        key = e.get("primaryKey")
        if key is None:
            key = e.get("stringId")
        if key is not None:
            lookup[str(key)] = e
    try:
        entries = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except (KeyError, TypeError):
        return 0, 0
    fv = mv = 0
    for entry in entries:
        k = entry.get("primaryKey")
        if k is None:
            k = entry.get("stringId")
        if k is None:
            continue
        t = lookup.get(str(k))
        if not t:
            continue
        new_fv = (t.get("femaleVariant") or "").strip()
        new_mv = (t.get("maleVariant") or "").strip()
        # one Hebrew variant -> use it for both gender slots (replaces Arabic mv)
        if new_fv and not new_mv and HEBREW_RE.search(new_fv):
            new_mv = new_fv
        elif new_mv and not new_fv and HEBREW_RE.search(new_mv):
            new_fv = new_mv
        if new_fv and HEBREW_RE.search(new_fv) and new_fv != entry.get("femaleVariant", ""):
            entry["femaleVariant"] = new_fv
            fv += 1
        if new_mv and HEBREW_RE.search(new_mv) and new_mv != entry.get("maleVariant", ""):
            entry["maleVariant"] = new_mv
            mv += 1
    if fv or mv:
        with open(text_json_path, "w", encoding="utf-8") as f:
            json.dump(wkit, f, ensure_ascii=False, indent=2)
    return fv, mv


def process_section(section: str, entries: list, force: bool, st: dict) -> None:
    rel = section_to_relpath(section)
    src_cr2w = os.path.join(EXTRACT_DIR, rel.replace("/", os.sep))
    dst_cr2w = os.path.join(PROJ_DLC_SRC, rel.replace("/", os.sep))

    if not force and os.path.exists(dst_cr2w) and os.path.getsize(dst_cr2w) > 100:
        st["skipped"] += 1
        return
    if not os.path.exists(src_cr2w):
        st["missing_src"] += 1
        log(f"  [!] no Arabic skeleton for {section}")
        return
    if not any(isinstance(e, dict) and HEBREW_RE.search(e.get("femaleVariant") or "")
               for e in entries):
        st["no_hebrew"] += 1                       # nothing translated yet — skip
        return

    fname = os.path.basename(src_cr2w)
    tdir = os.path.join(TEXT_DIR, "_f")
    edir = os.path.join(ENCODED_DIR, "_f")
    os.makedirs(tdir, exist_ok=True)
    os.makedirs(edir, exist_ok=True)
    txt = os.path.join(tdir, fname + ".json")
    enc = os.path.join(edir, fname)
    for p in (txt, enc):
        if os.path.exists(p):
            os.remove(p)

    ok, out = run_cli(["convert", "serialize", src_cr2w, "-o", tdir])
    if not ok or not os.path.exists(txt):
        st["fail_serialize"] += 1
        log(f"  [!] serialize failed {section}: {out[-160:]}")
        return
    try:
        fv, mv = apply_hebrew(txt, entries)
    except Exception as e:                                  # noqa: BLE001
        st["fail_apply"] += 1
        log(f"  [!] apply failed {section}: {e}")
        return
    if fv == 0 and mv == 0:
        st["no_changes"] += 1
        os.remove(txt)
        return
    ok, out = run_cli(["convert", "deserialize", txt, "-o", edir])
    if not ok or not os.path.exists(enc):
        st["fail_deserialize"] += 1
        log(f"  [!] deserialize failed {section}: {out[-160:]}")
        return
    os.makedirs(os.path.dirname(dst_cr2w), exist_ok=True)
    if os.path.exists(dst_cr2w):
        os.remove(dst_cr2w)
    os.replace(enc, dst_cr2w)
    if os.path.exists(txt):
        os.remove(txt)
    st["baked"] += 1
    st["fv"] += fv
    st["mv"] += mv


def phase2_bake(force: bool) -> dict:
    log(f"Phase 2: baking DLC sections from {os.path.basename(DLC_TRANSLATED)}")
    with open(DLC_TRANSLATED, "r", encoding="utf-8") as f:
        dlc = json.load(f)
    sections = [s for s in sorted(dlc) if isinstance(dlc[s], list)]
    log(f"  {len(sections):,} sections to process")
    st = dict(baked=0, skipped=0, no_hebrew=0, no_changes=0, missing_src=0,
              fail_serialize=0, fail_apply=0, fail_deserialize=0, fv=0, mv=0)
    t0 = time.time()
    for i, section in enumerate(sections, 1):
        process_section(section, dlc[section], force, st)
        if i % 50 == 0 or i == len(sections):
            rate = i / max(time.time() - t0, 1)
            eta = (len(sections) - i) / rate / 60 if rate else 0
            log(f"  [{i}/{len(sections)}] baked={st['baked']} skipped={st['skipped']} "
                f"no_heb={st['no_hebrew']} fail={st['fail_serialize']+st['fail_apply']+st['fail_deserialize']}"
                f"  ETA {eta:.0f}m")
    log("Phase 2 stats: " + ", ".join(f"{k}={v:,}" for k, v in st.items()))
    return st


# ── Phase 3 — pack + deploy ──────────────────────────────────────────────────
def phase3_pack_deploy() -> None:
    log("Phase 3: packing z_hebrew_dlc.archive")
    file_count = sum(1 for _, _, fs in os.walk(PROJ_DLC_SRC) for _ in fs)
    if file_count == 0:
        fatal("DLC project tree is empty — nothing baked, refusing to pack")
    log(f"  DLC tree carries {file_count:,} CR2W files")
    out_dir = os.path.dirname(PROJ_PACKED)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(PROJ_PACKED):
        os.remove(PROJ_PACKED)
    ok, out = run_cli(["pack", PROJ_DLC_SRC, "-o", out_dir], timeout=900)
    if not ok or not os.path.exists(PROJ_PACKED):
        fatal(f"pack failed: {out[-500:]}")
    log(f"  packed -> {PROJ_PACKED} ({os.path.getsize(PROJ_PACKED):,} bytes)")

    log("Phase 3: deploying z_hebrew_dlc.archive")
    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    if os.path.exists(DEPLOY):
        bdir = os.path.join(GAME, "archive", "pc", "mod_backups",
                            "dlc_" + time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(bdir, exist_ok=True)
        shutil.copy2(DEPLOY, os.path.join(bdir, os.path.basename(DEPLOY)))
        log(f"  backed up previous z_hebrew_dlc.archive -> {bdir}")
        try:
            os.remove(DEPLOY)
        except PermissionError:
            fatal("deploy target locked — close Cyberpunk 2077 and re-run.")
    shutil.copy2(PROJ_PACKED, DEPLOY)
    log(f"  deployed -> {DEPLOY} ({os.path.getsize(DEPLOY):,} bytes)")


def main() -> int:
    force = "--force-rebake" in sys.argv
    log("=" * 70)
    log("rebuild_dlc_and_pack starting" + ("  (--force-rebake)" if force else ""))
    log("=" * 70)
    t0 = time.time()

    for p, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"),
                    (EP1_AR_ARCH, "ep1/lang_ar_text.archive"),
                    (DLC_TRANSLATED, "dlc_ep1_translated.json")]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except PermissionError:
            fatal(f"deploy target locked (game running?): {DEPLOY}")

    if force and os.path.exists(PROJ_DLC_SRC):
        shutil.rmtree(PROJ_DLC_SRC, ignore_errors=True)
    os.makedirs(PROJ_DLC_SRC, exist_ok=True)

    phase1_extract()
    phase2_bake(force)
    phase3_pack_deploy()

    log("=" * 70)
    log(f"DONE — total {(time.time() - t0) / 60:.1f} min")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
