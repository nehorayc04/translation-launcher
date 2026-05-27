"""End-to-end test of the Steam mod local lifecycle (steam_mod.py).

Sequence: install (populate_cache + enable) -> verify -> disable ->
re-enable -> clear_cache. Asserts the `.orig` backup scheme and state
transitions at every step. Self-restoring — clear_cache leaves the
Steam install exactly as it was found.

PRECONDITION: Steam must be closed.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from translation_manager import steam_apply, steam_mod

_pass = 0
_fail = 0


def check(label: str, cond: bool) -> bool:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"  [PASS] {label}")
    else:
        _fail += 1
        print(f"  [FAIL] {label}")
    return cond


def sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


steam = steam_apply.find_steam_install()
if steam is None:
    print("FATAL: Steam install not found")
    sys.exit(1)
print(f"Steam install: {steam}\n")

# ── 0. clean slate ───────────────────────────────────────────
print("[0] clean slate")
if steam_mod.is_cached():
    print("  (prior cache found — clearing first)")
    steam_mod.clear_cache()
check("is_cached() is False", not steam_mod.is_cached())

# ── 1. populate cache, then capture the Steam baseline ───────
print("[1] populate cache + baseline")
src = steam_apply._source_dir()
r = steam_mod.populate_cache(src, version="test")
check(f"populate_cache ok (count={r.get('count')})", bool(r.get("ok")))

managed = steam_mod._cache_files()                       # [(rel, cache_path)]
check(f"cache holds 8 files (got {len(managed)})", len(managed) == 8)

# Baseline: per managed file, Steam's state BEFORE we touch anything.
baseline: dict[str, str | None] = {}
for rel, _ in managed:
    baseline[rel] = sha(steam / rel)
had_original = [rel for rel, h in baseline.items() if h is not None]
ours_only    = [rel for rel, h in baseline.items() if h is None]
print(f"  Steam already ships: {len(had_original)} of 8  (the rest are ours: {ours_only})")

# ── 2. enable ────────────────────────────────────────────────
print("[2] enable (install)")
r = steam_mod.enable()
check(f"enable ok (count={r.get('count')})", bool(r.get("ok")))
st = steam_mod.read_state()
check("state.enabled is True", st.get("enabled") is True)
installed = st.get("installed_files", [])
check(f"installed_files recorded ({len(installed)})", len(installed) == len(managed))

ok_orig = ok_live = ok_noorig = True
for rel, cache_path in managed:
    live = steam / rel
    orig = live.with_name(live.name + ".orig")
    if baseline[rel] is not None:                        # Steam shipped this file
        if sha(orig) != baseline[rel]:
            ok_orig = False
    else:                                                # purely ours
        if orig.exists():
            ok_noorig = False
    if sha(live) != sha(cache_path):                     # live must equal the cache copy
        ok_live = False
check(".orig captures the genuine original for every shipped file", ok_orig)
check("no .orig for files that were purely ours", ok_noorig)
check("every live file now equals the cached Hebrew copy", ok_live)

# ── 3. disable ───────────────────────────────────────────────
print("[3] disable")
r = steam_mod.disable()
check(f"disable ok (count={r.get('count')})", bool(r.get("ok")))
check("state.enabled is False", steam_mod.read_state().get("enabled") is False)
ok_restore = True
for rel in had_original:
    if sha(steam / rel) != baseline[rel]:
        ok_restore = False
ok_removed = all(not (steam / rel).exists() for rel in ours_only)
check("every shipped file restored to its original", ok_restore)
check("every purely-ours file deleted", ok_removed)
check("cache still intact", steam_mod.is_cached())

# ── 4. re-enable (idempotency) ───────────────────────────────
print("[4] re-enable")
r = steam_mod.enable()
check(f"re-enable ok (count={r.get('count')})", bool(r.get("ok")))
ok_reorig = True
for rel in had_original:
    orig = (steam / rel).with_name((steam / rel).name + ".orig")
    if sha(orig) != baseline[rel]:                       # .orig must NOT be re-captured
        ok_reorig = False
check(".orig still holds the genuine original (not re-captured from Hebrew)", ok_reorig)

# ── 5. clear cache ───────────────────────────────────────────
print("[5] clear cache")
r = steam_mod.clear_cache()
check("clear_cache ok", bool(r.get("ok")))
check("is_cached() is False", not steam_mod.is_cached())
check("CACHE_DIR removed", not steam_mod.CACHE_DIR.exists())
ok_final = True
for rel in had_original:
    if sha(steam / rel) != baseline[rel]:
        ok_final = False
ok_finalrm  = all(not (steam / rel).exists() for rel in ours_only)
ok_noorigs  = all(
    not (steam / rel).with_name((steam / rel).name + ".orig").exists()
    for rel, _ in managed
)
check("every shipped file back to its original", ok_final)
check("every purely-ours file gone", ok_finalrm)
check("all .orig backups removed — Steam left pristine", ok_noorigs)

print()
print(f"=== {_pass} passed, {_fail} failed ===")
sys.exit(0 if _fail == 0 else 1)
