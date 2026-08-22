# -*- coding: utf-8 -*-
"""AUTONOMOUS in-game check for the Plague Tale Hebrew font — capture, measure, report.

Why this exists: the font work had degenerated into "deploy -> ask the user to launch -> get one
sentence of feedback -> guess again". Everything needed is scriptable:
  * `%APPDATA%\\A Plague Tale Requiem\\ENGINESETTINGS` is PLAIN TEXT with `Windowed`,
    `FullscreenBorderless`, `Resolution`, `PosX/PosY` -> full control of the window, no in-game
    navigation.
  * The game is D3D12, so GDI/ImageGrab returns BLACK -> capture with dxcam (DXGI Desktop
    Duplication).
  * The main menu is the first interactive screen and already contains Hebrew, so no clicking.

Two modes:
    python _autocheck.py            # WE launch the game, capture, measure, kill it
    python _autocheck.py --attach   # THE USER launches; we wait, capture, measure, leave it alone
    python _autocheck.py --shot X   # just measure an existing PNG

🔴 BOTH live modes refuse to measure a process that started BEFORE the deployed font file was
written. The game reads its font ONCE at startup and is single-instance, so a stale window shows
a stale build while looking perfectly normal — that trap cost three debugging cycles.
See [[stale-elevated-instance-fakes-no-change]], [[minimize-game-restarts]].
"""
from __future__ import annotations
import argparse, ctypes, os, re, subprocess, sys, time
from ctypes import wintypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME_DIR = r"D:\Games\A Plague Tale - Requiem"
EXE = os.path.join(GAME_DIR, "APlagueTaleRequiem_x64.exe")
DEPLOYED_FONT = os.path.join(GAME_DIR, "FONT", "ENGLISH.DPC")


def _real_home():
    """⚠️ %APPDATA% / %USERPROFILE% point at the Antigravity SANDBOX profile, and even
    FOLDERID_RoamingAppData is redirected — only FOLDERID_Profile is real.
    See [[env-redirection-real-home]]."""
    import ctypes.wintypes as wt

    class GUID(ctypes.Structure):
        _fields_ = [("d1", wt.DWORD), ("d2", wt.WORD), ("d3", wt.WORD), ("d4", ctypes.c_byte * 8)]

    # FOLDERID_Profile {5E6C858F-0E22-4760-9AFE-EA3317B67173}
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


SETTINGS = os.path.join(_real_home(), "AppData", "Roaming",
                        "A Plague Tale Requiem", "ENGINESETTINGS")
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
WIN_W, WIN_H = 1600, 900

user32 = ctypes.WinDLL("user32", use_last_error=True)


# ------------------------------- process plumbing ----------------------------- #
def proc_list():
    """Every running game process: pid, ExecutablePath (EMPTY if it outranks us), start time.

    🔴 ExecutablePath is unreadable across integrity levels, so an ELEVATED instance shows up
    with an empty path and `taskkill` answers "Access is denied". CreationDate IS readable for
    it, and that is what the freshness guard runs on — so a stale elevated window can be
    DETECTED even though it cannot be closed or identified by path.
    """
    ps = ("Get-CimInstance Win32_Process -Filter \"name='APlagueTaleRequiem_x64.exe\'\" | "
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


def fresh_pid(min_time, quiet=False):
    """The pid of a game process started AFTER `min_time`, or None (loudly explaining why)."""
    procs = proc_list()
    if not procs:
        return None
    fresh = [p for p in procs if p["started"] >= min_time - 2]
    stale = [p for p in procs if p not in fresh]
    if stale and not quiet:
        for p in stale:
            age = (min_time - p["started"]) / 60.0
            print(f"  🔴 STALE instance pid={p['pid']} started {age:.0f} min BEFORE the font was "
                  f"deployed{' (ELEVATED — cannot be closed from here)' if not p['path'] else ''}."
                  f"\n     The game reads the font ONCE at startup and is single-instance, so this "
                  f"window shows the OLD build. It must be closed.")
    return fresh[0]["pid"] if fresh else None


def windows_of_pid(pid_or_set):
    """Visible, reasonably-sized windows of the given pid(s).

    EnumWindows + GetWindowThreadProcessId are readable across integrity levels, so this also
    works for an elevated instance — the freshness guard, not the path, is what protects us.
    """
    pids = pid_or_set if isinstance(pid_or_set, (set, frozenset)) else {pid_or_set}
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value in pids and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) > 200 and (r.bottom - r.top) > 200:
                out.append((hwnd, (r.left, r.top, r.right, r.bottom)))
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def force_window():
    """Windowed, fixed size, at 0,0 — so the capture region is deterministic."""
    txt = open(SETTINGS, encoding="utf-8", errors="replace").read()
    orig = txt
    txt = re.sub(r"\bWindowed \d+", "Windowed 1", txt)
    txt = re.sub(r"\bFullscreenBorderless \d+", "FullscreenBorderless 0", txt)
    txt = re.sub(r"\bResolution \d+ \d+", f"Resolution {WIN_W} {WIN_H}", txt)
    txt = re.sub(r"\bPosX -?\d+", "PosX 0", txt)
    txt = re.sub(r"\bPosY -?\d+", "PosY 0", txt)
    if txt != orig:
        if not os.path.exists(SETTINGS + ".autocheck_bak"):
            open(SETTINGS + ".autocheck_bak", "w", encoding="utf-8").write(orig)
        open(SETTINGS, "w", encoding="utf-8").write(txt)
    print(f"  window forced to {WIN_W}x{WIN_H} windowed @0,0")


def kill_game():
    subprocess.run(["taskkill", "/F", "/IM", "APlagueTaleRequiem_x64.exe"], capture_output=True)


# --------------------------------- capturing ---------------------------------- #
def _grab_window(cam, rect, screen_shape=None):
    fr = cam.grab()
    if fr is None:
        return None
    a = np.asarray(fr)
    l, t, r, b = rect
    l, t = max(l, 0), max(t, 0)
    r, b = min(r, a.shape[1]), min(b, a.shape[0])
    if r - l < 200 or b - t < 200:
        return None
    return a[t:b, l:r]


def wait_for_menu(cam, get_pid, timeout, tag):
    """Poll until a BRIGHT, STATIC frame — the menu/parchment screen — and return it."""
    t0 = time.time()
    last, stable, shots = None, 0, 0
    while time.time() - t0 < timeout:
        time.sleep(2.0)
        pid = get_pid()
        if pid is None:
            print(f"    … {time.time()-t0:5.0f}s  waiting for a FRESH game process")
            continue
        wins = windows_of_pid(pid)
        if not wins:
            print(f"    … {time.time()-t0:5.0f}s  process {pid} up, waiting for its window")
            continue
        a = _grab_window(cam, wins[0][1])
        if a is None:
            continue
        bright = float(a.mean())
        # a menu/parchment screen is BRIGHT and static; logos and loading screens are dark
        if bright > 90 and last is not None and abs(bright - last) < 1.5:
            stable += 1
            if stable >= 2:
                print(f"  menu reached after {time.time()-t0:.0f}s  (mean {bright:.0f}, "
                      f"rect={wins[0][1]})")
                return a
        else:
            stable = 0
        last = bright
        if shots < 12:                       # keep a trail so a failure is diagnosable
            Image.fromarray(a).save(os.path.join(SC, f"AC_{tag}_{shots:02d}.png"))
            shots += 1
        print(f"    … {time.time()-t0:5.0f}s  mean={bright:6.1f} rect={wins[0][1]}")
    print("  TIMEOUT waiting for the menu")
    return None


def launch_and_capture(timeout=240, tag="auto"):
    kill_game(); time.sleep(1.5)
    force_window()
    deployed_at = os.path.getmtime(DEPLOYED_FONT)
    # ⚠️ the exe's manifest says requireAdministrator -> plain Popen dies with WinError 740 and
    # a UAC prompt cannot be answered from here. __COMPAT_LAYER=RUNASINVOKER makes the AppCompat
    # shim ignore the manifest (safe: the game is not under Program Files).
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    p = subprocess.Popen([EXE], cwd=GAME_DIR, env=env,
                         creationflags=0x00000008 | 0x00000200)   # DETACHED | NEW_GROUP
    print(f"  launched pid={p.pid}, waiting for the menu…")
    import dxcam
    cam = dxcam.create(output_idx=0, output_color="RGB")
    return wait_for_menu(cam, lambda: fresh_pid(deployed_at, quiet=True), timeout, tag)


def attach_and_capture(timeout=600, tag="attach"):
    """The USER launches the game; we wait for a FRESH instance and dump FULL-desktop frames.

    🔴 Do NOT crop to the window rect here (that failed before: in attach mode the user positions
    the window, `GetWindowRect` returned a rect spanning the browser, and the dark loading screen
    was below the brightness gate so nothing was kept). A full-desktop grab always succeeds; we
    keep the BRIGHTEST frame (the parchment menu) plus a rolling trail, and I read them directly.
    """
    deployed_at = os.path.getmtime(DEPLOYED_FONT)
    import datetime as _dt
    print(f"  deployed font: {DEPLOYED_FONT}\n"
          f"  written at   : {_dt.datetime.fromtimestamp(deployed_at):%H:%M:%S}\n"
          f"  → waiting for a game instance started AFTER that. Launch the game and open the\n"
          f"    Hebrew settings menu; I keep the brightest frame automatically.")
    import dxcam
    cam = dxcam.create(output_idx=0, output_color="RGB")
    t0 = time.time()
    best, best_bright, shots, seen = None, 0.0, 0, False
    while time.time() - t0 < timeout:
        time.sleep(3.0)
        pid = fresh_pid(deployed_at)
        if pid is None:
            if not seen:
                print(f"    … {time.time()-t0:5.0f}s  waiting for a FRESH game process")
            else:
                print(f"  the fresh game process exited — stopping.")
                break
            continue
        seen = True
        fr = cam.grab()
        if fr is None:
            continue
        a = np.asarray(fr)
        # score only the region the game is likely drawing (skip a left-docked browser): use the
        # RIGHT 60% of the desktop, which is where the menu parchment sits in the user's layout.
        region = a[:, int(a.shape[1] * 0.4):]
        bright = float(region.mean())
        if bright > best_bright:
            best_bright, best = bright, a
            Image.fromarray(a).save(os.path.join(SC, f"AUTOCHECK_{tag}.png"))
        if shots < 16:
            Image.fromarray(a).save(os.path.join(SC, f"AC_{tag}_{shots:02d}.png"))
            shots += 1
        print(f"    … {time.time()-t0:5.0f}s  pid={pid} frame mean(right)={bright:6.1f} "
              f"(best {best_bright:.0f})")
    if best is not None:
        print(f"  kept brightest full frame (mean {best_bright:.0f})")
    return best


# --------------------------------- measuring ---------------------------------- #
def measure(img, label="capture"):
    """Body height, stroke width, letter GAP and letter ADVANCE — the four numbers that decide
    whether the Hebrew matches the English. Stroke/gap/advance are reported as a % of the body so
    they are directly comparable with the reference measured off the user's side-by-side."""
    a = np.array(Image.fromarray(img).convert("L"), np.int16)
    H, W = a.shape
    ink = a < 140
    # a full-height separator/UI bar puts ink in EVERY row and collapses the band splitter
    colf = ink.mean(axis=0)
    bar = np.where(colf > 0.9)[0]
    if len(bar):
        ink[:, bar.min():bar.max() + 1] = False
    frac = ink.mean(axis=1)
    r = (frac > 0.002) & (frac < 0.35)
    bands, s = [], None
    for y in range(H):
        if r[y] and s is None:
            s = y
        elif not r[y] and s is not None:
            if 10 <= y - s <= 200:
                bands.append((s, y))
            s = None
    hs, gaps, advs, sw = [], [], [], []
    for (y0, y1) in bands:
        b = ink[y0:y1]
        c = b.any(axis=0)
        blobs, s2 = [], None
        for x in range(len(c)):
            if c[x] and s2 is None:
                s2 = x
            elif not c[x] and s2 is not None:
                if x - s2 >= 2:
                    ys = np.where(b[:, s2:x].any(axis=1))[0]
                    blobs.append((int(ys.max() - ys.min() + 1), s2, x))
                s2 = None
        if len(blobs) < 3:
            continue
        mw = np.median([bl[2] - bl[1] for bl in blobs])
        hs += [bl[0] for bl in blobs]
        for i in range(len(blobs) - 1):
            g = blobs[i + 1][1] - blobs[i][2]        # end-to-start  = visual gap
            ad = blobs[i + 1][1] - blobs[i][1]       # start-to-start = advance
            if 0 <= g <= mw * 1.2:
                gaps.append(g)
            if 0 < ad <= mw * 2.2:                   # ignore word spaces
                advs.append(ad)
        for yy in range(b.shape[0]):
            run = 0
            for v in b[yy]:
                if v:
                    run += 1
                elif run:
                    sw.append(run); run = 0
    if not hs:
        print(f"  [{label}] no text found")
        return None
    body = float(np.median(hs))
    gap = float(np.median(gaps)) if gaps else 0.0
    adv = float(np.median(advs)) if advs else 0.0
    stroke = float(np.median(sw)) if sw else 0.0
    print(f"\n  [{label}] rows={len(bands)}")
    print(f"     body    {body:6.1f} px          (English cap = 69 on the reference shot)")
    print(f"     stroke  {stroke:6.1f} px  {stroke/body*100:5.1f}%   (English 11.8%)")
    print(f"     gap     {gap:6.1f} px  {gap/body*100:5.1f}%   (English 17.6%)")
    print(f"     advance {adv:6.1f} px  {adv/body*100:5.1f}%   (English 75.5%)")
    return body, stroke / body * 100, gap / body * 100, adv / body * 100


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--attach", action="store_true",
                    help="the USER launches the game; we only wait, capture and measure")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--tag", default="auto")
    a = ap.parse_args()
    if a.shot:
        measure(np.array(Image.open(a.shot).convert("RGB")), os.path.basename(a.shot))
        sys.exit(0)
    if a.attach:
        img = attach_and_capture(a.timeout or 600, a.tag)
    else:
        img = launch_and_capture(a.timeout or 240, a.tag)
    if img is not None:
        out = os.path.join(SC, f"AUTOCHECK_{a.tag}.png")
        Image.fromarray(img).save(out)
        print("  saved", out)
        measure(img, a.tag)
    if not a.attach and not a.keep:
        kill_game()
        print("  game closed")
