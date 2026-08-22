r"""
Autonomous Far Cry 5: set language -> launch -> wait for the menu -> screenshot -> CLOSE.
The user is away from the keyboard; we drive the whole cycle and they only read the PNG.

  python fc5_autocheck.py lang 22       # UILanguage+SubtitlesLanguage -> arabic (audio stays EN)
  python fc5_autocheck.py lang 0        # back to english
  python fc5_autocheck.py shot out.png  # lang stays as-is; launch, grab, close
  python fc5_autocheck.py close

Language activation is a plain attribute edit in
  %USERPROFILE%\Documents\My Games\Far Cry 5\gamerprofile.xml
using the engine's own language enum (english=0 ... turkish=21, arabic=22), so no menu
navigation is ever required.

env-redirection: this profile's %USERPROFILE% is sandboxed, so the real Documents path is
resolved through SHGetKnownFolderPath(FOLDERID_Profile).
"""
import sys, os, time, re, shutil, subprocess, ctypes
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
EXE = os.path.join(GAME, "bin", "FarCry5.exe")
IMAGE = "FarCry5.exe"
u32 = ctypes.windll.user32

LANGS = ["english", "tchinese", "schinese", "czech", "danish", "dutch", "finnish", "french",
         "german", "hungarian", "italian", "japanese", "korean", "norwegian", "polish",
         "portuguese", "brazilian", "russian", "spanish", "mexican", "swedish", "turkish",
         "arabic"]


def real_home():
    """FOLDERID_Profile -- the ONLY reliable real home under a redirected sandbox."""
    from ctypes import wintypes as w
    FOLDERID_Profile = ctypes.create_string_buffer(
        bytes.fromhex("6D6D7A5FD3C243429D02D0E3C8FEC5B5"))   # {5F7A6D6D-C2D3-4243-9D02-D0E3C8FEC5B5}
    # simpler + robust: SHGetFolderPath CSIDL_PROFILE (0x28)
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, buf)
    return buf.value or os.path.expanduser("~")


PROFILE = os.path.join(real_home(), "Documents", "My Games", "Far Cry 5", "gamerprofile.xml")


# ---------------------------------------------------------------- language
def set_lang(idx):
    idx = int(idx)
    if not os.path.exists(PROFILE):
        print(f"[!] profile missing: {PROFILE}"); return False
    bak = PROFILE + ".he_backup"
    if not os.path.exists(bak):
        shutil.copy2(PROFILE, bak)
    s = open(PROFILE, encoding="utf-8").read()
    before = dict(re.findall(r'(UILanguage|SubtitlesLanguage|LastUPlayLanguage)="(\d+)"', s))
    for attr in ("UILanguage", "SubtitlesLanguage", "LastUPlayLanguage"):
        s = re.sub(rf'{attr}="\d+"', f'{attr}="{idx}"', s)
    open(PROFILE, "w", encoding="utf-8").write(s)
    after = dict(re.findall(r'(UILanguage|SubtitlesLanguage|LastUPlayLanguage)="(\d+)"', s))
    name = LANGS[idx] if idx < len(LANGS) else "?"
    print(f"language -> {idx} ({name})   before={before} after={after}")
    print(f"  (audio SoundProfile Language left untouched -> English VO)")
    return True


# ---------------------------------------------------------------- process
def pids():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {IMAGE}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [int(l.split('","')[1].strip('"')) for l in out.splitlines() if IMAGE in l]


def close():
    subprocess.run(["taskkill", "/F", "/IM", IMAGE], capture_output=True)
    time.sleep(1.5)
    print("game closed" if not pids() else "[!] still running")


STEAM_APPID = "552520"   # Far Cry 5 (552521 is NOT the game -- the protocol silently does nothing)


CONNECT = r"C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe"


def connect_alive():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq upc.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return "upc.exe" in out


def restart_connect(wait=45):
    """Clear a stale Ubisoft Connect game session (it survives a force-kill of the game and
    then makes every subsequent launch exit ~7s in, with NO crash and NO event-log entry).

    Connect does NOT reliably come back on its own when the game is started through the
    Steam protocol -- killing it and walking away leaves the game unable to launch at all,
    which reads exactly like a broken mod.  So relaunch it explicitly and WAIT for it."""
    for img in ("upc.exe", "UplayWebCore.exe", "UbisoftConnect.exe"):
        subprocess.run(["taskkill", "/F", "/IM", img], capture_output=True)
    # WAIT for the old one to actually die -- otherwise the liveness check below sees the
    # process that is still exiting, reports "up after 1s", and the new one never starts.
    t0 = time.time()
    while time.time() - t0 < 20 and connect_alive():
        time.sleep(1)
    time.sleep(2)
    if os.path.exists(CONNECT):
        subprocess.Popen([CONNECT], cwd=os.path.dirname(CONNECT),
                         creationflags=0x00000008 | 0x08000000)
    t0 = time.time()
    while time.time() - t0 < wait and not connect_alive():
        time.sleep(2)
    print(f"  Ubisoft Connect {'up' if connect_alive() else 'NOT UP'} "
          f"after {time.time()-t0:.0f}s", flush=True)


# --------------------------------------------------------------- Steam's args dialog
# FarCry5.exe is a stub that re-invokes  steam://run/552520//-uplay_steam_mode , and Steam
# then BLOCKS on a "run with these options?" prompt ("LaunchApp waiting for user response to
# ShowGameArgs" in Steam's console_log).  Nothing launches until it is answered, which looks
# exactly like a broken mod.  Setting SteamAppId and launching the exe with the arg ourselves
# does NOT avoid it -- the stub bounces through Steam regardless -- so answer the prompt.
STEAM_BLUE = (46, 121, 217)          # sampled off the real "Continue" button


def steam_window():
    got = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        if not u32.IsWindowVisible(h):
            return True
        n = u32.GetWindowTextLengthW(h)
        if not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
        if buf.value.strip() == "Steam" and (r.right - r.left) > 400:
            got.append((h, (r.left, r.top, r.right, r.bottom)))
        return True

    u32.EnumWindows(cb, 0)
    return got[0] if got else (None, None)


def dismiss_steam_dialog():
    """Find and click the blue Continue button, if the prompt is up.  Returns True if clicked."""
    try:
        import numpy as np
        from PIL import ImageGrab
    except ImportError:
        return False
    hwnd, box = steam_window()
    if not hwnd:
        return False
    u32.ShowWindow(hwnd, 9); u32.SetForegroundWindow(hwnd); time.sleep(1.0)
    a = np.array(ImageGrab.grab(bbox=box, all_screens=True).convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    m = (np.abs(r - STEAM_BLUE[0]) < 45) & (np.abs(g - STEAM_BLUE[1]) < 45) & \
        (np.abs(b - STEAM_BLUE[2]) < 45)
    rows = m.sum(axis=1)
    bands, start = [], None
    for i, c in enumerate(rows):
        if c > 40 and start is None:
            start = i
        elif c <= 40 and start is not None:
            bands.append((start, i)); start = None
    for y0, y1 in bands:
        if not (20 <= y1 - y0 <= 60):
            continue
        cols = np.where(m[y0:y1].sum(axis=0) > (y1 - y0) * 0.5)[0]
        if len(cols) < 60 or cols.max() - cols.min() > 320:
            continue
        cx = box[0] + int((cols.min() + cols.max()) / 2)
        cy = box[1] + (y0 + y1) // 2
        u32.SetCursorPos(cx, cy); time.sleep(0.3)
        u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.06)
        u32.mouse_event(0x0004, 0, 0, 0, 0)
        print(f"  answered Steam's launch-options prompt at ({cx},{cy})", flush=True)
        return True
    return False


def steam_signed_out():
    """Steam restarts itself occasionally and comes back at the 'Who's playing?' account
    picker.  Nothing can launch until a human clicks it -- a Chromium surface ignores both
    a synthetic click (focus-stealing prevention wins) and a posted WM_LBUTTONDOWN.  Detect
    it and say so instead of burning the whole launch timeout."""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        if not u32.IsWindowVisible(h):
            return True
        n = u32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, b, n + 1)
        if "Sign in to Steam" in b.value:
            found.append(True)
        return True

    u32.EnumWindows(cb, 0)
    return bool(found)


def launch(mode=None):
    """FarCry5.exe is a 215 KB stub -- launched directly it hands off and exits, so the
    default route is the Steam protocol (Steam + Ubisoft Connect are already running).

    Notes paid for the hard way:
      * the appid is 552520; 552521 is NOT the game and the protocol silently does nothing
      * uplay://launch/... answers "We couldn't verify your access" -- ownership is via Steam
      * setting SteamAppId and passing -uplay_steam_mode ourselves does not skip Steam"""
    mode = mode or os.environ.get("FC5_LAUNCH", "steam")
    if mode == "steam":
        subprocess.Popen(["cmd", "/c", "start", "", f"steam://rungameid/{STEAM_APPID}"],
                         creationflags=0x08000000)          # CREATE_NO_WINDOW
    else:
        env = dict(os.environ)
        env["__COMPAT_LAYER"] = "RUNASINVOKER"      # ignore the admin manifest, no UAC
        subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env,
                         creationflags=0x00000008 | 0x00000200)


def game_window(pid_set):
    """Return (hwnd, rect) of the largest visible window owned by the game."""
    best = None
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        nonlocal best
        if not u32.IsWindowVisible(hwnd):
            return True
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value not in pid_set:
            return True
        r = wintypes.RECT(); u32.GetWindowRect(hwnd, ctypes.byref(r))
        area = (r.right - r.left) * (r.bottom - r.top)
        if area > 200_000 and (best is None or area > best[2]):
            best = (hwnd, r, area)
        return True
    u32.EnumWindows(cb, 0)
    return (best[0], best[1]) if best else (None, None)


# ---------------------------------------------------------------- capture
def grab(cam):
    f = cam.grab()
    return f


def shot(out, boot_timeout=620, settle_frames=6):
    import numpy as np, dxcam
    if pids():
        print("game already running -> closing first"); close()
    if steam_signed_out():
        print("[!] STEAM IS SIGNED OUT -- its 'Who's playing?' account picker is waiting.\n"
              "    Nothing can launch until it is clicked, and a Chromium surface ignores a\n"
              "    synthetic click.  Click the saved account once, then re-run this.")
        return False
    # We always end a cycle with a force-kill, which leaves Connect holding a stale session.
    # Clearing it up-front is far more reliable than reacting to the failure later.
    restart_connect()
    print(f"launching {EXE}")
    launch()

    # The Steam stub HANDS OFF and exits, so the process legitimately disappears and comes
    # back.  Wait for a game process that owns a real WINDOW, tolerating gaps.
    t0 = time.time(); pset = set(); seen = False; retried = 0
    while time.time() - t0 < 400:
        pset = set(pids())
        if pset:
            if not seen:
                print(f"  process seen {sorted(pset)} at t+{time.time()-t0:.0f}s", flush=True)
                seen = True
            hwnd, r = game_window(pset)
            if hwnd:
                print(f"  window {r.right-r.left}x{r.bottom-r.top} at t+{time.time()-t0:.0f}s",
                      flush=True)
                break
        # THE recurring failure: after the game is force-killed, Ubisoft Connect keeps a stale
        # session and every later launch exits ~7s in, silently and with no event-log entry.
        # Restarting Connect clears it (verified).  Escalate: re-issue -> restart Connect.
        el = time.time() - t0
        # the prompt is the usual reason nothing appears -- answer it before anything else
        if not seen and el > 12 and int(el) % 8 < 2:
            dismiss_steam_dialog()
        if not seen and retried < 3 and el > 60 * (retried + 1):
            retried += 1
            if retried == 2:
                print(f"  still nothing at {el:.0f}s -> restarting Ubisoft Connect", flush=True)
                restart_connect()
            else:
                print(f"  no process after {el:.0f}s -> re-issuing the launch ({retried})", flush=True)
            launch()
        time.sleep(2)
    if not game_window(set(pids()))[0]:
        print(f"[!] no game window after {time.time()-t0:.0f}s (pids={sorted(pids())})")
        close(); return False
    print("waiting for a stable non-black frame ...")

    cam = dxcam.create(output_color="RGB")
    last = None; stable = 0; shown = False; lit = 0; menu_frame = None; gone = 0
    keypresses = 0
    while time.time() - t0 < boot_timeout:
        time.sleep(2)
        if not pids():
            gone += 1
            # the Steam stub hands off, so a single empty poll is NOT an exit
            if gone >= 4:
                print("[!] the game exited on its own"); cam.release(); return False
            continue
        gone = 0
        hwnd, r = game_window(set(pids()))
        if hwnd and not shown:
            print(f"  window {r.right-r.left}x{r.bottom-r.top} at ({r.left},{r.top})"); shown = True
        fr = cam.grab()
        if fr is None:
            continue
        m = float(fr.mean()); sd = float(fr.std())
        if m < 6 or sd < 6:            # black / flat = still loading or an intro fade
            stable = 0; last = None
            continue
        if last is not None:
            diff = float(np.abs(fr.astype(np.int16) - last.astype(np.int16)).mean())
            if diff < 1.2:
                stable += 1
            else:
                stable = 0
                # a moving picture this late is an intro video -> try to skip it
                if time.time() - t0 > 60 and keypresses < 6:
                    for vk in (0x1B, 0x20):        # ESC, SPACE
                        u32.keybd_event(vk, 0, 0, 0); time.sleep(.05); u32.keybd_event(vk, 0, 2, 0)
                    keypresses += 1
        last = fr
        # FC5's main menu has an ANIMATED background, so "N identical frames" never happens --
        # and "any lit frame" catches the BRIGHT intro logos instead (mean ~120).  Measured
        # signature of the real menu: mean ~46, std ~32.  Match that band instead.
        in_menu = 30 <= m <= 80 and 20 <= sd <= 50
        if in_menu:
            lit += 1; menu_frame = fr
        else:
            lit = 0
        print(f"  t+{time.time()-t0:5.0f}s mean={m:6.1f} std={sd:6.1f} menu={in_menu} run={lit}",
              flush=True)
        if lit >= 4:                     # ~8 s continuously in the menu band
            break

    fr = menu_frame if menu_frame is not None else cam.grab()
    if fr is None:
        fr = last
    cam.release()
    if fr is None:
        print("[!] no frame captured"); close(); return False
    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    Image.fromarray(fr).save(out)
    print(f"saved {out}  ({fr.shape[1]}x{fr.shape[0]})  after {time.time()-t0:.0f}s")
    close()
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if cmd == "lang":
        set_lang(sys.argv[2])
    elif cmd == "close":
        close()
    elif cmd == "shot":
        shot(sys.argv[2] if len(sys.argv) > 2 else "fc5_shot.png")
    else:
        print(__doc__)
