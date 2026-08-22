"""
game_visual_logger.py
=====================
Universal **Visual LQA** capture backbone — a read-only screen logger that
prepares gameplay frames for a Vision-Language Model (VLM) to inspect for
on-screen UI text overflow, reversed RTL letters, and context mismatches.

It is game-agnostic: a single config dict (`GAME_WINDOW_TITLES`) maps a
logical `game_id` to the window titles that identify it, so the same loop
serves Cyberpunk 2077 and Marvel's Spider-Man 2 (and any future title).

How it works
------------
A safe background loop polls the *foreground* (focused) window title every
few seconds:

  * If the focused window belongs to a target game, the game window's screen
    region is captured (scoped to its monitor), downscaled, and encoded to a
    JPEG buffer (to protect VRAM / disk bandwidth), written under
    `_archive/visual_logs/frames/<game_id>/`,
    and a structured record `{timestamp, game_id, frame_path, ...}` is
    appended to `_archive/visual_logs/runtime_log.jsonl`.
  * If no target game is focused, the loop drops into an **idle state** and
    only sleeps — it never grabs the screen, so 100% of GPU/CPU stays with
    the game and the system.

Dependencies
------------
The core path needs **only Pillow** (already a project dependency) and the
native Win32 API reached through `ctypes` — no `pywin32`, `pygetwindow`,
`psutil`, or `mss` install is required, which is what guarantees a clean
run on Python 3.13. `psutil` is used *opportunistically* (if importable) to
annotate the focused process name; its absence changes nothing.

Safety
------
This script is **strictly read-only toward the game**. It never opens, reads,
or writes a single game file or translation data array. The ONLY paths it
writes are inside `_archive/visual_logs/`; every write first passes through
`_safe_write_check()`, which hard-stops (exit 99) on any target outside that
directory — the same protected-write idiom the audit pipeline uses.

CLI
---
  python game_visual_logger.py run            # the background capture loop
  python game_visual_logger.py probe          # print the focused window + match
  python game_visual_logger.py --once         # one probe+capture (test helper)
  python game_visual_logger.py selftest       # compile/deps/IO smoke test
"""
from __future__ import annotations

import argparse
import io
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

__version__ = "0.1.0"

# Defensive: Windows consoles can refuse to print Hebrew under cp1255.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ── paths ───────────────────────────────────────────────────────────────────
HERE              = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT      = os.path.dirname(os.path.dirname(HERE))   # visual_bridge → universal → root
ARCHIVE_DIR       = os.path.join(PROJECT_ROOT, "_archive")
VISUAL_LOGS_DIR   = os.path.join(ARCHIVE_DIR, "visual_logs")
FRAMES_DIR        = os.path.join(VISUAL_LOGS_DIR, "frames")
RUNTIME_LOG       = os.path.join(VISUAL_LOGS_DIR, "runtime_log.jsonl")

VISUAL_LOGS_DIR_ABS = os.path.abspath(VISUAL_LOGS_DIR)


# ── game targets ────────────────────────────────────────────────────────────
# game_id → list of window-title fragments that identify it. Matching is
# case-insensitive substring (the live CP2077 window title carries the full
# copyright suffix, so an exact match would be brittle). Order the fragments
# most-specific first.
GAME_WINDOW_TITLES: dict[str, list[str]] = {
    "cyberpunk2077": [
        "Cyberpunk 2077 (C) 2020 by CD Projekt RED",
        "Cyberpunk 2077",
    ],
    "spiderman2": [
        "Marvel's Spider-Man 2",
        "Spider-Man 2",
    ],
}


# ── tunables (all overridable from the CLI) ─────────────────────────────────
DEFAULT_POLL_SECONDS     = 4.0    # how often we re-check the focused window
DEFAULT_CAPTURE_INTERVAL = 5.0    # minimum seconds between two captured frames
DEFAULT_IDLE_POLL        = 4.0    # poll cadence while no game is focused
DEFAULT_MAX_DIM          = 1280   # longest edge of the downscaled JPEG (px)
DEFAULT_JPEG_QUALITY     = 70     # JPEG quality 1-95


# ── read-only safety guard ──────────────────────────────────────────────────
def _critical_safety_stop(reason: str) -> None:
    """Emit a loud CRITICAL_SAFETY_STOP marker and exit code 99.
    Called whenever a write target escapes `_archive/visual_logs/`."""
    msg = (
        "\n" + ("!" * 72) + "\n"
        "CRITICAL_SAFETY_STOP — refusing to continue.\n"
        f"REASON: {reason}\n"
        + ("!" * 72) + "\n"
    )
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.exit(99)


def _safe_write_check(path: str) -> None:
    """Refuse any write whose target is not inside `_archive/visual_logs/`.
    This is what makes the logger structurally incapable of touching a game
    file, a translation spine, or anything else on disk."""
    abs_path = os.path.abspath(path)
    if not (abs_path == VISUAL_LOGS_DIR_ABS
            or abs_path.startswith(VISUAL_LOGS_DIR_ABS + os.sep)):
        _critical_safety_stop(
            f"attempted write outside visual_logs: {abs_path} "
            f"(allowed root={VISUAL_LOGS_DIR_ABS})"
        )


def _safe_makedirs(path: str) -> None:
    _safe_write_check(path)
    os.makedirs(path, exist_ok=True)


# ── optional enrichment libs (never required) ───────────────────────────────
try:
    import psutil  # type: ignore
    _HAVE_PSUTIL = True
except Exception:  # pragma: no cover - absence is the normal case here
    psutil = None  # type: ignore
    _HAVE_PSUTIL = False


# ── native Win32 foreground-window probe (ctypes, no pywin32) ────────────────
_user32 = None  # lazily bound ctypes handle


def _win32() -> object | None:
    """Return a configured `user32` ctypes handle, or None off-Windows."""
    global _user32
    if sys.platform != "win32":
        return None
    if _user32 is not None:
        return _user32
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32  # type: ignore[attr-defined]
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowTextW.restype = ctypes.c_int
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                           ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    _user32 = u
    return _user32


def _window_bbox(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return the focused window's screen rectangle (left, top, right, bottom)
    in virtual-desktop coordinates, or None if it can't be read. Used to scope
    the screen grab to the game window — so a game on a SECONDARY monitor is
    captured correctly, not whatever happens to be on the primary display."""
    u = _win32()
    if u is None or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if not u.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None  # minimized / degenerate
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return None


@dataclass
class FocusInfo:
    """A snapshot of the currently focused window."""
    hwnd: int = 0
    title: str = ""
    pid: int = 0
    process_name: str | None = None


def foreground_focus() -> FocusInfo | None:
    """Read the focused window's title (and, if psutil is present, the owning
    process name). Returns None on a non-Windows host or when nothing is
    focused. Never raises — a probe failure must not kill the loop."""
    u = _win32()
    if u is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return None
        length = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        pname = None
        if _HAVE_PSUTIL and pid.value:
            try:
                pname = psutil.Process(pid.value).name()  # type: ignore[union-attr]
            except Exception:
                pname = None

        return FocusInfo(hwnd=int(hwnd), title=title,
                         pid=int(pid.value), process_name=pname)
    except Exception:
        return None


def match_game(title: str | None) -> str | None:
    """Return the game_id whose configured title fragments match `title`
    (case-insensitive substring), or None. First config entry wins."""
    if not title:
        return None
    low = title.lower()
    for game_id, fragments in GAME_WINDOW_TITLES.items():
        for frag in fragments:
            if frag.lower() in low:
                return game_id
    return None


# ── capture engine ──────────────────────────────────────────────────────────
def _resample():
    """Pillow resampling enum, compatible across Pillow 9.1+ … 12.x."""
    from PIL import Image
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:  # ancient Pillow
        return Image.LANCZOS  # type: ignore[attr-defined]


@dataclass
class FrameResult:
    frame_path: str
    original_size: tuple[int, int]
    scaled_size: tuple[int, int]
    jpeg_bytes: int


def capture_frame(game_id: str,
                  hwnd: int = 0,
                  max_dim: int = DEFAULT_MAX_DIM,
                  quality: int = DEFAULT_JPEG_QUALITY) -> FrameResult | None:
    """Grab the focused game window's screen region, downscale so the longest
    edge ≤ `max_dim`, encode to an in-memory JPEG buffer, and write it under
    `_archive/visual_logs/frames/<game_id>/`. Returns the FrameResult, or None
    on any failure — the caller logs `capture_failed` and moves on.

    When `hwnd` is known we scope the grab to that window's rect over the whole
    virtual desktop, so a game on a SECONDARY monitor is captured correctly
    (a bare `ImageGrab.grab()` would only ever see the primary display). If the
    rect can't be read we fall back to grabbing the entire virtual desktop.

    All-black frames are detected and rejected (returns None): GDI screen
    capture — what Pillow's ImageGrab uses — cannot read an *exclusive*
    fullscreen DXGI surface and yields a black image. Run the game in
    *borderless windowed* mode for Visual LQA capture.

    The grab → downscale → encode → write chain runs entirely inside one
    try/except so NO failure (grab error, encode error, disk-full, a transient
    AV/indexer file lock on the new .jpg) can ever propagate out and kill the
    background loop. A genuine safety-guard violation (`_safe_write_check`)
    still hard-stops, because it raises SystemExit, not Exception.
    """
    from PIL import ImageGrab

    img = None
    try:
        bbox = _window_bbox(hwnd)
        if bbox is not None:
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
        else:
            img = ImageGrab.grab(all_screens=True)  # whole virtual desktop
        if img is None:
            return None
        original_size = img.size
        # Downscale in place; thumbnail() preserves aspect ratio and is a
        # no-op when the frame is already smaller than the cap.
        img.thumbnail((max_dim, max_dim), _resample())
        scaled_size = img.size

        # Reject an all-black frame (exclusive-fullscreen GDI capture). getextrema()
        # on the luminance channel is cheap on the already-downscaled image.
        try:
            lo, hi = img.convert("L").getextrema()
            if hi == 0:
                sys.stderr.write(f"[visual] black frame for {game_id} "
                                 f"(likely exclusive fullscreen — use borderless)\n")
                return None
        except Exception:
            pass  # if the heuristic itself fails, keep the frame

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG",
                                quality=int(quality), optimize=True)
        data = buf.getvalue()
        buf.close()

        ts = datetime.now(timezone.utc)
        fname = ts.strftime("%Y%m%d_%H%M%S_") + f"{ts.microsecond // 1000:03d}.jpg"
        out_dir = os.path.join(FRAMES_DIR, game_id)
        _safe_makedirs(out_dir)
        out_path = os.path.join(out_dir, fname)
        _safe_write_check(out_path)
        with open(out_path, "wb") as fh:
            fh.write(data)

        return FrameResult(frame_path=out_path,
                           original_size=original_size,
                           scaled_size=scaled_size,
                           jpeg_bytes=len(data))
    except Exception as exc:  # capture must never crash the loop
        sys.stderr.write(f"[visual] capture failed for {game_id}: {exc}\n")
        return None
    finally:
        # Release the (potentially large) raw bitmap promptly.
        try:
            if img is not None:
                img.close()
        except Exception:
            pass


# ── structured runtime log (JSONL, append-only) ─────────────────────────────
def log_event(record: dict) -> None:
    """Append one JSON object as a line to runtime_log.jsonl (UTF-8).

    A transient OSError on the append (disk full, an AV/indexer holding the
    JSONL) must not kill the loop, so it is swallowed and reported to stderr.
    A `_safe_write_check` violation still hard-stops — it raises SystemExit,
    which is not caught here."""
    try:
        _safe_makedirs(VISUAL_LOGS_DIR)
        _safe_write_check(RUNTIME_LOG)
        line = json.dumps(record, ensure_ascii=False)
        with open(RUNTIME_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        sys.stderr.write(f"[visual] log_event failed: {exc}\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _capture_and_log(game_id: str, focus: FocusInfo,
                     max_dim: int, quality: int,
                     do_capture: bool) -> None:
    """Capture one frame (unless --no-capture) and append its log record."""
    record: dict = {
        "event": "capture",
        "timestamp": _now_iso(),
        "epoch": time.time(),
        "game_id": game_id,
        "window_title": focus.title,
        "pid": focus.pid,
        "process_name": focus.process_name,
        "frame_path": None,
    }
    if do_capture:
        result = capture_frame(game_id, hwnd=focus.hwnd,
                               max_dim=max_dim, quality=quality)
        if result is None:
            record["event"] = "capture_failed"
        else:
            record["frame_path"] = result.frame_path
            record["original_size"] = list(result.original_size)
            record["scaled_size"] = list(result.scaled_size)
            record["jpeg_bytes"] = result.jpeg_bytes
    else:
        record["event"] = "capture_skipped"  # --no-capture dry run
    log_event(record)


# ── the background loop ─────────────────────────────────────────────────────
_STOP = False


def _install_signal_handlers() -> None:
    def _handler(_signum, _frame):
        global _STOP
        _STOP = True
    try:
        signal.signal(signal.SIGINT, _handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handler)
    except Exception:
        pass  # e.g. non-main thread — Ctrl+C still raises KeyboardInterrupt


def _sleep_interruptible(seconds: float) -> None:
    """Sleep in small slices so a stop request lands within ~0.25 s."""
    deadline = time.time() + max(0.0, seconds)
    while not _STOP and time.time() < deadline:
        time.sleep(0.25)


@dataclass
class LoopConfig:
    poll_seconds: float = DEFAULT_POLL_SECONDS
    capture_interval: float = DEFAULT_CAPTURE_INTERVAL
    idle_poll: float = DEFAULT_IDLE_POLL
    max_dim: int = DEFAULT_MAX_DIM
    quality: int = DEFAULT_JPEG_QUALITY
    only_game: str | None = None   # restrict captures to one game_id
    do_capture: bool = True        # False = log decisions, never grab


def run_loop(cfg: LoopConfig) -> int:
    """Run the focus-aware capture loop until interrupted. Returns 0."""
    _install_signal_handlers()
    if sys.platform != "win32":
        sys.stderr.write("[visual] foreground tracking needs Windows; "
                         "the loop will idle on this platform.\n")

    _safe_makedirs(VISUAL_LOGS_DIR)
    log_event({"event": "loop_start", "timestamp": _now_iso(),
               "epoch": time.time(), "version": __version__,
               "have_psutil": _HAVE_PSUTIL, "platform": sys.platform,
               "config": {"poll": cfg.poll_seconds,
                          "capture_interval": cfg.capture_interval,
                          "idle_poll": cfg.idle_poll,
                          "max_dim": cfg.max_dim, "quality": cfg.quality,
                          "only_game": cfg.only_game,
                          "do_capture": cfg.do_capture}})

    last_capture = 0.0
    state: str | None = None   # "active" | "idle"
    try:
        while not _STOP:
            # Per-iteration guard: a transient probe/capture/log error must
            # degrade to a logged miss, never end a multi-hour session. A
            # safety-guard violation still escapes (it's SystemExit, not
            # Exception); Ctrl+C escapes to the outer handler.
            try:
                focus = foreground_focus()
                game_id = match_game(focus.title) if focus else None
                if cfg.only_game and game_id != cfg.only_game:
                    game_id = None

                if game_id:
                    if state != "active":
                        log_event({"event": "focus_gained", "timestamp": _now_iso(),
                                   "epoch": time.time(), "game_id": game_id,
                                   "window_title": focus.title if focus else ""})
                        state = "active"
                    now = time.time()
                    if now - last_capture >= cfg.capture_interval:
                        _capture_and_log(game_id, focus, cfg.max_dim,
                                         cfg.quality, cfg.do_capture)
                        last_capture = now
                    _sleep_interruptible(cfg.poll_seconds)
                else:
                    # Idle state: no game focused → never grab the screen, just
                    # sleep, so GPU/CPU stays free for the system.
                    if state != "idle":
                        log_event({"event": "idle", "timestamp": _now_iso(),
                                   "epoch": time.time(),
                                   "window_title": focus.title if focus else ""})
                        state = "idle"
                    _sleep_interruptible(cfg.idle_poll)
            except Exception as exc:
                sys.stderr.write(f"[visual] loop iteration error: {exc}\n")
                _sleep_interruptible(1.0)
    except KeyboardInterrupt:
        pass

    log_event({"event": "loop_stop", "timestamp": _now_iso(),
               "epoch": time.time()})
    return 0


# ── one-shot helpers (probe / --once / selftest) ────────────────────────────
def cmd_probe() -> int:
    """Print the focused window title and whether it matches a target."""
    focus = foreground_focus()
    if focus is None:
        print("focused window: <none / not Windows>")
        return 0
    game_id = match_game(focus.title)
    print(f"focused window : {focus.title!r}")
    print(f"process        : {focus.process_name or '<unknown>'} (pid {focus.pid})")
    print(f"matched game_id: {game_id or '<none>'}")
    return 0


def cmd_once(cfg: LoopConfig) -> int:
    """One probe; capture a single frame if a target game is focused."""
    focus = foreground_focus()
    game_id = match_game(focus.title) if focus else None
    if cfg.only_game and game_id != cfg.only_game:
        game_id = None
    if not game_id or focus is None:
        print("no target game focused — nothing captured.")
        log_event({"event": "once_no_target", "timestamp": _now_iso(),
                   "epoch": time.time(),
                   "window_title": focus.title if focus else ""})
        return 0
    _capture_and_log(game_id, focus, cfg.max_dim, cfg.quality, cfg.do_capture)
    print(f"captured one frame for {game_id} → runtime_log.jsonl")
    return 0


def cmd_selftest() -> int:
    """Compile/dependency/IO smoke test — needs no game running.

    Verifies: Python ≥ 3.9, Pillow importable, the Win32 probe is reachable
    (on Windows), and that we can create + write + delete inside
    `_archive/visual_logs/`. Reports optional libs. Exit 0 on success."""
    ok = True

    print(f"python         : {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        print("  ! needs Python 3.9+")
        ok = False

    try:
        import PIL  # noqa: F401
        from PIL import ImageGrab, Image  # noqa: F401
        print(f"pillow         : {getattr(PIL, '__version__', '?')} (ImageGrab OK)")
    except Exception as exc:
        print(f"pillow         : MISSING — {exc}")
        ok = False

    if sys.platform == "win32":
        u = _win32()
        print(f"win32 user32   : {'OK' if u is not None else 'UNAVAILABLE'}")
        if u is None:
            ok = False
        focus = foreground_focus()
        print(f"foreground probe: {focus.title!r}" if focus
              else "foreground probe: <none>")
    else:
        print(f"win32 user32   : skipped (platform={sys.platform})")

    print(f"psutil (opt)   : {'present' if _HAVE_PSUTIL else 'absent (fine)'}")

    # IO round-trip inside the allowed dir.
    try:
        _safe_makedirs(VISUAL_LOGS_DIR)
        probe = os.path.join(VISUAL_LOGS_DIR, ".selftest_probe")
        _safe_write_check(probe)
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        print(f"io round-trip  : OK ({VISUAL_LOGS_DIR})")
    except Exception as exc:
        print(f"io round-trip  : FAILED — {exc}")
        ok = False

    # The safety guard must reject a write outside visual_logs.
    guard_ok = False
    try:
        # Probe the predicate directly (don't actually exit the process).
        outside = os.path.abspath(os.path.join(PROJECT_ROOT, "games.json"))
        guard_ok = not (outside == VISUAL_LOGS_DIR_ABS
                        or outside.startswith(VISUAL_LOGS_DIR_ABS + os.sep))
    except Exception:
        guard_ok = False
    print(f"safety guard   : {'OK (rejects game files)' if guard_ok else 'BROKEN'}")
    ok = ok and guard_ok

    print()
    print("SELFTEST: PASS" if ok else "SELFTEST: FAIL")
    return 0 if ok else 1


# ── CLI ─────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="game_visual_logger",
        description="Read-only Visual LQA capture backbone "
                    "(Cyberpunk 2077 + Spider-Man 2).",
    )
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "probe", "selftest"],
                   help="run the loop (default), probe the focused window, "
                        "or run the dependency/IO selftest.")
    p.add_argument("--once", action="store_true",
                   help="capture a single frame now (if a game is focused) "
                        "and exit — handy for testing.")
    p.add_argument("--game", default=None,
                   help="restrict capture to one game_id "
                        f"({', '.join(GAME_WINDOW_TITLES)}).")
    p.add_argument("--no-capture", action="store_true",
                   help="log focus decisions but never grab the screen.")
    p.add_argument("--poll", type=float, default=DEFAULT_POLL_SECONDS,
                   help=f"focused-window poll seconds (default {DEFAULT_POLL_SECONDS}).")
    p.add_argument("--interval", type=float, default=DEFAULT_CAPTURE_INTERVAL,
                   help=f"min seconds between frames (default {DEFAULT_CAPTURE_INTERVAL}).")
    p.add_argument("--idle-poll", type=float, default=DEFAULT_IDLE_POLL,
                   help=f"poll seconds while idle (default {DEFAULT_IDLE_POLL}).")
    p.add_argument("--max-dim", type=int, default=DEFAULT_MAX_DIM,
                   help=f"longest JPEG edge in px (default {DEFAULT_MAX_DIM}).")
    p.add_argument("--quality", type=int, default=DEFAULT_JPEG_QUALITY,
                   help=f"JPEG quality 1-95 (default {DEFAULT_JPEG_QUALITY}).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.game and args.game not in GAME_WINDOW_TITLES:
        sys.stderr.write(f"unknown --game {args.game!r}; "
                         f"known: {', '.join(GAME_WINDOW_TITLES)}\n")
        return 2

    cfg = LoopConfig(
        poll_seconds=args.poll,
        capture_interval=args.interval,
        idle_poll=args.idle_poll,
        max_dim=args.max_dim,
        quality=args.quality,
        only_game=args.game,
        do_capture=not args.no_capture,
    )

    if args.command == "selftest":
        return cmd_selftest()
    if args.command == "probe":
        return cmd_probe()
    if args.once:
        return cmd_once(cfg)
    return run_loop(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
