# -*- coding: utf-8 -*-
"""The worker engine — a QThread running the resilient pull-loop (LINE model).

v1.0.2 rewrite. The previous build called the control plane with the OLD
job-batch signatures while client.py had already moved to single lines:

    client.submit(worker, item["job_id"], item["out"], proxy)   # 4 args
    def submit(worker_id, out, proxy)                           # 3 params

so the job id was passed AS the payload, the server answered 400, and the engine
treated that as "rejected → drop it locally". Every finished translation was
silently discarded, and the heartbeat was never sent at all, so the server kept
reclaiming this device's lines while it was alive. Both are fixed here.

One tick:
    1. heartbeat if the server's live interval has elapsed  (ONE cheap write)
    2. flush the outbox   (submit finished lines; a blip → stay buffered)
    3. refill the inbox   (claim ahead so a blip never stalls work; capped)
    4. translate a slice from the inbox with the volunteer's own providers
Off = idle, but finished work is still pushed. A drop to the control plane does
NOT stop translation — the worker keeps going from its local buffer.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

import client
import keystore
import providers
from config import POLL_IDLE_S, POLL_MAX_S, PREFETCH_LINES, TRANSLATE_SLICE
from state import State


class Engine(QThread):
    status = Signal(dict)

    def __init__(self, state: State):
        super().__init__()
        self._st = state
        self._alive = True
        self._on = bool(state.settings().get("enabled"))
        self._online = False
        self._providers_ok = False
        self._note = ""
        self._stage = 0            # 0 pull · 1 translate · 2 check · 3 send
        self._busy = False
        self._last_beat = 0.0
        self._enrolled = False
        self._started_at = 0.0
        self._session_lines = 0

    # -------- control from the UI thread
    def set_on(self, on: bool) -> None:
        self._on = on
        self._st.set_setting("enabled", on)
        if on:
            self._started_at = time.time()
        else:
            self._started_at = 0.0
            self._busy = False
        self._emit()

    def stop(self) -> None:
        self._alive = False

    def uptime(self) -> int:
        return int(time.time() - self._started_at) if self._started_at else 0

    # -------- status
    def _emit(self) -> None:
        keys = keystore.load()
        snap = self._st.snapshot()
        self.status.emit({
            "on": self._on,
            "online": self._online,
            "providers_ok": self._providers_ok,
            "has_keys": bool(providers.available(keys)),
            "n_keys": len(providers.available(keys)),
            "inbox": snap["inbox"],
            "outbox": snap["outbox"],
            "lines": snap["lines_done"],
            "session": self._session_lines,
            "by_provider": snap["by_provider"],
            "note": self._note,
            "stage": self._stage,
            "busy": self._busy,
            "uptime": self.uptime(),
            "blocked": client.BLOCKED,
            "config": dict(client.SERVER_CONFIG),
        })

    def _set_stage(self, stage: int, busy: bool = True) -> None:
        self._stage, self._busy = stage, busy
        self._emit()

    # -------- the loop
    def run(self) -> None:
        backoff = POLL_IDLE_S
        if self._on:
            self._started_at = time.time()
        self._emit()

        while self._alive:
            keys = keystore.load()
            proxy = self._st.settings().get("proxy", "") or ""
            provs = providers.available(keys)

            if not self._on:
                self._flush_outbox(proxy)          # still push finished work
                self._note = "כבוי"
                self._set_stage(0, False)
                self._sleep(POLL_IDLE_S)
                backoff = POLL_IDLE_S
                continue

            if not provs:
                self._note = "צריך להוסיף מפתח לפחות מספק אחד"
                self._set_stage(0, False)
                self._sleep(POLL_IDLE_S)
                continue

            if client.BLOCKED:
                self._note = "המכשיר נחסם על ידי המנהל"
                self._set_stage(0, False)
                self._sleep(POLL_MAX_S)
                continue

            # 0. enroll once (and again whenever the server asks us to)
            if not self._enrolled or client.NEEDS_REENROLL:
                try:
                    client.enroll(self._st.worker_id, "windows", proxy)
                    self._enrolled, self._online = True, True
                    self._last_beat = time.time()
                except client.NetworkError:
                    self._online = False
                    self._note = "אין קשר לשרת — מנסה שוב"
                    self._set_stage(0, False)
                    self._sleep(min(backoff, POLL_MAX_S))
                    backoff = min(backoff * 2, POLL_MAX_S)
                    continue
                except client.ApiError as e:
                    self._note = "השרת דחה: " + str(e)[:60]
                    self._set_stage(0, False)
                    self._sleep(min(backoff, POLL_MAX_S))
                    backoff = min(backoff * 2, POLL_MAX_S)
                    continue

            # 1. heartbeat on the server's OWN live interval (retunable, no rebuild)
            beat = max(60, int(client.SERVER_CONFIG.get("heartbeat_seconds") or 300))
            if self._online and time.time() - self._last_beat >= beat:
                try:
                    if client.renew(self._st.worker_id, proxy):
                        self._last_beat = time.time()
                    elif client.NEEDS_REENROLL:
                        self._enrolled = False      # the server forgot us → re-enroll next tick
                except client.NetworkError:
                    self._online = False
                except client.ApiError:
                    pass

            did_work = False

            # 2. push whatever is already translated
            if self._st.outbox_count():
                self._set_stage(3)
            self._flush_outbox(proxy)

            # 3. refill the buffer (claim ahead) while online and under the cap.
            #    The size is the SERVER's call (it ignores our `max` on purpose), and it
            #    already bounds us by batch_size + max_inflight — so keep EVERYTHING it
            #    hands over. Slicing the reply here would strand the discarded lines:
            #    they are already leased to this worker, so nobody else can take them
            #    until the lease expires, and we would never translate them.
            if self._online and self._st.inbox_count() < PREFETCH_LINES:
                self._set_stage(0)
                try:
                    batch = int(client.SERVER_CONFIG.get("batch_size") or 50)
                    lines = client.claim(self._st.worker_id, batch, proxy)
                    if lines:
                        self._st.add_inbox(lines)
                        self._online = True
                except client.NetworkError:
                    self._online = False
                except client.ApiError as e:
                    self._note = "השרת דחה: " + str(e)[:60]

            # 4. translate a slice locally (needs the PROVIDERS, not the server)
            slice_ = self._st.take_inbox(TRANSLATE_SLICE)
            if slice_:
                self._set_stage(1)
                sysmsg = slice_[0].get("sys") or ""
                items = {ln["id"]: ln.get("src") or "" for ln in slice_}
                try:
                    out, counts = providers.translate_batch(keys, sysmsg, items, proxy)
                except Exception:
                    out, counts = {}, {}
                if out:
                    self._set_stage(2)
                    self._st.add_outbox(out, counts)
                    self._providers_ok = True
                    did_work = True
                    missing = [ln for ln in slice_ if ln["id"] not in out]
                    if missing:
                        self._st.put_back(missing)   # a dropped line is retried, never lost
                    self._set_stage(3)
                    self._flush_outbox(proxy)
                else:
                    self._st.put_back(slice_)
                    self._providers_ok = False

            # 5. status + pacing
            if did_work:
                backoff = POLL_IDLE_S
                self._note = "פעיל" if self._online else "פעיל — נאגר מקומית (השרת לא זמין)"
                self._emit()
            else:
                if not self._online and self._st.inbox_count() == 0:
                    self._note = "אין קשר לשרת — ממתין וחוזר אוטומטית"
                elif not self._providers_ok and self._st.inbox_count() > 0:
                    self._note = "אין קשר לספקים — ממתין"
                else:
                    self._note = "אין כרגע עבודה בתור"
                backoff = min(backoff * 2, POLL_MAX_S)
                self._set_stage(0, False)
                self._sleep(backoff)

        # graceful exit: push what we have, then hand the rest back to the pool
        proxy = self._st.settings().get("proxy", "") or ""
        self._flush_outbox(proxy)
        try:
            if self._enrolled:
                client.release(self._st.worker_id, proxy)
        except Exception:
            pass

    # -------- helpers
    def _flush_outbox(self, proxy: str) -> None:
        pending = self._st.peek_outbox()
        if not pending:
            return
        try:
            accepted = client.submit(self._st.worker_id, pending, proxy)
            # Drop ALL submitted ids: an id the server refused is one we no longer
            # hold (its lease moved on), so retrying it forever would wedge the
            # outbox. Only the ACCEPTED ones are credited.
            self._st.drop_outbox(list(pending), accepted)
            self._session_lines += accepted
            self._online = True
        except client.NetworkError:
            self._online = False        # server down → keep everything buffered
        except client.ApiError:
            self._st.drop_outbox(list(pending), 0)

    def _sleep(self, secs: float) -> None:
        end = time.time() + secs
        while self._alive and time.time() < end:
            time.sleep(0.2)
