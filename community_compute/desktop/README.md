
---

## v1.0.2 — the line model, and what was actually broken

The desktop worker had been left behind when the control plane moved from job
batches to single lines. `client.py` was updated; `engine.py` and `state.py` were
not, so:

- `client.submit(worker, item["job_id"], item["out"], proxy)` was called against
  `def submit(worker_id, out, proxy)` — the **job id was passed as the payload**.
  The server answered 400, the engine read that as "rejected → drop it", and
  **every finished translation was silently discarded**. A volunteer's machine
  could run for hours and contribute nothing, while the UI showed it working.
- `renew()` was **never called**, so the server never heard a heartbeat and kept
  reclaiming this device's lines while it was alive.
- `release()` was never called, so closing the app stranded its lines until the
  lease expired.

All three are fixed. The lesson worth keeping: **a client and its transport must
be re-tested together after a protocol change** — each file looked internally
consistent, and only the call SHAPE across the boundary was wrong.

### The claim reply must be kept whole

`claim(worker, max)`'s `max` is **advisory** — the pool sizes the batch itself
(`batch_size`, bounded by `max_inflight`) so the operator can retune the fleet
with no client rebuild. Whatever comes back is already leased to this worker, so
slicing the reply strands the discarded lines until the lease expires. The engine
keeps all of it.

### Tests

- `/c/tmp/cc_smoke_ui.py` — 32/32, offscreen Qt: builds the window, every nav
  view, every status branch, all four ring stages, settings, the counter, and the
  state round-trip.
- `/c/tmp/cc_e2e_desktop.py` — 12/12 against the **live self-hosted pool** over
  SSH with a fake provider: enroll → claim → renew → submit → release, then the
  real `Engine` draining 10 lines to `done` with nothing left claimed.
  ⚠️ `state.APP_DIR` is resolved **at import**, so the test must set `%APPDATA%`
  *before* the first local import or it writes the real user state file (it did,
  once — same class as the `PYTHONPATH` trap in `selfhost/README.md`).

### Pointing at the self-hosted pool

Settings → «כתובת השרת» → e.g. `https://cc.hebrew-translation-hub.com/cc` → «החל».
Empty = the default Worker URL. This is the one setting a live `config` reply
cannot carry (it cannot describe its own address), which is why it is in the UI.
