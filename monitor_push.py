"""
Universal live-progress push library.

Replaces the legacy Upstash KV write. Any per-game monitor script (current
or future) calls `push_progress(...)` with whatever numbers it computed
locally; this library handles the network call, the API contract, and the
silent-failure semantics.

Wiring requirements (read once at import):
  • PROGRESS_API_URL   — defaults to https://hebrew-translation-hub.com
  • MONITOR_TOKEN      — shared secret matching the Vercel env var. The
                         script's writes are accepted by /api/admin/progress
                         as a monitor-token bearer, no Supabase JWT needed.

Read from environment OR from the same .env file the legacy push used:
   <project root>/.env

Everything is wrapped in try/except so a network blip never bubbles up
into the live TUI render loop — failures only log a warning line.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:                                  # pragma: no cover
    requests = None  # type: ignore[assignment]

# Hebrew labels for the three primary phases — frontend can override per
# game via the admin panel (phase_label_he), but these are the defaults
# the script sends.
DEFAULT_PHASE_LABELS_HE = {
    "extraction":  "שליפת נתונים",
    "translation": "תרגום נתונים",
    "packaging":   "אריזת נתונים",
    "qa":          "בקרת איכות",
    "deployment":  "פריסה",
    "idle":        "הושלם",
}

# Default units per phase. Translation counts lines; everything else
# operates on files/items. Override with `unit=` if your phase counts
# something else (e.g. "סצנות").
DEFAULT_UNITS_HE = {
    "extraction":  "קבצים",
    "translation": "שורות",
    "packaging":   "קבצים",
    "qa":          "פריטים",
    "deployment":  "פריטים",
    "idle":        "קבצים",
}


# ── env loading ────────────────────────────────────────────────────────
def _load_env_file(path: Path) -> dict[str, str]:
    """Tiny .env parser — just `KEY=VALUE` lines, comments + blanks ignored.
    Stops short of full python-dotenv to keep the script dependency-free."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip()
            # strip optional surrounding quotes
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    except OSError:
        pass
    return out


def _resolve_config() -> tuple[Optional[str], Optional[str]]:
    """Returns (api_url, monitor_token). Reads OS env first, then a sibling
    .env file at PROJECT_DIR/.env (where the legacy KV creds lived)."""
    api_url = os.environ.get("PROGRESS_API_URL")
    token   = os.environ.get("MONITOR_TOKEN")
    if api_url and token:
        return api_url, token

    # Walk up from this file looking for the project root containing .env
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent, here.parent.parent):
        kv = _load_env_file(candidate / ".env")
        if kv:
            api_url = api_url or kv.get("PROGRESS_API_URL")
            token   = token   or kv.get("MONITOR_TOKEN")
            if api_url and token:
                break

    # Final fallback for the public API root — only the token must be
    # supplied locally; the website's URL is stable.
    if not api_url:
        api_url = "https://hebrew-translation-hub.com"
    return api_url, token


_API_URL, _MONITOR_TOKEN = _resolve_config()


def is_configured() -> bool:
    """True iff a monitor token is available — caller can decide to skip
    the push entirely on dev machines that never write to prod."""
    return bool(_MONITOR_TOKEN) and requests is not None


# ── push ──────────────────────────────────────────────────────────────
def push_progress(
    game_id: str,
    *,
    phase: str,
    processed: int,
    total: int,
    rate_per_hour: float = 0.0,
    unit: Optional[str] = None,
    gpu_model: str = "",
    ai_model: str = "",
    phase_label_he: Optional[str] = None,
    meta: Optional[dict] = None,
    timeout: float = 5.0,
) -> bool:
    """Push one snapshot. Returns True on success, False on any failure.
    Silent — only writes a single-line warning via print() if the API
    rejects the payload, so noisy TUI output isn't broken on transient
    network issues."""
    if not is_configured():
        return False

    payload = {
        "gameId":        game_id,
        "phase":         phase,
        "processed":     int(processed or 0),
        "total":         int(total or 0),
        "ratePerHour":   int(rate_per_hour or 0),
        "unit":          unit or DEFAULT_UNITS_HE.get(phase, "שורות"),
        "gpuModel":      gpu_model,
        "aiModel":       ai_model,
        "phaseLabelHe":  phase_label_he,                # null = use frontend default
        "meta":          meta,
        # `updatedAt` is recorded server-side by the upsert handler; we
        # don't trust client clocks for canonical timestamps.
    }

    try:
        r = requests.post(                              # type: ignore[union-attr]
            f"{_API_URL.rstrip('/')}/api/admin/progress",
            headers={
                "Authorization": f"Bearer {_MONITOR_TOKEN}",
                "Content-Type":  "application/json",
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=timeout,
        )
        if r.status_code >= 400:
            # Don't dump the body on success paths; on failure show enough
            # to debug without flooding the TUI.
            print(f"[progress] push {r.status_code} — {r.text[:200]}")
            return False
        return True
    except Exception as e:                              # pylint: disable=broad-except
        print(f"[progress] push skipped — {type(e).__name__}: {e}")
        return False


# ── convenience ──────────────────────────────────────────────────────
_last_push_ts: dict[str, float] = {}

def push_progress_throttled(
    game_id: str, *, min_interval_sec: float = 60.0, **kwargs
) -> bool:
    """Same as `push_progress` but no-ops if the last successful push for
    this game was less than `min_interval_sec` ago. Saves the live TUI
    from spamming the API on every screen refresh."""
    now = time.time()
    last = _last_push_ts.get(game_id, 0.0)
    if (now - last) < min_interval_sec:
        return False
    ok = push_progress(game_id, **kwargs)
    if ok:
        _last_push_ts[game_id] = now
    return ok
