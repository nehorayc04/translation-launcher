"""Unified mod-version publisher — the website-sync + checks + preview layer.

This is the "single source" propagation step: given a mod + version + stage it
computes the canonical version (auto beta counter), runs pre-publish checks,
and writes BOTH the website's games row AND the mod_version_history timeline —
respecting per-field override LOCKS. The mod-specific archive build + GitHub
release + Worker manifest are produced by the per-mod pack script
(pack_cp2077_mod.py / the SM2 packer); this script syncs the website to match.

Operator flow (Claude runs this when the user says "publish"):
    1. DRY-RUN (default) → prints a preview to confirm.
    2. --apply           → commits to the DB after confirmation.

Usage:
    python publish_version.py <game_id> <base_version> [--stage alpha|beta|rc|stable]
        [--changelog TEXT] [--sha SHA256] [--size BYTES] [--archive-url URL] [--apply]

Examples:
    publish_version.py cyberpunk 1.1.0 --stage beta            # preview 1.1.0-beta.N
    publish_version.py cyberpunk 1.0.3 --changelog "תיקוני RTL" --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

# Windows consoles default to cp1255/cp1252 → Hebrew + "→" crash on print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import versioning as V  # noqa: E402

WEBSITE = HERE.parent / "website"


# ── DB ───────────────────────────────────────────────────────────────────
def _db_url() -> str:
    for line in (WEBSITE / ".env").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("SUPABASE_DB_URL="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("SUPABASE_DB_URL not found in website/.env")


def _connect():
    import psycopg2
    p = urlparse(_db_url())
    return psycopg2.connect(
        host=p.hostname, port=p.port or 5432, dbname=(p.path or "/postgres").lstrip("/") or "postgres",
        user=unquote(p.username or ""), password=unquote(p.password or ""),
        sslmode="require", connect_timeout=30,
    )


# ── plan ─────────────────────────────────────────────────────────────────
def build_plan(cur, game_id: str, base: str, stage: str, changelog: str | None,
               sha: str | None, size: int | None, archive_url: str | None) -> dict:
    cur.execute(
        "select title_en, version, release_stage, changelog, coalesce(locked_fields,'{}'::jsonb) "
        "from games where id=%s", (game_id,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"game '{game_id}' not found in games table")
    title, cur_version, cur_stage, cur_changelog, locks = row
    locks = locks or {}

    cur.execute("select version from mod_version_history where game_id=%s", (game_id,))
    existing = [r[0] for r in cur.fetchall()]

    # If the caller already passed a staged version, respect it; else compose.
    if "-" in base:
        new_version = base.lstrip("vV")
        stage = V.stage_of(new_version)
    elif stage == "stable":
        new_version = V.compose(base, "stable")
    else:
        counter = V.next_counter(existing, base, stage)
        new_version = V.compose(base, stage, counter)

    checks = []
    # monotonic
    newer = V.is_newer(new_version, cur_version)
    checks.append(("version newer than current", newer,
                   f"{V.fmt(new_version)} {'>' if newer else '≤'} {V.fmt(cur_version)}"))
    # not a duplicate history entry
    dup = new_version.lstrip("vV") in [e.lstrip("vV") for e in existing]
    checks.append(("version not already published", not dup,
                   "duplicate in history" if dup else "new"))
    # sha format
    if sha is not None:
        ok = len(sha) == 64 and all(c in "0123456789abcdefABCDEF" for c in sha)
        checks.append(("sha256 well-formed", ok, sha[:16] + "…"))
    # archive link
    if archive_url:
        ok, detail = _link_ok(archive_url)
        checks.append(("download link reachable", ok, detail))

    # what fields will change (respecting locks)
    field_plan = []
    for fld, newval, oldval, lockkey in [
        ("version", new_version, cur_version, "version"),
        ("release_stage", stage, cur_stage, "release_stage"),
    ]:
        locked = bool(locks.get(lockkey))
        field_plan.append((fld, oldval, newval, locked))
    if changelog is not None:
        field_plan.append(("changelog", (cur_changelog or "")[:40], changelog[:40], bool(locks.get("changelog"))))

    return {
        "game_id": game_id, "title": title,
        "cur_version": cur_version, "new_version": new_version, "stage": stage,
        "changelog": changelog, "sha": sha, "size": size, "archive_url": archive_url,
        "locks": locks, "checks": checks, "field_plan": field_plan,
        "checks_pass": all(c[1] for c in checks),
    }


def _link_ok(url: str) -> tuple[bool, str]:
    try:
        import requests
        r = requests.head(url, allow_redirects=True, timeout=15)
        if r.status_code == 405:  # some hosts reject HEAD
            r = requests.get(url, stream=True, timeout=15)
        return (r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, str(e)[:50])


# ── preview ──────────────────────────────────────────────────────────────
def print_preview(plan: dict) -> None:
    print("=" * 60)
    print(f"  פרסום: {plan['title']}  ({plan['game_id']})")
    print(f"  גרסה:  {V.fmt(plan['cur_version'])}  →  {V.fmt(plan['new_version'])}   [{plan['stage']}]")
    print("=" * 60)
    print("  שדות שיתעדכנו (🔒 = נעול, לא ייגע):")
    for fld, old, new, locked in plan["field_plan"]:
        mark = "🔒 דילוג" if locked else "✓"
        print(f"    {mark}  {fld}: {old!r} → {new!r}")
    print("  בדיקות טרם-פרסום:")
    for name, ok, detail in plan["checks"]:
        print(f"    {'✓' if ok else '✗'}  {name}  ({detail})")
    print("=" * 60)
    print(f"  סטטוס בדיקות: {'הכול עבר' if plan['checks_pass'] else 'יש כשל — תיקון נדרש'}")


# ── apply ────────────────────────────────────────────────────────────────
def apply_plan(conn, cur, plan: dict) -> None:
    gid, locks = plan["game_id"], plan["locks"]
    gpatch = {}
    if not locks.get("version"):       gpatch["version"] = plan["new_version"]
    if not locks.get("release_stage"): gpatch["release_stage"] = plan["stage"]
    if plan["changelog"] is not None and not locks.get("changelog"):
        gpatch["changelog"] = plan["changelog"]
    if gpatch:
        sets = ", ".join(f"{k}=%s" for k in gpatch)
        cur.execute(f"update games set {sets} where id=%s", (*gpatch.values(), gid))

    # history: flip current off, upsert new current row
    cur.execute("update mod_version_history set is_current=false where game_id=%s and is_current=true", (gid,))
    cur.execute(
        "insert into mod_version_history "
        "(game_id, version, stage, changelog, sha256, size_bytes, archive_url, is_current, published_at) "
        "values (%s,%s,%s,%s,%s,%s,%s,true, now()) "
        "on conflict (game_id, version) do update set "
        "stage=excluded.stage, changelog=excluded.changelog, sha256=excluded.sha256, "
        "size_bytes=excluded.size_bytes, archive_url=excluded.archive_url, "
        "is_current=true, published_at=now()",
        (gid, plan["new_version"], plan["stage"], plan["changelog"] or "",
         plan["sha"], plan["size"], plan["archive_url"]))
    conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description="Unified mod-version publisher (website sync).")
    ap.add_argument("game_id")
    ap.add_argument("version", help="base version (e.g. 1.1.0) or full staged (1.1.0-beta.2)")
    ap.add_argument("--stage", default="stable", choices=list(V.STAGES))
    ap.add_argument("--changelog", default=None)
    ap.add_argument("--sha", default=None)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--archive-url", dest="archive_url", default=None)
    ap.add_argument("--apply", action="store_true", help="commit (default: preview only)")
    a = ap.parse_args()

    conn = _connect()
    cur = conn.cursor()
    plan = build_plan(cur, a.game_id, a.version, a.stage, a.changelog, a.sha, a.size, a.archive_url)
    print_preview(plan)

    if not a.apply:
        print("\n(תצוגה מקדימה בלבד — הוסף --apply כדי לפרסם)")
        return 0
    if not plan["checks_pass"]:
        print("\n✗ לא מפרסם — בדיקות נכשלו.")
        return 2
    apply_plan(conn, cur, plan)
    print(f"\n✓ פורסם {plan['title']} {V.fmt(plan['new_version'])} ({plan['stage']}) → אתר + היסטוריה עודכנו")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
