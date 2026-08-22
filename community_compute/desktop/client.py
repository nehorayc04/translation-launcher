# -*- coding: utf-8 -*-
"""Control-plane client — talks to the Supabase SECURITY DEFINER RPCs.

Pull model: the worker connects OUT to Supabase, claims jobs, submits results.
The operator never connects to the worker, so never learns its IP; the volunteer's
API keys never appear here. Anon (publishable) key + the shared app_secret are
the only credentials, and both are low-value by design (RLS + leases + the QA
gate are the real protections).

The whole point of NetworkError vs ApiError: a NetworkError means "the server is
unreachable right now" → the engine keeps working from its local buffer and
retries; an ApiError (paused/unauthorized) is a real answer to act on.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from config import CC_BASE, CC_SECRET  # v1.0.1: Turso /cc/* control plane (not Supabase)

_SSL = ssl.create_default_context()


class NetworkError(Exception):
    """Transient — server unreachable / timeout / 5xx. Buffer and retry."""


class ApiError(Exception):
    """The server answered with a 4xx (unauthorized secret, fleet paused, …)."""


def _opener(proxy: str):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=_SSL))
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL))


# v1.0.1: the control plane moved OFF the site's Supabase to its own Turso queue,
# reached through the Worker's secret-gated /cc/* routes — the volunteer fleet can
# no longer affect the site's AUTH/storage. Line-model (one row per line), and the
# server returns a live `config` on every reply so heartbeat/batch are tunable with
# NO client rebuild. Mirrors android/lib/client.dart.

# Live server tuning, refreshed from every reply.
SERVER_CONFIG = {"heartbeat_seconds": 300, "lease_ttl_seconds": 1200,
                 "batch_size": 50, "max_inflight": 300}
NEEDS_REENROLL = False
BLOCKED = False

# The ONE thing a live `config` reply cannot carry is its own address, so the
# base URL is overridable at runtime (Settings → server). That is what lets the
# fleet move to the self-hosted pool without shipping a new build.
_BASE_OVERRIDE = ""


def set_base(url: str) -> None:
    global _BASE_OVERRIDE
    _BASE_OVERRIDE = (url or "").strip().rstrip("/")


def base() -> str:
    return _BASE_OVERRIDE or CC_BASE


def _cc(op: str, body: dict, proxy: str = "", timeout: int = 45) -> dict:
    global NEEDS_REENROLL, BLOCKED
    req = urllib.request.Request(
        f"{base()}/{op}",
        data=json.dumps(body).encode(), method="POST",
        headers={"x-cc-secret": CC_SECRET, "Content-Type": "application/json"})
    try:
        raw = _opener(proxy).open(req, timeout=timeout).read().decode().strip()
    except urllib.error.HTTPError as e:
        if 500 <= e.code < 600:
            raise NetworkError(f"{op} {e.code}") from e
        raise ApiError(f"{op} {e.code}: {e.read().decode(errors='replace')[:200]}") from e
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as e:
        raise NetworkError(str(e)) from e
    m = json.loads(raw) if raw else {}
    if not isinstance(m, dict):
        return {}
    cfg = m.get("config")
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k in SERVER_CONFIG:
                try:
                    SERVER_CONFIG[k] = int(v)
                except (TypeError, ValueError):
                    pass
    if m.get("blocked") is True:
        BLOCKED = True
    if m.get("reenroll") is True:
        NEEDS_REENROLL = True
    return m


def enroll(worker_id: str, platform: str = "windows", proxy: str = "") -> None:
    global NEEDS_REENROLL, BLOCKED
    m = _cc("enroll", {"worker": worker_id, "platform": platform}, proxy)
    BLOCKED = m.get("blocked") is True
    NEEDS_REENROLL = False


def claim(worker_id: str, max_jobs: int, proxy: str = "") -> list:
    """Returns [{'id','sys','target','src'}] — single LINES. [] if the queue is empty.

    `max_jobs` is ADVISORY: the server sizes the batch itself (batch_size, bounded by
    max_inflight) so the operator can retune the whole fleet with no client rebuild.
    Whatever comes back is already leased to us — the caller must keep ALL of it or
    those lines sit stranded until the lease expires.
    """
    m = _cc("claim", {"worker": worker_id, "max": max_jobs}, proxy)
    return [{"id": str(r["id"]), "sys": r.get("sys") or "",
             "target": r.get("target") or "", "src": r.get("src") or ""}
            for r in (m.get("lines") or [])]


def submit(worker_id: str, out: dict, proxy: str = "") -> int:
    """Commit {line_id: hebrew}. The server accepts ONLY lines this worker holds."""
    m = _cc("submit", {"worker": worker_id, "out": out}, proxy)
    try:
        return int(m.get("accepted") or 0)
    except (TypeError, ValueError):
        return 0


def renew(worker_id: str, proxy: str = "") -> int:
    """Heartbeat — ONE cheap write (per-worker lease)."""
    return 1 if _cc("renew", {"worker": worker_id}, proxy).get("ok") is True else 0


def release(worker_id: str, proxy: str = "") -> int:
    """Graceful release — return this worker's claimed lines to the pool now."""
    m = _cc("release", {"worker": worker_id}, proxy)
    try:
        return int(m.get("released") or 0)
    except (TypeError, ValueError):
        return 0


def stats(proxy: str = "") -> dict:
    return _cc("stats", {}, proxy)
