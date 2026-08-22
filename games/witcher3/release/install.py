# -*- coding: utf-8 -*-
"""The Witcher 3: Wild Hunt - Hebrew translation. Core installer engine.

Driven by the double-click launcher (install_console.py) or from the command line:

    python install.py "D:\\Games\\The Witcher 3"      (install)
    python install.py "D:\\Games\\The Witcher 3" --revert

Everything it touches is backed up first (a sibling `.he_backup`), and `--revert` puts the game
back exactly as it was. Re-running install is safe (idempotent - every op restores the vanilla
backup first, then re-applies).

5 parts, each a separate mechanism the mod had to crack:
  1. TEXT      - writes 34 Hebrew `ar.w3strings` (base + every DLC): ~97,000 lines.
  2. FONTS     - injects 27 Hebrew letters (David) into all 6 faces (fonts_ar + gfxfontlib), r4gui.bundle.
  3. CINEMATICS- the launch recap subtitle is MULTIPLEXED inside the video (recap_wip.usm, CRI Sofdec
                 @SBT stream, channel 14 = the Arabic slot); patched in place. The storybook .subs too.
  4. LANGUAGE  - every other language file's "Arabic" entry is renamed "Hebrew" so a player in any UI
                 can FIND the Hebrew option.
  5. DLC ART   - the expansion banners ship in 5 langs (ch/cz/en/pl/ru) with NO Arabic -> the Arabic
                 locale falls through to CHINESE art; swap two path strings in texture.cache to English.

ACTIVATION: launch -> Options -> Language -> Text = Hebrew. Voice/Speech can stay English.
"""
import os, sys, re, json, glob, struct, shutil, zlib


def _base():
    """Directory that holds the bundled data/ + lib/ - works as a plain script or a frozen exe."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = _base()
sys.path.insert(0, os.path.join(HERE, "lib"))
import potato_bundle as PB
import w3strings as W
import w3strings_patch as WP

DATA = os.path.join(HERE, "data")
BAK = ".he_backup"
LANG_ID = 1084972
LATIN = "Hebrew"
AR_CHANNEL = 14

COMMON = [
    r"C:\Program Files (x86)\Steam\steamapps\common\The Witcher 3",
    r"C:\Program Files\Steam\steamapps\common\The Witcher 3",
    r"C:\GOG Games\The Witcher 3 Wild Hunt GOTY",
    r"D:\Games\The Witcher 3 - Complete Edition",
]

# ---- console BiDi: the Windows console does NOT reorder RTL text, so logical Hebrew shows reversed.
# We pre-reverse (visual order) so it reads correctly: reverse the whole line, then un-reverse the
# Latin/number "islands" so English words and numbers stay readable. A line with no Hebrew is left
# untouched (paths, English menus). Callers keep multi-token Latin / "->" arrows on their OWN lines.
_HEB = re.compile(r"[֐-׿]")
_LTR = re.compile(r"[0-9A-Za-z][0-9A-Za-z .,:;_+\-/\\%=\"'!?]*[0-9A-Za-z]|[0-9A-Za-z]")


def vis(s):
    if not _HEB.search(s):
        return s
    return _LTR.sub(lambda m: m.group(0)[::-1], s[::-1])


def _default_log(m):
    print(vis(str(m)))


def _state_path(game):
    return os.path.join(game, "content", "content0", "_witcher3_hebrew_state.json")


def validate_game(game):
    """-> (ok, reason). A valid W3 install has the Arabic locale slot the mod hijacks."""
    if not game or not os.path.isdir(game):
        return False, "התיקייה לא קיימת."
    ar = os.path.join(game, "content", "content0", "ar.w3strings")
    if not os.path.isfile(ar):
        return False, ("לא נמצא content\\content0\\ar.w3strings בנתיב הזה. "
                       "בחר את תיקיית השורש של המשחק (זו שמכילה content).")
    return True, "ok"


def find_game(argv):
    for a in argv:
        if not a.startswith("-") and os.path.isdir(a):
            return a
    env = os.environ.get("W3_GAME")
    if env and os.path.isdir(env):
        return env
    for c in COMMON:
        if os.path.isfile(os.path.join(c, "content", "content0", "ar.w3strings")):
            return c
    return None


def backup(path):
    b = path + BAK
    if not os.path.exists(b):
        shutil.copy2(path, b)


def _vanilla_bytes(path):
    """Pristine bytes from the .he_backup if present, else the file itself (and save it as the
    backup). Guarantees every op starts from vanilla -> re-install is always safe."""
    b = path + BAK
    if os.path.exists(b):
        return open(b, "rb").read()
    shutil.copy2(path, b)
    return open(path, "rb").read()


# ---------------------------------------------------------------- 1. text
def install_text(game, log):
    man = json.load(open(os.path.join(DATA, "w3strings", "manifest.json"), encoding="utf-8"))
    n = 0
    for m in man:
        dst = os.path.join(game, m["rel"])
        if not os.path.exists(dst):
            continue
        backup(dst)
        shutil.copy2(os.path.join(DATA, "w3strings", m["file"]), dst)
        n += 1
    log(f"  1/5  טקסט: נכתבו {n} קובצי טקסט")


# ---------------------------------------------------------------- 2. fonts (r4gui.bundle)
def _repack(bundle, new_map, base_bytes):
    """Contiguous repack of `base_bytes` (VANILLA); every untouched entry keeps its bytes + pack mode."""
    d = bytearray(base_bytes)
    _fs, _sz, header_sz, _ds = struct.unpack_from("<IIII", d, 8)
    ents = []
    for i in range(header_sz // 320):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})
    ents_off = sorted(ents, key=lambda x: x["offs"])
    data_start = ents_off[0]["offs"]
    out = bytearray(d[:data_start]); cur = data_start
    for e in ents_off:
        pad = (-cur) % 16
        out += b"\x00" * pad; cur += pad
        key = e["name"].lower()
        if key in new_map:
            payload, pack = new_map[key]
            raw = zlib.compress(payload, 9) if pack == 1 else payload
            e["ns"], e["np"] = len(payload), pack
        else:
            raw = bytes(d[e["offs"]:e["offs"] + e["zsize"]])
            e["ns"], e["np"] = e["size"], e["pack"]
        e["no"], e["nz"] = cur, len(raw)
        out += raw; cur += len(raw)
    for e in ents:
        b = e["base"]
        struct.pack_into("<III", out, b + 256 + 16 + 4, e["ns"], e["nz"], e["no"])
        struct.pack_into("<I", out, b + 320 - 4, e["np"])
    struct.pack_into("<I", out, 8, len(out))
    struct.pack_into("<I", out, 12, len(out) - data_start)
    open(bundle, "wb").write(bytes(out))


def install_fonts(game, log):
    bundle = os.path.join(game, "content", "content0", "bundles", "r4gui.bundle")
    vanilla = _vanilla_bytes(bundle)
    new = {}
    _d, ents = PB.list_entries(bundle + BAK)
    for nm in ["fonts_ar.redswf", "gfxfontlib.redswf"]:
        payload = open(os.path.join(DATA, "fonts", nm), "rb").read()
        e = [x for x in ents if x["name"].endswith(nm)][0]
        new[e["name"].lower()] = (payload, 1)
    _repack(bundle, new, vanilla)
    log("  2/5  פונטים: עברית הוזרקה ל-6 פנים")


# ---------------------------------------------------------------- 3. cinematics (movies.bundle)
def install_cinematics(game, log):
    bundle = os.path.join(game, "content", "content0", "bundles", "movies.bundle")
    vanilla = _vanilla_bytes(bundle)
    man = json.load(open(os.path.join(DATA, "subs", "manifest.json"), encoding="utf-8"))
    new = {}
    for m in man:
        payload = open(os.path.join(DATA, "subs", m["file"]), "rb").read()
        new[m["name"].lower()] = (payload, m["pack"])
    _repack(bundle, new, vanilla)
    heb = {int(k): v for k, v in json.load(open(os.path.join(DATA, "recap_usm.json"), encoding="utf-8")).items()}
    d, ents = PB.list_entries(bundle)
    e = [x for x in ents if x["name"].lower().endswith("recap_wip.usm")][0]
    with open(bundle, "rb") as f:
        f.seek(e["offs"]); usm = bytearray(f.read(e["zsize"]))
    pos = n = 0
    while True:
        pos = usm.find(b"@SBT", pos)
        if pos == -1:
            break
        size = struct.unpack_from(">I", usm, pos + 4)[0]
        p0 = pos + 8
        if struct.unpack_from("<I", usm, p0 + 8 + 16)[0] == AR_CHANNEL:
            start = struct.unpack_from(">I", usm, p0 + 8)[0]
            he = heb.get(start)
            if he:
                hb = he.encode("utf-8")
                if len(hb) <= size - 44:
                    struct.pack_into("<I", usm, p0 + 40, len(hb))
                    usm[p0 + 44:p0 + 44 + len(hb)] = hb
                    for i in range(p0 + 44 + len(hb), p0 + size):
                        usm[i] = 0
                    n += 1
        pos += 4
    with open(bundle, "r+b") as f:
        f.seek(e["offs"]); f.write(bytes(usm))
    epi = os.path.join(game, "content", "content0", "movies", "cutscenes", "gamestart", "epilepsy")
    ar, en = os.path.join(epi, "epilepsy_ar.usm"), os.path.join(epi, "epilepsy_en.usm")
    if os.path.exists(ar) and os.path.exists(en) and os.path.getsize(ar) != os.path.getsize(en):
        backup(ar); shutil.copy2(en, ar)
    log(f"  3/5  סרטונים: {len(man)} כתוביות + {n} שורות בסרטון הפתיחה")


# ---------------------------------------------------------------- 4. language selector
def install_langname(game, log):
    n = 0
    for f in sorted(glob.glob(os.path.join(game, "content", "content0", "*.w3strings"))):
        if os.path.basename(f) == "ar.w3strings":
            continue
        raw = _vanilla_bytes(f)
        try:
            d = W.decode(raw)
            if not [e for e in d["entries"] if e["str_id"] == LANG_ID]:
                continue
            new = WP.patch_string(raw, LANG_ID, LATIN)
            ok, _why = WP.verify(raw, new, LANG_ID, LATIN)
        except Exception:
            continue
        if not ok:
            continue
        open(f, "wb").write(new)
        n += 1
    log(f"  4/5  בורר שפה: עברית ב-{n} שפות")


# ---------------------------------------------------------------- 5. DLC banner art
BANNER_PREFIX = rb"gameplay\gui_new\icons\quests\ep_logos"
BANNER_PAIRS = [(b"ep1_logo_ch.png", b"ep1_logo_en.png"), (b"ep2_logo_ch.png", b"ep2_logo_en.png")]


def install_banner(game, log):
    cache = os.path.join(game, "content", "content0", "texture.cache")
    if not os.path.exists(cache):
        log("  5/5  באנרי DLC: לא נמצא - דולג"); return []
    size = os.path.getsize(cache)
    start = max(0, size - 8 * 1024 * 1024)
    with open(cache, "rb") as f:
        f.seek(start); tail = f.read()
    edits = []
    for ch_name, en_name in BANNER_PAIRS:
        pair = []
        for name, cur in ((ch_name, b"ch"), (en_name, b"en")):
            full = BANNER_PREFIX + b"\\" + name
            i = tail.find(full)
            if i < 0 or tail.find(full, i + 1) >= 0:
                pair = []; break
            pair.append(start + i + len(full) - len(b"ch.png"))
        if len(pair) == 2:
            edits.append({"offset": pair[0], "orig": "ch", "new": "en"})
            edits.append({"offset": pair[1], "orig": "en", "new": "ch"})
    if not edits:
        log("  5/5  באנרי DLC: כבר הוחל / לא נמצא - דולג"); return []
    with open(cache, "r+b") as f:
        for e in edits:
            f.seek(e["offset"]); f.write(e["new"].encode())
    log(f"  5/5  באנרי DLC: {len(edits)} נתיבים הוסבו לאנגלית")
    return edits


# ---------------------------------------------------------------- install / revert
def _load_state(game):
    p = _state_path(game)
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return None
    legacy = os.path.join(_app_dir(), "installed.json")
    if os.path.exists(legacy):
        try:
            return json.load(open(legacy, encoding="utf-8"))
        except Exception:
            return None
    return None


def install(game, log=None):
    log = log or _default_log
    ok, why = validate_game(game)
    if not ok:
        raise ValueError(why)
    log("The Witcher 3 - התקנת התרגום לעברית")
    log(game)
    log("")
    prev = _load_state(game)
    install_text(game, log)
    install_fonts(game, log)
    install_cinematics(game, log)
    install_langname(game, log)
    edits = install_banner(game, log)
    banner = edits if edits else ((prev or {}).get("banner") or [])
    tmp = _state_path(game) + ".tmp"
    json.dump({"game": game, "banner": banner}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, _state_path(game))
    log("")
    log("הושלם. במשחק בחר:")
    log("   Options -> Language -> Text = Hebrew")


def revert(game, log=None):
    log = log or _default_log
    ok, why = validate_game(game)
    if not ok:
        raise ValueError(why)
    n = 0
    for f in glob.glob(os.path.join(game, "content", "content*", "*" + BAK)) + \
             glob.glob(os.path.join(game, "dlc", "*", "content", "*" + BAK)) + \
             glob.glob(os.path.join(game, "content", "content0", "bundles", "*" + BAK)) + \
             glob.glob(os.path.join(game, "content", "content0", "movies", "cutscenes", "gamestart",
                                    "epilepsy", "*" + BAK)):
        orig = f[:-len(BAK)]
        shutil.copy2(f, orig); os.remove(f); n += 1
    st = _load_state(game)
    if st and st.get("banner"):
        cache = os.path.join(game, "content", "content0", "texture.cache")
        if os.path.exists(cache):
            with open(cache, "r+b") as fh:
                for e in st["banner"]:
                    fh.seek(e["offset"]); fh.write(e["orig"].encode())
            n += len(st["banner"])
    for p in (_state_path(game), os.path.join(_app_dir(), "installed.json")):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    log(f"בוצע שחזור. {n} פריטים הוחזרו, המשחק חזר למקורי.")


if __name__ == "__main__":
    args = sys.argv[1:]
    g = find_game(args)
    if not g:
        sys.exit('לא נמצא המשחק. הרץ:  python install.py "<נתיב תיקיית המשחק>"')
    if "--revert" in args:
        revert(g)
    else:
        install(g)
