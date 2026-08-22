"""
perf_manager.py - the launcher's machine-aware, adaptive performance brain.

The launcher runs on EVERY kind of PC: a 4-core laptop with 8 GB, or a 16-core
desktop with 64 GB - and it very often runs WHILE a game is running. A fixed
polling cadence + fixed memory footprint is wrong on both ends: it wastes power
on a small machine and it steals frames from a game on a big one.

This module senses the HOST (cores / RAM / live CPU+RAM load) and the APP's own
state (foreground / background / user-idle / hidden-in-tray) and derives a single
adaptive answer that every background consumer reads:

    perf_manager.poll_interval(base_ms)   → how long to wait before the next tick
    perf_manager.should_defer_heavy()     → is now a bad moment for a heavy job?
    perf_manager.trim_memory()            → hand idle RAM back to Windows NOW

Behaviour it produces, with zero configuration:
  • Launcher in the foreground on a healthy machine → full speed (base cadence).
  • Machine busy (a game is running, CPU pegged)    → back off, don't steal frames.
  • Launcher in the background / minimised to tray  → slow right down.
  • User idle (AFK) or window hidden                → near-dormant + RAM released.
  • Weak machine (few cores / little RAM)           → permanently gentler.

Zero new dependencies - pure ctypes against Win32 (GlobalMemoryStatusEx,
GetSystemTimes, GetLastInputInfo, GetForegroundWindow, EmptyWorkingSet). Every
call is defensive: on a non-Windows host, or if any API is unavailable, the
module degrades to safe neutral values and the launcher behaves exactly as it
did before.
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time

log = logging.getLogger(__name__)

_IS_WIN = sys.platform == "win32"

# How long a sensed reading stays valid. The sensors are cheap (microseconds),
# but callers may ask many times per tick - cache so we never sample in a loop.
_SENSE_TTL_S = 2.0

# User is considered AFK after this much input silence.
_IDLE_AFTER_S = 120.0

# Load thresholds (percent).
_CPU_BUSY   = 75.0     # machine is working hard (likely a game)
_CPU_PEGGED = 90.0     # machine is saturated - defer anything heavy
_RAM_TIGHT  = 88.0     # memory pressure


# ─────────────────────────────────────────────────────────────
# Win32 plumbing (all optional - every use is guarded)
# ─────────────────────────────────────────────────────────────
class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength",                ctypes.c_ulong),
        ("dwMemoryLoad",            ctypes.c_ulong),
        ("ullTotalPhys",            ctypes.c_ulonglong),
        ("ullAvailPhys",            ctypes.c_ulonglong),
        ("ullTotalPageFile",        ctypes.c_ulonglong),
        ("ullAvailPageFile",        ctypes.c_ulonglong),
        ("ullTotalVirtual",         ctypes.c_ulonglong),
        ("ullAvailVirtual",         ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]

    @property
    def value(self) -> int:
        return (self.dwHighDateTime << 32) | self.dwLowDateTime


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus",        ctypes.c_ubyte),   # 0=battery, 1=AC, 255=unknown
        ("BatteryFlag",         ctypes.c_ubyte),
        ("BatteryLifePercent",  ctypes.c_ubyte),
        ("SystemStatusFlag",    ctypes.c_ubyte),
        ("BatteryLifeTime",     ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


# Win32 prototypes MUST be declared explicitly on 64-bit. ctypes defaults every
# unknown return/argument to a 32-bit C int, which silently TRUNCATES a 64-bit
# HANDLE/HWND - e.g. GetCurrentProcess()'s -1 pseudo-handle became 0xFFFFFFFF and
# EmptyWorkingSet then failed with no error at all (the RAM trim was a no-op).
# Declared once, lazily, and cached.
_api: dict | None = None


def _win() -> dict | None:
    """{k32, user32, psapi} with correct prototypes, or None off-Windows."""
    global _api
    if _api is not None:
        return _api or None
    if not _IS_WIN:
        _api = {}
        return None
    try:
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        psapi = ctypes.windll.psapi

        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.GetCurrentProcess.argtypes = []
        k32.GetTickCount.restype = ctypes.c_ulong
        k32.GetTickCount.argtypes = []

        u32.GetForegroundWindow.restype = ctypes.c_void_p
        u32.GetForegroundWindow.argtypes = []
        u32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_ulong)]

        psapi.EmptyWorkingSet.restype = ctypes.c_int
        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]

        _api = {"k32": k32, "u32": u32, "psapi": psapi}
        return _api
    except Exception:                                    # pragma: no cover
        _api = {}
        return None


def _kernel32():
    a = _win()
    return a["k32"] if a else None


def _user32():
    a = _win()
    return a["u32"] if a else None


# ─────────────────────────────────────────────────────────────
# Static hardware profile - sensed once, never changes
# ─────────────────────────────────────────────────────────────
_hw_lock = threading.Lock()
_hw: dict | None = None


def hardware() -> dict:
    """{cores, ram_total_mb, tier}. Sensed once and cached for the process.

    tier: "low"      - ≤2 cores or <6 GB RAM   (be gentle, always)
          "balanced" - the mainstream machine
          "high"     - ≥8 cores and ≥16 GB RAM (can afford full cadence)
    """
    global _hw
    if _hw is not None:
        return _hw
    with _hw_lock:
        if _hw is not None:                              # double-checked
            return _hw
        cores = 0
        try:
            cores = os.cpu_count() or 0
        except Exception:                                # pragma: no cover
            cores = 0
        ram_mb = 0
        try:
            st = _MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            k = _kernel32()
            if k and k.GlobalMemoryStatusEx(ctypes.byref(st)):
                ram_mb = int(st.ullTotalPhys / (1024 * 1024))
        except Exception:                                # pragma: no cover
            ram_mb = 0

        if (cores and cores <= 2) or (ram_mb and ram_mb < 6144):
            tier = "low"
        elif cores >= 8 and ram_mb >= 16384:
            tier = "high"
        else:
            tier = "balanced"

        _hw = {"cores": cores, "ram_total_mb": ram_mb, "tier": tier}
        log.info("[perf] hardware: %s", _hw)
        return _hw


def tier() -> str:
    return hardware()["tier"]


# ─────────────────────────────────────────────────────────────
# Live sensing (cached for _SENSE_TTL_S)
# ─────────────────────────────────────────────────────────────
_sense_lock = threading.Lock()
_sense_at   = 0.0
_sense: dict = {}

# CPU% needs two samples of GetSystemTimes - keep the previous one.
_cpu_prev: tuple[int, int, int] | None = None

# The Qt shell can tell us it went to the tray / was minimised. None = unknown,
# and we fall back to sensing the foreground window ourselves.
_explicit_hidden: bool | None = None


def set_hidden(hidden: bool | None) -> None:
    """Called by the shell when the window is minimised / hidden to tray /
    restored. Purely an optimisation - sensing still works without it."""
    global _explicit_hidden, _sense_at
    if hidden == _explicit_hidden:
        return
    _explicit_hidden = hidden
    # INVALIDATE the sense cache. snapshot() memoises for _SENSE_TTL_S, so
    # without this the new visibility would not be observed for up to 2s and the
    # very next poll_interval()/is_dormant() would still answer with the OLD
    # state - which is exactly the tick that should have backed off / trimmed.
    _sense_at = 0.0


def prime() -> None:
    """Take the FIRST CPU sample so the first real reading is a true delta.

    _cpu_percent needs TWO GetSystemTimes samples; without a primed baseline the
    first call returns 0.0 = "machine idle", so the very first poll_multiplier()
    runs at FULL cadence and the first should_defer_heavy() says False - exactly
    during boot / game-load, the heaviest moment. Called once at import; also
    safe to call again. Never raises."""
    try:
        _cpu_percent()
    except Exception:                                    # pragma: no cover
        pass


def _cpu_percent() -> float:
    """System-wide CPU load from GetSystemTimes deltas. 0.0 when unknown."""
    global _cpu_prev
    k = _kernel32()
    if not k:
        return 0.0
    try:
        idle, kern, usr = _FILETIME(), _FILETIME(), _FILETIME()
        if not k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern),
                                ctypes.byref(usr)):
            return 0.0
        cur = (idle.value, kern.value, usr.value)
        prev, _cpu_prev = _cpu_prev, cur
        if prev is None:
            return 0.0
        d_idle = cur[0] - prev[0]
        # NOTE: on Windows `kernel` time ALREADY includes idle time.
        d_total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if d_total <= 0:
            return 0.0
        busy = 100.0 * (1.0 - (d_idle / d_total))
        return max(0.0, min(100.0, busy))
    except Exception:                                    # pragma: no cover
        return 0.0


def _ram() -> tuple[float, int]:
    """(load_percent, available_mb). (0.0, 0) when unknown."""
    k = _kernel32()
    if not k:
        return 0.0, 0
    try:
        st = _MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not k.GlobalMemoryStatusEx(ctypes.byref(st)):
            return 0.0, 0
        return float(st.dwMemoryLoad), int(st.ullAvailPhys / (1024 * 1024))
    except Exception:                                    # pragma: no cover
        return 0.0, 0


def _user_idle_s() -> float:
    """Seconds since the last keyboard/mouse input, system-wide. 0.0 unknown."""
    u, k = _user32(), _kernel32()
    if not (u and k):
        return 0.0
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not u.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        # GetTickCount wraps every ~49.7 days; mask to 32 bits so the delta
        # stays sane across a wrap instead of going hugely negative.
        now = k.GetTickCount() & 0xFFFFFFFF
        delta = (now - (lii.dwTime & 0xFFFFFFFF)) & 0xFFFFFFFF
        return delta / 1000.0
    except Exception:                                    # pragma: no cover
        return 0.0


def _on_battery() -> bool:
    """True when the machine is running on BATTERY (not AC).

    A laptop on battery is the one host where our background work has a cost the
    user actually feels: drain + the thermal downclock that follows. We sensed
    CPU load but never power state, so a tray-idle launcher polled just as
    eagerly on 12% battery as on mains. Unknown/desktop → False (unchanged
    behaviour)."""
    k = _kernel32()
    if not k:
        return False
    try:
        st = _SYSTEM_POWER_STATUS()
        if not k.GetSystemPowerStatus(ctypes.byref(st)):
            return False
        return st.ACLineStatus == 0
    except Exception:                                    # pragma: no cover
        return False


def _is_foreground() -> bool:
    """True when the foreground window belongs to OUR process."""
    u = _user32()
    if not u:
        return True                                      # assume active elsewhere
    try:
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        pid = ctypes.c_ulong(0)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == os.getpid()
    except Exception:                                    # pragma: no cover
        return True


def snapshot(*, force: bool = False) -> dict:
    """Live view of the machine + our app state. Cached for _SENSE_TTL_S.

    Keys: cpu_percent · ram_percent · ram_available_mb · user_idle_s ·
          foreground · state · tier · cores · ram_total_mb
    state ∈ {"active", "background", "idle", "hidden"}
    """
    global _sense_at, _sense
    now = time.time()
    if not force and _sense and (now - _sense_at) < _SENSE_TTL_S:
        return _sense
    with _sense_lock:
        if not force and _sense and (time.time() - _sense_at) < _SENSE_TTL_S:
            return _sense
        cpu = _cpu_percent()
        ram_pct, ram_avail = _ram()
        idle_s = _user_idle_s()
        fg = _is_foreground()
        battery = _on_battery()

        if _explicit_hidden:
            state = "hidden"
        elif idle_s >= _IDLE_AFTER_S:
            state = "idle"
        elif fg:
            state = "active"
        else:
            state = "background"

        hw = hardware()
        _sense = {
            "cpu_percent":      round(cpu, 1),
            "ram_percent":      round(ram_pct, 1),
            "ram_available_mb": ram_avail,
            "user_idle_s":      round(idle_s, 1),
            "foreground":       fg,
            "on_battery":       battery,
            "state":            state,
            "tier":             hw["tier"],
            "cores":            hw["cores"],
            "ram_total_mb":     hw["ram_total_mb"],
        }
        _sense_at = time.time()
        return _sense


# ─────────────────────────────────────────────────────────────
# The adaptive answer every background consumer reads
# ─────────────────────────────────────────────────────────────
# How much to stretch a background interval, per app state.
_STATE_MULT = {
    "active":     1.0,
    "background": 3.0,
    "idle":       6.0,
    "hidden":     8.0,
}

MIN_INTERVAL_MS = 5_000
MAX_INTERVAL_MS = 30 * 60_000        # never sleep longer than 30 min


_game_running = False
_game_run_count = 0            # REFERENCE COUNT, not a bool - see set_game_running
_game_run_lock = threading.Lock()


def set_game_running(running: bool) -> None:
    """The shell calls this around a game launch/exit.

    Inferring it from CPU load (below) is a LAGGING signal - it only kicks in
    once the machine is already pegged, i.e. after the user has felt the stutter.
    Knowing a game is running lets every poller back off from the first second.

    REFERENCE-COUNTED, not a bare bool: `_yield_to_game()` in main_eel.py calls
    True on launch and False (from a background watcher thread) once THAT game's
    process exits. If the user launches a SECOND game while the first is still
    open, both watchers are alive concurrently - a bare bool would let the first
    game's exit clobber the flag to False while the second game is still running,
    silently telling every background poller "nothing is playing" and speeding
    them back up mid-session. Counting launches/exits keeps it True until the
    LAST tracked game has actually exited.
    """
    global _game_running, _game_run_count
    with _game_run_lock:
        _game_run_count = max(0, _game_run_count + (1 if running else -1))
        _game_running = _game_run_count > 0


def game_running() -> bool:
    return _game_running


def poll_multiplier() -> float:
    """Multiply a base background interval by this. 1.0 = full speed."""
    s = snapshot()
    m = _STATE_MULT.get(s["state"], 1.0)

    # A game is ON. Nothing we do in the background is worth a frame - this is
    # the strongest back-off in the function, and unlike the CPU heuristic it
    # applies from the moment of launch instead of after the machine is pegged.
    if _game_running:
        m *= 6.0

    # A busy machine almost always means a GAME is running - the single most
    # important moment NOT to steal CPU. Back off hard, even in the foreground.
    if s["cpu_percent"] >= _CPU_PEGGED:
        m *= 3.0
    elif s["cpu_percent"] >= _CPU_BUSY:
        m *= 2.0

    # Memory pressure - do less work, hold fewer buffers.
    if s["ram_percent"] >= _RAM_TIGHT:
        m *= 1.5

    # A weak machine is permanently gentler; a strong idle one can stay snappy.
    if s["tier"] == "low":
        m *= 1.5
    elif s["tier"] == "high" and s["state"] == "active":
        m *= 0.85

    # On BATTERY every avoidable wake costs the user runtime (and invites a
    # thermal downclock). Ease off - more so when nobody is even looking.
    if s.get("on_battery"):
        m *= 2.0 if s["state"] == "active" else 3.0

    return max(0.5, min(60.0, m))


def poll_interval(base_ms: int) -> int:
    """The adaptive interval (ms) for a background job whose full-speed cadence
    is `base_ms`. Clamped so we never spin hot and never sleep forever."""
    try:
        v = int(base_ms * poll_multiplier())
    except Exception:                                    # pragma: no cover
        return int(base_ms)
    return max(MIN_INTERVAL_MS, min(MAX_INTERVAL_MS, v))


def should_defer_heavy() -> bool:
    """True when NOW is a bad moment for an expensive job (a deep drive scan, a
    big download, a mod apply). The caller should postpone rather than compete
    with whatever is loading the machine."""
    s = snapshot()
    if s["cpu_percent"] >= _CPU_PEGGED:
        return True
    if s["ram_available_mb"] and s["ram_available_mb"] < 512:
        return True
    return False


def is_dormant() -> bool:
    """True when nobody is looking at us (tray / AFK) - safe to release RAM and
    skip non-essential work entirely."""
    return snapshot()["state"] in ("idle", "hidden")


# ─────────────────────────────────────────────────────────────
# Real-time RAM reduction
# ─────────────────────────────────────────────────────────────
_last_trim = 0.0
_TRIM_COOLDOWN_S = 60.0


def trim_memory(*, force: bool = False) -> bool:
    """Hand our idle working set back to Windows RIGHT NOW.

    `EmptyWorkingSet` asks the OS to page out what we aren't actively touching.
    The pages come back on demand, so this costs nothing but a few soft faults
    the next time the user opens the window - and it is exactly what drops the
    launcher's resident RAM while it sits in the tray behind a game.

    Rate-limited (once a minute) so it can be called freely from a poll tick.
    Returns True when a trim was actually issued. Never raises.
    """
    global _last_trim
    if not _IS_WIN:
        return False
    now = time.time()
    if not force and (now - _last_trim) < _TRIM_COOLDOWN_S:
        return False
    a = _win()
    if not a:
        return False
    try:
        # Free Python's own garbage first, or we just page out garbage.
        import gc
        gc.collect()
        handle = a["k32"].GetCurrentProcess()            # 64-bit pseudo-handle
        ok = bool(a["psapi"].EmptyWorkingSet(handle))
        _last_trim = now
        if ok:
            log.debug("[perf] working set trimmed")
        return ok
    except Exception:                                    # pragma: no cover
        _last_trim = now
        return False


def on_background_tick() -> None:
    """Convenience for a periodic caller: when we're dormant, release memory.
    Cheap, rate-limited, never raises."""
    try:
        if is_dormant():
            trim_memory()
    except Exception:                                    # pragma: no cover
        pass


# Prime the CPU baseline at import so the first sensed reading is a real delta
# instead of a fake "0% = idle". Cheap (one GetSystemTimes call).
prime()
