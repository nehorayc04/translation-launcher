"""FULL Hebrew build for R&C Rift Apart — the shipping mod.

Reads the QA-normalized community translation (hebrew_clean.json), converts every line to
VISUAL storage via the real UBA (rc_rtl.to_visual — bidi=NONE was proven in-game), patches
ALL 32 localization variants (so any in-game language pick shows Hebrew) and bundles the two
Hebrew-injected Proxima Nova fonts. Deploys via the SM2 applier (index-redirect, no repack).

    python 40_build_full.py            # build the .stage + offline-validate
    python 40_build_full.py --deploy   # build + apply to the game (GAME MUST BE CLOSED)
    python 40_build_full.py --revert
"""
import os, sys, io, re, json, struct, zipfile, bisect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.path.insert(0, os.path.join(ROOT, "translation_manager"))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1
import dat1lib.crc32 as c32          # Insomniac CRC32 — hash(key, normalize=False) IS the loc key hash
import rc_rtl

LOCS  = os.path.join(HERE, "..", "extracted", "loc_variants")
FONTS = os.path.join(HERE, "fonts")
HEB   = os.path.join(HERE, "hebrew_clean.json")
OUT   = os.path.join(HERE, "build"); os.makedirs(OUT, exist_ok=True)
STAGE = os.path.join(OUT, "rc_hebrew_full.stage")

LOC_AID, FONT_REG, FONT_BLD = 0xBE55D94F171BF8DE, 0xA2197874D2B7B1AC, 0xB5F411285669C55D
# Sony platform Gothic (system UI: save/profile screens + system dialogs) — round-2 font gate
SIE_REG, SIE_BLD = 0xB927D5EA184444C1, 0x8187C80EF59344DC
# §8b per-surface bidi — and the split is BY KEY, not by span (the launcher and the in-game
# menu read the SAME span 8; the difference is WHICH KEY each reads):
#   • the in-game Pause->Settings menu = cohtml, does NO bidi -> VISUAL. It reads the console-style
#     UPPERCASE variant of every option (proven: it shows the _UPPERCASE 'יחס גודל'/'טריליניארי').
#   • the pre-game Nixxes launcher (Qt) = does its OWN bidi -> LOGICAL. It reads the BASE variant
#     (proven: it shows the base 'שלושה קווים' for trilinear).
# So: a base key that HAS an _UPPERCASE twin is launcher-only -> LOGICAL; the _UPPERCASE twin (and
# _DESC tooltips) are in-game -> VISUAL; a base key with NO twin is used in-game directly -> VISUAL
# (mostly LTR acronyms DLSS/FSR/TAA where bidi is a no-op, plus a couple of audio labels).
SHARED_PCSETTINGS = ("PCGRAPHICSSETTINGS_", "PCDISPLAYSETTINGS_", "PC_", "PCAUDIO")
# launcher-ONLY surfaces (never rendered in-game) -> LOGICAL always.
LAUNCHER_ONLY = ("LAUNCHER_", "SETTINGSCATEGORY_")
TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903
# The engine NEVER looks a string up by its key STRING — it looks it up by HASH:
#   crc32.hash(key, normalize=False) -> bisect into TAG_HASH_SORTED -> TAG_INDEX_MAP[pos] = entry index
# (verified: 24,575/24,575 hashes reproduce exactly, and the map round-trips for every entry).
# So a key can be ADDED to the table as long as we also insert its hash + index-map slot.
TAG_HASH_ENTRY, TAG_HASH_SORTED = 0x06A58050, 0xC43731B5   # u32[cnt]: hash in entry order / sorted
TAG_FLAGS, TAG_INDEX_MAP = 0xB0653243, 0x0CD2CFE9          # u32[cnt] flags / u16[cnt] sorted-pos -> entry
HEADER_SIZE, SECTION_HEADER_SIZE, ALIGN = 16, 12, 16


def cstr(b, o):
    e = b.find(b"\x00", o); return b[o:(e if e >= 0 else len(b))]
def align_up(x, a): return (x + a - 1) // a * a


def rebuild(path, patches, add_keys=()):
    """Rebuild ONE variant DAT1 with {key: value_bytes} applied.

    `add_keys` may name keys that do NOT exist in the shipped table — they are APPENDED
    (key blob + offsets + hash + flags) and their hash is inserted into the sorted-hash /
    index-map pair so the engine's hash lookup finds them. Returns (blob, hits, added)."""
    raw = open(path, "rb").read(); pay = raw[36:]
    d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
    S = {sh.tag: (sh.offset, sh.size) for sh in d.header.sections}
    def sb(t): o, s = S[t]; return pay[o:o + s]
    cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
    kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
    to = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
    ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
    A  = list(struct.unpack(f"<{cnt}I", sb(TAG_HASH_ENTRY)))
    B  = list(struct.unpack(f"<{cnt}I", sb(TAG_HASH_SORTED)))
    C  = list(struct.unpack(f"<{cnt}I", sb(TAG_FLAGS)))
    U  = list(struct.unpack(f"<{cnt}H", sb(TAG_INDEX_MAP)))
    ent = [[cstr(kb, ko[i]).decode("utf-8", "replace"), cstr(vb, to[i])] for i in range(cnt)]
    have = {k for k, _ in ent}
    hit = 0
    for i, (k, v) in enumerate(ent):
        if k in patches:
            ent[i][1] = patches[k]; hit += 1

    # --- append genuinely-new keys (hash-addressable, so the engine can resolve them)
    nkb, nko, added = bytearray(kb), list(ko), 0
    for k in add_keys:
        v = patches.get(k)
        if k in have or v is None: continue
        h = c32.hash(k, False)
        p = bisect.bisect_left(B, h)
        if p < len(B) and B[p] == h:
            print(f"    [!] hash collision, refusing to add {k}"); continue
        ei = len(ent)
        nko.append(len(nkb)); nkb.extend(k.encode("utf-8")); nkb.append(0)
        ent.append([k, v]); A.append(h); C.append(0)
        B.insert(p, h); U.insert(p, ei)
        added += 1
    cnt = len(ent)
    assert cnt < 0x10000, "index map is u16 — cannot exceed 65535 entries"

    nv = bytearray(b"\x00"); seen = {b"": 0}; nt = [0] * cnt
    for i, (k, v) in enumerate(ent):
        if v in seen: nt[i] = seen[v]; continue
        nt[i] = len(nv); nv.extend(v); nv.extend(b"\x00"); seen[v] = nt[i]
    ov = {TAG_VALUES: bytes(nv), TAG_TEXT_OFFSETS: struct.pack(f"<{cnt}I", *nt),
          TAG_ENTRY_COUNT: struct.pack("<I", cnt),
          TAG_KEYS: bytes(nkb), TAG_KEY_OFFSETS: struct.pack(f"<{cnt}I", *nko),
          TAG_HASH_ENTRY: struct.pack(f"<{cnt}I", *A), TAG_HASH_SORTED: struct.pack(f"<{cnt}I", *B),
          TAG_FLAGS: struct.pack(f"<{cnt}I", *C), TAG_INDEX_MAP: struct.pack(f"<{cnt}H", *U)}
    heads = list(d.header.sections)
    sd = {sh.tag: (ov.get(sh.tag, pay[sh.offset:sh.offset + sh.size]), sh) for sh in heads}
    out = bytearray(pay[:HEADER_SIZE])
    for sh in heads: out.extend(struct.pack("<III", sh.tag, 0, 0))
    if d.header.unknowns: out.extend(d.header.unknowns)
    first = min(sh.offset for sh in heads)
    if len(out) < first: out.extend(pay[len(out):first])
    no = {}
    for sh in sorted(heads, key=lambda s: s.offset):
        c = align_up(len(out), ALIGN)
        if c > len(out): out.extend(b"\x00" * (c - len(out)))
        no[sh.tag] = len(out); out.extend(sd[sh.tag][0])
    for idx, sh in enumerate(heads):
        struct.pack_into("<III", out, HEADER_SIZE + idx * SECTION_HEADER_SIZE,
                         sh.tag, no[sh.tag], len(sd[sh.tag][0]))
    ho = bytes(pay[:HEADER_SIZE]).find(struct.pack("<I", d.header.size))
    if ho >= 0: struct.pack_into("<I", out, ho, len(out))
    return bytes(out), hit, added


def _logical(v): return rc_rtl._unesc(v).encode("utf-8")      # LOGICAL + unescaped (launcher / bidi renderer)
def _visual(v):  return rc_rtl.to_visual(v).encode("utf-8")    # VISUAL  + escaped   (in-game cohtml, no bidi)


def store_value(k, v, allkeys):
    """§8b per-KEY split. Every SHARED PC-settings BASE key (PCGRAPHICSSETTINGS_/PCDISPLAYSETTINGS_/
    PC_/PCAUDIO, no _UPPERCASE/_DESC suffix) is read ONLY by the launcher's config-doc-driven UI (does
    its own bidi) -> LOGICAL — whether or not it has an _UPPERCASE twin: proven on TWO independent
    cases (PC_AUDIO_COMPLEXITY/PC_LISTENINGMODE_TITLE titles, and PCDISPLAYSETTINGS_AUTO — a dropdown
    VALUE with no twin that the user confirmed renders reversed on the launcher). A pure-Latin no-twin
    key (DLSS/FSR/TAA…) is unaffected either way, so defaulting the whole class to LOGICAL is safe.
    The _UPPERCASE twin itself (+ _DESC tooltips) is read ONLY by the no-bidi in-game menu -> VISUAL.
    Launcher-only keys (LAUNCHER_/SETTINGSCATEGORY_) -> LOGICAL always; everything else is in-game
    content -> VISUAL. (Keys OUTSIDE this PC-prefix family, e.g. SETTINGS_GAMEPAD_TAB, are genuinely
    in-game-only and stay plain VISUAL via the final fallthrough.)"""
    if k.startswith(SHARED_PCSETTINGS):
        if k.endswith("_UPPERCASE") or k.endswith("_DESC"):
            return _visual(v)                                   # in-game (cohtml, no bidi)
        return _logical(v)                                      # every base PC-settings key -> launcher
    if k.startswith(LAUNCHER_ONLY):
        return _logical(v)
    return _visual(v)


# The three settings tabs whose widget class draws the config-doc string RAW (see rc_cfgpatch).
# Deliberately an A/B on the unknown bidi mode of that raw-draw path: 2 VISUAL vs 1 LOGICAL.
CFG_TABS = {"SETTINGS_DISPLAY_GRAPHICS_TAB": "visual",
            "SETTINGS_KEY_BINDING_TAB":      "logical",
            "SETTINGS_MOUSE_TAB":            "visual"}


def build_config_patch(clean):
    """Delta-0 patch the UI config-doc so the raw-draw tabs carry Hebrew. Returns (name, blob)."""
    import rc_cfgpatch
    toc_bak = os.path.join(GAME, "toc.tm_he_backup")
    toc_src = toc_bak if os.path.exists(toc_bak) else os.path.join(GAME, "toc")
    if not os.path.exists(toc_src):
        print("[!] no toc — skipping the config-doc tab patch"); return None
    with open(toc_src, "rb") as f: t = dat1lib.read(f)      # PRISTINE toc, never the deployed one
    t.dat1.set_recalculation_strategy(dat1lib.types.dat1.RECALCULATE_ORIGINAL_ORDER)
    t.set_archives_dir(GAME)
    assets = t.get_assets_section()
    ids = getattr(assets, "ids", None) or getattr(assets, "values", None) or []
    def _aid(x): return int.from_bytes(bytes(x), "little") if not isinstance(x, int) else x
    gi = next((i for i, x in enumerate(ids) if _aid(x) == rc_cfgpatch.CFG_AID), -1)
    if gi < 0:
        print("[!] config doc not in toc — skipping"); return None
    span = next(s for s, sp in enumerate(t.get_spans_section().entries)
                if sp.asset_index <= gi < sp.asset_index + sp.count)
    doc = bytes(t.extract_asset(gi))
    repl = {k: (_visual(clean[k]) if m == "visual" else _logical(clean[k]))
            for k, m in CFG_TABS.items() if k in clean}
    new, done = rc_cfgpatch.patch(doc, repl, hash_of=lambda k: c32.hash(k, False))
    nd = rc_cfgpatch.verify(doc, new, done)
    for k, off, ln, used in done:
        print(f"    cfg-doc {k:32s} slot={ln:3d}B used={used:3d}B mode={CFG_TABS[k]}")
    print(f"[+] config-doc patched delta-0: {len(done)} tab labels, {nd} bytes changed, "
          f"size {len(new)} (unchanged), span={span}")
    return f"{span}/{rc_cfgpatch.CFG_AID:016X}", new[36:]   # header_offset != -1 -> ship the BODY


def build():
    clean = json.load(open(HEB, encoding="utf-8"))
    allkeys = set(clean)
    nlog = sum(1 for k in clean if store_value(k, clean[k], allkeys) == _logical(clean[k])
               and store_value(k, clean[k], allkeys) != _visual(clean[k]))
    nlonly = sum(1 for k in clean if k.startswith(LAUNCHER_ONLY))
    print(f"[*] {len(clean)} Hebrew lines | key-split: base-with-twin + launcher-only -> LOGICAL "
          f"(~{nlog + nlonly} keys), everything else -> VISUAL …")
    vis = {k: store_value(k, v, allkeys) for k, v in clean.items()}   # span-independent, per-KEY

    files = sorted(os.listdir(LOCS)); assert len(files) == 32, f"want 32 variants, got {len(files)}"

    # GUARD: rebuild() can only patch keys the shipped table already has. Any corpus key that is
    # absent used to be SILENTLY DROPPED (that is how a whole "fix" once shipped as a no-op).
    # Now every absent key is explicitly ADDED to the table instead, and reported.
    ref = os.path.join(LOCS, files[1])
    _raw = open(ref, "rb").read()[36:]
    _d = dat1lib.types.dat1.DAT1(io.BytesIO(_raw), None)
    _S = {sh.tag: (sh.offset, sh.size) for sh in _d.header.sections}
    _cnt = struct.unpack("<I", _raw[_S[TAG_ENTRY_COUNT][0]:_S[TAG_ENTRY_COUNT][0] + 4])[0]
    _kb = _raw[_S[TAG_KEYS][0]:_S[TAG_KEYS][0] + _S[TAG_KEYS][1]]
    _ko = struct.unpack(f"<{_cnt}I", _raw[_S[TAG_KEY_OFFSETS][0]:_S[TAG_KEY_OFFSETS][0] + _cnt * 4])
    lockeys = {cstr(_kb, o).decode("utf-8", "replace") for o in _ko}
    add_keys = sorted(k for k in clean if k not in lockeys)
    if add_keys:
        print(f"[*] {len(add_keys)} corpus key(s) absent from the shipped table -> ADDING "
              f"(hash-addressable): {', '.join(add_keys)}")

    entries, total_hits, total_added = {}, 0, 0
    for fn in files:
        n = int(re.match(r"variant_(\d+)_", fn).group(1))
        blob, hit, added = rebuild(os.path.join(LOCS, fn), vis, add_keys)
        entries[f"{n * 8}/{LOC_AID:016X}"] = blob
        total_hits += hit; total_added += added
    assert total_added == len(add_keys) * len(files), \
        f"add-key incomplete: {total_added} != {len(add_keys)}*{len(files)}"
    print(f"[+] patched {len(entries)} variants, {total_hits} total key-hits "
          f"(~{total_hits // len(entries)}/variant), {total_added} added "
          f"({len(add_keys)}/variant); PC-settings split BY KEY (launcher=base, game=_UPPERCASE)")

    cfg = build_config_patch(clean)
    if cfg: entries[cfg[0]] = cfg[1]

    FF = {FONT_REG: "proximanova_regular_normal_he.ttf", FONT_BLD: "proximanova_bold_normal_he.ttf",
          SIE_REG:  "sie_gothic_regular_he.ttf",         SIE_BLD:  "sie_gothic_bold_he.ttf"}
    with zipfile.ZipFile(STAGE, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in entries.items(): z.writestr(k, v)
        for aid, fn in FF.items():
            z.writestr(f"0/{aid:016X}", open(os.path.join(FONTS, fn), "rb").read())
        z.writestr("info.json", '{"name":"R&C Rift Apart - Hebrew","author":"translation-hub"}')
    print(f"[+] bundled {len(FF)} fonts (Proxima Nova R/B + SIE-Gothic R/B)")
    print(f"[+] {STAGE}  ({os.path.getsize(STAGE)/1e6:.1f} MB)")
    return clean


def validate_offline(clean):
    """Validate the built stage: 32 spans, every loc blob re-parses, a Hebrew line round-trips."""
    print("\n[*] offline validation of the built stage …")
    with zipfile.ZipFile(STAGE) as z:
        names = z.namelist()
    spans = sorted(int(n.split("/")[0]) for n in names if "/" in n and n.split("/")[0].isdigit()
                   and n.endswith(f"{LOC_AID:016X}"))
    assert spans == [i * 8 for i in range(32)], f"span set wrong: {spans[:5]}…"
    with zipfile.ZipFile(STAGE) as z:
        for n in names:
            if n.endswith(f"{LOC_AID:016X}"):
                d = dat1lib.types.dat1.DAT1(io.BytesIO(z.read(n)), None)
                assert any(sh.tag == TAG_VALUES for sh in d.header.sections)
        # fonts present
        assert f"0/{FONT_REG:016X}" in names and f"0/{FONT_BLD:016X}" in names, "fonts missing"
        # spot-check: a menu Hebrew line's VISUAL form is present in the live span-8 blob
        k = next(k for k in clean if "MENU" in k and rc_rtl.HEBREW.search(clean[k]))
        want = rc_rtl.to_visual(clean[k]).encode("utf-8")
        assert want in z.read(f"8/{LOC_AID:016X}"), f"visual line not found in span-8 for {k}"
        # spot-check the KEY SPLIT on the trilinear pair (the user's own differential):
        #   base 'שלושה קווים' (launcher) -> LOGICAL ;  _UPPERCASE 'טריליניארי' (game) -> VISUAL
        b8 = z.read(f"8/{LOC_AID:016X}")
        base, up = "PCGRAPHICSSETTINGS_TRILINEAR", "PCGRAPHICSSETTINGS_TRILINEAR_UPPERCASE"
        if base in clean and up in clean:
            assert _logical(clean[base]) in b8, f"{base} not LOGICAL (launcher)"
            assert _visual(clean[up]) in b8,    f"{up} not VISUAL (game)"
            print(f"[+] key-split OK: {base}=LOGICAL(launcher), {up}=VISUAL(game)")

        # THE decisive check — simulate the ENGINE's own read path on the built span-8 blob:
        #   crc32.hash(key,False) -> bisect(sorted hashes) -> index map -> value.
        # This is what actually renders in-game; a key that only "appears somewhere in the bytes"
        # proves nothing (that mistake once shipped a fix that was a silent no-op).
        pay = z.read(f"8/{LOC_AID:016X}")
        dd = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
        SS = {sh.tag: (sh.offset, sh.size) for sh in dd.header.sections}
        def _sb(t): o, s = SS[t]; return pay[o:o + s]
        n = struct.unpack("<I", _sb(TAG_ENTRY_COUNT))[0]
        _kb, _vb = _sb(TAG_KEYS), _sb(TAG_VALUES)
        _ko = struct.unpack(f"<{n}I", _sb(TAG_KEY_OFFSETS))
        _to = struct.unpack(f"<{n}I", _sb(TAG_TEXT_OFFSETS))
        _A  = struct.unpack(f"<{n}I", _sb(TAG_HASH_ENTRY))
        _B  = list(struct.unpack(f"<{n}I", _sb(TAG_HASH_SORTED)))
        _U  = struct.unpack(f"<{n}H", _sb(TAG_INDEX_MAP))
        assert all(_B[i] <= _B[i + 1] for i in range(n - 1)), "sorted-hash array is not sorted"
        assert len(set(_B)) == n, "duplicate hash in the lookup table"
        kn = [cstr(_kb, _ko[i]).decode("utf-8", "replace") for i in range(n)]
        broken = 0
        for i in range(n):
            if c32.hash(kn[i], False) != _A[i]: broken += 1; continue
            p = bisect.bisect_left(_B, _A[i])
            if p >= n or _B[p] != _A[i] or _U[p] != i: broken += 1
        assert broken == 0, f"{broken}/{n} entries are NOT resolvable by the engine's hash lookup"
        print(f"[+] engine-lookup simulation: {n} entries, ALL resolvable by hash (0 broken)")
        # and every corpus key must round-trip through that lookup to the exact bytes we intended
        ki = {k: i for i, k in enumerate(kn)}
        miss = [k for k in clean if k not in ki]
        assert not miss, f"corpus keys still absent from the table: {miss[:5]}"
        wrong = []
        for k, v in clean.items():
            p = bisect.bisect_left(_B, c32.hash(k, False))
            got = cstr(_vb, _to[_U[p]])
            if got != store_value(k, v, set(clean)): wrong.append(k)
        assert not wrong, f"{len(wrong)} keys resolve to the wrong bytes, e.g. {wrong[:5]}"
        print(f"[+] all {len(clean)} corpus keys resolve via hash to exactly the intended bytes")
    print(f"[+] stage OK: 32 spans + 2 fonts, all loc blobs re-parse")
    print(f"[+] spot-check: {k} VISUAL line present in the live span-8 blob")
    print("[+] OFFLINE VALIDATION PASS")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        import spiderman2_mod as sm
        print("[revert]", sm.revert(GAME)); sys.exit()
    clean = build()
    validate_offline(clean)
    if "--deploy" in sys.argv:
        import spiderman2_mod as sm
        print("\n[*] deploying (GAME MUST BE CLOSED) …")
        r = sm.apply(GAME, [STAGE],
                     cb=lambda p, pct, m: print(f"    {pct:5.1f}% {m}") if pct in (5.0, 50.0, 97.0, 100.0) else None)
        print("[deploy]", r)
    else:
        print("\n(dry — pass --deploy to apply; game must be closed)")
