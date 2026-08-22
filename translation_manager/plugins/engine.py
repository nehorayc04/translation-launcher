"""
plugins.engine - the SAFE, declarative action dispatcher for cloud plugins.

A cloud plugin is DECLARATIVE data: a `ui` tree (drawn by the launcher's generic
renderer) + a set of ACTIONS it may call. This module maps an action NAME to a
bundled, AUDITED primitive - it NEVER downloads-and-executes code, so a hostile
manifest can at worst mis-drive a feature the app already knows how to run safely
(the same posture stated in `plugins/__init__.py`). New plugin UI + new plugins in
the launcher's domain (game saves / files) ship from the cloud with NO app rebuild;
only a genuinely NEW primitive needs a (small, reviewed) code change.

For `kind == "save_backup"` the primitives wrap `save_backup.py` + `registry` +
`host`. `get_state(pid)` returns the plain dict the declarative UI binds to;
`run_action(pid, action, args)` performs one audited operation and returns fresh
state so the UI re-renders. Nothing here raises to the caller.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

# The Hebrew schedule labels the declarative "schedule" field offers. Kept here
# (not in the cloud manifest) so a bad manifest can never invent an unknown value.
SCHEDULE_OPTIONS = [
    {"value": "daily",     "label": "כל יום"},
    {"value": "weekly",    "label": "כל שבוע"},
    {"value": "monthly",   "label": "כל חודש"},
    {"value": "on_boot",   "label": "בכל הפעלת מחשב"},
    {"value": "on_launch", "label": "בהפעלת משחק"},
    {"value": "realtime",  "label": "תוך כדי משחק"},
    {"value": "manual",    "label": "ידני בלבד"},
]

# main_eel injects capabilities that need the RPC layer's context (the installed-
# games list for detection; the native folder picker). Kept as callbacks so the
# engine stays decoupled, exactly like `registry.configure(owns_any_game=...)`.
_detect_fn: Callable[[], list[dict]] | None = None
_pick_folder_fn: Callable[[str], dict] | None = None
_pick_file_fn: Callable[[str], dict] | None = None
_open_folder_fn: Callable[[str], Any] | None = None

# The last auto-detect result per plugin (ephemeral - a fresh scan replaces it).
# get_state FILTERS out candidates whose folder is already tracked, so the
# "found automatically" list only ever shows NOT-yet-added saves: pressing "add"
# moves an item into the backed-up list instead of leaving a duplicate below.
_last_detected: dict[str, list] = {}
# The last Ubisoft account tree per plugin (accounts -> games), same lifecycle.
_last_ubisoft: dict[str, list] = {}


def _ubi_name(g: dict) -> str:
    """A Ubisoft game's display name: the real title (resolved from its product
    id) when known, else the bare number as a labelled fallback.
    `detect_ubisoft_accounts` already fills `name` from the shipped id→title DB;
    resolve here too as a belt-and-suspenders for older cached trees."""
    n = (g.get("name") or "").strip()
    if not n:
        try:
            from . import save_backup
            n = save_backup.ubisoft_game_name(g.get("number") or "")
        except Exception:
            n = ""
    return n or f"משחק {g.get('number')}"


def configure(*, detect_fn: Callable[[], list[dict]] | None = None,
              pick_folder_fn: Callable[[str], dict] | None = None,
              pick_file_fn: Callable[[str], dict] | None = None,
              open_folder_fn: Callable[[str], Any] | None = None) -> None:
    global _detect_fn, _pick_folder_fn, _open_folder_fn, _pick_file_fn
    if detect_fn is not None:
        _detect_fn = detect_fn
    if pick_folder_fn is not None:
        _pick_folder_fn = pick_folder_fn
    if pick_file_fn is not None:
        _pick_file_fn = pick_file_fn
    if open_folder_fn is not None:
        _open_folder_fn = open_folder_fn


# ─────────────────────────────────────────────────────────────
# Views (shape the raw config/primitive output for the UI to bind to)
# ─────────────────────────────────────────────────────────────
def _safe_name(s: str) -> str:
    from . import save_backup
    return save_backup._safe_name(s)


def _leaf(path: str) -> str:
    import re
    parts = [p for p in re.split(r"[\\/]+", path or "") if p]
    return parts[-1] if parts else "שמירה"


def _entry_view(e: dict) -> dict:
    return {
        "id":      e.get("id", ""),
        "game_id": e.get("game_id", ""),
        "label":   e.get("label", ""),
        "source":  e.get("source", ""),
        "enabled": bool(e.get("enabled", True)),
        "auto":    bool(e.get("auto", False)),
    }


def _backup_view(b: dict) -> dict:
    return {
        "label":  b.get("label", ""),
        "when":   b.get("when", ""),
        "path":   b.get("path", ""),
        "files":  b.get("files", 0),
        "sizeMb": b.get("size_mb", 0),
    }


def _detect_view(d: dict) -> dict | None:
    """One row per game = its best candidate (the UI shows one per game)."""
    cands = d.get("candidates") or []
    if not cands:
        return None
    c = cands[0]
    return {
        "game_id":       d.get("game_id", ""),
        "title":         d.get("title", ""),
        "path":          c.get("path", ""),
        "label":         c.get("label", d.get("title", "")),
        "source":        c.get("source", ""),
        "confidencePct": int(round(float(c.get("confidence", 0)) * 100)),
        "sure":          c.get("source") == "known",
    }


def _kind_of(pid: str) -> str | None:
    """The plugin's kind, from install-state first (authoritative once
    installed), else the catalog. Used to route get_state/run_action to the
    right kind engine below - each kind module (save_backup, game_copilot)
    owns its own state shape and never sees the other's."""
    from . import registry
    try:
        ent = registry.installed().get(pid)
        if ent and ent.get("kind"):
            return ent["kind"]
        meta = registry.by_id(pid)
        return meta.get("kind") if meta else None
    except Exception:                                        # pragma: no cover
        return None


def get_state(pid: str) -> dict:
    """The dict the declarative UI binds to. Detection is NOT auto-run here (it
    scans the disk) - the 'detect' action fills `detected` on demand."""
    if _kind_of(pid) == "game_copilot":
        from . import game_copilot
        return game_copilot.get_state(pid)
    if _kind_of(pid) == "community_compute":
        from . import community_compute
        return community_compute.get_state(pid)

    from . import registry, save_backup
    try:
        cfg = registry.get_config(pid)
    except Exception:                                        # pragma: no cover
        cfg = {}
    entries = cfg.get("entries") or []
    try:
        backups = save_backup.list_backups(cfg)
    except Exception:                                        # pragma: no cover
        backups = []
    entries_v = [_entry_view(e) for e in entries]
    # A backup can be restored only if its game's save folder is still tracked
    # (that folder is the restore target). Precompute so the UI need not.
    restorable = {_safe_name(e.get("label") or e.get("game_id") or "") for e in entries}
    backups_v = []
    for b in backups:
        bv = _backup_view(b)
        bv["canRestore"] = bv["label"] in restorable
        bv["whenDisplay"] = str(bv["when"]).replace("_", " ")
        backups_v.append(bv)
    # Only surface auto-detected candidates NOT already tracked (so "add" moves an
    # item up rather than leaving a duplicate in the detected list).
    added_srcs = {(e.get("source") or "").lower() for e in entries_v}
    detected_v = [d for d in _last_detected.get(pid, [])
                  if (d.get("path") or "").lower() not in added_srcs]
    # Ubisoft account tree: per account, its games (with an already-added flag) +
    # an editable display label (cfg["ubi_account_labels"]).
    acct_labels = cfg.get("ubi_account_labels") or {}
    ubi_accounts = []
    for acc in _last_ubisoft.get(pid, []):
        default = (f"{acc['container']} · {acc['accountShort']}"
                   if acc.get("container") else acc["accountShort"])
        games, n_added = [], 0
        for g in acc.get("games", []):
            is_added = (g.get("path") or "").lower() in added_srcs
            n_added += 1 if is_added else 0
            games.append({"number": g.get("number"), "path": g.get("path"),
                          "name": _ubi_name(g), "added": is_added})
        ubi_accounts.append({
            "account": acc["account"], "accountShort": acc["accountShort"],
            "container": acc.get("container"), "path": acc["path"],
            "label": acct_labels.get(acc["account"]) or default,
            "games": games, "gamesCount": len(games), "addedCount": n_added,
            "allAdded": bool(games) and n_added == len(games),
        })
    return {
        "entitled":        _entitled(),
        "installed":       registry.is_installed(pid),
        "enabled":         registry.is_enabled(pid),
        "schedule":        cfg.get("schedule", "daily"),
        "scheduleOptions": SCHEDULE_OPTIONS,
        # The EFFECTIVE path (a custom one, or the default when unset) - so the UI
        # always shows a real location instead of a blank field.
        "destination":     cfg.get("destination") or str(save_backup._BACKUP_ROOT_DEFAULT),
        # The built-in default, and whether the user has moved away from it - the
        # reset button shows only when it would actually do something.
        "destinationDefault":  str(save_backup._BACKUP_ROOT_DEFAULT),
        "destinationIsCustom": bool(cfg.get("destination")
                                    and cfg["destination"] != str(save_backup._BACKUP_ROOT_DEFAULT)),
        "keep":            cfg.get("keep", 10),
        "entries":         entries_v,
        "entriesCount":    len(entries_v),
        "hasEntries":      bool(entries_v),
        "backups":         backups_v,
        "backupsCount":    len(backups_v),
        "hasBackups":      bool(backups_v),
        "detected":        detected_v,
        "detectedCount":   len(detected_v),
        "ubisoftAccounts": ubi_accounts,
        "hasUbisoft":      bool(ubi_accounts),
    }


def _entitled() -> bool:
    from . import registry
    try:
        return bool(registry.can_use_plugins())
    except Exception:                                        # pragma: no cover
        return False


# ─────────────────────────────────────────────────────────────
# Entry helpers
# ─────────────────────────────────────────────────────────────
def _eid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _mk_entry(args: dict) -> dict | None:
    """Build a save entry from a detected/candidate payload {game_id, path, label}."""
    path = str((args or {}).get("path") or "").strip()
    if not path:
        return None
    gid = str((args or {}).get("game_id") or "").strip() or "manual"
    label = str((args or {}).get("label") or "").strip() or _leaf(path)
    return {"id": _eid(f"d_{gid}"), "game_id": gid, "label": label,
            "source": path, "enabled": True, "auto": True}


def _add_entry(cfg: dict, entry: dict) -> bool:
    """Append an entry unless its source folder is already tracked. Returns added?"""
    entries = cfg.setdefault("entries", [])
    src = entry.get("source", "").lower()
    if any((x.get("source", "").lower() == src) for x in entries):
        return False
    entries.append(entry)
    return True


def _resolve_target(cfg: dict, label: str) -> str | None:
    """Map a backup's label (= _safe_name(entry.label)) back to the live save
    folder to restore INTO. None if no matching tracked entry exists - OR if
    MORE THAN ONE entry shares that label (fail safe on ambiguity rather than
    silently picking whichever happens to come first).

    Labels are meant to be unique per entry by design (Ubisoft games fold the
    account uuid into the label specifically so two entries never collide -
    see save_backup._KNOWN's comment). Nothing enforced that invariant here,
    which matters because `add_manual`/`add_ubi_game`/`rename_entry` all
    accept a raw, unvalidated label/path from action args: a hostile or
    malformed cloud manifest could add one entry pointing at a sensitive path
    and a second entry (sharing the same label) pointing at attacker-chosen
    content, back up both, then call restore naming that label with the
    OTHER entry's backup snapshot path - which still passes the "must be
    under the configured destination root" check - and silently resolve to
    the sensitive entry as the overwrite target. Requiring an exact single
    match closes that without touching the (intended, user-facing) ability
    to add any folder manually."""
    want = _safe_name(label)
    matches = [e for e in cfg.get("entries") or []
               if _safe_name(e.get("label") or e.get("game_id") or "") == want]
    if len(matches) != 1:
        return None
    return matches[0].get("source")


# ─────────────────────────────────────────────────────────────
# The audited action dispatcher
# ─────────────────────────────────────────────────────────────
def _ubi_default_label(pid: str, acct: str) -> str:
    acc = next((x for x in _last_ubisoft.get(pid, []) if x.get("account") == acct), None)
    if not acc:
        return acct[:8] if acct else "יוביסופט"
    return (f"{acc['container']} · {acc['accountShort']}"
            if acc.get("container") else acc["accountShort"])


def run_action(pid: str, action: str, args: dict | None = None) -> dict:
    """Perform ONE audited primitive. Returns {ok, state?, status?, error?, path?}.
    Never raises."""
    try:
        return _dispatch(pid, action, args if isinstance(args, dict) else {})
    except Exception as e:                                   # pragma: no cover
        log.warning("[plugins.engine] action %r failed: %s", action, e)
        return {"ok": False, "error": "action-failed"}


def _dispatch(pid: str, action: str, args: dict) -> dict:
    if _kind_of(pid) == "game_copilot":
        from . import game_copilot
        return game_copilot.run_action(pid, action, args)
    if _kind_of(pid) == "community_compute":
        from . import community_compute
        return community_compute.run_action(pid, action, args)

    from . import registry, save_backup, host
    a = (action or "").strip()

    # ── read-only (no entitlement / install gate) ─────────────
    if a in ("refresh", "state"):
        return {"ok": True, "state": get_state(pid)}

    if a == "detect":
        cands: list[dict] = []
        if _detect_fn is not None:
            try:
                cands = _detect_fn() or []
            except Exception:                                # pragma: no cover
                cands = []
        ubi = save_backup.detect_ubisoft_accounts()
        ubi_root = str(save_backup._ubi_savegames_root() or "").lower()
        # Flat list = cataloged (minus Ubisoft account folders, which the tree
        # covers at per-game granularity) + a generic sweep of the game roots.
        flat: list[dict] = []
        covered: set[str] = set()
        for d in cands:
            v = _detect_view(d)
            if not v:
                continue
            p = (v.get("path") or "").lower()
            if ubi_root and p.startswith(ubi_root):
                continue
            flat.append(v)
            covered.add(p)
        for acc in ubi:
            for g in acc.get("games", []):
                covered.add((g.get("path") or "").lower())
        for g in save_backup.detect_generic_saves(covered):
            flat.append({"game_id": g["game_id"], "title": g["title"], "path": g["path"],
                         "label": g["label"], "source": g["source"],
                         "confidencePct": int(round(float(g["confidence"]) * 100)),
                         "sure": False})
        _last_detected[pid] = flat
        _last_ubisoft[pid] = ubi
        st = get_state(pid)
        total = len(flat) + sum(len(a.get("games", [])) for a in ubi)
        return {"ok": True, "state": st, "status": f"נמצאו {total} תיקיות שמירה"}

    if a == "pick_folder":
        path = ""
        if _pick_folder_fn is not None:
            try:
                r = _pick_folder_fn(str(args.get("title") or "בחר תיקיית שמירות"))
                if isinstance(r, dict) and r.get("ok"):
                    path = r.get("path") or ""
            except Exception:                                # pragma: no cover
                path = ""
        return {"ok": True, "path": path}

    if a == "open_folder":
        p = str(args.get("path") or "")
        if p and _open_folder_fn is not None:
            try:
                _open_folder_fn(p)
            except Exception:                                # pragma: no cover
                pass
        return {"ok": True}

    if a == "open_backup_folder":
        # The root where backups live, organised <destination>/<game label>/<date>.
        cfg = registry.get_config(pid)
        dest = cfg.get("destination") or str(save_backup._BACKUP_ROOT_DEFAULT)
        try:
            from pathlib import Path as _P
            _P(dest).mkdir(parents=True, exist_ok=True)   # may not exist before the first backup
        except Exception:                                    # pragma: no cover
            pass
        if _open_folder_fn is not None:
            try:
                _open_folder_fn(dest)
            except Exception:                                # pragma: no cover
                pass
        return {"ok": True}

    # ── mutating (require an installed plugin; install is entitlement-gated) ──
    if not registry.is_installed(pid):
        return {"ok": False, "error": "not-installed"}
    cfg = registry.get_config(pid)

    if a == "add_detected":
        entry = _mk_entry(args)
        if entry is None:
            return {"ok": False, "error": "bad-args"}
        added = _add_entry(cfg, entry)
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid),
                "status": (f"נוסף לגיבוי: {entry['label']}" if added
                           else "התיקייה כבר קיימת ברשימה")}

    if a == "add_all":
        items = args.get("items")
        if not isinstance(items, list):
            return {"ok": False, "error": "bad-args"}
        n = 0
        for it in items:
            e = _mk_entry(it if isinstance(it, dict) else {})
            if e and _add_entry(cfg, e):
                n += 1
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid),
                "status": (f"נוספו {n} תיקיות לגיבוי" if n
                           else "כל התיקיות שנמצאו כבר ברשימה")}

    if a == "add_manual":
        path = str(args.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "bad-args"}
        label = str(args.get("label") or "").strip() or _leaf(path)
        e = {"id": _eid("m"), "game_id": "manual", "label": label,
             "source": path, "enabled": True, "auto": False}
        added = _add_entry(cfg, e)
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid),
                "status": (f"נוסף לגיבוי: {label}" if added
                           else "התיקייה כבר קיימת ברשימה")}

    if a == "remove_entry":
        eid = str(args.get("id") or "")
        cfg["entries"] = [x for x in (cfg.get("entries") or []) if x.get("id") != eid]
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid), "status": "הוסר מהגיבוי"}

    if a == "add_ubi_game":
        acct = str(args.get("account") or "")
        number = str(args.get("number") or "")
        path = str(args.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "bad-args"}
        acct_label = ((cfg.get("ubi_account_labels") or {}).get(acct)
                      or _ubi_default_label(pid, acct))
        gname = _ubi_name({"number": number, "name": args.get("gameName")})
        # Heavy-backup guard: warn + require confirmation before adding a huge
        # save folder (e.g. Anno 1800's tens-of-GB autosaves). Skipped once the
        # user confirmed (the re-call carries confirmed=True).
        if not args.get("confirmed"):
            try:
                size, trunc = save_backup.folder_size(path)
                if size >= save_backup.HEAVY_BYTES:
                    approx = ("מעל " if trunc else "כ-") + save_backup.fmt_size(size)
                    return {"ok": True, "state": get_state(pid),
                            "confirm": f"הגיבוי של \"{gname}\" ישקול {approx} "
                                       f"(שמירות אוטומטיות רבות). להוסיף לגיבוי בכל זאת?"}
            except Exception:
                pass
        label = f"{acct_label} · {gname}" if number else (acct_label or _leaf(path))
        entry = {"id": _eid(f"ubi_{acct}"), "game_id": f"ubi_{acct}_{number}",
                 "label": label, "source": path, "enabled": True, "auto": True,
                 "ubi_account": acct, "ubi_number": number}
        added = _add_entry(cfg, entry)
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid),
                "status": (f"נוסף לגיבוי: {label}" if added else "התיקייה כבר קיימת ברשימה")}

    if a == "add_ubi_account":
        acct = str(args.get("account") or "")
        acc = next((x for x in _last_ubisoft.get(pid, []) if x.get("account") == acct), None)
        if acc is None:
            return {"ok": False, "error": "unknown-account"}
        acct_label = ((cfg.get("ubi_account_labels") or {}).get(acct)
                      or _ubi_default_label(pid, acct))
        games = acc.get("games", [])
        # Heavy-backup guard for "add all": measure each NOT-yet-added folder and,
        # if any is large, list them (with sizes) and ask once before adding.
        if not args.get("confirmed"):
            try:
                added_srcs = {(e.get("source") or "").lower()
                              for e in (cfg.get("entries") or [])}
                heavy = []
                for g in games:
                    if (g.get("path") or "").lower() in added_srcs:
                        continue
                    size, trunc = save_backup.folder_size(g.get("path") or "")
                    if size >= save_backup.HEAVY_BYTES:
                        heavy.append((_ubi_name(g), size, trunc))
                if heavy:
                    heavy.sort(key=lambda t: t[1], reverse=True)
                    lines = "\n".join(
                        f"• {nm} — {'מעל ' if tr else 'כ-'}{save_backup.fmt_size(sz)}"
                        for nm, sz, tr in heavy)
                    total = sum(sz for _, sz, _ in heavy)
                    return {"ok": True, "state": get_state(pid),
                            "confirm": "המשחקים הבאים ישקלו הרבה בגיבוי (שמירות "
                                       f"אוטומטיות רבות):\n\n{lines}\n\nסה\"כ כ-"
                                       f"{save_backup.fmt_size(total)}. להוסיף את כולם?"}
            except Exception:
                pass
        n = 0
        for g in games:
            entry = {"id": _eid(f"ubi_{acct}"),
                     "game_id": f"ubi_{acct}_{g['number']}",
                     "label": f"{acct_label} · {_ubi_name(g)}", "source": g["path"],
                     "enabled": True, "auto": True,
                     "ubi_account": acct, "ubi_number": g["number"]}
            if _add_entry(cfg, entry):
                n += 1
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid),
                "status": (f"נוספו {n} משחקים מהחשבון" if n else "כל המשחקים כבר ברשימה")}

    if a == "rename_account":
        acct = str(args.get("account") or "")
        name = str(args.get("name") or "").strip()
        if not acct or not name:
            return {"ok": False, "error": "bad-args"}
        cfg.setdefault("ubi_account_labels", {})[acct] = name
        for e in cfg.get("entries") or []:          # relabel this account's added games
            if e.get("ubi_account") == acct:
                e["label"] = f"{name} · משחק {e.get('ubi_number')}"
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid), "status": "שם החשבון עודכן"}

    if a == "rename_entry":
        eid = str(args.get("id") or "")
        name = str(args.get("label") or "").strip()
        if not eid or not name:
            return {"ok": False, "error": "bad-args"}
        for e in cfg.get("entries") or []:
            if e.get("id") == eid:
                e["label"] = name
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid), "status": "השם עודכן"}

    if a == "set_entry_enabled":
        eid = str(args.get("id") or "")
        on = bool(args.get("enabled"))
        for x in cfg.get("entries") or []:
            if x.get("id") == eid:
                x["enabled"] = on
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid)}

    if a == "set_schedule":
        val = str(args.get("value") or "daily")
        if val in save_backup.SCHEDULES:
            cfg["schedule"] = val
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid), "status": "לוח הזמנים עודכן"}

    if a == "set_field":
        key = str(args.get("key") or "")
        val = args.get("value")
        if key == "destination":
            cfg["destination"] = str(val or "")
        elif key == "keep":
            try:
                cfg["keep"] = max(0, int(val))          # 0 = unlimited (keep everything)
            except (TypeError, ValueError):
                pass
        else:
            return {"ok": False, "error": "bad-field"}
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid)}

    if a == "pick_destination":
        if _pick_folder_fn is not None:
            try:
                # The native folder dialog is open-ended (the user can leave it
                # open for a long time) while `cfg` above was read BEFORE it
                # opened - patch_config (not set_config) so another action that
                # completes meanwhile (e.g. add/remove an entry) is never
                # silently reverted by this stale snapshot's eventual write.
                r = _pick_folder_fn("בחר תיקיית יעד לגיבויים")
                if isinstance(r, dict) and r.get("ok") and r.get("path"):
                    registry.patch_config(pid, {"destination": r["path"]})
                    return {"ok": True, "state": get_state(pid), "status": "מיקום הגיבוי עודכן"}
            except Exception:                                # pragma: no cover
                pass
        return {"ok": True, "state": get_state(pid)}

    if a == "reset_destination":
        # Back to the built-in default (an empty destination → save_backup falls
        # back to _BACKUP_ROOT_DEFAULT). Storing "" rather than the resolved path
        # keeps it correct if the default ever moves.
        cfg["destination"] = ""
        registry.set_config(pid, cfg)
        return {"ok": True, "state": get_state(pid), "status": "מיקום הגיבוי אופס לברירת המחדל"}

    if a == "backup_now":
        res = host.run_now(pid, str(args.get("name") or ""))
        n = int(res.get("backed_up") or 0)
        errs = res.get("errors") or []
        if any((e.get("error") == "diskfull") for e in errs):
            return {"ok": False, "state": get_state(pid),
                    "status": "אין מקום פנוי בכונן היעד - פנה מקום או שנה את מיקום הגיבוי"}
        if errs:
            # Surface the failure (source folder gone / drive offline / no access)
            # instead of the misleading "no new changes" - naming the folders.
            labels = ", ".join(str(e.get("label") or "?") for e in errs[:3])
            return {"ok": False, "state": get_state(pid),
                    "status": (f"הגיבוי נכשל עבור {len(errs)} תיקיות ({labels}) - ודא שהתיקייה קיימת ונגישה"
                               + (f"; גובו {n} תיקיות אחרות" if n else ""))}
        return {"ok": True, "state": get_state(pid),
                "status": (f"גובו {n} תיקיות" if n else "אין שינוי חדש לגבות")}

    if a == "restore":
        # SECURITY: never trust a raw backup_path/target from args (a cloud-managed
        # `ui` manifest could otherwise drive an arbitrary shutil.copytree overwrite).
        # target is ALWAYS resolved from a tracked entry via its label; backup_path
        # must resolve under the configured backup destination root.
        tgt = _resolve_target(cfg, str(args.get("label") or "")) or ""
        if not tgt:
            return {"ok": False, "error": "no-target",
                    "status": "הוסף קודם את תיקיית השמירה של המשחק כדי לשחזר אליה"}
        dest_root = Path(cfg.get("destination") or save_backup._BACKUP_ROOT_DEFAULT).resolve()
        bp_raw = str(args.get("backup_path") or "")
        try:
            bp_resolved = Path(bp_raw).resolve()
            bp_ok = bool(bp_raw) and bp_resolved.is_relative_to(dest_root)
        except Exception:
            bp_ok = False
        if not bp_ok:
            return {"ok": False, "error": "bad-backup-path",
                    "status": "נתיב הגיבוי אינו תקין"}
        res = save_backup.restore(str(bp_resolved), tgt)
        return {"ok": bool(res.get("ok")), "state": get_state(pid),
                "status": ("השחזור הושלם (נשמר גיבוי-ביטחון של המצב הקודם)"
                           if res.get("ok") else "השחזור נכשל")}

    return {"ok": False, "error": "unknown-action"}


def pick_file(title: str = "") -> str:
    """Native file picker for a plugin action ("" = cancelled/unavailable).
    Lives here because the host injects the real dialog, exactly like the
    folder picker - a plugin kind must never import Qt."""
    if _pick_file_fn is None:
        return ""
    try:
        return str((_pick_file_fn(title) or {}).get("path") or "")
    except Exception:                                     # pragma: no cover
        return ""
