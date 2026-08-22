"""Launch Skyrim SE, capture the main menu, close it -- no user needed.

Skyrim is DX11 flip-model, so GDI/ImageGrab returns a black frame: capture with
dxcam (DXGI Desktop Duplication). The main menu background is ANIMATED, so an
"N identical frames" settle never fires -- we wait for the window to stop being
mostly-black and grab a few frames.

env-redirection: %USERPROFILE% inside this sandbox points at the Antigravity
profile, so the real Documents folder is resolved via FOLDERID_Profile.

usage: python autocheck.py shot <out.png> [--seconds 90] [--keep]
       python autocheck.py windowed        # just write the ini, don't launch
       python autocheck.py kill
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

GAME = Path(os.environ.get("SKYRIM_GAME",
                           r"D:\Games\TES - Skyrim - Anniversary Edition"))
EXE = GAME / "SkyrimSE.exe"
WIN_W, WIN_H = 1280, 720


def real_profile() -> Path:
    """FOLDERID_Profile -- %USERPROFILE% is redirected inside this sandbox."""
    from ctypes import windll, c_wchar_p, byref
    from uuid import UUID
    class GUID(ctypes.Structure):
        _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort),
                    ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]
    u = UUID("5E6C858F-0E22-4760-9AFE-EA3317B67173")     # FOLDERID_Profile
    f = u.fields
    g = GUID(f[0], f[1], f[2], (ctypes.c_ubyte * 8)(f[3], f[4], *u.bytes[10:]))
    p = c_wchar_p()
    if windll.shell32.SHGetKnownFolderPath(byref(g), 0, None, byref(p)) != 0:
        return Path(r"C:\Users\Nehoray_Cohen")
    return Path(p.value)


def prefs_dir() -> Path:
    return real_profile() / "Documents" / "My Games" / "Skyrim Special Edition"


def force_windowed() -> Path:
    d = prefs_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = d / "SkyrimPrefs.ini"
    want = {"bFull Screen": "0", "bBorderless": "0",
            "iSize W": str(WIN_W), "iSize H": str(WIN_H),
            "iLocation X": "40", "iLocation Y": "40"}
    if p.exists():
        txt = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out, seen, sect = [], set(), ""
        for ln in txt:
            s = ln.strip()
            if s.startswith("["):
                if sect.lower() == "[display]":
                    for k, v in want.items():
                        if k.lower() not in seen:
                            out.append(f"{k}={v}")
                sect = s
                seen = set()
            elif sect.lower() == "[display]" and "=" in s:
                k = s.split("=", 1)[0].strip()
                if k.lower() in {w.lower() for w in want}:
                    key = next(w for w in want if w.lower() == k.lower())
                    ln = f"{key}={want[key]}"
                    seen.add(k.lower())
            out.append(ln)
        if sect.lower() == "[display]":
            for k, v in want.items():
                if k.lower() not in seen:
                    out.append(f"{k}={v}")
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
    else:
        body = "[Display]\n" + "".join(f"{k}={v}\n" for k, v in want.items())
        p.write_text(body, encoding="utf-8")
    return p


def skip_intro() -> Path | None:
    """[General] sIntroSequence=  -> no Bethesda logo, the menu comes straight up.

    Without this the first non-black frame is the BRIGHT intro logo, which passes
    every "is something rendered yet" heuristic and yields a useless screenshot.
    """
    p = prefs_dir() / "Skyrim.INI"
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if any(l.strip().lower().startswith("sintrosequence") for l in lines):
        return p
    out, done = [], False
    for ln in lines:
        out.append(ln)
        if not done and ln.strip().lower() == "[general]":
            out.append("sIntroSequence=")
            done = True
    if not done:
        out = ["[General]", "sIntroSequence="] + out
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def _tap(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def pids() -> list[int]:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SkyrimSE.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True).stdout
    return [int(l.split('","')[1].strip('"')) for l in out.splitlines() if "SkyrimSE.exe" in l]


def kill() -> None:
    for p in pids():
        subprocess.run(["taskkill", "/F", "/PID", str(p)], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "SkyrimSELauncher.exe"], capture_output=True)


def window_for(pid: int):
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 300 and r.bottom - r.top > 200:
                found.append((hwnd, (r.left, r.top, r.right, r.bottom)))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def shot(out: Path, seconds: int = 120, keep: bool = False, warmup: int = 30) -> int:
    import dxcam
    kill()
    time.sleep(1)
    force_windowed()
    skip_intro()
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    proc = subprocess.Popen([str(EXE)], cwd=str(GAME), env=env,
                            creationflags=subprocess.DETACHED_PROCESS |
                            subprocess.CREATE_NEW_PROCESS_GROUP)
    print(f"launched pid={proc.pid}")
    cam = dxcam.create(output_color="RGB")
    t0 = time.time()
    best = None
    hwnd_rect = None
    while time.time() - t0 < seconds:
        time.sleep(2)
        ps = pids()
        if not ps:
            print(f"  [{int(time.time()-t0):>3}s] no SkyrimSE.exe yet")
            continue
        w = window_for(ps[-1])
        if not w:
            print(f"  [{int(time.time()-t0):>3}s] pid {ps[-1]} alive, no window yet")
            continue
        hwnd_rect = w[1]
        ctypes.windll.user32.SetForegroundWindow(w[0])
        time.sleep(0.4)
        frame = cam.grab(region=hwnd_rect)
        if frame is None:
            continue
        mean = float(frame.mean())
        std = float(frame.std())
        el = time.time() - t0
        print(f"  [{int(el):>3}s] window {hwnd_rect} mean={mean:.1f} std={std:.1f}")
        _tap(0x1B)                          # ESC -- skips any intro movie still playing
        # a bright frame BEFORE `warmup` is the intro logo, not the menu: keep waiting
        if el >= warmup and mean > 12 and std > 12:
            best = frame
            for _ in range(3):              # a few more, the menu fades in
                time.sleep(3)
                f2 = cam.grab(region=hwnd_rect)
                if f2 is not None:
                    best = f2
            break
    del cam
    if best is None:
        print("NO FRAME captured")
        if not keep:
            kill()
        return 1
    from PIL import Image
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(best).save(out)
    print(f"-> {out}  {best.shape}")
    if not keep:
        kill()
        print("game closed")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if cmd == "kill":
        kill(); print("killed")
    elif cmd == "windowed":
        print("wrote", force_windowed())
    else:
        dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("_menu.png")
        secs = int(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 120
        raise SystemExit(shot(dst, secs, "--keep" in sys.argv))
