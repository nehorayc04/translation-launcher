"""GDI-based watch (ImageGrab, not dxcam) -- dxcam's Desktop Duplication capture was proven
to fail/return black during this machine's DX12 exclusive-fullscreen transitions (cross-check
2026-08-10: dxcam mean=0.12 "black" while a simultaneous GDI grab showed mean=82.4, a perfectly
normal lit Marvel logo frame). GDI is slower and can't capture a TRUE exclusive-fullscreen
surface either in general, but empirically it succeeded where dxcam failed here -- use it for
any further MSMR capture work instead of dxcam.

Sends a periodic Enter to clear confirmation dialogs (Launcher, Sony privacy consent) and
watches log growth + GDI frame brightness.
"""
from __future__ import annotations
import argparse, ctypes, os, subprocess, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image, ImageGrab

GAME_DIR = r"D:\Games\Spider-man Remastered"
EXE = os.path.join(GAME_DIR, "Spider-Man.exe")
EXE_NAME = "Spider-Man.exe"
LOG = r"C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man Remastered\Marvel's Spider-Man Remastered.log"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\77e37445-9937-4b2d-81c1-56e4dca2738b\scratchpad")
os.makedirs(SC, exist_ok=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
VK_RETURN = 0x0D


def press_enter():
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.08)
    user32.keybd_event(VK_RETURN, 0, 2, 0)


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], capture_output=True)


def proc_alive(t_launch):
    ps = (f"Get-CimInstance Win32_Process -Filter \"name='{EXE_NAME}'\" | "
          "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate.ToString('o'))\" }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                        capture_output=True, text=True)
    import datetime as _dt
    for line in r.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) >= 2 and parts[0].isdigit():
            try:
                t = _dt.datetime.fromisoformat(parts[1]).timestamp()
            except Exception:
                t = 0.0
            if t >= t_launch - 2:
                return True
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-before-click", type=float, default=10.0)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--poll", type=float, default=8.0)
    ap.add_argument("--enter-every", type=float, default=22.0)
    ap.add_argument("--tag", default="gdi")
    a = ap.parse_args()

    kill_game()
    time.sleep(1.5)
    log_before = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    p = subprocess.Popen([EXE], cwd=GAME_DIR, creationflags=0x00000008 | 0x00000200)
    t_launch = time.time()
    print(f"launched pid={p.pid}")
    time.sleep(a.wait_before_click)
    print("sending first Enter (Launcher)...")
    press_enter()

    last_log = log_before
    last_growth_t = time.time()
    last_enter_t = time.time()
    shots = 0
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        time.sleep(a.poll)
        elapsed = time.time() - t0
        alive = proc_alive(t_launch)
        sz = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        grew = sz - last_log
        if grew > 0:
            last_log = sz
            last_growth_t = time.time()
        stall = time.time() - last_growth_t
        fr = ImageGrab.grab()
        arr = np.asarray(fr.convert("RGB"))
        bright = float(arr.mean())
        print(f"  t={elapsed:6.0f}s  alive={alive!s:5}  log={sz:9d}B (+{grew:5d})  "
              f"log_stall={stall:5.0f}s  gdi_mean={bright:6.1f}")
        if shots < 40:
            path = os.path.join(SC, f"MSMR_{a.tag}_{shots:03d}_t{int(elapsed):04d}.png")
            fr.save(path)
            shots += 1
        if not alive:
            print("  process EXITED")
            break
        if a.enter_every > 0 and time.time() - last_enter_t >= a.enter_every:
            print("    -> sending another Enter")
            press_enter()
            last_enter_t = time.time()

    print(f"\nfinal: log grew {last_log - log_before} B total since launch")
    kill_game()
    print("game closed")
