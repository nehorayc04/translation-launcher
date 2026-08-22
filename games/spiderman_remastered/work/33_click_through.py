"""Launch MSMR, wait for the pre-game "Launcher" overlay to appear, click "Play" to force
past it, then keep watching (log-growth + dxcam) to see whether the REAL game boot
(Insomniac logo -> splash -> main menu) proceeds normally and resolves text correctly --
testing whether the Launcher's raw-key bug is a separate, non-blocking pre-game overlay
issue rather than something that also affects the main engine.
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

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D


def click_at(x, y):
    """Absolute-screen click via SetCursorPos + mouse_event (works across any foreground
    window, no window handle needed -- the Launcher overlay may not be a normal HWND)."""
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def press_enter():
    """Global Enter keypress via keybd_event -- avoids all coordinate-guessing; the
    Launcher's first/highlighted option is very likely 'Play' by default."""
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    time.sleep(0.08)
    user32.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)


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
    ap.add_argument("--wait-before-click", type=float, default=8.0,
                     help="seconds to wait after launch before clicking Play "
                          "(the Launcher overlay needs a moment to render)")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--tag", default="click")
    ap.add_argument("--play-x", type=int, default=612)
    ap.add_argument("--play-y", type=int, default=605)
    ap.add_argument("--enter-every", type=float, default=25.0,
                     help="send another Enter keypress every N seconds during the watch, "
                          "to push through any further confirmation dialogs (privacy "
                          "consent, EULA, etc) without needing exact click coordinates")
    a = ap.parse_args()

    kill_game()
    time.sleep(1.5)
    log_before = os.path.getsize(LOG) if os.path.exists(LOG) else 0

    p = subprocess.Popen([EXE], cwd=GAME_DIR, creationflags=0x00000008 | 0x00000200)
    t_launch = time.time()
    print(f"launched pid={p.pid}")

    import dxcam
    cam = dxcam.create(output_idx=0, output_color="RGB")

    print(f"waiting {a.wait_before_click}s for the Launcher overlay to render...")
    time.sleep(a.wait_before_click)
    fr = cam.grab()
    if fr is not None:
        Image.fromarray(np.asarray(fr)).save(os.path.join(SC, f"MSMR_{a.tag}_before_click.png"))
        print("saved pre-click frame")

    print("pressing Enter (Launcher's default/highlighted option is very likely 'Play')...")
    press_enter()
    time.sleep(1.0)
    fr = cam.grab()
    if fr is not None:
        Image.fromarray(np.asarray(fr)).save(os.path.join(SC, f"MSMR_{a.tag}_after_click.png"))
        print("saved post-click frame")

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
        fr = cam.grab()
        bright = float(np.asarray(fr).mean()) if fr is not None else -1
        print(f"  t={elapsed:6.0f}s  alive={alive!s:5}  log={sz:9d}B (+{grew:5d})  "
              f"log_stall={stall:5.0f}s  frame_mean={bright:6.1f}")
        if shots < 40 and fr is not None:
            path = os.path.join(SC, f"MSMR_{a.tag}_{shots:03d}_t{int(elapsed):04d}.png")
            Image.fromarray(np.asarray(fr)).save(path)
            shots += 1
        if not alive:
            print("  process EXITED")
            break
        if a.enter_every > 0 and time.time() - last_enter_t >= a.enter_every:
            print("    -> sending another Enter (push through any confirmation dialog)")
            press_enter()
            last_enter_t = time.time()

    print(f"\nfinal: log grew {last_log - log_before} B total since launch")
    kill_game()
    print("game closed")
