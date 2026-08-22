"""Marvel's Spider-Man Remastered (MSMR) — THE FONT GATE.

READ-ONLY against D:\\Games\\Spider-man Remastered.

Stages (each independently runnable via argv):
  control  - prove the sfnt validator + fontTools work on a KNOWN-GOOD font
             (never claim a negative without a positive control)
  strings  - mine Spider-Man.exe + the game DLLs for font-path / font-name hints
  paths    - resolve candidate font asset paths by crc64 against the MSMR toc
  analyze  - extract every resolved font asset, detect the sfnt offset (0/8/12/36
             or a scan of the first 64 bytes), parse with fontTools, report
             family / outline format (glyf vs CFF) / cmap coverage of
             Hebrew U+05D0..U+05EA, Latin, Arabic, and the bidi controls
  config   - locate + dump the UI font-map / font-fallback config asset
  scan     - fallback: extract every toc asset in the font size band and test
             for an sfnt magic (slow; use --limit / --archives)

Engine: Insomniac "Luna". MSMR toc = magic 0x77AF12AF, zlib(DAT1),
VERSION_MSMR (12-byte SizeEntry: always1/value/index -> NO header_offset field,
unlike RCRA's 16-byte RcraSizeEntry). Archives may be DSAR-compressed, so a raw
byte scan of the archive file is NOT reliable -- everything goes through
dat1lib.extract_asset.
"""
import os, re, sys, io, json, struct, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"D:\Games\Spider-man Remastered"
ARCH = os.path.join(GAME, "asset_archive")
TOC  = os.path.join(ARCH, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman_remastered", "extract", "fonts")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import dat1lib, dat1lib.types.toc, dat1lib.crc64 as crc64
from fontTools.ttLib import TTFont

SFNT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")
KNOWN_TAGS = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
              b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
              b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF", b"fpgm", b"prep",
              b"cvt ", b"gasp", b"kern", b"VDMX", b"LTSH", b"hdmx", b"morx"}
BIDI_CONTROLS = [0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x061C]


# ------------------------------------------------------------------ sfnt utils
def sfnt_dir_ok(buf, j):
    """Structural table-directory sanity check at offset j. Returns (ntables,
    known_tag_count, max_extent) or None. The magic alone matches huge amounts
    of random binary -- this is the filter that makes a hit believable."""
    if buf[j:j+4] not in SFNT_MAGICS:
        return None
    if j + 12 > len(buf):
        return None
    nt = struct.unpack(">H", buf[j+4:j+6])[0]
    if not (4 <= nt <= 64):
        return None
    if j + 12 + nt*16 > len(buf):
        return None
    known, mx = 0, 0
    for k in range(nt):
        rec = buf[j+12 + k*16: j+12 + (k+1)*16]
        tag = rec[:4]
        if not all(0x20 <= b <= 0x7E for b in tag):
            return None
        off, ln = struct.unpack(">II", rec[8:16])
        if tag in KNOWN_TAGS:
            known += 1
        mx = max(mx, off + ln)
    if known < 5:
        return None
    return (nt, known, mx)


def find_sfnt_offset(data):
    """Where does the real sfnt start inside this asset blob?
    Tries the usual Insomniac wrapper sizes first, then a byte scan of the head."""
    for cand in (0, 8, 12, 36):
        if sfnt_dir_ok(data, cand):
            return cand
    for cand in range(0, min(len(data), 512) - 4):
        if sfnt_dir_ok(data, cand):
            return cand
    return None


def analyze_font(raw, label):
    """Full report on one font blob. Returns dict or None."""
    off = find_sfnt_offset(raw)
    if off is None:
        return None
    info = sfnt_dir_ok(raw, off)
    body = raw[off:]
    rec = {"label": label, "sfnt_offset": off, "blob_len": len(raw),
           "ntables": info[0], "known_tags": info[1], "declared_extent": info[2],
           "magic": body[:4].hex()}
    try:
        f = TTFont(io.BytesIO(body), lazy=False, fontNumber=0)
    except Exception as ex:
        rec["fonttools_error"] = f"{type(ex).__name__}: {ex}"
        return rec
    rec["tables"] = sorted(t if isinstance(t, str) else t.decode() for t in f.keys())
    rec["outline"] = "glyf(TrueType)" if "glyf" in f else ("CFF(PostScript)" if ("CFF " in f or "CFF2" in f) else "?")
    try:
        nm = f["name"]
        def g(nid):
            r = nm.getDebugName(nid)
            return r if r else ""
        rec["family"] = g(1); rec["subfamily"] = g(2)
        rec["fullname"] = g(4); rec["postscript"] = g(6)
    except Exception:
        rec["family"] = rec["subfamily"] = rec["fullname"] = rec["postscript"] = "?"
    try:
        cm = f.getBestCmap()
    except Exception as ex:
        cm = {}
        rec["cmap_error"] = str(ex)
    cps = set(cm.keys())
    rec["numGlyphs"] = f["maxp"].numGlyphs if "maxp" in f else -1
    rec["cmap_total"] = len(cps)

    def cov(lo, hi):
        return sum(1 for cp in cps if lo <= cp <= hi)
    rec["hebrew_letters"] = cov(0x05D0, 0x05EA)      # /27  the 22+5 final letters
    rec["hebrew_block"]   = cov(0x0590, 0x05FF)      # /112 incl. niqqud/punct
    rec["arabic"]         = cov(0x0600, 0x06FF)
    rec["arabic_presf"]   = cov(0xFB50, 0xFEFF)
    rec["latin_upper"]    = cov(0x41, 0x5A)          # /26
    rec["latin_lower"]    = cov(0x61, 0x7A)          # /26
    rec["cyrillic"]       = cov(0x0400, 0x04FF)
    rec["cjk"]            = cov(0x4E00, 0x9FFF)
    rec["hangul"]         = cov(0xAC00, 0xD7AF)
    rec["kana"]           = cov(0x3040, 0x30FF)
    rec["bidi_controls"]  = {hex(cp): (cp in cps) for cp in BIDI_CONTROLS}
    rec["hebrew_cps"] = [hex(cp) for cp in sorted(cps) if 0x0590 <= cp <= 0x05FF]
    try:
        f.close()
    except Exception:
        pass
    return rec


def print_font(rec):
    if rec is None:
        print("      !! no valid sfnt table directory found in blob")
        return
    if "fonttools_error" in rec:
        print(f"      sfnt@{rec['sfnt_offset']} magic={rec['magic']} !! fontTools: {rec['fonttools_error']}")
        return
    print(f"      sfnt@{rec['sfnt_offset']} magic={rec['magic']} tables={rec['ntables']} "
          f"outline={rec['outline']} glyphs={rec['numGlyphs']}")
    print(f"      Family={rec['family']!r} Sub={rec['subfamily']!r} PS={rec['postscript']!r}")
    print(f"      cmap={rec['cmap_total']}  HEB(05D0-05EA)={rec['hebrew_letters']}/27  "
          f"HEBblock={rec['hebrew_block']}/112  ARA={rec['arabic']}  ARApres={rec['arabic_presf']}")
    print(f"      LAT_up={rec['latin_upper']}/26 LAT_lo={rec['latin_lower']}/26 CYR={rec['cyrillic']} "
          f"CJK={rec['cjk']} HANGUL={rec['hangul']} KANA={rec['kana']}")
    bc = ",".join(k for k, v in rec["bidi_controls"].items() if v) or "none"
    print(f"      bidi controls present: {bc}")
    if rec["hebrew_cps"]:
        print(f"      hebrew cps: {rec['hebrew_cps'][:40]}")


# ------------------------------------------------------------------ stage: control
def stage_control():
    print("=" * 78)
    print("STAGE 0 - CONTROL (prove the tooling on a KNOWN-GOOD font)")
    print("=" * 78)
    ctl = os.path.join(ROOT, "games", "spiderman2", "extracted", "_heebo", "Heebo-Regular.ttf")
    print(f"[*] control font: {ctl} exists={os.path.exists(ctl)}")
    if not os.path.exists(ctl):
        print("[!] control font missing - CANNOT trust any negative result below")
        return False
    raw = open(ctl, "rb").read()
    rec = analyze_font(raw, "CONTROL Heebo-Regular")
    print_font(rec)
    ok = rec and rec.get("hebrew_letters", 0) == 27
    print(f"[{'+' if ok else '!'}] control {'PASSED' if ok else 'FAILED'} "
          f"(expect 27/27 Hebrew letters)")
    # negative control: random bytes must NOT validate
    import hashlib
    junk = hashlib.sha512(b"junk").digest() * 200
    print(f"[+] negative control: sfnt_dir_ok on junk -> {find_sfnt_offset(junk)} (expect None)")
    return ok


# ------------------------------------------------------------------ stage: strings
FONT_RE = re.compile(rb"[ -~]{4,220}")
HINT = re.compile(rb"(?i)(\.ttf|\.otf|\.ttc|\.woff|font|glyph|typeface|azbuka|frutiger|"
                  rb"proxima|avenir|helvetica|arial|noto|myriad|sie-tb|magicspell|kdream|"
                  rb"myinghei|melle|fallback)")

def stage_strings(dump=True):
    print("\n" + "=" * 78)
    print("STAGE 1 - STRING MINE the exe + DLLs for font hints")
    print("=" * 78)
    targets = [os.path.join(GAME, "Spider-Man.exe"),
               os.path.join(GAME, "gattaca.dll"),
               os.path.join(GAME, "crs-client.dll"),
               os.path.join(GAME, "liblipsync_tltb64.dll"),
               os.path.join(GAME, "_SSE Fix", "peterpider.dll")]
    found = {}
    for p in targets:
        if not os.path.exists(p):
            print(f"[-] missing {p}")
            continue
        data = open(p, "rb").read()
        hits = []
        for m in FONT_RE.finditer(data):
            s = m.group()
            if HINT.search(s):
                hits.append((m.start(), s.decode("latin-1")))
        # also UTF-16LE strings
        u16 = []
        for m in re.finditer(rb"(?:[ -~]\x00){4,200}", data):
            s = m.group().decode("utf-16-le", "replace")
            if HINT.search(s.encode("latin-1", "replace")):
                u16.append((m.start(), s))
        print(f"\n[*] {os.path.basename(p)} ({len(data):,} B): {len(hits)} ascii + {len(u16)} utf16 font-ish strings")
        found[os.path.basename(p)] = {"ascii": hits, "utf16": u16}
        if dump:
            seen = set()
            for off, s in hits + u16:
                key = s.strip()
                if key in seen or len(key) < 4:
                    continue
                seen.add(key)
                if re.search(r"(?i)\.(ttf|otf|ttc)\b|fonts?/|font_|_font|fallback", key):
                    print(f"    [{off:>10}] {key!r}")
    outp = os.path.join(OUT, "_exe_font_strings.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump({k: {"ascii": v["ascii"], "utf16": v["utf16"]} for k, v in found.items()},
                  f, ensure_ascii=False, indent=1)
    print(f"\n[+] full string dump -> {outp}")
    return found


# ------------------------------------------------------------------ toc helpers
_TOC = None
def get_toc():
    global _TOC
    if _TOC is None:
        with open(TOC, "rb") as f:
            _TOC = dat1lib.read(f)
        _TOC.set_archives_dir(ARCH)
    return _TOC


def arch_names(t):
    out = {}
    for i, a in enumerate(t.get_archives_section().archives):
        try:
            out[i] = bytes(a.filename).split(b"\x00")[0].decode("ascii", "ignore")
        except Exception:
            out[i] = "?"
    return out


# ------------------------------------------------------------------ stage: paths
PREFIXES = [
    "",
    "fonts/",
    "font/",
    "ui/fonts/",
    "ui/font/",
    "ui/loaded/authored/_common/fonts/",
    "ui/loaded/authored/_common/font/",
    "ui/loaded/authored/_common/",
    "ui/loaded/authored/fonts/",
    "ui/loaded/fonts/",
    "loaded/authored/_common/fonts/",
    "authored/_common/fonts/",
    "_common/fonts/",
    "userinterface/fonts/",
    "conduit/fonts/",
    "conduit/",
    "ui/",
]
NAMES = [
    # Insomniac house faces seen in SM2 / R&C
    "AzbukaPro-Regular.ttf", "AzbukaPro-Medium.ttf", "AzbukaPro-Bold.ttf",
    "AzbukaPro-Black.ttf", "AzbukaPro-Light.ttf",
    "NeueFrutigerArabic-Regular.ttf", "NeueFrutigerArabic-Bold.ttf",
    "MagicSpellJF.otf",
    "proximanova_regular_normal.ttf", "proximanova_bold_normal.ttf",
    "proximanova_semibold_normal.ttf", "proximanova_light_normal.ttf",
    "proximanova_black_normal.ttf",
    # CJK / platform fallbacks (R&C names)
    "cs/MYingHeiPRC-W4.ttf", "ct/MElleHK-Medium.ttf",
    "jp/SIE-TBGoStdR-Normal.ttf", "kr/AsiaKDREAM2-R.ttf",
    "SIE-TBGoStdR-Normal.ttf", "SIE-TBGoStdB-Normal.ttf",
    "MYingHeiPRC-W4.ttf", "MElleHK-Medium.ttf", "AsiaKDREAM2-R.ttf",
]
CONFIG_PATHS = [
    "configs/uiconfig/uifontmap.config",
    "configs/uiconfig/fontmap.config",
    "configs/ui/uifontmap.config",
    "configs/uiconfig/uiconfig.config",
    "ui/fontmap.config",
    "configs/uiconfig/uifontfallback.config",
    "configs/uiconfig/localization.config",
    "configs/localization/localization.config",
]


def try_path(t, path):
    aid = crc64.hash(path)
    ents = [e for e in (t.get_asset_entries_by_assetid(aid, stop_on_first=True) or []) if e]
    return aid, ents


def stage_paths(extra_names=None):
    print("\n" + "=" * 78)
    print("STAGE 2 - resolve candidate FONT paths by crc64 against the MSMR toc")
    print("=" * 78)
    t = get_toc()
    an = arch_names(t)
    sizes = t.get_sizes_section()
    print(f"[*] archives={len(an)} assets={len(t.get_assets_section().ids)} "
          f"sizes={len(sizes.entries)} sizeentry={type(sizes.entries[0]).__name__}")

    # POSITIVE CONTROL: the localization path is known to resolve
    ctl_path = "localization/localization_all.localization"
    aid, ents = try_path(t, ctl_path)
    print(f"[control] {ctl_path!r} aid=0x{aid:016X} -> {len(ents)} entries "
          f"({'PASS' if ents else 'FAIL - crc64 lookup broken!'})")

    names = list(NAMES) + list(extra_names or [])
    seen = set()
    names = [n for n in names if not (n in seen or seen.add(n))]
    hits = []
    for name in names:
        for pre in PREFIXES:
            p = pre + name
            aid, ents = try_path(t, p)
            if ents:
                e = ents[0]
                print(f"[+] {p!r}\n      aid=0x{aid:016X} idx={e.index} archive={e.archive}"
                      f"({an.get(e.archive,'?')}) offset={e.offset} size={e.size}")
                hits.append({"path": p, "aid": aid, "index": e.index,
                             "archive": e.archive, "archive_name": an.get(e.archive, "?"),
                             "offset": e.offset, "size": e.size})
                break
        else:
            print(f"[-] {name}: no prefix variant matched")
    outp = os.path.join(OUT, "_path_hits.json")
    json.dump(hits, open(outp, "w"), indent=1)
    print(f"\n[+] {len(hits)} font path hits -> {outp}")
    return hits


# ------------------------------------------------------------------ stage: analyze
def stage_analyze(hits=None):
    print("\n" + "=" * 78)
    print("STAGE 3 - EXTRACT + ANALYZE every resolved font asset")
    print("=" * 78)
    if hits is None:
        p = os.path.join(OUT, "_path_hits.json")
        hits = json.load(open(p)) if os.path.exists(p) else []
    if not hits:
        print("[-] no path hits to analyze")
        return []
    t = get_toc()
    recs = []
    for h in hits:
        try:
            raw = bytes(t.extract_asset(t.get_asset_entry_by_index(h["index"])))
        except Exception as ex:
            print(f"[!] {h['path']}: extract failed {ex}")
            continue
        print(f"\n[*] {h['path']}  idx={h['index']} size={len(raw)} head={raw[:16].hex()}")
        rec = analyze_font(raw, h["path"])
        print_font(rec)
        fn = os.path.join(OUT, os.path.basename(h["path"]).replace("/", "_") + ".rawasset")
        open(fn, "wb").write(raw)
        if rec:
            rec.update(h)
            recs.append(rec)
    json.dump(recs, open(os.path.join(OUT, "_font_report.json"), "w"), indent=1)
    return recs


# ------------------------------------------------------------------ stage: config
def stage_config():
    print("\n" + "=" * 78)
    print("STAGE 4 - locate the UI font-map / fallback CONFIG asset")
    print("=" * 78)
    t = get_toc()
    an = arch_names(t)
    found = []
    for p in CONFIG_PATHS:
        aid, ents = try_path(t, p)
        status = f"{len(ents)} entries" if ents else "-"
        print(f"  0x{aid:016X}  {p!r} -> {status}")
        if ents:
            raw = bytes(t.extract_asset(ents[0]))
            fn = os.path.join(OUT, p.replace("/", "_"))
            open(fn, "wb").write(raw)
            print(f"    [+] {len(raw)} B archive={ents[0].archive}({an.get(ents[0].archive,'?')}) -> {fn}")
            strs = set()
            for m in re.finditer(rb"[ -~]{3,200}", raw):
                strs.add(m.group().decode("latin-1"))
            for s in sorted(strs):
                if re.search(r"(?i)\.(ttf|otf|ttc)|font|lang|fallback", s):
                    print(f"       {s!r}")
            found.append(p)
    return found


# ------------------------------------------------------------------ stage: scan
def stage_scan(lo=12000, hi=8_000_000, limit=None, only_archives=None):
    """Fallback: walk every toc asset in the font size band, extract just the head,
    and test for an sfnt table directory. Slow but exhaustive + DSAR-safe."""
    print("\n" + "=" * 78)
    print(f"STAGE 5 - BRUTE SCAN toc assets in size band [{lo},{hi}] for sfnt")
    print("=" * 78)
    t = get_toc()
    an = arch_names(t)
    ids = t.get_assets_section().ids
    sizes = t.get_sizes_section().entries
    offs = t.get_offsets_section().entries
    cand = []
    for i in range(len(ids)):
        v = sizes[i].value
        if lo <= v <= hi:
            ai = offs[i].archive_index
            if only_archives is None or ai in only_archives:
                cand.append((i, v, ai))
    print(f"[*] {len(cand):,} candidate assets of {len(ids):,} "
          f"(archives: {sorted(set(a for _,_,a in cand))})")
    if limit:
        cand = cand[:limit]
    hits = []
    for n, (i, v, ai) in enumerate(cand):
        if n % 500 == 0:
            print(f"    ...{n}/{len(cand)}  hits={len(hits)}", flush=True)
        try:
            raw = bytes(t.extract_asset(t.get_asset_entry_by_index(i)))
        except Exception:
            continue
        off = find_sfnt_offset(raw[:2048]) if len(raw) > 2048 else find_sfnt_offset(raw)
        if off is None:
            continue
        rec = analyze_font(raw, f"idx{i}")
        if rec is None:
            continue
        rec.update({"index": i, "aid": ids[i], "archive": ai,
                    "archive_name": an.get(ai, "?"), "size": v})
        hits.append(rec)
        print(f"\n[+] SFNT idx={i} aid=0x{ids[i]:016X} archive={ai}({an.get(ai,'?')}) size={v}")
        print_font(rec)
        open(os.path.join(OUT, f"scan_idx{i}.rawasset"), "wb").write(raw)
    json.dump(hits, open(os.path.join(OUT, "_scan_hits.json"), "w"), indent=1, default=str)
    print(f"\n[+] scan done: {len(hits)} fonts")
    return hits


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stages", nargs="*", default=["control", "strings", "paths", "analyze", "config"])
    ap.add_argument("--lo", type=int, default=12000)
    ap.add_argument("--hi", type=int, default=8_000_000)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--archives", type=str, default=None)
    a = ap.parse_args()
    st = a.stages or ["control", "strings", "paths", "analyze", "config"]
    extra = []
    hits = None
    if "control" in st: stage_control()
    if "strings" in st:
        f = stage_strings()
        # harvest any *.ttf/otf names the exe mentions
        for v in f.values():
            for _, s in v["ascii"] + v["utf16"]:
                for m in re.finditer(r"[\w\-. /\\]{1,80}\.(?:ttf|otf|ttc)", s, re.I):
                    extra.append(m.group().strip().replace("\\", "/").lstrip("/"))
        extra = sorted(set(extra))
        if extra:
            print(f"\n[+] harvested {len(extra)} font filenames from binaries:")
            for e in extra[:80]: print(f"    {e!r}")
    if "paths" in st: hits = stage_paths(extra)
    if "analyze" in st: stage_analyze(hits)
    if "config" in st: stage_config()
    if "scan" in st:
        onlyar = set(int(x) for x in a.archives.split(",")) if a.archives else None
        stage_scan(a.lo, a.hi, a.limit, onlyar)
