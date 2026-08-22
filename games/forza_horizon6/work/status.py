"""FH6 install health check — run this AFTER EVERY update step.

Reports the version marker, whether the exe/fonts/language packs are intact,
and (once a *.xxh128 manifest exists) how many manifest files are missing.
A patch that "finished" but left something broken shows up here immediately,
which is how the previous install silently ended up unusable.
"""
import os, re, sys, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fh6_zip as Z
import fh6_str as S

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
ST = os.path.join(GAME, "media", "Stripped", "StringTables")

print("=" * 62)
print("Forza Horizon 6 —", GAME)
print("=" * 62)

# --- version marker ---------------------------------------------------------
cfg = os.path.join(GAME, "MicrosoftGame.config")
ver = "?"
if os.path.exists(cfg):
    m = re.search(r'<Identity[^>]*Version="([^"]+)"', open(cfg, encoding="utf-8-sig").read())
    ver = m.group(1) if m else "?"
print(f"  version marker            {ver}      (target: 2.403.798.0)")

# --- the files that were broken last time -----------------------------------
exe = os.path.join(GAME, "forzahorizon6.exe")
print(f"  forzahorizon6.exe         {'OK  ' + format(os.path.getsize(exe), ',') + ' B' if os.path.exists(exe) else 'MISSING  <-- game cannot launch'}")

for rel in (r"media\ObjectModelGame.zip", r"media\Audio\DialogueLength.xml"):
    p = os.path.join(GAME, rel)
    print(f"  {rel:<25s} {'OK' if os.path.exists(p) else 'MISSING'}")

fonts = os.path.join(GAME, "media", "UI", "Fonts.zip")
if os.path.exists(fonts):
    ents, pay = Z.read(fonts)
    bad = [n for n, v in pay.items() if not v]
    print(f"  media\\UI\\Fonts.zip        {len(ents)} entries, "
          f"{'ALL READABLE' if not bad else f'{len(bad)} UNREADABLE -> {bad[:4]}'}")
else:
    print("  media\\UI\\Fonts.zip        MISSING")

# --- language packs ---------------------------------------------------------
langs = sorted(f[:-4] for f in os.listdir(ST)) if os.path.isdir(ST) else []
print(f"\n  language packs            {len(langs)}/24  {' '.join(langs)}")
bad_lang, counts = [], set()
for L in langs:
    try:
        _, pay = Z.read(os.path.join(ST, L + ".zip"))
        n = sum(1 for k, v in pay.items() if S.is_table(k) and not v)
        tot = sum(len(S.parse(v)) for k, v in pay.items() if S.is_table(k) and v)
        counts.add(tot)
        if n:
            bad_lang.append(f"{L}({n})")
    except Exception as e:                                   # noqa: BLE001
        bad_lang.append(f"{L}(ERR {type(e).__name__})")
print(f"  broken tables             {'none' if not bad_lang else ' '.join(bad_lang)}")
print(f"  entries per language      {sorted(counts)}   (v354.221=57518, v403.798=58179)")

# --- manifest, once an update ships one ------------------------------------
man = sorted(glob.glob(os.path.join(GAME, "*.xxh128")))
if man:
    miss = 0
    for line in open(man[-1], encoding="utf-8", errors="replace"):
        if " *" in line and not os.path.exists(
                os.path.join(GAME, line.rstrip("\n").split(" *", 1)[1].replace("/", os.sep))):
            miss += 1
    print(f"\n  manifest {os.path.basename(man[-1]):<22s} {miss} missing "
          f"(700-ish = per-language audio, that is normal for an English-only install)")
else:
    print("\n  no *.xxh128 manifest yet (it ships with a later update)")

print("\n  mod deployed:",
      "YES" if os.path.exists(os.path.join(ST, "GB.zip.he_backup")) else "no (clean)")
