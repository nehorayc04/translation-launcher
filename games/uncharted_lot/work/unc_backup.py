#!/usr/bin/env python3
r"""
unc_backup.py — update-aware backup/restore for the UNCHARTED probe deploys.

WHY THIS EXISTS (a real incident, 2026-07-24): a probe was deployed, then the USER
UPDATED THE GAME.  The updater overwrote every patched archive with a newer vendor
build — so the patches were gone (fine) but the `.he_backup` files were now copies of
the *previous game version*.  A later `--revert` would have cheerfully restored 2022
archives over a 2023 install, desyncing them from the sibling archives the update DID
replace (`dc1.psarc`), and the only symptom would have shown up inside the game.

`shutil.copy2(backup, live)` cannot tell "restore my patch" from "downgrade the game".
So record what we saved AND what we wrote, and let restore() decide:

    live == deployed  -> our patch is in place        -> restore
    live == original  -> already reverted             -> drop the backup, no write
    otherwise         -> the game changed underneath  -> REFUSE (stale backup)

The sidecar is `<file>.he_backup.json`.  md5 is plenty here — this guards against an
installer, never against an adversary — and it is only computed on deploy/revert, not
per read.

    from unc_backup import backup, deploy_done, restore, status
"""
import os
import json
import time
import shutil
import hashlib

SUFFIX = ".he_backup"
META = ".he_backup.json"


def md5(path, chunk=1 << 22):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _meta_path(path):
    return path + META


def _load(path):
    try:
        with open(_meta_path(path), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def backup(path, quiet=False):
    """Save the pristine file once. Returns the backup path.

    Refuses to overwrite an existing backup — on a re-deploy the live file is OUR
    patch, and re-copying it would destroy the only pristine copy we have.
    """
    b = path + SUFFIX
    if os.path.exists(b):
        return b
    shutil.copy2(path, b)
    with open(_meta_path(path), "w", encoding="utf-8") as f:
        json.dump({"original_md5": md5(b), "original_size": os.path.getsize(b),
                   "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=1)
    if not quiet:
        print(f"  backup -> {os.path.basename(b)}")
    return b


def deploy_done(path):
    """Record the md5 we just wrote, so restore() can recognise our own output."""
    m = _load(path)
    m["deployed_md5"] = md5(path)
    m["deployed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_meta_path(path), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)


def status(path):
    """-> 'clean' | 'deployed' | 'reverted' | 'changed' | 'unknown'."""
    b = path + SUFFIX
    if not os.path.exists(b):
        return "clean"
    m = _load(path)
    if not os.path.exists(path):
        return "unknown"
    live = md5(path)
    if live == m.get("deployed_md5"):
        return "deployed"
    if live == m.get("original_md5") or live == md5(b):
        return "reverted"
    return "changed"


def restore(path, force=False):
    """Restore only when the live file is still what we deployed.

    Returns (action, note). `force=True` drops a stale backup without writing —
    the right move after a game update, since the vendor's new file is correct and
    ours is simply obsolete.
    """
    b = path + SUFFIX
    if not os.path.exists(b):
        return "none", "no backup"
    st = status(path)
    if st == "changed":
        if not force:
            return "refused", ("the live file is NEITHER our patch NOR the backup — the game "
                               "was updated/verified underneath. This backup is STALE; "
                               "restoring it would DOWNGRADE the game. Re-run with force=True "
                               "to just delete it.")
        os.remove(b)
        if os.path.exists(_meta_path(path)):
            os.remove(_meta_path(path))
        return "dropped", "stale backup deleted, live file left untouched (it is the newer one)"
    if st == "reverted":
        os.remove(b)
        if os.path.exists(_meta_path(path)):
            os.remove(_meta_path(path))
        return "already", "already vanilla; backup removed"
    shutil.copy2(b, path)
    os.remove(b)
    if os.path.exists(_meta_path(path)):
        os.remove(_meta_path(path))
    return "restored", ""


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(f"{status(p):9s} {p}")
