"""
Launch FC6 -> wait for the main menu -> scan the RUNNING process memory for the
font(s) actually loaded -> identify them -> close.  Read-only (ReadProcessMemory).

Answers: is the menu font one of the archive fonts (editable) or a unique font
packed in the Denuvo dll (not editable)?
"""
import sys, os, time, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc6_autocheck as A
import fc6_memdump as M


def wait_menu(timeout=280):
    A._kill(); time.sleep(3)
    print("launching ..."); A._launch()
    t0 = time.time(); gp = 0
    while time.time() - t0 < 150:
        time.sleep(2); gp = A._pid()
        if gp > 0 and A._fg_is_game(gp):
            print(f"[{int(time.time()-t0)}s] game foreground"); break
    else:
        return 0
    # skip intro + wait for a settled menu
    import dxcam
    cam = dxcam.create(output_color="RGB"); lastm = None; stable = 0
    while time.time() - t0 < timeout:
        for vk in (0x20, 0x0D, 0x1B):
            if A._fg_is_game(gp):
                A._sendkey(vk)
        time.sleep(3)
        f = cam.grab()
        if f is None:
            continue
        import numpy as np
        m = float(f.astype("float32").mean())
        if m > 20:
            if lastm is not None and abs(m - lastm) < 1.5:
                stable += 1
            else:
                stable = 0
            lastm = m
            if stable >= 3 and time.time() - t0 > 40:
                print(f"[{int(time.time()-t0)}s] menu settled"); break
    del cam
    return gp


def scan(gp):
    h = M.open_proc(gp)
    # 1) which archive font NAMES are resident?
    names = [b"Noto Kufi Arabic", b"TT Commons Ubisoft", b"TitlingGothicFB",
             b"Benguiat Pro ITC", b"Noto Sans Thai", b"DFGHSGothic", b"MDChamGothic",
             b"Adihaus", b"Arial", b"Segoe", b"Myriad", b"Din", b"DIN", b"Frutiger",
             b"Roboto", b"Helvetica"]
    print("--- resident font-name strings (utf8 & utf16) ---")
    for nm in names:
        cnt8 = cnt16 = 0
        for base, size in M.regions(h):
            d = M.read(h, base, size)
            if not d:
                continue
            cnt8 += d.count(nm)
            cnt16 += d.count(nm.decode().encode("utf-16-le"))
            if cnt8 + cnt16 > 0 and cnt8 + cnt16 > 200:
                break
        if cnt8 or cnt16:
            print(f"   {nm.decode():22} utf8={cnt8} utf16={cnt16}")
    # 2) any OTHER font family name near a 'name' table? scan for sfnt headers in RAM
    print("--- sfnt/wOFF font blobs resident (first 12) ---")
    found = 0
    for base, size in M.regions(h):
        if found >= 12:
            break
        d = M.read(h, base, size)
        if not d:
            continue
        for mg in (b"\x00\x01\x00\x00", b"OTTO", b"wOFF", b"true"):
            i = d.find(mg)
            while i >= 0 and found < 12:
                try:
                    if mg != b"wOFF":
                        nt = struct.unpack_from(">H", d, i + 4)[0]
                        if 4 <= nt <= 40 and d[i+12:i+16] in (b"GDEF", b"GPOS", b"GSUB", b"OS/2", b"cmap", b"CFF ", b"FFTM", b"DSIG"):
                            print(f"   sfnt blob @ region {base:#x}+{i:#x} tag0={d[i+12:i+16]}")
                            found += 1
                except Exception:
                    pass
                i = d.find(mg, i + 1)
    print(f"sfnt blobs found: {found}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    gp = wait_menu()
    if gp <= 0:
        print("no menu"); A._kill(); sys.exit()
    print(f"scanning RAM of pid {gp} ...")
    try:
        scan(gp)
    finally:
        print("closing game ..."); A._kill(); time.sleep(2)
        print("closed" if not A._pid() else "still running")
