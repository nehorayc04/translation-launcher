# -*- coding: utf-8 -*-
"""Extract + serialize ALL game languages' SUBTITLES (base + ep1) into TEMP, resumable.
Extraction of one lang's 3,085 subtitle CR2W = ~6s; serialize = the slow part.
Uses one `convert serialize <subtitles-root>` per lang (recursive). Read-only vs the game.
Run in background; a separate assembler builds the panel. Resumable via .extracted/.serialized markers.
"""
import json, os, subprocess, time
from pathlib import Path

GAME = r"C:\Game Lab\Cyberpunk 2077"
CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_subpanel")
# gender-strong languages first so the fleet can start on well-covered lines sooner
LANGS = ["ar","ru","pl","cs","es-es","es-mx","fr","it","pt","de",
         "ja","ko","zh-cn","zh-tw","tr","th","hu","ua","en"]

def run(args, timeout):
    try:
        r = subprocess.run([CLI]+args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, (r.stdout or "")+(r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT {timeout}s"
    except Exception as e:
        return False, str(e)

def log(m):
    line = f"[{time.strftime('%F %T')}] {m}"
    print(line, flush=True)

def do(scope, lang):
    arch = os.path.join(GAME, "archive", "pc",
                        "content" if scope=="base" else "ep1", f"lang_{lang}_text.archive")
    if not os.path.exists(arch):
        log(f"{scope}/{lang}: no archive, skip"); return
    ex = WORK / scope / lang
    ex.mkdir(parents=True, exist_ok=True)
    # 1) extract subtitles CR2W
    if not (ex/".extracted").exists():
        ok, out = run(["extract", arch, "-o", str(ex), "-w", "*subtitles*"], 600)
        if not ok:
            log(f"{scope}/{lang}: EXTRACT FAIL {out[-150:]}"); return
        (ex/".extracted").touch()
    # locate the subtitles root (loc folder name varies: ru-ru, cz-cz, ar-ar ...)
    roots = [p for p in ex.rglob("subtitles") if p.is_dir()]
    if not roots:
        log(f"{scope}/{lang}: no subtitles dir"); return
    subroot = roots[0]
    n_cr2w = sum(1 for _ in subroot.rglob("*.json") if not _.name.endswith(".json.json"))
    # 2) serialize the whole subtitles tree (recursive)
    if not (ex/".serialized").exists():
        t0=time.time()
        ok, out = run(["convert","serialize",str(subroot),"-w","*.json"], 7200)
        n_out = sum(1 for _ in subroot.rglob("*.json.json"))
        log(f"{scope}/{lang}: serialized {n_out}/{n_cr2w} in {time.time()-t0:.0f}s  ok={ok}")
        if n_out >= n_cr2w*0.9:
            (ex/".serialized").touch()
        else:
            log(f"{scope}/{lang}: LOW yield ({n_out}/{n_cr2w}) — NOT recursive? tail={out[-150:]}")
    else:
        log(f"{scope}/{lang}: already serialized")

def main():
    WORK.mkdir(parents=True, exist_ok=True)
    for scope in ("base","ep1"):
        for lang in LANGS:
            do(scope, lang)
    log("ALL SUBTITLE EXTRACTION DONE")

if __name__ == "__main__":
    main()
