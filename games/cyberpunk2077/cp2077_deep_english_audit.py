"""
cp2077_deep_english_audit.py
============================
Deep, 5-layer audit of every English string still visible to a Cyberpunk 2077
player after the Hebrew translation mod is installed. Base game only — DLC
(Phantom Liberty) is intentionally excluded; it has its own pipeline.

Layers:
  1.  Source JSON  — cp2077_qa_defects.scan_all() over localization_translated.json
                     (foreign / english_leak / missing / structural defects).
  2.  Baked archive — extract z_hebrew_translation.archive and z_hebrew_static.archive
                     via WolvenKit CLI, serialize every CR2W, and verify each
                     baked entry against the source JSON. Flags bake-drift
                     (source has Hebrew but baked output is English / Arabic /
                     blank) and markup-drop-in-bake.
  3.  Dropped wrappers — entries whose secondaryKey is markup
                     (<kiroshi>/<mothertongue>/<Rich>) but whose femaleVariant
                     lost the wrapper while keeping the Hebrew text. Type-A:
                     the translation reads, but the foreign-audio styling is
                     lost. Not flagged by cp2077_qa_defects.
  4.  Loose game text — scan small JSON/YAML/TXT/REDs files in the game install
                     for English-only text. Defensive layer.
  5.  Aggregation  — categorize all findings into 9 buckets (A..I) and emit:
                     cp2077_deep_english_audit.txt + .json.

Run from the project root:
    python cp2077_deep_english_audit.py

Cyberpunk 2077 must be closed (we open the archive read-only, but the deploy
target might be locked otherwise).
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import audit_translations as _audit        # detect_scripts, has_hebrew
import cp2077_status_report as _rep         # classify, needs_translation, paths
import cp2077_qa_defects as _qa             # scan_all, is_markup, translatable_text
import cp2077_markup_translate as _markup   # parse_slots (markup slot model)


# ── paths ───────────────────────────────────────────────────────────────────
SCRIPTS_DIR = _rep.SCRIPTS_DIR
GAME_DIR    = os.path.join(SCRIPTS_DIR, "Cyberpunk 2077")
MOD_DIR     = os.path.join(GAME_DIR, "archive", "pc", "mod")

TRANSLATED_JSON = _rep.TRANSLATED
EXPORT_JSON     = _rep.EXPORT

MOD_MAIN   = os.path.join(MOD_DIR, "z_hebrew_translation.archive")
MOD_STATIC = os.path.join(MOD_DIR, "z_hebrew_static.archive")

CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"

WORK_ROOT = os.path.join(os.environ.get("TEMP", r"C:\Users\Nehoray_Cohen\AppData\Local\Temp"),
                         "cp2077_deep_audit")

REPORT_TXT  = os.path.join(SCRIPTS_DIR, "cp2077_deep_english_audit.txt")
REPORT_JSON = os.path.join(SCRIPTS_DIR, "cp2077_deep_english_audit.json")

# Loose-text scan — text-like file extensions to read. Skip everything binary.
LOOSE_EXTS    = {".json", ".yaml", ".yml", ".txt", ".ini", ".cfg"}
LOOSE_MAX_KB  = 1024  # ignore files > 1 MB — likely binary blobs or data dumps
# Heavy folders inside the game install: do not walk into them. These hold
# either CDPR-shipped English (we deliberately ship those untouched) or
# tooling / engine internals that are never user-facing.
LOOSE_SKIP_DIRS = {
    "content", "ep1", "metadata.store", "mod_backups",
    "lang_en_text.archive", "lang_ar_text.archive",
    # CDPR modding tools — source/build artefacts, never user-visible
    "tools",
    # engine configs / GI weights / binary launcher bits
    "engine", "_Redist",
    # r6/config/* is input-mapping / settings DEFAULTS (display labels live
    # in onscreens, not here); r6/publishing/* is Steam add-on metadata which
    # is managed by Steam, not localized via mod.
    "config", "publishing", "scripts", "cache",
}
# Top-level files we deliberately ignore at the game root — they're
# launcher / mod-manager metadata (UI labels live in the launcher itself).
LOOSE_SKIP_BASENAMES = {
    "launcher-configuration.json", "vortex.deployment.json",
    "metadata.store",
}
# Inside bin/x64/ the only thing worth scanning is user-installed plugins'
# UI text (CET mods, RED4ext mods). bin/x64/*.ini and the cyber_engine_tweaks
# config / persistent files are engine state, not translation candidates.
LOOSE_BIN_X64_KEEP = re.compile(
    r"bin/x64/plugins/(?:cyber_engine_tweaks/mods|red4ext/plugins)/",
    re.IGNORECASE,
)
# Path fragments we always skip — code subfolders inside mods (never UI text)
LOOSE_SKIP_PATH_FRAGMENTS = (
    "/classes/", "/lib/", "/libs/", "/vendor/", "/external/",
)

# Words that are not "real English prose" by themselves — short tokens, all-caps
# acronyms, CDPR brand vocabulary. Reuse the brand/common-word whitelists from
# cp2077_qa_defects so the loose-text scan stays consistent with the source
# audit.
BRAND_WHITELIST = _qa.BRAND_WHITELIST

WOLVENKIT_TIMEOUT  = 600
WOLVENKIT_WORKERS  = 4         # parallel serialize() workers


# ── small helpers ───────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_cli(args, timeout: int = WOLVENKIT_TIMEOUT) -> tuple[bool, str]:
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


def has_hebrew(text: str) -> bool:
    return _audit.has_hebrew(text or "")


def has_arabic(text: str) -> bool:
    if not text:
        return False
    return any(0x0600 <= ord(c) <= 0x06FF or 0x0750 <= ord(c) <= 0x077F
               for c in text)


# ── finding model ──────────────────────────────────────────────────────────
@dataclass
class Finding:
    """One row in the aggregated report."""
    layer:    str          # 'source' | 'baked_main' | 'baked_static' | 'wrappers' | 'loose'
    section:  str          # JSON section key or relative path
    pk:       str          # primary key, or "" for loose-text findings
    field:    str          # 'femaleVariant' / 'maleVariant' / '' for loose
    kind:     str          # raw defect type (foreign / english_leak / missing / structural / bake_drift / ...)
    detail:   str          # human-readable specifics
    value:    str          # the offending value (truncated to 240 chars in the report)
    english:  str          # source English (for context)
    extras:   dict = field(default_factory=dict)


# ── layer 1 — source JSON audit ─────────────────────────────────────────────
def layer1_source_audit(translated: dict, export: dict) -> list[Finding]:
    """Re-run cp2077_qa_defects.scan_all() and convert each Defect to a Finding.

    The scanner already covers all four classes (foreign / english_leak /
    missing / structural) and is the canonical detector — every other QA tool
    in the project agrees with it.
    """
    log("layer 1: scanning source JSON for defects …")
    defects = _qa.scan_all(translated, export)
    out: list[Finding] = []
    for d in defects:
        out.append(Finding(
            layer   = "source",
            section = d.section,
            pk      = d.pk,
            field   = d.field,
            kind    = d.kind,
            detail  = d.detail,
            value   = d.value,
            english = d.english,
            extras  = {"is_markup": d.is_markup},
        ))
    by_kind = Counter(f.kind for f in out)
    log(f"  layer 1 defects: {len(out):,} ({dict(by_kind)})")
    return out


# ── layer 2 — baked archive verification ────────────────────────────────────
def _serialize_one(cr2w: Path, out_dir: Path) -> Optional[Path]:
    ok, msg = run_cli(["convert", "serialize", str(cr2w), "-o", str(out_dir)])
    if not ok:
        return None
    cand = out_dir / (cr2w.name + ".json")
    return cand if cand.exists() else None


def _extract_archive(archive_path: str, raw_dir: Path) -> bool:
    raw_dir.mkdir(parents=True, exist_ok=True)
    existing = sum(1 for _ in raw_dir.rglob("*.json"))
    if existing > 0:
        log(f"  cache hit — reusing {existing:,} pre-extracted CR2W in {raw_dir.name}/")
        return True
    log(f"  extracting {os.path.basename(archive_path)} -> {raw_dir.name}/")
    ok, msg = run_cli(["extract", archive_path, "-o", str(raw_dir)],
                      timeout=900)
    if not ok:
        log(f"  extract failed: {msg[-300:]}")
        return False
    cnt = sum(1 for _ in raw_dir.rglob("*.json"))
    log(f"  extracted {cnt:,} CR2W files")
    return cnt > 0


def _serialize_tree(
    raw_dir: Path,
    json_dir: Path,
    locale_filter: Optional[str] = "ar-ar",
) -> dict[str, Path]:
    """Serialize every *.json CR2W under raw_dir into json_dir, returning
    {section_key: serialized_path}.

    locale_filter selects which `base/localization/<locale>/` subtree to keep.
    For the main translation archive only `ar-ar` is relevant (everything else
    is base game). For the static archive pass `None` to keep all locales.

    section_key uniquely identifies a baked file:
      * ar-ar:  path relative to base/localization/ar-ar/  (matches source JSON)
      * other:  base/localization/<locale>/<rest>           (static archive)
    """
    json_dir.mkdir(parents=True, exist_ok=True)

    # WolvenKit serialize emits FLAT output: <input_filename>.json regardless
    # of input subdir. To preserve uniqueness we serialize each file into its
    # own subdirectory mirroring the source tree, then read it from there.
    cr2ws = list(raw_dir.rglob("*.json"))
    log(f"  found {len(cr2ws):,} CR2W files under {raw_dir.name}/")

    jobs: list[tuple[Path, Path, str]] = []
    skipped: dict[str, Path] = {}      # already-serialized — count toward cache hits
    base_loc = raw_dir / "base" / "localization"

    for cr2w in cr2ws:
        try:
            rel_to_loc = cr2w.relative_to(base_loc)
        except ValueError:
            continue   # outside base/localization/ (video swap, etc.)
        parts = rel_to_loc.parts
        if not parts:
            continue
        locale = parts[0]
        if locale_filter is not None and locale != locale_filter:
            continue
        # section_key derivation
        if locale_filter == "ar-ar":
            section_key = Path(*parts[1:]).as_posix()
        else:
            section_key = rel_to_loc.as_posix()
        sub_out = json_dir / rel_to_loc.parent
        sub_out.mkdir(parents=True, exist_ok=True)
        # Cache hit — if a serialized json already exists, reuse it
        cached = sub_out / (cr2w.name + ".json")
        if cached.exists() and cached.stat().st_size > 0:
            skipped[section_key] = cached
            continue
        jobs.append((cr2w, sub_out, section_key))

    if skipped:
        log(f"  cache hit — reusing {len(skipped):,} pre-serialized files")
    log(f"  serializing {len(jobs):,} new CR2W files with {WOLVENKIT_WORKERS} workers …")

    result: dict[str, Path] = dict(skipped)
    if not jobs:
        log(f"  serialize ok: {len(result):,} / {len(skipped) + len(jobs):,}")
        return result

    t0 = time.time()
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WOLVENKIT_WORKERS) as ex:
        futures = {
            ex.submit(_serialize_one, cr2w, out): (cr2w, out, sk)
            for cr2w, out, sk in jobs
        }
        for fut in concurrent.futures.as_completed(futures):
            cr2w, out, sk = futures[fut]
            try:
                produced = fut.result()
            except Exception:
                produced = None
            if produced is not None:
                result[sk] = produced
            done += 1
            if done % 50 == 0 or done == len(jobs):
                log(f"    serialized {done:,}/{len(jobs):,} "
                    f"({(time.time() - t0):.0f}s elapsed)")
    log(f"  serialize ok: {len(result):,} (cache {len(skipped):,} + new {len(jobs):,})")
    return result


def _baked_entries_for(section_path: Path) -> list[dict]:
    try:
        with open(section_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def _index_by_pk(entries: list[dict]) -> dict[str, dict]:
    """Index a localization entry list by its lookup key.

    The same logical ID is named `primaryKey` in `localization_translated.json`
    (the source) and in baked ONSCREENS CR2W, but `stringId` in baked SUBTITLE
    CR2W (the `localizationPersistenceSubtitleEntry` type). Accept either —
    both fields hold the same 64-bit integer per entry.
    """
    out: dict[str, dict] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        pk = e.get("primaryKey")
        if pk is None:
            pk = e.get("stringId")
        if pk is None:
            continue
        out[str(pk)] = e
    return out


_DLC_SK_RE = re.compile(r"(?:^|[-_])(?:ep1|EP1|Ep1)(?:[-_]|$)")


def _is_dlc_entry(entry: dict) -> bool:
    """A source entry is DLC content (Phantom Liberty) when its secondaryKey
    carries an `ep1` / `EP1` segment. These entries leaked into the base-game
    source JSON; they belong in the (separate) DLC archive, not in the base
    z_hebrew_translation.archive.
    """
    sk = entry.get("secondaryKey", "") or ""
    return bool(_DLC_SK_RE.search(sk))


def _compare_baked_vs_source(
    layer_label: str,
    section_key: str,
    baked_entries: list[dict],
    source_entries: list[dict],
    export_idx: dict,
) -> list[Finding]:
    """For each entry that exists in BOTH source and baked, judge whether the
    baked value carries the correct Hebrew or whether something went wrong in
    the bake. Source-only or baked-only entries are reported separately.

    DLC content (ep1/EP1 secondaryKey markers) is excluded — those entries
    belong in the DLC archive (when one exists), not the base game archive,
    so their absence from the base bake is by design, not drift.
    """
    findings: list[Finding] = []
    baked_idx  = _index_by_pk(baked_entries)
    # Drop DLC entries from source before comparing.
    source_idx = {pk: e for pk, e in _index_by_pk(source_entries).items()
                  if not _is_dlc_entry(e)}

    common_pks = set(baked_idx.keys()) & set(source_idx.keys())
    only_baked = set(baked_idx.keys()) - set(source_idx.keys())

    for pk in common_pks:
        b = baked_idx[pk]
        s = source_idx[pk]
        eng = export_idx.get((section_key, pk), "") or s.get("secondaryKey", "") or ""

        for fld in ("femaleVariant", "maleVariant"):
            bv = (b.get(fld) or "")
            sv = (s.get(fld) or "")
            if not sv:
                # Source intentionally blank — bake should mirror it.
                continue

            # Source-side judgement: does the source carry Hebrew?
            src_has_he = has_hebrew(sv)
            bake_has_he = has_hebrew(bv)

            if src_has_he and not bake_has_he:
                # Source has Hebrew, baked output does not → bake-drift.
                if not bv.strip():
                    kind = "bake_blank"
                    detail = "source has Hebrew; baked output is BLANK"
                elif has_arabic(bv):
                    kind = "bake_arabic_skeleton"
                    detail = "source has Hebrew; baked output is the AR skeleton"
                else:
                    kind = "bake_english"
                    detail = "source has Hebrew; baked output is English / non-Hebrew"
                findings.append(Finding(
                    layer=layer_label, section=section_key, pk=pk, field=fld,
                    kind=kind, detail=detail, value=bv, english=eng,
                    extras={"source_value": sv},
                ))
                continue

            # Markup-drop in the bake: source carries kiroshi/mothertongue/Rich
            # but the baked entry lost the wrapper.
            if _qa.is_markup(sv) and bake_has_he and not _qa.is_markup(bv):
                findings.append(Finding(
                    layer=layer_label, section=section_key, pk=pk, field=fld,
                    kind="bake_markup_drop",
                    detail="source has markup wrapper; baked output is plain Hebrew",
                    value=bv, english=eng,
                    extras={"source_value": sv},
                ))

    # Source-only entries (a pk exists in the source JSON but not in the baked
    # CR2W) — these would render as the engine fallback (English). Important to
    # know about because they'd be invisible in source-only audits.
    only_source = set(source_idx.keys()) - set(baked_idx.keys())
    for pk in only_source:
        s = source_idx[pk]
        fv = s.get("femaleVariant", "") or ""
        if has_hebrew(fv):
            eng = export_idx.get((section_key, pk), "") or s.get("secondaryKey", "") or ""
            findings.append(Finding(
                layer=layer_label, section=section_key, pk=pk, field="femaleVariant",
                kind="bake_missing_entry",
                detail="source has translated entry but baked CR2W has no such pk",
                value=fv, english=eng,
            ))

    return findings


def layer2_baked_archive(
    archive_path: str,
    label: str,
    work_subdir: str,
    translated: dict,
    export_idx: dict,
) -> tuple[list[Finding], dict]:
    """Extract + serialize + diff the main translation archive. Returns
    (findings, stats). Only ar-ar/ files are considered — everything else in
    z_hebrew_translation.archive is incidental.
    """
    findings: list[Finding] = []
    stats = {
        "archive": archive_path,
        "exists": os.path.exists(archive_path),
        "sections_baked": 0,
        "sections_with_findings": 0,
        "common_pks": 0,
    }

    if not stats["exists"]:
        log(f"  [skip] archive missing: {archive_path}")
        return findings, stats

    work = Path(WORK_ROOT) / work_subdir
    raw  = work / "raw"
    jout = work / "json"

    if not _extract_archive(archive_path, raw):
        return findings, stats

    section_paths = _serialize_tree(raw, jout, locale_filter="ar-ar")
    stats["sections_baked"] = len(section_paths)

    sections_with = 0
    common_total  = 0
    for section_key, sp in sorted(section_paths.items()):
        baked = _baked_entries_for(sp)
        source = translated.get(section_key, [])
        if not source:
            findings.append(Finding(
                layer=label, section=section_key, pk="", field="",
                kind="baked_orphan_section",
                detail=f"baked CR2W has {len(baked):,} entries but the section "
                       "is absent from localization_translated.json",
                value="", english="",
            ))
            sections_with += 1
            continue
        sf = _compare_baked_vs_source(label, section_key, baked, source, export_idx)
        if sf:
            sections_with += 1
            findings.extend(sf)
        common_total += len(set(_index_by_pk(baked).keys())
                            & set(_index_by_pk(source).keys()))

    stats["sections_with_findings"] = sections_with
    stats["common_pks"] = common_total
    by_kind = Counter(f.kind for f in findings)
    log(f"  layer 2 ({label}): {len(findings):,} findings across "
        f"{sections_with:,}/{len(section_paths):,} sections ({dict(by_kind)})")
    return findings, stats


_MENU_LABEL_SK_SUFFIX = "UI-Settings-Language-Arabic"
_MENU_LABEL_PK        = "49601"
# The patch INTENTIONALLY writes the Latin word "Hebrew" — see the comment
# block in build_hebrew_menu_label_patch.py. We accept that exact label OR a
# Hebrew rendition ("עברית"), to future-proof against a relabel.
_VALID_MENU_LABELS    = {"hebrew", "עברית", "ivrit"}


def layer2_baked_static(
    archive_path: str,
    label: str,
    work_subdir: str,
) -> tuple[list[Finding], dict]:
    """Spot-check z_hebrew_static.archive. This archive hijacks the
    `Settings -> Language` Arabic-slot label across 18 locales by overriding
    pk=49601 (`UI-Settings-Language-Arabic`) in each locale's onscreens
    CR2W. The override is the *Latin word* "Hebrew" — chosen for universal
    discoverability across all UI languages — not Hebrew characters.

    So the verification is: each locale's onscreens.json AND
    onscreens_final.json must contain pk=49601 with femaleVariant set to one
    of the accepted labels. A "no Hebrew character anywhere" check would be
    a false positive (we'd flag any locale whose original translation lacks
    an unrelated CDPR easter-egg Hebrew string).
    """
    findings: list[Finding] = []
    stats = {
        "archive": archive_path,
        "exists": os.path.exists(archive_path),
        "sections_baked": 0,
        "sections_with_findings": 0,
        "common_pks": 0,
    }

    if not stats["exists"]:
        log(f"  [skip] archive missing: {archive_path}")
        return findings, stats

    work = Path(WORK_ROOT) / work_subdir
    raw  = work / "raw"
    jout = work / "json"

    if not _extract_archive(archive_path, raw):
        return findings, stats

    # All locales — the static archive intentionally writes to every locale's
    # onscreens tree to override the Hebrew label.
    section_paths = _serialize_tree(raw, jout, locale_filter=None)
    stats["sections_baked"] = len(section_paths)

    locales_seen: set[str] = set()
    for section_key, sp in sorted(section_paths.items()):
        baked = _baked_entries_for(sp)
        locale = section_key.split("/", 1)[0] if "/" in section_key else "?"
        locales_seen.add(locale)
        if not baked:
            findings.append(Finding(
                layer=label, section=section_key, pk="", field="",
                kind="static_no_entries",
                detail="baked CR2W has no entries (file produced 0-entry result)",
                value="", english="",
            ))
            continue
        # Find the menu-label override entry — by pk OR secondaryKey suffix.
        menu_entry = None
        for e in baked:
            pk_str = str(e.get("primaryKey") or e.get("stringId") or "")
            sk = e.get("secondaryKey", "") or ""
            if pk_str == _MENU_LABEL_PK or sk.endswith(_MENU_LABEL_SK_SUFFIX):
                menu_entry = e
                break
        if menu_entry is None:
            findings.append(Finding(
                layer=label, section=section_key, pk="", field="femaleVariant",
                kind="static_label_missing",
                detail=f"locale={locale}: pk=49601 / UI-Settings-Language-Arabic "
                       "not found in baked CR2W — the menu-label patch didn't apply",
                value="", english="",
                extras={"locale": locale},
            ))
            continue
        fv = (menu_entry.get("femaleVariant", "") or "").strip()
        if fv.lower() not in _VALID_MENU_LABELS:
            findings.append(Finding(
                layer=label, section=section_key, pk=str(menu_entry.get("primaryKey")),
                field="femaleVariant",
                kind="static_label_wrong",
                detail=f"locale={locale}: pk=49601 label is {fv!r}, expected "
                       f"one of {sorted(_VALID_MENU_LABELS)}",
                value=fv, english="",
                extras={"locale": locale},
            ))
            continue
        # Patch applied correctly — informational row only.
        findings.append(Finding(
            layer=label, section=section_key, pk=str(menu_entry.get("primaryKey")),
            field="femaleVariant",
            kind="static_ok",
            detail=f"locale={locale}; pk=49601 label = {fv!r}",
            value=fv, english="",
            extras={"locale": locale},
        ))

    # Only count "ok" entries toward common_pks (so the headline counter
    # reflects real-coverage, not the sanity rows)
    stats["sections_with_findings"] = sum(
        1 for f in findings if f.kind != "static_ok"
    )
    stats["common_pks"] = len(locales_seen)
    by_kind = Counter(f.kind for f in findings)
    log(f"  layer 2 ({label}): {len(findings):,} rows ({dict(by_kind)}); "
        f"locales covered: {len(locales_seen):,}")
    return findings, stats


# ── layer 3 — dropped wrappers ──────────────────────────────────────────────
def layer3_dropped_wrappers(translated: dict) -> list[Finding]:
    """Type-A drops: secondaryKey is markup, femaleVariant is plain Hebrew
    (Hebrew is intact, but the <kiroshi>/<mothertongue>/<Rich> wrapper that
    styles the foreign audio is gone). Not a defect by qa_defects but an
    information-class finding the user wants surfaced.
    """
    log("layer 3: scanning for dropped markup wrappers …")
    findings: list[Finding] = []
    for section, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            sk = entry.get("secondaryKey") or ""
            fv = entry.get("femaleVariant") or ""
            mv = entry.get("maleVariant") or ""
            pk = str(entry.get("primaryKey", ""))
            for fld, val in (("femaleVariant", fv), ("maleVariant", mv)):
                if (_qa.is_markup(sk) and val
                        and not _qa.is_markup(val)
                        and has_hebrew(val)):
                    findings.append(Finding(
                        layer="wrappers", section=section, pk=pk, field=fld,
                        kind="dropped_markup_wrapper",
                        detail="source secondaryKey is markup; value is plain Hebrew",
                        value=val, english=sk,
                    ))
    log(f"  layer 3 dropped wrappers: {len(findings):,}")
    return findings


# ── layer 4 — loose game-folder text ────────────────────────────────────────
_LATIN_WORD   = re.compile(r"[A-Za-z]{4,}")
_HEB_CHAR     = re.compile(r"[֐-׿]")
# A line of code looks like: starts with one of these, or is mostly composed
# of identifier syntax (=, (), {}, [], :, ;, $, --comment, //comment, etc.).
_CODE_STARTS = re.compile(
    r"^\s*(?:<\?xml|<!--|--\[\[|--|//|/\*|local\s|require\(|function\s|"
    r"import\s|from\s|#include|#define|using\s|namespace\s|class\s|"
    r"def\s|return\s|module\.exports|export\s|var\s|let\s|const\s)",
    re.IGNORECASE | re.MULTILINE,
)
# Quoted-string extractor — UI labels are usually in quotes.
_QUOTED_STRING = re.compile(r'"([^"\n]{8,})"|\'([^\'\n]{8,})\'')


def _extract_user_strings(raw: str) -> list[str]:
    """Pull strings that *might* be user-facing UI text out of code/config.

    A string qualifies when:
      * It is in quotes ("..." or '...') and at least 8 chars.
      * Has 2+ long Latin words.
      * Contains at least one lowercase common English word (so we hit prose
        like "Settings menu" but skip identifiers like "BindingsMenu").
      * Is not a path / URL / file-reference (no /, \\, .lua, .json, ., ../).
    """
    if not raw or _CODE_STARTS.search(raw[:200]):
        # First-line indication this is code → no user text.
        # (we still scan for quoted strings below, but only those.)
        pass
    out: list[str] = []
    for m in _QUOTED_STRING.finditer(raw):
        s = m.group(1) or m.group(2) or ""
        if not s or len(s) < 8:
            continue
        if _HEB_CHAR.search(s):
            continue
        # File-reference / path / URL
        if any(tok in s for tok in ("/", "\\", "..", "://", ".lua", ".json",
                                     ".xml", ".reds", ".tweak", ".ini")):
            continue
        # CamelCase / snake_case / kebab-case identifier?
        if " " not in s and ("_" in s or "-" in s or s[0].isupper()):
            continue
        words = _LATIN_WORD.findall(s)
        if len(words) < 2:
            continue
        # Need at least ONE lowercase common-English word (real prose).
        if not any(w.islower() and w.lower() in _qa.COMMON_EN_WORDS
                   for w in words):
            continue
        out.append(s)
    return out


def _looks_like_user_facing(text: str) -> bool:
    """True iff at least one quoted prose-string was extractable."""
    return bool(_extract_user_strings(text))


def _walk_loose_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        # prune heavy / pristine-EN / tools / engine directories
        dirnames[:] = [d for d in dirnames if d not in LOOSE_SKIP_DIRS]
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        rel_norm = "/" + rel + "/"
        if any(frag in rel_norm for frag in LOOSE_SKIP_PATH_FRAGMENTS):
            continue
        # Inside bin/x64/: skip everything except CET / RED4ext mod content
        if rel.startswith("bin/x64") and not LOOSE_BIN_X64_KEEP.search(rel + "/"):
            continue
        for fn in filenames:
            if fn in LOOSE_SKIP_BASENAMES:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext not in LOOSE_EXTS:
                continue
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) > LOOSE_MAX_KB * 1024:
                    continue
            except OSError:
                continue
            yield full


def layer4_loose_game_text(game_root: str) -> list[Finding]:
    """Walk the game install for small text files containing English prose
    strings that look like UI labels (not code identifiers or paths).
    """
    log("layer 4: scanning game folder for loose English text …")
    findings: list[Finding] = []
    scanned = 0
    for path in _walk_loose_files(game_root):
        scanned += 1
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except OSError:
            continue
        if not raw:
            continue
        strings = _extract_user_strings(raw)
        if not strings:
            continue
        rel = os.path.relpath(path, game_root).replace("\\", "/")
        # Show up to 3 sample strings so the user knows WHY this file was flagged.
        sample = " | ".join(strings[:3])
        findings.append(Finding(
            layer="loose", section=rel, pk="", field="",
            kind="loose_english_text",
            detail=f"{len(strings):,} candidate UI string(s) — first 3 shown",
            value=sample, english="",
            extras={"all_strings": strings[:20]},
        ))
    log(f"  layer 4 scanned: {scanned:,} files; flagged: {len(findings):,}")
    return findings


# ── layer 5 — categorize + report ───────────────────────────────────────────
# Category labels — see plan for definitions
CATEGORIES = {
    "A": "fixable_missing",
    "B": "fixable_english_leak",
    "C": "foreign_voiceset",
    "D": "code_or_acronym",
    "E": "dev_junk",
    "F": "dropped_markup_wrapper",
    "G": "bake_drift",
    "H": "foreign_script",
    "I": "loose_game_text",
    "J": "structural_markup",
    "K": "translated_but_not_in_base_bake",
    "L": "orphan_or_other",
}


_UNIT_TOKENS = (
    # technical / display
    "FPS|fps|Hz|hz|MHz|GHz|kHz|ms|sec|s|min|h|"
    "KB|MB|GB|TB|kb|mb|gb|tb|Kbps|Mbps|Gbps|"
    "ISO|HDR|HDR10|PQ|scRGB|RGB|sRGB|YUV|YCbCr|"
    # measurements / physical
    "mmHg|psi|bar|atm|kPa|MPa|Pa|"
    "km/h|mph|rpm|cm|mm|nm|μm|m|km|ft|mi|in|"
    "kg|g|oz|lb|t|"
    "°C|°F|°K|"
    "V|mV|kV|MV|A|mA|kA|W|mW|kW|MW|GW|J|kJ|MJ|Wh|kWh|MWh|"
    "AM|PM|EST|PST|CET|UTC"
)
_CODE_PATTERNS = [
    re.compile(r"^[A-Z0-9._-]{2,}$"),                       # NC484, HDR10, db_db
    re.compile(r"^Mk\.?\d+\b", re.IGNORECASE),               # Mk.31 HMG
    re.compile(rf"^\d+(?:[.,/]\d+)*\s*(?:{_UNIT_TOKENS})\b"),  # 100 FPS, 52/102 mmHg
    re.compile(rf"^[A-Za-z]+\s*\d+\s*(?:{_UNIT_TOKENS})?\b"),  # ISO 100, HDR10 PQ, F 5.6
    re.compile(r"^v?\d+\.\d+(?:\.\d+)?$"),                   # version numbers
    re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?$"),  # 12:00 AM, 23:59:59
    re.compile(r"^[A-Z]{2,}\s+\d+(?:\s+[A-Z]+)?$"),          # MLT 503, BFC 9000
    re.compile(r"^[A-Z]{2,}\d+(?:\s+[A-Za-z0-9]+)*$"),       # HDR10 PQ, HDR10 scRGB
    re.compile(r"^HD?[\\\\n\s\.]+", re.IGNORECASE),          # HD\nF 5.6\nISO 100 — camera HUD
]

_DEV_JUNK_RE = re.compile(
    r"\b(?:TO BE DELETED|PLACEHOLDER|DO NOT TRANSLATE|DON'?T TRANSLATE|"
    r"DEPRECATED|DEBUG|debug|chickentest|chicken[_-]?test|IGNORE|"
    r"test[_-]?(?:data|string|123)|"
    r"DEV|TEMP|TBD|DUMMY|XXX|"
    r"placeholder|template_id)\b"
)
# Strings that LOOK like dev gibberish: a short token built mostly from random
# letter+digit mash, OR a string that's almost entirely emoticons/punctuation.
_DEV_GIBBERISH_RE = re.compile(
    r"^[a-zA-Z]*\d[a-zA-Z0-9]*\s+[a-zA-Z]*\d[a-zA-Z0-9]*$"   # 5as4 2asd1 / 1qaz 2wsx
)
_EMOTICON_RE = re.compile(r"^[a-zA-Z]{0,6}[\s]*[;:][\)\(D\|]")  # xoxo ;) / hi :D
# CDPR internal-DB tag prefix: `[db_db]wns_news_07`, `[pl_pl]xx`, etc. These
# never reach the player — they're broken cross-refs in the localization data
# itself. Sometimes the brackets only — `[db_db][...........]`.
_DB_TAG_RE = re.compile(r"^\[\w{2,5}_\w{2,5}\]")
# A snake_case database identifier with no whitespace and no upper-case run —
# these are CDPR's internal string keys, not text intended for the player
# (e.g. "wns_sq_021_03_quest_hook_b", "your_business_04"). Conservative: at
# least one underscore, no spaces, mostly lowercase letters + digits.
_DB_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*_[a-z0-9_]+$")


def _is_code_or_acronym(english: str, value: str) -> bool:
    text = (english or value or "").strip()
    if not text:
        return False
    if any(p.match(text) for p in _CODE_PATTERNS):
        return True
    # All-caps acronym >= 2 chars, optionally with digits / hyphens
    if re.fullmatch(r"[A-Z][A-Z0-9._-]{1,}", text):
        return True
    # Bracketed dev tag: [db_db], [pl_pl]
    if re.fullmatch(r"\[[A-Za-z0-9_]+\]", text):
        return True
    # Short token without spaces and no Hebrew
    if " " not in text and len(text) <= 16 and not _HEB_CHAR.search(text):
        return True
    # Camera-HUD style strings (multi-line HD/F-stop/ISO blocks)
    if text.startswith("HD") and "\\n" in text and ("ISO" in text or "F " in text):
        return True
    return False


def _is_dev_junk(english: str, value: str) -> bool:
    text = (english or value or "").strip()
    if not text:
        return False
    if _DEV_JUNK_RE.search(text):
        return True
    if _DEV_GIBBERISH_RE.match(text):
        return True
    if _EMOTICON_RE.match(text):
        return True
    if _DB_TAG_RE.match(text):
        return True
    if _DB_IDENTIFIER_RE.match(text):
        return True
    return False


def _is_foreign_voiceset(english: str) -> bool:
    if not english:
        return False
    return ('<kiroshi' in english or '<mothertongue' in english)


def categorize(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Bucket every finding into one of the 11 categories."""
    buckets: dict[str, list[Finding]] = {k: [] for k in CATEGORIES}

    for f in findings:
        kind = f.kind
        eng  = f.english or ""
        val  = f.value or ""

        # Layer 4 — always "I"
        if f.layer == "loose":
            buckets["I"].append(f)
            continue

        # Wrappers — always "F"
        if kind == "dropped_markup_wrapper":
            buckets["F"].append(f)
            continue

        # Static-archive sanity rows: these aren't defects — silently swallow
        # the OK ones, route NO-HEBREW / NO-ENTRIES to "G" (bake drift).
        if kind == "static_ok":
            continue
        if kind in ("static_no_hebrew", "static_no_entries",
                     "static_label_missing", "static_label_wrong"):
            buckets["G"].append(f)
            continue

        # "Source has translated entry but baked CR2W lacks the pk" is not
        # in-game English — those entries simply aren't shipped by the base
        # mod (because the Arabic skeleton has no slot for them; they belong
        # in the DLC archive). Route to K, not G.
        if kind == "bake_missing_entry":
            buckets["K"].append(f)
            continue

        # Real bake drift (same pk on both sides, baked has wrong text).
        if kind in ("bake_blank", "bake_arabic_skeleton", "bake_english",
                    "bake_markup_drop", "baked_orphan_section"):
            buckets["G"].append(f)
            continue

        # Source defects (Layer 1):
        if kind == "foreign":
            buckets["H"].append(f)
            continue
        if kind == "structural":
            buckets["J"].append(f)
            continue
        if kind == "english_leak":
            buckets["B"].append(f)
            continue
        if kind == "missing":
            # Decide between A, C, D, E
            if _is_dev_junk(eng, val):
                buckets["E"].append(f)
            elif _is_foreign_voiceset(eng):
                buckets["C"].append(f)
            elif _is_code_or_acronym(eng, val):
                buckets["D"].append(f)
            else:
                buckets["A"].append(f)
            continue

        # Unknown kind
        buckets["L"].append(f)

    return buckets


# ── report emission ─────────────────────────────────────────────────────────
def _truncate(s: str, n: int = 240) -> str:
    if not s:
        return ""
    s = s.replace("\n", "\\n").replace("\r", "")
    return s if len(s) <= n else (s[: n - 1] + "…")


def emit_report(buckets: dict[str, list[Finding]],
                stats: dict,
                run_meta: dict) -> None:
    """Write the human-readable .txt and the machine-readable .json side-by-side."""
    cat_titles = {
        "A": "A. fixable_missing                  — אנגלית 'אמיתית' שעדיין יש לתרגם",
        "B": "B. fixable_english_leak             — פרגמנט אנגלי בתוך משפט עברי",
        "C": "C. foreign_voiceset                 — <kiroshi/mothertongue l=...> אודיו זר בכוונה",
        "D": "D. code_or_acronym                  — HDR10 / ISO 100 / NC484 / Mk.31 — לא לתרגום",
        "E": "E. dev_junk                         — chickentest / IGNORE / [db_db] — שאריות פיתוח CDPR",
        "F": "F. dropped_markup_wrapper           — type-A: עברית תקינה, ה-wrapper נפל",
        "G": "G. bake_drift                       — חוסר התאמה בין המקור לארכיב המבושל",
        "H": "H. foreign_script                   — קרסה / יוונית / CJK בעברית",
        "I": "I. loose_game_text                  — טקסט אנגלי בקובץ קונפיג/מוד בתיקיית המשחק",
        "J": "J. structural_markup                — markup damaged (parse_slots rejected)",
        "K": "K. translated_but_not_in_base_bake  — תורגם אבל לא נכלל בארכיב הבסיס (DLC overflow)",
        "L": "L. orphan_or_other                  — לא מיופה לקטגוריה",
    }

    # Build the .txt
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("CYBERPUNK 2077 — Deep English-Tail Audit (Base game only)")
    add("=" * 78)
    add(f"Generated:       {run_meta['generated_at']}")
    add(f"Run time:        {run_meta['elapsed_sec']:.1f} s")
    add(f"Source JSON:     {run_meta['translated_path']}")
    add(f"Source size:     {run_meta['translated_size']:,} bytes "
        f"(mtime: {run_meta['translated_mtime']})")
    add(f"Mod main:        {MOD_MAIN}")
    add(f"Mod static:      {MOD_STATIC}")
    add("")

    add("─── totals per category ───")
    total_findings = sum(len(v) for v in buckets.values())
    for code in "ABCDEFGHIJKL":
        add(f"  {cat_titles[code]:<70} {len(buckets[code]):>6,}")
    add(f"  {'TOTAL':<70} {total_findings:>6,}")
    add("")

    add("─── bake stats (Layer 2) ───")
    for label, st in stats.items():
        add(f"  archive: {label}")
        add(f"    path:           {st.get('archive', '')}")
        add(f"    exists:         {st.get('exists')}")
        add(f"    sections baked: {st.get('sections_baked', 0):,}")
        add(f"    sections w/ findings: {st.get('sections_with_findings', 0):,}")
        add(f"    common pks vs source: {st.get('common_pks', 0):,}")
        add("")

    for code in "ABCDEFGHIJKL":
        bucket = buckets[code]
        add("=" * 78)
        add(cat_titles[code])
        add(f"count: {len(bucket):,}")
        add("=" * 78)
        if not bucket:
            add("  (none)")
            add("")
            continue

        # Section-level histogram
        by_section = Counter(f.section for f in bucket)
        add("Top sections:")
        for sec, n in by_section.most_common(10):
            add(f"  {n:>5,}  {sec}")
        add("")
        # Up to 50 samples (or all, if fewer)
        cap = 50
        for f in bucket[:cap]:
            tag = f.kind if f.layer != "source" else f"src/{f.kind}"
            add(f"- [{f.layer}/{tag}] {f.section} pk={f.pk} field={f.field}")
            if f.english:
                add(f"    EN: {_truncate(f.english)}")
            if f.value:
                add(f"    VL: {_truncate(f.value)}")
            if f.detail:
                add(f"    >>  {f.detail}")
        if len(bucket) > cap:
            add(f"  … and {len(bucket) - cap:,} more not shown")
        add("")

    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"wrote {REPORT_TXT}  ({os.path.getsize(REPORT_TXT):,} bytes)")

    # JSON sidecar — every finding, in full
    payload = {
        "meta": run_meta,
        "categories": {code: cat_titles[code] for code in "ABCDEFGHIJKL"},
        "counts":     {code: len(buckets[code]) for code in "ABCDEFGHIJKL"},
        "bake_stats": stats,
        "findings":   {code: [asdict(f) for f in buckets[code]]
                       for code in "ABCDEFGHIJKL"},
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"wrote {REPORT_JSON}  ({os.path.getsize(REPORT_JSON):,} bytes)")


# ── main ────────────────────────────────────────────────────────────────────
def _check_deploy_lock() -> None:
    """If z_hebrew_translation.archive is locked (game running), abort. We open
    archives read-only but the user gets surprising errors if the game is up.
    """
    for path in (MOD_MAIN, MOD_STATIC):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb"):
                pass
        except PermissionError:
            log(f"FATAL: {path} is locked. Close Cyberpunk 2077 and retry.")
            sys.exit(1)


def main() -> int:
    log("=" * 78)
    log("cp2077_deep_english_audit starting")
    log("=" * 78)
    t0 = time.time()

    _check_deploy_lock()

    log(f"loading source translations: {TRANSLATED_JSON}")
    with open(TRANSLATED_JSON, "r", encoding="utf-8") as f:
        translated = json.load(f)
    log(f"  sections: {len(translated):,}")

    log(f"loading English export: {EXPORT_JSON}")
    with open(EXPORT_JSON, "r", encoding="utf-8") as f:
        export = json.load(f)
    log(f"  export sections: {len(export):,}")

    export_idx = _qa.build_export_index(export)

    # ── layers
    f1 = layer1_source_audit(translated, export)

    if "--skip-bake" in sys.argv:
        log("--skip-bake: skipping layer 2 (archive verification)")
        f2_main, st_main = [], {"archive": MOD_MAIN, "exists": True,
                                "sections_baked": 0, "sections_with_findings": 0,
                                "common_pks": 0}
        f2_static, st_static = [], {"archive": MOD_STATIC, "exists": True,
                                    "sections_baked": 0, "sections_with_findings": 0,
                                    "common_pks": 0}
    else:
        log("layer 2: extracting + verifying z_hebrew_translation.archive …")
        f2_main, st_main = layer2_baked_archive(
            MOD_MAIN, "baked_main", "translation", translated, export_idx,
        )
        log("layer 2: extracting + verifying z_hebrew_static.archive …")
        f2_static, st_static = layer2_baked_static(
            MOD_STATIC, "baked_static", "static",
        )

    f3 = layer3_dropped_wrappers(translated)
    f4 = layer4_loose_game_text(GAME_DIR)

    all_findings = f1 + f2_main + f2_static + f3 + f4
    log(f"total raw findings: {len(all_findings):,}")

    buckets = categorize(all_findings)

    elapsed = time.time() - t0
    run_meta = {
        "generated_at":      time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec":       elapsed,
        "translated_path":   TRANSLATED_JSON,
        "translated_size":   os.path.getsize(TRANSLATED_JSON),
        "translated_mtime":  time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(os.path.getmtime(TRANSLATED_JSON)),
        ),
    }
    stats = {"main": st_main, "static": st_static}

    emit_report(buckets, stats, run_meta)

    log("=" * 78)
    log(f"DONE in {elapsed:.1f} s. See {REPORT_TXT}")
    log("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
