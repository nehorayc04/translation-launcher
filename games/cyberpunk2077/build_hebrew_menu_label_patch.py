"""
build_hebrew_menu_label_patch.py
================================
Patch builder — overrides pk=49601 (sec=UI-Settings-Language-Arabic) in
EVERY language localization so the Settings > Language dropdown reads
"Hebrew" no matter which interface language the player currently uses.

Why all locales: the player might boot CP2077 in French / German /
Japanese / etc. The original Arabic label gets localized into each
language (Arabe / Arabisch / アラビア語 / …). Without an override per
locale, our mod is undiscoverable.

Output: one combined override archive at
  <game>/archive/pc/mod/z_hebrew_menu_name_patch.archive

Each locale gets a CR2W override under base\\localization\\<locale>\\onscreens\\.
Hebrew/Arabic slot is INTENTIONALLY skipped — the main mod
(z_hebrew_translation.archive) handles ar-ar via the
localization_translated.json pipeline.

Re-runnable. Wipes its work dir on each invocation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLI         = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
CONTENT_DIR = os.path.join(GAME, r"archive\pc\content")

WORK        = r"C:\tmp\menu_label_patch"
EXTRACT_DIR = os.path.join(WORK, "extracted")
TEXT_DIR    = os.path.join(WORK, "text")
ENC_DIR     = os.path.join(WORK, "encoded")
PROJ_DIR    = os.path.join(WORK, "project")
PACKED_DIR  = os.path.join(PROJ_DIR, "packed", "archive", "pc", "mod")
PACKED_FILE = os.path.join(PACKED_DIR, "archive.archive")

DEPLOY      = os.path.join(GAME, r"archive\pc\mod\z_hebrew_menu_name_patch.archive")

LOG_FILE    = os.path.join(os.path.dirname(__file__), "build_hebrew_menu_label_patch.log")

# Map archive filename → (locale folder, display label).
# Hebrew/Arabic slot (ar-ar) intentionally NOT here — main mod handles it.
# The English-word "Hebrew" is the universally-recognizable label for the
# discoverability problem we're solving; we don't risk relying on
# localized translations (would force a per-locale glossary to maintain).
LOCALES: list[tuple[str, str, str]] = [
    # (archive filename,         locale folder,  label to set)
    ("lang_en_text.archive",     "en-us",        "Hebrew"),
    ("lang_fr_text.archive",     "fr-fr",        "Hebrew"),
    ("lang_de_text.archive",     "de-de",        "Hebrew"),
    ("lang_es-es_text.archive",  "es-es",        "Hebrew"),
    ("lang_es-mx_text.archive",  "es-mx",        "Hebrew"),
    ("lang_it_text.archive",     "it-it",        "Hebrew"),
    ("lang_pl_text.archive",     "pl-pl",        "Hebrew"),
    ("lang_pt_text.archive",     "pt-br",        "Hebrew"),
    ("lang_ru_text.archive",     "ru-ru",        "Hebrew"),
    ("lang_cs_text.archive",     "cz-cz",        "Hebrew"),
    ("lang_hu_text.archive",     "hu-hu",        "Hebrew"),
    ("lang_tr_text.archive",     "tr-tr",        "Hebrew"),
    ("lang_ja_text.archive",     "jp-jp",        "Hebrew"),
    ("lang_ko_text.archive",     "kr-kr",        "Hebrew"),
    ("lang_zh-cn_text.archive",  "zh-cn",        "Hebrew"),
    ("lang_zh-tw_text.archive",  "zh-tw",        "Hebrew"),
    ("lang_th_text.archive",     "th-th",        "Hebrew"),
    ("lang_ua_text.archive",     "ua-ua",        "Hebrew"),
]

# Onscreens files we override per locale.
ONSCREENS_FILES = ["onscreens.json", "onscreens_final.json"]

# Patch target — two-key match (primaryKey OR secondaryKey suffix).
TARGET_PK = 49601
TARGET_SEC_SUFFIX = "UI-Settings-Language-Arabic"

WKIT_TIMEOUT = 600


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


def run_cli(args: list[str], timeout: int = WKIT_TIMEOUT) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [CLI] + args,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def step0_sanity() -> None:
    log("STEP 0: Sanity checks")
    if not os.path.exists(CLI):  fatal(f"WolvenKit CLI missing at {CLI}")
    if not os.path.exists(GAME): fatal(f"Game folder missing at {GAME}")
    missing = []
    for fname, _, _ in LOCALES:
        path = os.path.join(CONTENT_DIR, fname)
        if not os.path.exists(path):
            missing.append(fname)
    if missing:
        log(f"  WARNING: {len(missing)} archives not found — will skip: {missing}")
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except OSError:
            fatal(f"deploy target locked (game running?): {DEPLOY}")
    log(f"  OK — {len(LOCALES) - len(missing)} locales to process")


def step1_clean_workdir() -> None:
    log("STEP 1: Cleaning workdir")
    if os.path.exists(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    for d in (EXTRACT_DIR, TEXT_DIR, ENC_DIR, PROJ_DIR):
        os.makedirs(d, exist_ok=True)


def process_locale(archive_fname: str, locale: str, label: str) -> bool:
    """Extract → serialize → patch → deserialize → place for one locale.
    Returns True on success, False to skip (archive missing / no hit)."""
    arch_path = os.path.join(CONTENT_DIR, archive_fname)
    if not os.path.exists(arch_path):
        log(f"  [{locale}] skip — archive not present")
        return False

    log(f"  [{locale}] extracting onscreens from {archive_fname}")
    loc_extract_dir = os.path.join(EXTRACT_DIR, locale)
    loc_text_dir    = os.path.join(TEXT_DIR,    locale)
    loc_enc_dir     = os.path.join(ENC_DIR,     locale)
    for d in (loc_extract_dir, loc_text_dir, loc_enc_dir):
        os.makedirs(d, exist_ok=True)

    # Step a: extract both onscreens files from this locale's archive
    for fname in ONSCREENS_FILES:
        ok, out = run_cli(["extract", arch_path, "-o", loc_extract_dir, "-w", f"*{fname}*"])
        if not ok:
            log(f"  [{locale}] extract failed for {fname}: {out[-200:]}")
            return False

    # Find onscreens dir under loc_extract_dir — folder name differs per archive
    # (the archive's CR2Ws preserve their original path, which uses the
    # locale code embedded in the archive itself).
    onscreens_dir = None
    for root, dirs, files in os.walk(loc_extract_dir):
        if any(f in files for f in ONSCREENS_FILES):
            onscreens_dir = root
            break
    if not onscreens_dir:
        log(f"  [{locale}] onscreens dir not found after extract — skipping")
        return False

    # Derive the locale-folder-name from the extracted CR2W path so we
    # write the override into the SAME path the game expects.
    rel = os.path.relpath(onscreens_dir, loc_extract_dir).replace(os.sep, "/")
    log(f"  [{locale}] CR2W path: {rel}")

    patched_any = False
    for fname in ONSCREENS_FILES:
        src_cr2w = os.path.join(onscreens_dir, fname)
        if not os.path.exists(src_cr2w):
            log(f"  [{locale}] {fname} not in archive — skipping this file")
            continue

        # Step b: serialize
        ok, out = run_cli(["convert", "serialize", src_cr2w, "-o", loc_text_dir])
        if not ok:
            log(f"  [{locale}] serialize {fname} failed: {out[-200:]}")
            continue
        txt = os.path.join(loc_text_dir, fname + ".json")
        if not os.path.exists(txt):
            log(f"  [{locale}] text JSON missing for {fname}")
            continue

        # Step c: patch
        with open(txt, "r", encoding="utf-8") as f:
            wkit = json.load(f)
        try:
            entries = wkit["Data"]["RootChunk"]["root"]["Data"]["entries"]
        except (KeyError, TypeError):
            log(f"  [{locale}] unexpected CR2W shape for {fname}")
            continue
        hits = 0
        for entry in entries:
            pk = entry.get("primaryKey")
            sec = entry.get("secondaryKey") or ""
            if pk == TARGET_PK or sec.endswith(TARGET_SEC_SUFFIX):
                old = entry.get("femaleVariant")
                entry["femaleVariant"] = label
                hits += 1
                log(f"    {fname}: pk={pk}  fv {old!r} -> {label!r}")
        if hits == 0:
            log(f"  [{locale}] no matching entry in {fname} — skipping")
            continue
        with open(txt, "w", encoding="utf-8") as f:
            json.dump(wkit, f, ensure_ascii=False, indent=2)

        # Step d: deserialize
        ok, out = run_cli(["convert", "deserialize", txt, "-o", loc_enc_dir])
        if not ok:
            log(f"  [{locale}] deserialize {fname} failed: {out[-200:]}")
            continue
        enc = os.path.join(loc_enc_dir, fname)
        if not os.path.exists(enc):
            log(f"  [{locale}] encoded CR2W missing for {fname}")
            continue

        # Step e: place into combined project tree at the same path
        dst = os.path.join(PROJ_DIR, "source", "archive", rel.replace("/", os.sep), fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(enc, dst)
        patched_any = True

    return patched_any


def step2_process_all_locales() -> int:
    log(f"STEP 2: Processing {len(LOCALES)} locales")
    ok_count = 0
    for fname, locale, label in LOCALES:
        if process_locale(fname, locale, label):
            ok_count += 1
    log(f"  {ok_count}/{len(LOCALES)} locales patched successfully")
    return ok_count


def step3_pack_and_deploy() -> None:
    log("STEP 3: Packing combined override archive")
    src_archive = os.path.join(PROJ_DIR, "source", "archive")
    # Count files we're about to pack — paranoid sanity check
    file_count = sum(1 for _, _, files in os.walk(src_archive) for f in files)
    if file_count == 0:
        fatal("nothing patched — refusing to ship empty archive")
    log(f"  archive will contain {file_count} CR2W files")

    os.makedirs(PACKED_DIR, exist_ok=True)
    if os.path.exists(PACKED_FILE):
        os.remove(PACKED_FILE)
    ok, out = run_cli(["pack", src_archive, "-o", PACKED_DIR])
    if not ok or not os.path.exists(PACKED_FILE):
        fatal(f"pack failed: {out[-400:]}")
    sz = os.path.getsize(PACKED_FILE)
    log(f"  packed -> {PACKED_FILE} ({sz:,} bytes)")

    log("STEP 4: Deploying override to game mod folder")
    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    if os.path.exists(DEPLOY):
        try:
            os.remove(DEPLOY)
        except PermissionError:
            fatal("deploy target locked — close the game first.")
    shutil.copy2(PACKED_FILE, DEPLOY)
    log(f"  deployed -> {DEPLOY} ({os.path.getsize(DEPLOY):,} bytes)")


def main() -> None:
    t0 = time.time()
    log("=" * 78)
    log("build_hebrew_menu_label_patch starting (multi-locale)")
    log("=" * 78)
    step0_sanity()
    step1_clean_workdir()
    ok = step2_process_all_locales()
    if ok == 0:
        fatal("no locales patched — nothing to ship")
    step3_pack_and_deploy()
    log("=" * 78)
    log(f"DONE — total {(time.time()-t0)/60:.1f} min ({int(time.time()-t0)}s) — "
        f"{ok} locales patched")
    log("=" * 78)


if __name__ == "__main__":
    main()
