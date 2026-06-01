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

import os, sys, io, json, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

VAR_NAME = "variant_18_idx1276510.localization"
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants", VAR_NAME)
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
    "MENU_LOBBY_ALLSETTINGS_HEADER":       "כל ההגדרות",
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
}
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
            print(f"  [{mark}] {k:<40}  {v!r}")
            if v == expected_hebrew: ok += 1
            found = True
            break
    if not found:
        print(f"  [MISSING] {k}")
print(f"\n[+] {ok}/{len(HEBREW)} verified.")
