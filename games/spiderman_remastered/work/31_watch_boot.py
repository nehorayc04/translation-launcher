# -*- coding: utf-8 -*-
"""Watch a fresh MSMR launch to distinguish "still loading" from "actually hung": tail the
game's OWN log file (which keeps growing while it's genuinely progressing) alongside periodic
desktop captures, for up to `--timeout` seconds. Does NOT force-kill on timeout (--keep-like by
default) so a slow-but-alive process is never mistaken for a hang.
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
LOG = r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man Remastered\Marvel's Spider-Man Remastered.log"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\77e37445-9937-4b2d-81c1-56e4dca2738b\scratchpad")
os.makedirs(SC, exist_ok=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


def proc_list():
    ps = (f"Get-CimInstance Win32_Process -Filter \"name='{EXE_NAME}'\" | "
          "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate.ToString('o'))\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True)
    out = []
    for line in r.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 2 and parts[0].isdigit():
            import datetime as _dt
            try:
                t = _dt.datetime.fromisoformat(parts[1]).timestamp()
            except Exception:
                t = 0.0
            out.append({"pid": int(parts[0]), "started": t})
    return out


def related_procs():
    """Any process whose name suggests it belongs to this game's launch chain — catches a
    hung helper (crs-handler.exe, steamclient64, etc) that our own taskkill never targets."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match "
          "'Spider-Man|crs-|steamclient|steam_api|GFSDK|NxApp' } | "
          "ForEach-Object { \"$($_.ProcessId)|$($_.Name)\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True)
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], capture_output=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=360)
    ap.add_argument("--poll", type=float, default=8.0)
    ap.add_argument("--tag", default="watch")
    ap.add_argument("--nokill", action="store_true")
    ap.add_argument("--stall-limit", type=float, default=90.0)
    ap.add_argument("--no-compat", action="store_true",
                     help="launch WITHOUT __COMPAT_LAYER=RUNASINVOKER (test whether that "
                          "override itself is what's causing the hang)")
    a = ap.parse_args()

    kill_game()
    time.sleep(1.5)
    log_pos_before = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    env = dict(os.environ)
    if not a.no_compat:
        env["__COMPAT_LAYER"] = "RUNASINVOKER"
    print(f"launching with __COMPAT_LAYER={'RUNASINVOKER' if not a.no_compat else '(unset — plain launch)'}")
    p = subprocess.Popen([EXE], cwd=GAME_DIR, env=env,
                          creationflags=0x00000008 | 0x00000200)
    t_launch = time.time()
    print(f"launched pid={p.pid}, log was {log_pos_before} B before launch")

    import dxcam
    cam = dxcam.create(output_idx=0, output_color="RGB")

    last_log_size = log_pos_before
    last_growth_t = time.time()
    shots = 0
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        time.sleep(a.poll)
        elapsed = time.time() - t0
        procs = [pp for pp in proc_list() if pp["started"] >= t_launch - 2]
        alive = bool(procs)
        sz = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        grew = sz - last_log_size
        if grew > 0:
            last_log_size = sz
            last_growth_t = time.time()
        stall = time.time() - last_growth_t
        fr = cam.grab()
        bright = float(np.asarray(fr).mean()) if fr is not None else -1
        rel = related_procs()
        print(f"  t={elapsed:6.0f}s  alive={alive!s:5}  log={sz:9d}B (+{grew:5d})  "
              f"log_stall={stall:5.0f}s  frame_mean={bright:6.1f}  procs={rel}")
        if shots < 60:
            path = os.path.join(SC, f"MSMR_{a.tag}_{shots:03d}_t{int(elapsed):04d}.png")
            if fr is not None:
                Image.fromarray(np.asarray(fr)).save(path)
            shots += 1
        if not alive:
            print("  process EXITED — stopping watch")
            break
        if stall > a.stall_limit and elapsed > a.stall_limit:
            print(f"  🔴 log has not grown in {stall:.0f}s while the process is still alive "
                  f"— likely a genuine hang, not a slow load. Stopping watch.")
            break

    print(f"\nfinal: log grew {last_log_size - log_pos_before} B total")
    if not a.nokill:
        kill_game()
        print("game closed")
