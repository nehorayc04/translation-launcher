"""Insert Claude-authored news / announcement suggestions into `news_drafts`
with source='claude'.

These show up in the site's admin → "הצעות AI" tab under the **Claude** category,
where the admin approves (→ published to the public news feed) or rejects them.
Nothing is ever published automatically — every item waits for the admin.

WHEN to run: every time Claude makes a real change to the website or the
launcher (a release, a fix, a new feature, a version bump), it should ALSO drop
a few user-facing suggestions here describing the current state + any general
topics worth announcing. The admin decides what actually ships.

Reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from website/.env (gitignored).

Usage:
  # one suggestion via flags
  python claude_suggest.py --title "..." --detail "..." \
      [--kind system|mod] [--badge "חדש"] [--link cyberpunk] [--date 2026-06-14]

  # many at once: a JSON array on stdin (or --json <file>)
  #   [{"title","detail","kind"?,"badge"?,"link"?,"date"?}, ...]
  python claude_suggest.py --json suggestions.json
  echo '[{"title":"...","detail":"..."}]' | python claude_suggest.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import sys
from pathlib import Path

import requests

# Console-safe Hebrew on cp1255 terminals.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)

HERE = Path(__file__).resolve().parent
WEBSITE_ENV = HERE.parent / "website" / ".env"


def load_env(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if (v[:1], v[-1:]) in (('"', '"'), ("'", "'")):
            v = v[1:-1]
        out[k.strip()] = v
    return out


def _norm(it: dict, default_date: str) -> dict:
    """One raw suggestion dict → a valid news_drafts row (source='claude')."""
    title = str(it.get("title") or "").strip()
    if not title:
        raise SystemExit("each suggestion needs a non-empty title")
    kind = "mod" if str(it.get("kind") or "system") == "mod" else "system"
    return {
        "title":  title[:240],
        "detail": str(it.get("detail") or "").strip(),
        "kind":   kind,
        "badge":  (it.get("badge") or None),
        "link":   (it.get("link") or None),
        "date":   str(it.get("date") or default_date),
        "source": "claude",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Insert Claude news suggestions (source='claude').")
    ap.add_argument("--json", help="path to a JSON array of suggestions")
    ap.add_argument("--title")
    ap.add_argument("--detail", default="")
    ap.add_argument("--kind", choices=["system", "mod"], default="system")
    ap.add_argument("--badge", default=None)
    ap.add_argument("--link", default=None)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    today = args.date or _dt.date.today().isoformat()

    # Gather raw suggestions: --json file, stdin JSON array, or single --title.
    raw: list[dict]
    if args.json:
        raw = json.loads(Path(args.json).read_text(encoding="utf-8"))
    elif not sys.stdin.isatty() and (piped := sys.stdin.read().strip()):
        raw = json.loads(piped)
    elif args.title:
        raw = [{"title": args.title, "detail": args.detail, "kind": args.kind,
                "badge": args.badge, "link": args.link, "date": args.date}]
    else:
        raise SystemExit("provide --json <file>, a JSON array on stdin, or --title …")

    if isinstance(raw, dict):
        raw = [raw]
    rows = [_norm(it, today) for it in raw]

    env = load_env(WEBSITE_ENV)
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing in website/.env")

    r = requests.post(
        f"{url}/rest/v1/news_drafts",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=rows,
        timeout=30,
    )
    if not r.ok:
        raise SystemExit(f"insert failed: {r.status_code} {r.text[:400]}")
    inserted = r.json()
    print(f"[ok] inserted {len(inserted)} Claude suggestion(s) → admin → הצעות AI → Claude:")
    for d in inserted:
        print(f"     · {d.get('title')}")


if __name__ == "__main__":
    main()
