"""Patch the Arabic .localization with Hebrew strings for the main-menu test.

Strategy:
  - Start from variant_18 (Arabic file).
  - Replace N values with their Hebrew translation.
  - Rebuild ValuesSection from scratch (concatenated NUL-separated UTF-8 strings).
  - Rebuild TextOffsets (u32 per entry) so each entry points at its new value.
  - Keep KeyNames / TagOffsets / Flags / SortedHashes / SortedIndexes /
    EntryCount / x06A58050 BYTE-IDENTICAL to the source.
  - Re-emit the DAT1 with updated section sizes/offsets and the same 36-byte
    AssetEntry prefix.
  - Sanity-check: re-parse the file we just wrote and confirm every patched
    key now decodes to Hebrew."""

import os, sys, io, json, struct, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

# ⚠️ GAME-UPDATE-AWARE: the variant's size-entry INDEX is part of the filename and CHANGES with
# every game patch (v1.131 -> idx1276510, v2.629 -> idx1276615). Never hardcode it — resolve the
# newest variant_18/variant_00 by glob, so a re-extract (04_extract_all_locs.py) after a game
# update is automatically picked up. A stale base silently drops every string the patch added.
_LOCV = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants")


def _variant(n: int) -> str:
    import glob
    hits = sorted(glob.glob(os.path.join(_LOCV, f"variant_{n:02d}_idx*.localization")))
    if not hits:
        raise SystemExit(f"[!] variant_{n:02d} not found in {_LOCV} — run 04_extract_all_locs.py first")
    if len(hits) > 1:
        raise SystemExit(f"[!] {len(hits)} copies of variant_{n:02d} — stale extraction, keep only one:\n  "
                         + "\n  ".join(os.path.basename(h) for h in hits))
    return hits[0]


SRC = _variant(18)
VAR_NAME = os.path.basename(SRC)
OUT_DIR = os.path.join(ROOT, "games", "spiderman2", "work")
OUT_LOC = os.path.join(OUT_DIR, "arabic_patched_hebrew_menu.localization")

# ---- the Hebrew patch set (main menu + universal buttons) -------------------
HEBREW = {
    "MENU_LOBBY_CONTINUEGAME_HEADER":      "המשך משחק",
    "MENU_LOBBY_NEWGAME_HEADER":           "לפני שמתחילים",
    "MENU_LOBBY_INITIALSETUP_HEADER":      "הגדרה ראשונית",
    "MENU_LOBBY_ACCESSIBILITY_TITLE":      "ערכות נגישות",
    "MENU_LOBBY_AUDIOCALIBRATION_HEADER":  "כיוון שמע",
    "MENU_LOBBY_IMAGECALIBRATION_HEADER":  "כיוון תמונה",
    "MENU_LOBBY_COMMONSETTINGS_HEADER":    "הגדרות נפוצות",
    "MENU_LOBBY_ALLSETTINGS_HEADER":       "הגדרות",
    "MENU_AUDIO_HEADER":                   "הגדרות שמע",
    "MENU_LOBBY_APPLYPREORDER_TITLE":      "החל בונוסי הזמנה מוקדמת",
    # universal buttons
    "BTN_ACCEPT":                          "אישור",
    "BTN_CANCEL":                          "ביטול",
    "BTN_CLOSE":                           "סגירה",
    "BTN_CONTINUE":                        "המשך",
    "BTN_MENU_BACK":                       "חזרה",
    "BTN_MENU_SELECT":                     "בחירה",
    "BTN_APPLY_CHANGES":                   "החל שינויים",
    "BTN_APPLYANDRELOAD":                  "החל וטען מחדש",
    # boot launcher window (Play / Settings / Exit / Show-launcher checkbox)
    "LAUNCHER_PLAY":                       "שחק",
    "LAUNCHER_OPTIONS":                    "הגדרות",
    "LAUNCHER_QUIT":                       "יציאה",
    "LAUNCHER_ENABLED":                    "הצג משגר",
    "LAUNCHER_ENABLED_UPPERCASE":          "הצג משגר",
    # in-game Settings > Language label — show the hijacked Arabic slot as Hebrew
    "LANGUAGE_ARABIC":                     "עברית",
    "SETTING_LANG_TEXT_OPTION_ARABIC":     "עברית",
    # main lobby menu items (visible on the start screen)
    "TEXT_CONTINUE":                       "המשך",
    "TEXT_LOAD_GAME":                      "טען משחק",
    "MENU_LOBBY_PROLOGUEVIDEO_TITLE":      "בפרקים הקודמים...&rlm;",
    "MENU_LOBBY_VIEWCREDITS_TITLE":        "רשימת יוצרים",
    "TEXT_QUIT_GAME":                      "צא מהמשחק",
    "PAUSE_QUIT_TO_DESKTOP_TITLE":         "צא מהמשחק",
    # --- native pre-game graphics config dialog (probe: does it read our mod?) -
    "SETTINGSCATEGORY_DISPLAY":            "תצוגה",
    "SETTINGSCATEGORY_GRAPHICS":           "גרפיקה",
    "PCDISPLAYSETTINGS_MONITOR":           "מסך",
    "PCDISPLAYSETTINGS_WINDOWMODE":        "מצב חלון",
    "PCDISPLAYSETTINGS_WINDOWED":          "מצב חלון",
    "PCDISPLAYSETTINGS_DISPLAYRESOLUTION": "רזולוציה",
    "PCDISPLAYSETTINGS_ASPECTRATIO":       "יחס תצוגה",
    "PCDISPLAYSETTINGS_UPSCALEMETHOD":     "שיטת שדרוג תמונה",
    "PCDISPLAYSETTINGS_UPSCALEQUALITY":    "איכות שדרוג",
    "PCDISPLAYSETTINGS_UPSCALESHARPNESS":  "חדות שדרוג",
    "PCDISPLAYSETTINGS_FRAMEGEN":          "יצירת פריימים",
    "PCDISPLAYSETTINGS_DRS":               "קנה מידה דינמי",
    "PCDISPLAYSETTINGS_REFRESHRATE":       "קצב רענון",
    "PCDISPLAYSETTINGS_VSYNC":             "סנכרון אנכי",
    "PCDISPLAYSETTINGS_FULLSCREEN":        "מסך מלא",
    "PCDISPLAYSETTINGS_AUTO":              "אוטומטי",
    "PCDISPLAYSETTINGS_ON":                "פעיל",
    "PCDISPLAYSETTINGS_OFF":               "כבוי",
    "PCGRAPHICSSETTINGS_SSAA":             "החלקת קצוות",
    "PCGRAPHICSSETTINGS_ON":               "פעיל",
    "PCGRAPHICSSETTINGS_OFF":              "כבוי",
    "LAUNCHER_OPTIONS_OK":                 "אישור",
    "LAUNCHER_OPTIONS_CANCEL":             "ביטול",
    "LAUNCHER_OPTIONS_RESET":              "איפוס",
    "LAUNCHER_OPTIONS_TITLE":              "ספיידרמן 2 של מארוול - תצורה",
    # NOTE: the native config dialog is LTR-base, so a Latin token at the END of
    # the logical string renders on the RIGHT (read first in RTL). To make the
    # English/version read LAST, put it at the START of the logical string.
    "PCDISPLAYSETTINGS_HDRMAXNITS":        "HDR בהירות מרבית",
    "PCDISPLAYSETTINGS_HDRPAPERWHITE":     "HDR בהירות לבן-נייר",
    "PCDISPLAYSETTINGS_NVIDIAREFLEX":      "NVIDIA Reflex זמן תגובה",
    # window-mode + frame-gen + refresh-rate dropdown OPTIONS
    "PCDISPLAYSETTINGS_EXCLUSIVEFULLSCREEN":"מסך מלא בלעדי",
    "PCDISPLAYSETTINGS_FSRFRAMEGEN":       "FSR {FSR_VERSION} יצירת פריימים",
    "PCDISPLAYSETTINGS_DLSSG":             "DLSS יצירת פריימים",
    "PCDISPLAYSETTINGS_HALF_REFRESHRATE":  "חצי קצב רענון",
    "PCDISPLAYSETTINGS_ONE_THIRD_REFRESHRATE": "שליש קצב רענון",
    "PCDISPLAYSETTINGS_QUARTER_REFRESHRATE":   "רבע קצב רענון",
}

# ---- merge external menu/settings translation files (hand-translated, batched)
for fn in ("settings_he.json", "menus_he.json", "menus2_he.json",
           "menus3_he.json", "menus4_he.json", "menus5_he.json",
           "menus6_he.json", "menus7_he.json", "menus8_he.json",
           "menus9_he.json", "menus10_he.json", "menus11_he.json",
           "menus12_he.json", "menus13_he.json",
           "subtitles_he.json", "dialogue_he.json"):
    p = os.path.join(OUT_DIR, fn)
    if os.path.exists(p):
        extra = json.load(open(p, encoding="utf-8"))
        HEBREW.update(extra)
        print(f"[+] merged {len(extra)} strings from {fn}")

# ---- ⛔ REMOVED: the "NATIVE_LTR" word-order hack (2026-07-26) ---------------
# It reordered a few labels Latin-FIRST so they read correctly in the pre-launch NATIVE
# config dialog (which is LTR-base). But the SAME keys also feed the IN-GAME cohtml
# settings menu, which is RTL-base and needs LOGICAL order — so the hack fixed a window
# the player sees once and broke the menu they use constantly.
# PROOF (one screenshot): 'טכנולוגיית NVIDIA Reflex לתגובה מהירה' (logical, untouched) rendered
# CORRECTLY in-game, while 'HDR בהירות מרבית של' (my LTR order) rendered reversed.
# DECIDING EVIDENCE: the game's OWN official Arabic stores LOGICAL order
# ('تقنية DLSS لتوليد الإطارات'), i.e. logical is what this engine expects.
# One stored string cannot satisfy both surfaces (an RLE/PDF embedding would, but Heebo has
# no glyphs for U+202B/U+202C -> tofu). So: store LOGICAL everywhere, matching vanilla, and
# accept that a couple of labels read sub-optimally in the one-time native config window.
# ---- NATIVE DIALOG FIXES — must run AFTER the json merge ---------------------
# The PC config dialog + PCWARNING popups are the game's own NATIVE widgets, not the
# cohtml UI. Two consequences, both confirmed in-game on v2.629:
#   1. They lay out with an LTR base direction. A Latin token at the END of the logical
#      string therefore renders on the RIGHT = read FIRST by a Hebrew reader
#      ("בהירות מרבית של HDR" -> reads "HDR בהירות מרבית של"). Putting the Latin token at
#      the START of the logical string makes it render leftmost = read LAST. ✅
#   2. They do NOT parse HTML entities, so a `&rlm;` anchor is drawn LITERALLY as ".rlm;".
# The json files above are bulk hand-translations that (correctly, for the cohtml UI)
# store logical order with the Latin at the end — so they MUST be overridden here for
# these specific native-dialog keys, or the merge silently undoes the fix.
# The ONLY genuine native-dialog key family is the pre-launch popups: those widgets render
# HTML entities literally, so a `&rlm;` shows up as ".rlm;". Everything under
# PCDISPLAYSETTINGS_/PCGRAPHICSSETTINGS_ is ALSO drawn by the IN-GAME cohtml menu, where the
# `&rlm;` is exactly what pins a trailing period to the RTL end — stripping it there is what
# put the sentence-final "." on the wrong side of the last line. So: strip for the explicit
# native popups ONLY, never by broad prefix.
_NATIVE_KEYS = ("PCWARNING_MISSINGFILE", "PCWARNING_SWAPCHAINREFLEAK")
_stripped = 0
for _k in _NATIVE_KEYS:
    _v = HEBREW.get(_k)
    if isinstance(_v, str):
        _n = _v.replace("&rlm;", "").replace("‏", "")
        if _n != _v:
            HEBREW[_k] = _n
            _stripped += 1
print(f"[+] stripped &rlm; from {_stripped} native-popup strings (entities render literally there)")

# auto-derive _UPPERCASE siblings (Hebrew has no case -> identical text). The
# builder safely skips any that don't exist in the localization.
for k in list(HEBREW.keys()):
    if not k.endswith("_UPPERCASE"):
        HEBREW.setdefault(k + "_UPPERCASE", HEBREW[k])

# ---- 🔑 ROOT FIX: force an RTL base on the PC-settings surface ---------------
# WHY (proven from the vanilla UI JS, asset B40AFA7568AA4412): under `langIsRightToLeft`
# the game sets ONLY `--languageNormalAlignment` / `--languageOppositeAlignment` (text
# ALIGNMENT) and a `cohinline` attribute on two css classes — it NEVER sets `direction`
# or `dir` anywhere. Insomniac even left a TODO there: "These css classes may not catch
# everything". So the PC-settings pages keep an LTR paragraph base, and the UBA then
# lays a mixed line "H1 <latin> H2" out left-to-right as H1|latin|H2 — which a Hebrew
# reader, scanning right-to-left, sees as "H2 latin H1":
#     stored  טכנולוגיית NVIDIA Reflex לתגובה מהירה
#     shown   לתגובה מהירה NVIDIA Reflex טכנולוגיית   ← exactly the reported bug
# and a sentence-final "." (a NEUTRAL) resolves to the LTR end = the wrong side.
# cohtml ignores CSS direction and honours ONLY Unicode bidi controls, so the fix is an
# EMBEDDING: RLE(U+202B) … PDF(U+202C) around each line forces the RTL base and the UBA
# then orders everything correctly — with the text kept in clean LOGICAL order (no word
# reordering, so "60 FPS" and every {TOKEN} stay intact). 94_fix_font_controls.py adds
# those two codepoints to Heebo as EMPTY zero-width glyphs so they draw nothing.
# Scope: the cohtml PC-settings families only. The two pre-launch NATIVE popups are
# excluded — they are not cohtml and get their own handling above.
_RLE, _PDF = "‫", "‬"
_RTL_PREFIXES = ("PCDISPLAYSETTINGS_", "PCGRAPHICSSETTINGS_", "PCWARNING_", "PC_")
_RTL_EXCLUDE = set(_NATIVE_KEYS)

def _force_rtl_base(s: str) -> str:
    # wrap each <br>-separated segment on its own: an embedding must not span a line break
    parts = re.split(r"(<br\s*/?>)", s)
    out = []
    for p in parts:
        if p.startswith("<br") or not p.strip():
            out.append(p)
            continue
        if p.startswith(_RLE):        # already wrapped -> idempotent
            out.append(p)
            continue
        out.append(_RLE + p + _PDF)
    return "".join(out)

_wrapped = 0
for _k in list(HEBREW.keys()):
    if _k in _RTL_EXCLUDE or not _k.startswith(_RTL_PREFIXES):
        continue
    _v = HEBREW[_k]
    if not isinstance(_v, str) or not _v.strip():
        continue
    _n = _force_rtl_base(_v)
    if _n != _v:
        HEBREW[_k] = _n
        _wrapped += 1
print(f"[+] RTL-base embedding (RLE…PDF) applied to {_wrapped} PC-settings strings")

print(f"[+] {len(HEBREW)} Hebrew translations queued")

# ---- read source ------------------------------------------------------------
raw = open(SRC, "rb").read()
prefix = raw[:36]          # AssetEntry header — kept verbatim
payload = raw[36:]         # DAT1 file
dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)

# Section tag map
TAG_VALUES        = 0x70A382B8
TAG_KEYS          = 0x4D73CEBD
TAG_TEXT_OFFSETS  = 0xF80DEEB4
TAG_KEY_OFFSETS   = 0xA4EA55B2
TAG_ENTRY_COUNT   = 0xD540A903

secs = {sh.tag: (sh.offset, sh.size) for sh in dat1.header.sections}
def sec_bytes(tag): off, sz = secs[tag]; return payload[off:off+sz]

entry_count = struct.unpack("<I", sec_bytes(TAG_ENTRY_COUNT))[0]
keys_blob   = sec_bytes(TAG_KEYS)
values_blob = sec_bytes(TAG_VALUES)
text_offs   = list(struct.unpack(f"<{entry_count}I", sec_bytes(TAG_TEXT_OFFSETS)))
key_offs    = list(struct.unpack(f"<{entry_count}I", sec_bytes(TAG_KEY_OFFSETS)))

def cstr(buf, off):
    end = buf.find(b"\x00", off);  end = end if end >= 0 else len(buf)
    return buf[off:end]

# Build (key, value_bytes) per entry
entries = []
for i in range(entry_count):
    k = cstr(keys_blob, key_offs[i]).decode("utf-8", "replace")
    v = cstr(values_blob, text_offs[i])      # keep as bytes (preserve whatever exotic punctuation)
    entries.append([k, v])

# ---- ENGLISH base for untranslated keys (instead of Arabic) -----------------
# The mod ships in the Arabic slot; untranslated subtitles/dialogue would
# otherwise be Arabic, which renders as tofu boxes in the Hebrew (Heebo) font.
# Replace every value with the ENGLISH equivalent (variant_00) FIRST, so the
# untranslated tail is readable English; the Hebrew menu patches below override
# the translated keys on top.
# Resolved by glob (see _variant): the index changes on every game patch, and the
# `if os.path.exists` below would SILENTLY skip the English fallback on a stale name,
# leaving untranslated lines as Arabic (= tofu in the Hebrew font).
ENG_VARIANT = _variant(0)
if os.path.exists(ENG_VARIANT):
    _eraw = open(ENG_VARIANT, "rb").read(); _epay = _eraw[36:]
    _edat = dat1lib.types.dat1.DAT1(io.BytesIO(_epay), None)
    _esecs = {sh.tag: (sh.offset, sh.size) for sh in _edat.header.sections}
    def _esec(tag): o, s = _esecs[tag]; return _epay[o:o+s]
    _ecnt = struct.unpack("<I", _esec(TAG_ENTRY_COUNT))[0]
    _ekeys = _esec(TAG_KEYS); _evals = _esec(TAG_VALUES)
    _etoff = list(struct.unpack(f"<{_ecnt}I", _esec(TAG_TEXT_OFFSETS)))
    _ekoff = list(struct.unpack(f"<{_ecnt}I", _esec(TAG_KEY_OFFSETS)))
    eng_map = {}
    for i in range(_ecnt):
        k = cstr(_ekeys, _ekoff[i]).decode("utf-8", "replace")
        if k not in eng_map:
            eng_map[k] = cstr(_evals, _etoff[i])
    _repl = 0
    for e in entries:
        ev = eng_map.get(e[0])
        if ev is not None and ev != e[1]:
            e[1] = ev; _repl += 1
    print(f"[+] English base: {_repl} untranslated values -> English (variant_00)")
else:
    print("[!] English variant not found — keeping Arabic base")

# Percent normalisation — FORMAT-AWARE.
#   • A display string (no printf arg) shows "%%" literally → collapse to "%".
#   • A printf FORMAT string (has %d/%s/…) must KEEP "%%" as the literal-percent
#     escape; collapsing it to a single "%" leaves a dangling specifier that the
#     engine renders as garbage (this is what broke UI_PERCENT="%d%%" → "%d%" →
#     "500" + tofu). In a format string a lone literal "%" is also doubled.
import re as _re
_SPEC = _re.compile(r'%[-+ #0]*\d*(?:\.\d+)?[diouxXeEfFgGaAcspn]')
def _norm_pct(s: str) -> str:
    if '%' not in s:
        return s
    if not _SPEC.search(s.replace('%%', '')):      # no real specifier → display
        return s.replace('%%', '%')
    out, i, n = [], 0, len(s)                       # printf format → keep/fix escapes
    while i < n:
        if s[i] == '%':
            if i + 1 < n and s[i + 1] == '%':
                out.append('%%'); i += 2
            else:
                m = _SPEC.match(s, i)
                if m:
                    out.append(m.group(0)); i = m.end()
                else:
                    out.append('%%'); i += 1        # lone literal % → escape it
        else:
            out.append(s[i]); i += 1
    return ''.join(out)
# (the percent normalisation + box-glyph pass runs AFTER the Hebrew patches —
#  see below — so it sees the FINAL value of every entry, English OR Hebrew.)

# Apply Hebrew patches — record which got applied
applied, missing = 0, []
for k, hebrew_str in HEBREW.items():
    found_indices = [i for i, e in enumerate(entries) if e[0] == k]
    if not found_indices:
        missing.append(k)
        continue
    new_v = hebrew_str.encode("utf-8")
    for i in found_indices:
        entries[i][1] = new_v
    applied += len(found_indices)
print(f"[+] applied {applied} patches across {len(HEBREW) - len(missing)}/{len(HEBREW)} keys")
if missing:
    print(f"[!] missing keys (skipped): {missing}")

# ---- FINAL pass: Arabic-gated percent escaping + box-glyph removal ----------
# The engine printf-formats SOME strings (value labels like "100%%", perk "%%110")
# and displays OTHERS raw (descriptions). In a printf string a literal "%" MUST be
# doubled ("%%") or the dangling specifier prints garbage — THIS is the "100"+tofu
# game-speed bug (my earlier "%%"->"%" collapse turned printf "100%%" into "100%").
# The shipped Arabic encodes the distinction per key: printf strings carry "%%",
# display strings a single "%". Mirror it exactly.
_ar = json.load(open(os.path.join(OUT_DIR, "arabic.json"), encoding="utf-8"))
def _double_pct(s):
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == '%':
            if i + 1 < n and s[i + 1] == '%':
                out.append('%%'); i += 2
            else:
                m = _SPEC.match(s, i)
                if m:
                    out.append(m.group(0)); i = m.end()
                else:
                    out.append('%%'); i += 1     # lone literal % -> escape it
        else:
            out.append(s[i]); i += 1
    return ''.join(out)
_BOX = {ord('؟'): '?', ord('،'): ',', 0xFFFC: None}
_pct = _box = 0
for e in entries:
    _s = e[1].decode('utf-8', 'replace')
    if '%' in _s:
        _ns = _double_pct(_s) if '%%' in _ar.get(e[0], '') else _s.replace('%%', '%')
    else:
        _ns = _s
    if any(ord(c) in _BOX for c in _ns):
        _ns = _ns.translate(_BOX); _box += 1
    if _ns != _s:
        e[1] = _ns.encode('utf-8'); _pct += 1
print(f"[+] final normalize: {_pct} values changed ({_box} box glyphs)")

# ---- rebuild ValuesSection + TextOffsets -----------------------------------
# Strategy: for each entry, append its value (+NUL) to a new values blob and
# record the start offset in new_text_offs.
# Special: index 0 is INVALID; preserve a leading empty (the original starts
# with \x00). Original layout had offsets reusing each other only when values
# were byte-identical — we'd lose that dedup if we naively append. Build a
# value→offset dedup map and reuse offsets when the bytes match exactly.
new_values = bytearray()
seen = {}   # bytes -> offset
new_text_offs = [0] * entry_count
new_values.extend(b"\x00")          # leading NUL byte (matches original layout)
seen[b""] = 0
for i, (k, v) in enumerate(entries):
    if v in seen:
        new_text_offs[i] = seen[v]
        continue
    new_text_offs[i] = len(new_values)
    new_values.extend(v)
    new_values.extend(b"\x00")
    seen[v] = new_text_offs[i]

print(f"[*] old values blob: {len(values_blob):8} bytes -> new: {len(new_values):8} bytes "
      f"(delta {len(new_values)-len(values_blob):+d})")
print(f"[*] unique values: {len(seen)} (entries {entry_count})")

new_text_offs_blob = struct.pack(f"<{entry_count}I", *new_text_offs)

# ---- rebuild the DAT1 file --------------------------------------------------
# DAT1 layout: header → section headers → padding → sections (in declared order).
# Section offsets in the header are RELATIVE to start of file. We need to lay
# out sections in stable order (sorted by ORIGINAL offset to preserve any
# implicit ordering invariants), recompute new offsets, and pad as needed
# to keep section starts 16-byte aligned (matches original).

# Pull every section's raw bytes (using new ones where applicable)
SECTION_OVERRIDES = {
    TAG_VALUES:       bytes(new_values),
    TAG_TEXT_OFFSETS: new_text_offs_blob,
}

# Original section headers (in declared order in file)
original_section_headers = list(dat1.header.sections)
section_data = []
for sh in original_section_headers:
    tag = sh.tag
    if tag in SECTION_OVERRIDES:
        section_data.append((tag, SECTION_OVERRIDES[tag], sh))
    else:
        section_data.append((tag, payload[sh.offset:sh.offset+sh.size], sh))

# ---- DAT1 header structure (from dat1.py DAT1Header) -----------------------
#   u32 magic | u32 unk1 | u32 size | u16 sections_count | u16 unknowns_count
HEADER_SIZE = 16
SECTION_HEADER_SIZE = 12
print(f"\n[*] DAT1 raw header bytes (first 16): {payload[:16].hex(' ')}")
hdr = dat1.header
print(f"[*] header attrs: magic={hex(hdr.magic)} unk1={hex(hdr.unk1)} size={hdr.size} sections={len(hdr.sections)} unknowns={len(hdr.unknowns)}")
for sh in original_section_headers[:3]:
    print(f"   sh: tag={hex(sh.tag)} off={sh.offset} size={sh.size}")

# Compute new layout
# Header (24 bytes) + N * (12 bytes section headers) + padded to align(?)
n = len(section_data)
section_headers_size = n * SECTION_HEADER_SIZE
first_data_off = HEADER_SIZE + section_headers_size

# Match original: first section starts at offset 160 (per earlier dump). Let's see.
print(f"[*] computed first_data_off = {first_data_off} (original first section at 160 = EntryCount)")

# Use the original alignment of the very first section start as our baseline
# (so we don't change ANY layout beyond what's required).
ORIGINAL_FIRST_OFF = min(sh.offset for sh in original_section_headers)
print(f"[*] original first section offset: {ORIGINAL_FIRST_OFF}")

# Build the new file
new_dat1 = bytearray()
# Header — re-emit the real 16-byte header, then any unknowns block, then
# placeholder section headers, then pad to the first section's offset.
orig_header_bytes = bytes(payload[:HEADER_SIZE])
new_dat1.extend(orig_header_bytes)

sd_by_tag = {tag: (raw, sh) for tag, raw, sh in section_data}

new_offsets_by_tag = {}
for sh in original_section_headers:
    new_dat1.extend(struct.pack("<III", sh.tag, 0, 0))   # placeholder

# Append the original 'unknowns' bytes (between section headers and strings table)
# per DAT1Header layout — important to preserve.
if hdr.unknowns:
    new_dat1.extend(hdr.unknowns)

# Pad to ORIGINAL_FIRST_OFF (this preserves the strings-table area as the
# original's NUL bytes — the parser walks it to build _strings_map).
if len(new_dat1) < ORIGINAL_FIRST_OFF:
    new_dat1.extend(payload[len(new_dat1):ORIGINAL_FIRST_OFF])  # keep original strings bytes
else:
    print(f"[!] header+section_headers ({len(new_dat1)}) > original first offset ({ORIGINAL_FIRST_OFF})")

# Now lay out the section data in the order they appear in the file body.
# Original layout: sort sections by original offset, place each at the next
# 16-aligned cursor. Keep alignment identical.
ALIGN = 16
def align_up(x, a): return (x + a - 1) // a * a

body_order = sorted(original_section_headers, key=lambda sh: sh.offset)
for sh in body_order:
    cursor = align_up(len(new_dat1), ALIGN)
    if cursor > len(new_dat1):
        new_dat1.extend(b"\x00" * (cursor - len(new_dat1)))
    new_offsets_by_tag[sh.tag] = len(new_dat1)
    raw, _ = sd_by_tag[sh.tag]
    new_dat1.extend(raw)

# Fill section header offsets/sizes in pass 2 — at the CORRECT base (16, not 24)
for idx, sh in enumerate(original_section_headers):
    pos = HEADER_SIZE + idx * SECTION_HEADER_SIZE
    new_off = new_offsets_by_tag[sh.tag]
    new_size = len(sd_by_tag[sh.tag][0])
    struct.pack_into("<III", new_dat1, pos, sh.tag, new_off, new_size)

# Update header.size at offset 12 (the 4-byte total DAT1 size). Look in dat1.py
# to confirm — header is magic(4)+unk1(4)+size(4)+section_count(4)+... but the
# ALERT print shows `header.size`. Let's update offset 8 (if size is third u32)
# Actually let me just write 0..24 as: magic, unk1, size, sections_count, ...
# The original first 24 hex showed structure starting with "31 54 41 44" (1TAD).
# I'll re-read the header to learn its exact field layout.

# Pad to even total (not strictly required, but safe)
print(f"\n[*] new DAT1 size: {len(new_dat1)} (original payload {len(payload)})")
new_size_delta = len(new_dat1) - len(payload)
print(f"[*] delta vs original payload: {new_size_delta:+d} bytes")

# Update size field in header (offset 12, u32) — taken from struct definition of HeaderRecord
# Let me re-check actual header. dat1lib parses header. The size field in DAT1's header
# usually represents the total DAT1 size. Inspecting:
print(f"[*] dat1.header.size before patch: {dat1.header.size} (original total)")

# Find which 4-byte slot in the original header equals dat1.header.size (~7,749,814)
needle = struct.pack("<I", dat1.header.size)
header_size_offset = orig_header_bytes.find(needle)
print(f"[*] header.size found at offset {header_size_offset} in 24-byte header")
if header_size_offset >= 0:
    struct.pack_into("<I", new_dat1, header_size_offset, len(new_dat1))
    print(f"[+] wrote new header.size = {len(new_dat1)}")
else:
    print("[!] couldn't locate size field — leaving header.size untouched (this may break loading)")

# ---- write out --------------------------------------------------------------
final = prefix + bytes(new_dat1)
with open(OUT_LOC, "wb") as f:
    f.write(final)
print(f"\n[+] wrote {OUT_LOC}  ({len(final)} bytes total, prefix {len(prefix)} + DAT1 {len(new_dat1)})")

# ---- sanity: re-parse and verify Hebrew values --------------------------
re_raw = open(OUT_LOC, "rb").read()
re_pay = re_raw[36:]
re_dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(re_pay), None)
re_secs = {sh.tag: (sh.offset, sh.size) for sh in re_dat1.header.sections}
def re_sec(tag): o, s = re_secs[tag]; return re_pay[o:o+s]

re_count = struct.unpack("<I", re_sec(TAG_ENTRY_COUNT))[0]
re_keys = re_sec(TAG_KEYS)
re_vals = re_sec(TAG_VALUES)
re_text_offs = list(struct.unpack(f"<{re_count}I", re_sec(TAG_TEXT_OFFSETS)))
re_key_offs  = list(struct.unpack(f"<{re_count}I", re_sec(TAG_KEY_OFFSETS)))

print(f"\n[*] re-parsed: count={re_count}, keys={len(re_keys)}, values={len(re_vals)}")
print("\n=== verification: read back each patched key ===")
ok = 0
for k, expected_hebrew in HEBREW.items():
    found = False
    for i in range(re_count):
        kn = cstr(re_keys, re_key_offs[i]).decode("utf-8", "replace")
        if kn == k:
            v = cstr(re_vals, re_text_offs[i]).decode("utf-8", "replace")
            mark = "OK" if v == expected_hebrew else "MISMATCH"
            print((f"  [{mark}] {k:<40}  {v!r}").encode("ascii", "backslashreplace").decode())
            if v == expected_hebrew: ok += 1
            found = True
            break
    if not found:
        print(f"  [MISSING] {k}")
print(f"\n[+] {ok}/{len(HEBREW)} verified.")
