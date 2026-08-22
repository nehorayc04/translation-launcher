#!/usr/bin/env python3
"""
cc_server — the SELF-HOSTED Community-Compute pool.

A faithful, byte-compatible port of the Cloudflare Worker's /cc/* contract
(games/steam/steam_mod_worker/src/index.js :: handleCc) onto a LOCAL SQLite
file, so the Android app / desktop client / fleet workers need NOTHING changed
except the base URL.

WHY a local SQLite instead of Turso:
  * no storage quota, no write quota  -> the 1,000-device ceiling disappears
  * the data lives on the operator's own machine
  * a claim is serialised by a real write lock (STRONGER than the remote HTTP
    pipeline, where two claims could in principle interleave)

DESIGN (unchanged from the Worker — see schema.sql):
  * per-WORKER lease: /cc/renew updates ONE row -> 1 write per heartbeat.
  * a claimed line is reclaimable iff its worker is stale/gone/blocked, NOT by
    the line's own lease -> a slow-but-alive device keeps its batch.
  * cc_config is returned on EVERY reply -> the operator retunes heartbeat /
    batch / cap live, with NO app rebuild.

Stdlib only (python3 + sqlite3). No pip install on the host.
"""
from __future__ import annotations

import contextlib
import json
import os
import socket
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CC_DB", os.path.join(HERE, "cc_pool.db"))
HOST = os.environ.get("CC_HOST", "127.0.0.1")
PORT = int(os.environ.get("CC_PORT", "8787"))
SECRET = os.environ.get("CC_SECRET", "")
ADMIN_SECRET = os.environ.get("CC_ADMIN_SECRET", "")
MAX_BODY = 8 * 1024 * 1024  # 8 MB — a 50-line submit is ~100 KB; this is generous
SOCKET_TIMEOUT = 30         # a client that stalls mid-request must not hold a thread
MAX_CONNECTIONS = 200       # hard ceiling on in-flight requests (thread-exhaustion guard)
LINGER_BYTES = 16 * 1024 * 1024  # bounded drain so an over-limit client still SEES its 413
LINGER_SECONDS = 5

DEFAULT_CONFIG = {
    "heartbeat_seconds": 300,
    "lease_ttl_seconds": 1200,
    "batch_size": 50,
    "max_inflight": 300,
}
# same clamps as the Worker, so a bad value can never brick the fleet
CONFIG_LIMITS = {
    "heartbeat_seconds": (60, 3600),
    "lease_ttl_seconds": (120, 86400),
    "batch_size": (1, 200),
    "max_inflight": (10, 5000),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS cc_config (
  k TEXT PRIMARY KEY,
  v INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cc_workers (
  id          TEXT PRIMARY KEY,
  platform    TEXT,
  last_seen   INTEGER NOT NULL,
  done        INTEGER NOT NULL DEFAULT 0,
  blocked     INTEGER NOT NULL DEFAULT 0,
  enrolled_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cc_lines (
  id          TEXT PRIMARY KEY,
  game        TEXT NOT NULL,
  target      TEXT NOT NULL,
  sys         TEXT NOT NULL,
  src         TEXT NOT NULL,
  out         TEXT,
  status      TEXT NOT NULL DEFAULT 'open',
  worker_id   TEXT,
  lease_until INTEGER,
  collected   INTEGER NOT NULL DEFAULT 0,
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS cc_lines_pick_idx   ON cc_lines (status, collected, created_at);
CREATE INDEX IF NOT EXISTS cc_lines_worker_idx ON cc_lines (worker_id, status);
CREATE INDEX IF NOT EXISTS cc_lines_game_idx   ON cc_lines (game, status);
CREATE INDEX IF NOT EXISTS cc_workers_seen_idx ON cc_workers (last_seen);
"""

_db_lock = threading.Lock()
_db: sqlite3.Connection | None = None


def db() -> sqlite3.Connection:
    global _db
    if _db is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")      # concurrent readers + a durable writer
        conn.execute("PRAGMA synchronous=NORMAL")    # safe with WAL, far fewer fsyncs
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_CONFIG.items():
            conn.execute("INSERT INTO cc_config(k,v) VALUES(?,?) ON CONFLICT(k) DO NOTHING", (k, v))
        conn.commit()
        _db = conn
    return _db


@contextlib.contextmanager
def write_txn():
    """A write transaction that is ALWAYS closed out.

    Without the rollback, an exception raised mid-op leaves the shared
    connection inside an open transaction — and the NEXT request's commit
    would then silently commit this failed request's partial write.
    """
    with _db_lock:
        conn = db()
        try:
            yield conn
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


def get_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    for row in db().execute("SELECT k, v FROM cc_config"):
        cfg[row["k"]] = int(row["v"])
    return cfg


def now_s() -> int:
    return int(time.time())


# ── the ops (a 1:1 port of handleCc) ────────────────────────────────────────

def op_stats(_body, _now):
    cfg = get_config()
    active = _now - cfg["lease_ttl_seconds"]
    row = db().execute(
        "SELECT (SELECT COUNT(*) FROM cc_lines WHERE status='open' AND collected=0) AS 'open',"
        "(SELECT COUNT(*) FROM cc_lines WHERE status='claimed') AS claimed,"
        "(SELECT COUNT(*) FROM cc_lines WHERE status='done' AND collected=0) AS done,"
        "(SELECT COUNT(*) FROM cc_workers WHERE last_seen>=? AND blocked=0) AS workers,"
        "(SELECT COUNT(DISTINCT game) FROM cc_lines WHERE collected=0) AS games",
        (active,),
    ).fetchone()
    return {**{k: row[k] for k in row.keys()}, "config": cfg}


def op_detail(_body, _now):
    cfg = get_config()
    active = _now - cfg["lease_ttl_seconds"]
    games = [dict(r) for r in db().execute(
        "SELECT game,"
        " SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS 'open',"
        " SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) AS claimed,"
        " SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done"
        " FROM cc_lines WHERE collected=0 GROUP BY game ORDER BY game")]
    workers = [dict(r) for r in db().execute(
        "SELECT id, platform, last_seen, done FROM cc_workers "
        "WHERE last_seen>=? AND blocked=0 ORDER BY last_seen DESC", (active,))]
    by_worker: dict[str, dict] = {}
    for r in db().execute(
        "SELECT worker_id, game, COUNT(*) AS n FROM cc_lines "
        "WHERE status='claimed' AND worker_id IS NOT NULL GROUP BY worker_id, game"):
        cur = by_worker.get(r["worker_id"])
        if not cur or int(r["n"]) > cur["n"]:
            by_worker[r["worker_id"]] = {"game": r["game"], "n": int(r["n"])}
    out_workers = [{
        "id": w["id"], "platform": w["platform"], "last_seen": w["last_seen"], "done": w["done"],
        "game": (by_worker.get(w["id"]) or {}).get("game"),
        "claimed": (by_worker.get(w["id"]) or {}).get("n", 0),
    } for w in workers]
    return {"games": games, "workers": out_workers, "config": cfg}


def op_config_get(_body, _now):
    return {"config": get_config()}


def op_config_set(body, _now):
    setv = body.get("set") or {}
    if not isinstance(setv, dict):
        return {"error": "set must be an object"}, 400
    # validate EVERYTHING before writing anything, so a bad 2nd key cannot
    # leave the 1st one half-applied
    pending = []
    for k, v in setv.items():
        if k not in CONFIG_LIMITS:
            continue
        try:
            num = int(float(v))
        except (TypeError, ValueError):
            return {"error": f"{k} must be a number"}, 400
        lo, hi = CONFIG_LIMITS[k]
        pending.append((k, max(lo, min(hi, num))))
    with write_txn() as conn:
        for k, n in pending:
            conn.execute("INSERT INTO cc_config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, n))
    return {"config": get_config()}


def op_block(body, now, block=True):
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    b = 1 if block else 0
    with write_txn() as conn:
        conn.execute("UPDATE cc_workers SET blocked=? WHERE id=?", (b, w))
        released = 0
        if b:
            cur = conn.execute(
                "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? "
                "WHERE worker_id=? AND status='claimed'", (now, w))
            released = cur.rowcount
    return {"ok": True, "worker": w, "blocked": bool(b), "released": released}


def op_enroll(body, now):
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    platform = body.get("platform")
    if platform is not None:
        platform = str(platform)[:64]
    with write_txn() as conn:
        conn.execute(
            "INSERT INTO cc_workers(id,platform,last_seen,enrolled_at) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen, "
            "platform=COALESCE(cc_workers.platform,excluded.platform)",
            (w, platform, now, now))
    row = db().execute("SELECT blocked FROM cc_workers WHERE id=?", (w,)).fetchone()
    return {"worker": w, "blocked": bool(row and row["blocked"]), "config": get_config()}


def op_renew(body, now):
    """The CHEAP heartbeat: exactly ONE write."""
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    with write_txn() as conn:
        changed = conn.execute("UPDATE cc_workers SET last_seen=? WHERE id=?", (now, w)).rowcount
    if not changed:
        return {"ok": False, "reenroll": True, "config": get_config()}
    row = db().execute("SELECT blocked FROM cc_workers WHERE id=?", (w,)).fetchone()
    return {"ok": True, "blocked": bool(row and row["blocked"]), "config": get_config()}


def op_release(body, now):
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    with write_txn() as conn:
        n = conn.execute(
            "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? "
            "WHERE worker_id=? AND status='claimed'", (now, w)).rowcount
    return {"released": n}


def op_submit(body, now):
    """Commits ONLY lines the worker still HOLDS (poison-safe)."""
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    out = body.get("out") or {}
    if not isinstance(out, dict):
        return {"error": "out must be an object"}, 400
    ids = list(out.keys())
    if not ids:
        return {"accepted": 0, "rejected": 0}
    accepted = 0
    with write_txn() as conn:
        for lid in ids:
            accepted += conn.execute(
                "UPDATE cc_lines SET out=?, status='done', updated_at=? "
                "WHERE id=? AND worker_id=? AND status='claimed'",
                (str(out[lid]), now, str(lid), w)).rowcount
        if accepted:
            conn.execute("UPDATE cc_workers SET done=done+? WHERE id=?", (accepted, w))
    return {"accepted": accepted, "rejected": len(ids) - accepted}


def op_claim(body, now):
    w = str(body.get("worker") or "")
    if not w:
        return {"error": "missing worker"}, 400
    # Optional GAME SCOPE: a worker that wants only one game's lines passes `game`. Omitted
    # (every worker before this) keeps the original cross-game behavior byte-for-byte, so the
    # live crimson-desert fleet is UNCHANGED by this addition -- it never sends `game`, so its
    # claim query is identical to before. This exists so a second game's fleet can share the
    # SAME queue/workers pool without ever being handed the other game's lines (and vice versa).
    game = body.get("game")
    game = str(game) if game else None
    cfg = get_config()
    with write_txn() as conn:
        # touch last_seen (the claim itself is a liveness signal)
        if not conn.execute("UPDATE cc_workers SET last_seen=? WHERE id=?", (now, w)).rowcount:
            return {"lines": [], "reenroll": True, "config": cfg}
        row = conn.execute("SELECT blocked FROM cc_workers WHERE id=?", (w,)).fetchone()
        if row and row["blocked"]:
            conn.execute(
                "UPDATE cc_lines SET status='open', worker_id=NULL, lease_until=NULL, updated_at=? "
                "WHERE worker_id=? AND status='claimed'", (now, w))
            return {"lines": [], "blocked": True, "config": cfg}
        inflight = conn.execute(
            "SELECT COUNT(*) AS n FROM cc_lines WHERE worker_id=? AND status='claimed'",
            (w,)).fetchone()["n"]
        n = min(cfg["batch_size"], max(0, cfg["max_inflight"] - int(inflight)))
        if n <= 0:
            return {"lines": [], "config": cfg}
        stale = now - cfg["lease_ttl_seconds"]
        # UNFILTERED legacy callers (crimson-desert's cc_worker.py never sends `game`) must
        # NEVER be handed a 007-first-light line -- only a worker that explicitly asks for it
        # by name may claim it. Scoped to this one game rather than "any filtered game" so a
        # THIRD game added later the same way is safe by default too (opt-in isolation, not
        # opt-out) -- extend this tuple, don't invert the logic.
        _RESTRICTED_UNLESS_ASKED = ("007-first-light",)
        if game:
            game_clause = " AND l.game=?"
            extra = (game,)
        elif _RESTRICTED_UNLESS_ASKED:
            game_clause = " AND l.game NOT IN (" + ",".join("?" * len(_RESTRICTED_UNLESS_ASKED)) + ")"
            extra = _RESTRICTED_UNLESS_ASKED
        else:
            game_clause, extra = "", ()
        params = (w, now + cfg["lease_ttl_seconds"], now, stale) + extra + (n,)
        rows = conn.execute(
            "UPDATE cc_lines SET worker_id=?, status='claimed', lease_until=?, updated_at=? "
            "WHERE id IN (SELECT l.id FROM cc_lines l WHERE l.collected=0 AND ("
            "l.status='open' OR (l.status='claimed' AND NOT EXISTS ("
            "SELECT 1 FROM cc_workers x WHERE x.id=l.worker_id AND x.blocked=0 AND x.last_seen>=?)))"
            + game_clause +
            " ORDER BY (l.status='open') DESC, l.created_at LIMIT ?) "
            "RETURNING id, target, sys, src",
            params).fetchall()
        return {"lines": [dict(r) for r in rows], "config": cfg}


ADMIN_OPS = {"block", "unblock", "detail"}


_conn_sem = threading.BoundedSemaphore(MAX_CONNECTIONS)


class Handler(BaseHTTPRequestHandler):
    server_version = "ccpool/1.0"
    protocol_version = "HTTP/1.1"
    timeout = SOCKET_TIMEOUT  # a stalled client is dropped instead of pinning a thread

    def log_message(self, fmt, *args):  # quiet: systemd journal only gets real errors
        pass

    def _linger(self):
        """Drain a BOUNDED amount of the body we chose not to read.

        Closing a socket while unread bytes are still arriving makes the OS
        send RST, and the RST destroys the response we just wrote — the client
        sees a connection reset instead of its 413. Draining first turns that
        into a clean shutdown. The cap keeps this from becoming a way to make
        the server chew on an attacker's endless upload.
        """
        try:
            remaining = LINGER_BYTES
            deadline = time.time() + LINGER_SECONDS
            self.connection.settimeout(0.5)
            while remaining > 0 and time.time() < deadline:
                try:
                    chunk = self.connection.recv(min(65536, remaining))
                except (socket.timeout, TimeoutError, OSError):
                    break
                if not chunk:
                    break
                remaining -= len(chunk)
        except Exception:
            pass

    def _json(self, obj, status=200, close=False, drain=False):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if close:
            # Answering WITHOUT having consumed the body: keep-alive would frame
            # the client's leftover bytes as the next request, so end the
            # connection instead.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True
            return
        if drain:
            self._linger()

    def _route(self, method):
        parts = [p for p in self.path.split("?")[0].split("/") if p]

        # unauthenticated liveness probe for the watchdog / uptime check
        if parts == ["health"]:
            try:
                db().execute("SELECT 1").fetchone()
                return self._json({"ok": True, "ts": now_s()})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if not parts or parts[0] != "cc":
            return self._json({"error": "not found"}, 404)

        op = parts[1] if len(parts) > 1 else ""
        is_admin_op = (op == "config" and method == "POST") or op in ADMIN_OPS
        secret = self.headers.get("x-cc-secret") or ""
        if is_admin_op:
            if not ADMIN_SECRET or secret != ADMIN_SECRET:
                return self._json({"error": "unauthorized (admin)"}, 401)
        elif secret != SECRET and not (ADMIN_SECRET and secret == ADMIN_SECRET):
            return self._json({"error": "unauthorized"}, 401)

        body = {}
        if method == "POST":
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json({"error": "bad length"}, 400, close=True, drain=True)
            if n < 0:
                return self._json({"error": "bad length"}, 400, close=True, drain=True)
            if n > MAX_BODY:
                # answer, drain what is already in flight, then hang up
                return self._json({"error": "body too large"}, 413, close=True, drain=True)
            raw = self.rfile.read(n) if n else b""
            if len(raw) != n:  # client vanished mid-body
                self.close_connection = True
                return self._json({"error": "incomplete body"}, 400, close=True)
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception:
                    return self._json({"error": "bad json"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "bad json"}, 400)

        now = now_s()
        try:
            if op == "stats":
                res = op_stats(body, now)
            elif op == "detail":
                res = op_detail(body, now)
            elif op == "config":
                res = op_config_set(body, now) if method == "POST" else op_config_get(body, now)
            elif op == "block":
                res = op_block(body, now, True)
            elif op == "unblock":
                res = op_block(body, now, False)
            elif op == "enroll":
                res = op_enroll(body, now)
            elif op == "renew":
                res = op_renew(body, now)
            elif op == "release":
                res = op_release(body, now)
            elif op == "submit":
                res = op_submit(body, now)
            elif op == "claim":
                res = op_claim(body, now)
            else:
                return self._json({"error": "not found"}, 404)
        except Exception as e:  # never let one bad request kill the pool
            return self._json({"error": str(e)}, 500)

        if isinstance(res, tuple):
            return self._json(res[0], res[1])
        return self._json(res)

    def _guarded(self, method):
        """Nothing may escape a handler: an uncaught error on a keep-alive
        connection leaves the client waiting for a response that never comes."""
        if not _conn_sem.acquire(blocking=False):
            try:
                self._json({"error": "server busy"}, 503, close=True)
            except Exception:
                pass
            return
        try:
            self._route(method)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, socket.timeout):
            self.close_connection = True
        except Exception as e:
            try:
                self._json({"error": f"internal: {e}"}, 500, close=True)
            except Exception:
                self.close_connection = True
        finally:
            _conn_sem.release()

    def do_GET(self):
        self._guarded("GET")

    def do_POST(self):
        self._guarded("POST")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    if not SECRET:
        print("FATAL: CC_SECRET is not set", file=sys.stderr)
        return 2
    db()  # build the schema before the first request
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    print(f"cc_server listening on {HOST}:{PORT}  db={DB_PATH}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
