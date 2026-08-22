"""
Autonomous FC6 launch -> wait-for-menu -> screenshot -> close.
The user is away; we drive the test cycle ourselves (they only look at the saved PNG).

  python fc6_autocheck.py shot <out.png>   # launch, wait for a stable non-black frame, grab, CLOSE
  python fc6_autocheck.py close            # just kill the game

DX12 game -> capture with dxcam (DXGI desktop duplication).  Launch FarCry6.exe
directly (Ubisoft Connect already running); asInvoker via __COMPAT_LAYER so no UAC.
Always closes the game when done so the user can read our messages.
"""
import sys, os, time, subprocess, ctypes
from ctypes import wintypes

GAME = os.environ.get("FC6_GAME", r"F:/Game Lab/Far Cry 6")
EXE = os.path.join(GAME, "bin", "FarCry6.exe")
u32 = ctypes.windll.user32


def _kill():
    subprocess.run(["taskkill", "/F", "/IM", "FarCry6.exe"], capture_output=True)


def _pid():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq FarCry6.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    if "FarCry6.exe" in out:
        try:
            return int(out.split('","')[1].strip('"'))
        except Exception:
            return -1
    return 0


def _launch():
    env = dict(os.environ); env["__COMPAT_LAYER"] = "RUNASINVOKER"
    subprocess.Popen([EXE], cwd=os.path.join(GAME, "bin"), env=env,
                     creationflags=0x00000008 | 0x00000200)


def _fg_is_game(game_pid):
    """True if the foreground window belongs to FarCry6.exe and is ~fullscreen."""
    hwnd = u32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value != game_pid:
        return False
    r = wintypes.RECT(); u32.GetWindowRect(hwnd, ctypes.byref(r))
    sw = u32.GetSystemMetrics(0); sh = u32.GetSystemMetrics(1)
    return (r.right - r.left) >= sw * 0.8 and (r.bottom - r.top) >= sh * 0.8


def _sendkey(vk):
    u32.keybd_event(vk, 0, 0, 0); time.sleep(0.05); u32.keybd_event(vk, 0, 2, 0)


def _mean_std(img):
    import numpy as np
    a = img.astype("float32"); return float(a.mean()), float(a.std())


def shot(out):
    import dxcam
    from PIL import Image
    if _pid():
        print("already running -> killing first"); _kill(); time.sleep(3)
    print("launching FarCry6.exe ..."); _launch()
    t0 = time.time()
    gp = 0
    # 1) wait for the game process + its window to be foreground fullscreen
    while time.time() - t0 < 150:
        time.sleep(2)
        gp = _pid()
        if gp <= 0:
            continue
        if _fg_is_game(gp):
            print(f"[{int(time.time()-t0)}s] game window is foreground fullscreen")
            break
    else:
        print("game never came to foreground"); _kill(); print("closed"); return
    # 2) skip intro / press-any-key: tap Space + Enter a few times over ~30s
    cam = dxcam.create(output_color="RGB")
    last_good = None; last_mean = None; stable = 0
    while time.time() - t0 < 260:
        if _pid() <= 0:
            print("process gone"); break
        for vk in (0x20, 0x0D, 0x1B):   # Space, Enter, Esc
            if _fg_is_game(gp):
                _sendkey(vk)
        time.sleep(3)
        f = cam.grab()
        if f is not None:
            last_good = f
            mean, std = _mean_std(f)
            state = "black" if mean < 6 else ("flat" if std < 12 else "content")
            print(f"[{int(time.time()-t0)}s] mean={mean:.1f} std={std:.1f} {state} fg={_fg_is_game(gp)}")
            if state == "content" and _fg_is_game(gp):
                if last_mean is not None and abs(mean - last_mean) < 1.5:
                    stable += 1
                else:
                    stable = 0
                last_mean = mean
                if stable >= 3 and time.time() - t0 > 45:  # settled menu, past intro
                    print("menu settled"); break
        else:
            print(f"[{int(time.time()-t0)}s] (no new frame)")
    # final grab (keep last_good if static -> grab None)
    time.sleep(1)
    f = cam.grab()
    if f is not None:
        last_good = f
    del cam
    if last_good is not None:
        Image.fromarray(last_good).save(out); print("SAVED", out, last_good.shape)
    else:
        print("NO FRAME captured")
    print("closing game ..."); _kill(); time.sleep(2)
    print("game closed" if not _pid() else "WARNING still running")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if cmd == "close":
        _kill(); print("killed")
    else:
        shot(sys.argv[2] if len(sys.argv) > 2 else "fc6_shot.png")
