# -*- coding: utf-8 -*-
"""AUTONOMOUS in-game check for MSMR — launch, capture, self-verify, close. No user round-trip.

Adapted from games/plague_tale_requiem/work/font/_autocheck.py's proven pattern. Two differences
from that template:
  * MSMR keeps its window/resolution settings in a BINARY per-Steam-profile `-userprefs.save`
    (Documents\\Marvel's Spider-Man Remastered\\<steamid>\\), NOT a plain-text config — this
    project's own rule is to never blind-edit a binary save. So this script does NOT force
    windowed mode; it captures the FULL DESKTOP via dxcam (DXGI Desktop Duplication), which
    works whether the game is exclusive-fullscreen, borderless, or windowed.
  * The log (`Marvel's Spider-Man Remastered.log`) shows the last session ran in Fullscreen —
    dxcam's Desktop Duplication API captures that fine as long as DWM hasn't been fully bypassed
    (true on Win10/11 with the flip model, which every prior game in this project's dxcam usage
    has confirmed).

Modes:
    python 30_autocheck.py            # launch, poll for N seconds, save a frame trail, close
    python 30_autocheck.py --timeout 60
"""
from __future__ import annotations
import argparse, ctypes, os, subprocess, sys, time
from ctypes import wintypes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image

GAME_DIR = r"D:\Games\Spider-man Remastered"
EXE = os.path.join(GAME_DIR, "Spider-Man.exe")
EXE_NAME = "Spider-Man.exe"


def _real_home() -> str:
    """FOLDERID_Profile — %USERPROFILE%/%APPDATA% are redirected in this sandbox.
    See [[env-redirection-real-home]]."""
    class GUID(ctypes.Structure):
        _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD),
                    ("d4", ctypes.c_byte * 8)]
    g = GUID(0x5E6C858F, 0x0E22, 0x4760,
             (ctypes.c_byte * 8)(0x9A, 0xFE, 0xEA, 0x33, 0x17, 0xB6, 0x71, 0x73))
    p = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None,
                                                        ctypes.byref(p)) == 0 and p.value:
            return p.value
    except Exception:
        pass
    return r"C:\Users\Nehoray_Cohen"


SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\77e37445-9937-4b2d-81c1-56e4dca2738b\scratchpad")
os.makedirs(SC, exist_ok=True)

user32 = ctypes.WinDLL("user32", use_last_error=True)


# ------------------------------- process plumbing ----------------------------- #
def proc_list():
    ps = (f"Get-CimInstance Win32_Process -Filter \"name='{EXE_NAME}'\" | "
          "ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)|"
          "$($_.CreationDate.ToString('o'))\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True)
    out = []
    for line in r.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 3 and parts[0].isdigit():
            try:
                import datetime as _dt
                t = _dt.datetime.fromisoformat(parts[2]).timestamp()
            except Exception:
                t = 0.0
            out.append({"pid": int(parts[0]), "path": parts[1].strip(), "started": t})
    return out


def fresh_pid(min_time):
    fresh = [p for p in proc_list() if p["started"] >= min_time - 2]
    return fresh[0]["pid"] if fresh else None


def windows_of_pid(pid):
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) > 200 and (r.bottom - r.top) > 200:
                out.append((hwnd, (r.left, r.top, r.right, r.bottom)))
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], capture_output=True)
    # kill any orphaned Steam-emu / DRM-check helper the exe may have spawned
    subprocess.run(["taskkill", "/F", "/IM", "Spider-Man.exe", "/T"], capture_output=True)


# --------------------------------- capturing ---------------------------------- #
def launch_and_capture(timeout=120, tag="auto", interval=2.0, max_frames=40):
    kill_game()
    time.sleep(1.5)
    t_launch = time.time()

    # ⚠️ if the exe manifest demands admin, a plain Popen dies WinError 740, no UAC answerable
    # here. RUNASINVOKER is a safe no-op if it does NOT require admin.
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    try:
        p = subprocess.Popen([EXE], cwd=GAME_DIR, env=env,
                              creationflags=0x00000008 | 0x00000200)  # DETACHED|NEW_GROUP
        print(f"  launched pid={p.pid}")
    except OSError as e:
        print(f"  [FAIL] launch raised {e!r}")
        return []

    import dxcam
    cam = dxcam.create(output_idx=0, output_color="RGB")

    frames = []
    t0 = time.time()
    pid = None
    while time.time() - t0 < timeout:
        time.sleep(interval)
        if pid is None:
            pid = fresh_pid(t_launch)
            if pid is None:
                print(f"    … {time.time()-t0:5.0f}s  waiting for a fresh process")
                continue
            print(f"    … {time.time()-t0:5.0f}s  process up, pid={pid}")
        else:
            # process may have died (crash) — check
            still = fresh_pid(t_launch)
            if still is None:
                print(f"    … {time.time()-t0:5.0f}s  🔴 process EXITED (crash or closed)")
                break
        fr = cam.grab()
        if fr is None:
            print(f"    … {time.time()-t0:5.0f}s  dxcam grab returned None")
            continue
        a = np.asarray(fr)
        bright = float(a.mean())
        std = float(a.std())
        wins = windows_of_pid(pid) if pid else []
        print(f"    … {time.time()-t0:5.0f}s  frame mean={bright:6.1f} std={std:5.1f} "
              f"windows={len(wins)}")
        if len(frames) < max_frames:
            path = os.path.join(SC, f"MSMR_{tag}_{len(frames):03d}_t{int(time.time()-t0):03d}.png")
            Image.fromarray(a).save(path)
            frames.append(path)
    print(f"  captured {len(frames)} frames over {time.time()-t0:.0f}s")
    return frames


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--tag", default="auto")
    ap.add_argument("--keep", action="store_true", help="don't kill the game at the end")
    a = ap.parse_args()
    frames = launch_and_capture(a.timeout, a.tag, a.interval)
    if not a.keep:
        kill_game()
        print("  game closed")
    print("\nFRAMES:")
    for f in frames:
        print(" ", f)
