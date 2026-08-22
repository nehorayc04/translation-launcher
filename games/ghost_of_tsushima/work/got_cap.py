# -*- coding: utf-8 -*-
r"""got_cap.py — autonomous launch / screenshot / click / kill for Ghost of Tsushima DC.

Lets THIS session close the in-game verification loop without the user present:
  launch the game, wait for the main menu, grab the window, Read the PNG, assess, iterate.

Ported from games/godofwar_ragnarok/work/{capture,click}.py (proven on GoWR).
Exe = GhostOfTsushima.exe. RUNE crack launches directly (no Steam). Text=Arabic persists
in the registry once set, so the menu shows the Arabic-slot (our Hebrew) with no navigation.

    python got_cap.py launch            # start the game detached (from the game root)
    python got_cap.py wait [out.png]    # poll until the window is big + non-black, then grab
    python got_cap.py shot [out.png] [move]   # one grab now (move = shove window top-right)
    python got_cap.py click <fx> <fy>   # left-click at fractional window coords
    python got_cap.py key <VK_hex>      # send a virtual-key press (scan-code SendInput)
    python got_cap.py kill              # taskkill the game
    python got_cap.py ps                # is it running? window rect?

Env: GOT_GAME (default F:/Games/Ghost of Tsushima DC). Run with the repo .venv python (PIL).
"""
import sys, os, ctypes, ctypes.wintypes as wt, time, subprocess

GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
EXE = "GhostOfTsushima.exe"

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
SW = user32.GetSystemMetrics(0)
SH = user32.GetSystemMetrics(1)


def pids():
    o = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE}", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True).stdout
    s = set()
    for l in o.splitlines():
        p = [x.strip('"') for x in l.split('","')]
        if len(p) >= 2 and p[0].lower().startswith("ghost"):
            try:
                s.add(int(p[1]))
            except ValueError:
                pass
    return s


def win(ps):
    best = [None, 0]
    def cb(h, l):
        if not user32.IsWindowVisible(h):
            return True
        pd = wt.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(pd))
        if pd.value not in ps:
            return True
        r = wt.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
        a = (r.right - r.left) * (r.bottom - r.top)
        if a > best[1]:
            best[0] = h; best[1] = a
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
    return best[0]


def rect(h):
    r = wt.RECT(); user32.GetWindowRect(h, ctypes.byref(r)); return r


_CAM = None


def _dxgrab(bbox):
    """DXGI Desktop Duplication grab of a screen region -> PIL image (captures DX12
    flip-model windows that GDI BitBlt returns black for). Retries for a fresh frame."""
    global _CAM
    import dxcam
    from PIL import Image
    if _CAM is None:
        _CAM = dxcam.create(output_idx=0, output_color="RGB")
    l, t, r, b = bbox
    l = max(0, l); t = max(0, t); r = min(SW, r); b = min(SH, b)
    fr = None
    for _ in range(20):
        fr = _CAM.grab(region=(l, t, r, b))
        if fr is not None:
            break
        time.sleep(0.15)
    if fr is None:
        return None, (l, t, r, b)
    return Image.fromarray(fr), (l, t, r, b)


def grab(h, out, move=False, gdi=False):
    if move:
        r = rect(h); W, H = r.right - r.left, r.bottom - r.top
        user32.SetWindowPos(h, -1, SW - W - 8, 8, 0, 0, 0x0001 | 0x0040)  # NOSIZE|SHOWWINDOW, TOPMOST
        time.sleep(0.6)
    else:
        user32.SetForegroundWindow(h); time.sleep(0.4)
    r = rect(h)
    if gdi:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)
    else:
        img, _ = _dxgrab((r.left, r.top, r.right, r.bottom))
        if img is None:      # fallback
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True)
    img.save(out)
    ex = img.convert("L").getextrema()
    return r, ex


def do_launch():
    if pids():
        print("already running"); return
    exe = os.path.join(GAME, EXE)
    # The exe manifest is requireAdministrator (CreateProcess -> WinError 740). We are NOT elevated
    # and cannot register a Highest-runlevel task (Access denied) or accept a UAC prompt (user away).
    # __COMPAT_LAYER=RUNASINVOKER forces asInvoker, ignoring the manifest -> no UAC, no elevation.
    # GoT is on F:\ (writable) and does not need real admin, so this runs fine.
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    subprocess.Popen([exe], cwd=GAME, env=env,
                     creationflags=0x00000008 | 0x00000200)  # DETACHED|NEW_GROUP
    print(f"launched {exe} (RUNASINVOKER, cwd={GAME})")


def do_wait(out):
    from PIL import ImageGrab
    t0 = time.time()
    while time.time() - t0 < 300:
        ps = pids()
        if not ps:
            print("process gone"); return 2
        h = win(ps)
        if h:
            r = rect(h); W, H = r.right - r.left, r.bottom - r.top
            if W >= 800 and H >= 600:
                r, ex = grab(h, out)
                if ex[1] > 20:   # non-black
                    print(f"MENU ready after {time.time()-t0:.0f}s -> {out} "
                          f"({W}x{H}, lum {ex[0]}..{ex[1]})")
                    return 0
                print(f"  {time.time()-t0:.0f}s: window {W}x{H} but black (lum {ex}), waiting")
        else:
            print(f"  {time.time()-t0:.0f}s: no window yet")
        time.sleep(6)
    print("timeout"); return 1


SC = {  # virtual-key -> scan code for SendInput (menu nav if ever needed)
    "esc": 0x01, "enter": 0x1c, "up": 0x48, "down": 0x50, "left": 0x4b, "right": 0x4d,
    "space": 0x39, "f": 0x21,
}


def do_key(vk):
    h = win(pids());
    if h: user32.SetForegroundWindow(h); time.sleep(0.3)
    code = SC.get(vk.lower())
    if code is None:
        code = int(vk, 16)
    # scancode via keybd_event (0x08 = KEYEVENTF_SCANCODE)
    user32.keybd_event(0, code, 0x0008, 0); time.sleep(0.05)
    user32.keybd_event(0, code, 0x0008 | 0x0002, 0)
    print(f"key {vk} (sc 0x{code:x})")


def main():
    a = sys.argv[1] if len(sys.argv) > 1 else "ps"
    if a == "launch":
        do_launch()
    elif a == "wait":
        sys.exit(do_wait(sys.argv[2] if len(sys.argv) > 2 else "got_menu.png"))
    elif a == "shot":
        out = sys.argv[2] if len(sys.argv) > 2 else "got_menu.png"
        h = win(pids())
        if not h: print("NOT RUNNING / no window"); sys.exit(2)
        r, ex = grab(h, out, move=("move" in sys.argv))
        print(f"captured {out} at ({r.left},{r.top}) {r.right-r.left}x{r.bottom-r.top} lum {ex[0]}..{ex[1]}")
    elif a == "click":
        h = win(pids()); r = rect(h)
        fx, fy = float(sys.argv[2]), float(sys.argv[3])
        x = int(r.left + (r.right - r.left) * fx); y = int(r.top + (r.bottom - r.top) * fy)
        user32.SetForegroundWindow(h); time.sleep(0.4)
        user32.SetCursorPos(x, y); time.sleep(0.25)
        user32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.05); user32.mouse_event(0x0004, 0, 0, 0, 0)
        print(f"clicked ({x},{y})")
    elif a == "key":
        do_key(sys.argv[2])
    elif a == "kill":
        subprocess.run(["taskkill", "/F", "/IM", EXE], capture_output=True)
        print("killed")
    else:
        ps = pids()
        if not ps: print("not running"); return
        h = win(ps); r = rect(h) if h else None
        print(f"running pids={ps} window={'none' if not h else f'{r.right-r.left}x{r.bottom-r.top} @({r.left},{r.top})'}")


if __name__ == "__main__":
    main()
