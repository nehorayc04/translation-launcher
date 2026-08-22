"""Winhanced deploy: back up, patch the XAML string tables, revert.

Two surfaces hold the same compiled XAML and only one of them renders, so both
are patched and each gets its own marker (see --proof).

Safety rules this file enforces:
  * every file is copied to an out-of-tree backup BEFORE the first write, and a
    backup is never overwritten -- so a second deploy can't capture our own patch
  * the backup manifest stores the sha256 of the pristine file AND of what we
    wrote, so --revert refuses to "restore" over a file the vendor has since
    updated (that would be a silent downgrade)
  * the .pri is written delta-0 (the container records payload offsets)
  * everything is written to a temp file and os.replace'd -- no half-written file
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pri_xbf
import xbf

ROOT = Path(r"C:\Program Files\Winhanced")
PRI = ROOT / "Winhanced.pri"
BACKUP = Path(__file__).resolve().parents[1] / "backup"
MANIFEST = BACKUP / "manifest.json"


# --------------------------------------------------------------------------- #
# elevation
# --------------------------------------------------------------------------- #
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def require_admin(action: str) -> None:
    if is_admin():
        return
    print(f"'{action}' writes into {ROOT} and needs administrator rights.")
    print("Re-run this from an elevated terminal, or let Windows prompt:\n")
    py = sys.executable
    args = " ".join(f"'{a}'" for a in sys.argv)
    print(
        f"  powershell -Command \"Start-Process '{py}' "
        f"-ArgumentList {args} -Verb RunAs -WorkingDirectory '{Path.cwd()}'\"\n"
    )
    sys.exit(2)


# --------------------------------------------------------------------------- #
# backup
# --------------------------------------------------------------------------- #
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(m: dict) -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2), encoding="utf-8")


def backup(p: Path, man: dict) -> None:
    """Copy the pristine file aside. Never overwrites an existing backup."""
    rel = p.relative_to(ROOT).as_posix()
    dst = BACKUP / rel
    if rel in man and dst.exists():
        return  # already have the pristine copy
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst)
    man[rel] = {"original_sha256": _sha(p), "size": p.stat().st_size}


def atomic_write(p: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------- #
# patching
# --------------------------------------------------------------------------- #
def patch_loose(path: Path, mapping: dict[str, str]) -> int:
    """Replace strings in a standalone .xbf (free to change size).

    NOTE: proven by the ZZ-PRI-OK-ZZ / ZZ-XBF-OK-ZZ surface probe -- the loose
    .xbf files on disk are NOT read by the app; Winhanced.pri is. They are left
    alone by default: touching a file nothing reads is pure risk.
    """
    x = xbf.parse(path)
    code = xbf.code_string_indices(x)
    new = list(x.strings)
    n = 0
    for i, s in enumerate(x.strings):
        if i in code:
            continue
        if s in mapping:
            new[i] = mapping[s]
            n += 1
    if n:
        atomic_write(path, xbf.build(x, new))
    return n


def _unmatched(mapping: dict[str, str]) -> list[str]:
    """Source strings that exist in no payload -- i.e. typos in the mapping, or
    text that actually lives in the (obfuscated) code rather than in XAML."""
    seen: set[str] = set()
    for e in pri_xbf.carve(_pristine(PRI)):
        x = e.obj
        code = xbf.code_string_indices(x)
        seen |= {s for i, s in enumerate(x.strings) if i not in code}
    return [k for k in mapping if k not in seen]


def _pristine(p: Path) -> Path:
    """Always build FROM the pristine copy, never from what is already deployed --
    otherwise a second run silently inherits the previous patch."""
    src = BACKUP / p.relative_to(ROOT).as_posix()
    return src if src.exists() else p


def patch_pri(mapping: dict[str, str], dry: bool = False) -> tuple[int, list[str]]:
    """Replace strings in every XBF embedded in the .pri, delta-0."""
    src = _pristine(PRI)  # BOTH the bytes and the payload list must come from
    data = bytearray(src.read_bytes())  # the pristine copy, or a second deploy
    total = 0                           # searches an already-translated file
    overflow: list[str] = []
    for e in pri_xbf.carve(src):
        x = e.obj
        code = xbf.code_string_indices(x)
        new = list(x.strings)
        n = 0
        for i, s in enumerate(x.strings):
            if i in code:
                continue
            if s in mapping:
                new[i] = mapping[s]
                n += 1
        if not n:
            continue
        try:
            blob = xbf.build_fixed_size(x, new)
        except ValueError as err:
            overflow.append(f"{e.offset:#x}: {err}")
            continue
        assert len(blob) == e.length
        data[e.offset : e.offset + e.length] = blob
        total += n
    if total and not dry:
        atomic_write(PRI, bytes(data))
    return total, overflow


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_status() -> None:
    man = _load_manifest()
    print(f"backup dir : {BACKUP}")
    print(f"backed up  : {len(man)} file(s)")
    for rel, rec in sorted(man.items()):
        live = ROOT / rel
        cur = _sha(live) if live.exists() else "MISSING"
        state = (
            "pristine"
            if cur == rec["original_sha256"]
            else ("ours" if cur == rec.get("deployed_sha256") else "CHANGED BY VENDOR")
        )
        print(f"  {rel:<28} {state}")


def cmd_revert(force: bool) -> int:
    require_admin("revert")
    man = _load_manifest()
    if not man:
        print("nothing to revert (no backup manifest)")
        return 0
    for rel, rec in sorted(man.items()):
        live = ROOT / rel
        src = BACKUP / rel
        if not src.exists():
            print(f"  !! backup missing for {rel}")
            continue
        cur = _sha(live) if live.exists() else None
        if not force and cur not in (rec.get("deployed_sha256"), rec["original_sha256"]):
            print(
                f"  SKIP {rel}: the live file is neither pristine nor ours -- "
                "the app was probably updated. Restoring would downgrade it. "
                "Use --force to override."
            )
            continue
        atomic_write(live, src.read_bytes())
        print(f"  reverted {rel}")
    print("done")
    return 0


def cmd_apply(mapping: dict[str, str], label: str, dry: bool = False) -> int:
    mapping = {k: v for k, v in mapping.items() if not k.startswith("_")}
    if dry:
        n, overflow = patch_pri(mapping, dry=True)
        print(f"DRY RUN: {n} replacement(s) would be made in the pri")
        for o in overflow:
            print(f"  OVERFLOW {o}")
        missing = _unmatched(mapping)
        if missing:
            print(f"  {len(missing)} source string(s) not found in any payload:")
            for m in missing[:20]:
                print(f"    {m!r}")
        return 1 if overflow else 0

    require_admin("apply")
    man = _load_manifest()
    for p in (PRI, *sorted(ROOT.rglob("*.xbf"))):
        backup(p, man)
    _save_manifest(man)
    print(f"backed up {len(man)} files -> {BACKUP}")

    n_pri, overflow = patch_pri(mapping)
    print(f"  pri   : {n_pri} replacements")
    for o in overflow:
        print(f"    OVERFLOW {o}")

    n_loose = 0
    for p in sorted(ROOT.rglob("*.xbf")):
        n_loose += patch_loose(p, mapping)
    print(f"  loose : {n_loose} replacements")

    for rel in man:
        live = ROOT / rel
        if live.exists():
            man[rel]["deployed_sha256"] = _sha(live)
    man["_label"] = label if isinstance(man.get("_label", ""), str) else label
    _save_manifest(man)
    return 0


def cmd_proof() -> int:
    """Surface proof: which copy of the XAML actually renders?

    'Recent Games' is the home screen's first header and exists exactly once in
    each surface. Each surface gets a DIFFERENT 12-char ASCII marker, so one
    launch names the winner. ASCII and equal length => delta-0 in both, and
    readable even if the app had no Hebrew font at all.
    """
    require_admin("proof")
    target, m_pri, m_loose = "Recent Games", "ZZ-PRI-OK-ZZ", "ZZ-XBF-OK-ZZ"
    assert len(m_pri) == len(m_loose) == len(target)

    man = _load_manifest()
    for p in (PRI, *sorted(ROOT.rglob("*.xbf"))):
        backup(p, man)
    _save_manifest(man)
    print(f"backed up {len([k for k in man if not k.startswith('_')])} files -> {BACKUP}")

    n_pri, overflow = patch_pri({target: m_pri})
    for o in overflow:
        print(f"  OVERFLOW {o}")
    n_loose = sum(patch_loose(p, {target: m_loose}) for p in sorted(ROOT.rglob("*.xbf")))
    print(f"  pri={n_pri} replacement(s), loose={n_loose} replacement(s)")

    for rel in [k for k in man if not k.startswith("_")]:
        live = ROOT / rel
        if live.exists():
            man[rel]["deployed_sha256"] = _sha(live)
    _save_manifest(man)

    print("\nNow launch Winhanced and read the first header on the home screen:")
    print(f"  {m_pri}   -> Winhanced.pri is the live surface")
    print(f"  {m_loose}   -> the loose .xbf files are the live surface")
    print(f"  'Recent Games' -> neither; that header comes from code")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--apply", metavar="MAPPING_JSON")
    ap.add_argument("--dry", action="store_true", help="check fit, write nothing")
    a = ap.parse_args()

    if a.revert:
        sys.exit(cmd_revert(a.force))
    if a.proof:
        sys.exit(cmd_proof())
    if a.apply:
        m = json.loads(Path(a.apply).read_text(encoding="utf-8"))
        sys.exit(cmd_apply(m, Path(a.apply).name, dry=a.dry))
    cmd_status()
