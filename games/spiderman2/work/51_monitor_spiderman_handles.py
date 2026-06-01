"""Monitor Spider-Man2.exe — log every file handle it opens that looks
font/UI-related.

Run this BEFORE launching the game. It waits for Spider-Man2.exe to appear,
then dumps all open handles every 2 seconds. The user runs the game, the
script logs what files get opened."""
import os, sys, time, psutil

WANT = ("font", "Font", "FONT",
        ".ttf", ".otf", ".ttc", ".woff",
        "fonts", "Fonts", "FONTS",
        "Azbuka", "Heebo", "NotoSans", "Segoe", "Arial",
        "Tahoma", "Adobe Arabic", "Sakkal", "Aldhabi",
        ".bff", ".fnt", ".cff", ".cff2",
        "d\\font", "d/font", "d\\userinterface")

EXCLUDE = ("\\Mods Library\\", "\\Profiles\\", ".dll", ".exe",
           ".pdb", ".log", ".ini", ".cfg", "\\d\\mods\\mod")

print(f"[*] waiting for Spider-Man2.exe ...", flush=True)
proc = None
while not proc:
    for p in psutil.process_iter(['name', 'pid']):
        try:
            if p.info['name'] == "Spider-Man2.exe":
                proc = p
                break
        except: pass
    if not proc: time.sleep(0.5)
print(f"[+] found Spider-Man2.exe pid={proc.pid}", flush=True)

seen = set()
end_time = time.time() + 180   # monitor for 3 minutes max
while time.time() < end_time:
    try:
        if not proc.is_running():
            print("[!] process exited", flush=True)
            break
        files = proc.open_files()
        for f in files:
            path = f.path
            if path in seen: continue
            if any(x in path for x in EXCLUDE): continue
            if any(w in path for w in WANT) or path.lower().endswith(('.ttf','.otf','.ttc','.woff','.woff2','.font','.bff')):
                seen.add(path)
                print(f"  FONT? {path}", flush=True)
            elif "Marvel" in path or "SM2" in path or "Spider" in path:
                if path not in seen:
                    seen.add(path)
                    print(f"  game: {path}", flush=True)
        time.sleep(2)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"[!] {e}", flush=True)
        break

print(f"\n[*] done. seen {len(seen)} unique paths.", flush=True)
print("\n=== all paths matching font tokens ===", flush=True)
for p in sorted(seen):
    print(f"  {p}", flush=True)
