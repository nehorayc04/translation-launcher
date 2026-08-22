# -*- coding: utf-8 -*-
"""Persistent local state — the LINE model.

v1.0.2: the control plane hands out single LINES (`{id, sys, target, src}`), not
job batches. The old shape kept `{job_id, items:{id:en}}`, which no longer
matches anything the server sends — a stale inbox from an older build is simply
dropped on load rather than crashing the worker.

Everything here is local and disposable: the queue is the server's source of
truth, so the worst case of losing this file is that a few claimed lines
lease-expire back into the pool.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "CommunityCompute")
STATE_PATH = os.path.join(APP_DIR, "state.json")
SCHEMA = 2  # 1 = job-batch model (pre-1.0.2), 2 = line model

_DEFAULT = {
    "schema": SCHEMA,
    "worker_id": "",
    "settings": {
        "enabled": False,
        "autostart": False,
        "min_to_tray": True,
        "proxy": "",
        "accent": "green",
        "anim": "full",        # full | normal | reduced | off
        "glass": True,
        "text_scale": 100,     # 75..125
        "base_override": "",   # empty = the baked default backend
    },
    "inbox":  [],   # [{id, sys, target, src}]     claimed, not yet translated
    "outbox": {},   # {line_id: hebrew}            translated, not yet submitted
    "lines_done": 0,
    "by_provider": {},
    "first_run": 0,
}


class State:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)
        self._lock = threading.RLock()
        self._d = self._read()
        if not self._d.get("worker_id"):
            self._d["worker_id"] = uuid.uuid4().hex[:12]
        if not self._d.get("first_run"):
            self._d["first_run"] = int(time.time())
        self._write()

    # ---------------------------------------------------------------- io
    def _read(self) -> dict:
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except Exception:
            return json.loads(json.dumps(_DEFAULT))

        # migrate: an inbox/outbox from the job-batch build cannot be replayed
        if int(d.get("schema") or 1) < SCHEMA:
            d["inbox"], d["outbox"] = [], {}
            d["schema"] = SCHEMA
        merged = json.loads(json.dumps(_DEFAULT))
        for k, v in d.items():
            if k == "settings" and isinstance(v, dict):
                merged["settings"].update(v)
            else:
                merged[k] = v
        if not isinstance(merged.get("outbox"), dict):
            merged["outbox"] = {}
        if not isinstance(merged.get("inbox"), list):
            merged["inbox"] = []
        return merged

    def _write(self) -> None:
        tmp = STATE_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._d, f, ensure_ascii=False)
            os.replace(tmp, STATE_PATH)
        except OSError:
            pass  # a locked/full disk must never take the worker down

    # ---------------------------------------------------------------- basics
    @property
    def worker_id(self) -> str:
        return self._d["worker_id"]

    def settings(self) -> dict:
        with self._lock:
            return dict(self._d["settings"])

    def set_setting(self, key: str, value) -> None:
        with self._lock:
            self._d["settings"][key] = value
            self._write()

    def first_run(self) -> int:
        return int(self._d.get("first_run") or 0)

    # ---------------------------------------------------------------- queues
    def inbox_count(self) -> int:
        with self._lock:
            return len(self._d["inbox"])

    def outbox_count(self) -> int:
        with self._lock:
            return len(self._d["outbox"])

    def add_inbox(self, lines: list) -> None:
        with self._lock:
            have = {j["id"] for j in self._d["inbox"]}
            done = set(self._d["outbox"])
            for line in lines:
                if line["id"] not in have and line["id"] not in done:
                    self._d["inbox"].append(line)
                    have.add(line["id"])
            self._write()

    def take_inbox(self, n: int = 1) -> list:
        """Pop up to n lines to translate."""
        with self._lock:
            out = self._d["inbox"][:n]
            self._d["inbox"] = self._d["inbox"][n:]
            if out:
                self._write()
            return out

    def put_back(self, lines: list) -> None:
        with self._lock:
            self._d["inbox"] = list(lines) + self._d["inbox"]
            self._write()

    def add_outbox(self, out: dict, provider_counts: dict | None = None) -> None:
        with self._lock:
            self._d["outbox"].update(out)
            for p, n in (provider_counts or {}).items():
                self._d["by_provider"][p] = self._d["by_provider"].get(p, 0) + n
            self._write()

    def peek_outbox(self, limit: int = 200) -> dict:
        with self._lock:
            items = list(self._d["outbox"].items())[:limit]
            return dict(items)

    def drop_outbox(self, ids, credited: int = 0) -> None:
        with self._lock:
            for i in ids:
                self._d["outbox"].pop(i, None)
            if credited:
                self._d["lines_done"] = int(self._d.get("lines_done") or 0) + credited
            self._write()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "inbox": len(self._d["inbox"]),
                "outbox": len(self._d["outbox"]),
                "lines_done": int(self._d.get("lines_done") or 0),
                "by_provider": dict(self._d.get("by_provider") or {}),
            }
