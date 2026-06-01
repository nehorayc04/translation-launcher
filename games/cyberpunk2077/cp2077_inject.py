"""
CP2077 Localization Injector
Reads translated JSON and writes modified CR2W localization files.

Usage:
  python cp2077_inject.py <translated_json>            # inject
  python cp2077_inject.py <translated_json> --dry-run  # preview only
  python cp2077_inject.py <translated_json> --verify   # inject + re-parse to confirm

The translated_json must have the same structure as localization_export.json:
  { "relative/path.json": [ {primaryKey, secondaryKey, femaleVariant, maleVariant}, ... ] }

Backups of original files are saved to source/archive_backup/ before any modification.
"""

import struct
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים")
ARCHIVE_DIR  = PROJECT_ROOT / "source" / "archive" / "base" / "localization" / "en-us"
BACKUP_DIR   = PROJECT_ROOT / "source" / "archive_backup"

# Default CName indices — used as fallback if per-file CName table parsing fails.
# These values match onscreens.json's CName table layout, but differ in subtitle
# files (smaller CName tables / different ordering). The inject_file() function
# parses each file's CName table to get the correct file-specific indices.
CNAME_PRIMARY_KEY    = 10
CNAME_UINT64         = 11
CNAME_SECONDARY_KEY  = 12
CNAME_STRING         = 13
CNAME_FEMALE_VARIANT = 14
CNAME_MALE_VARIANT   = 15

# CR2W v195 header layout (confirmed by binary inspection of onscreens.json)
HEADER_FILE_SIZE_OFFSET = 0x0C   # u32 — actual file size
HEADER_TABLES_OFFSET    = 0x28   # 10 × CR2WTable, each {offset:u32, count:u32, crc:u32} = 12 bytes
TABLE_ENTRY_SIZE        = 12
TABLE_EXPORTS           = 4      # exports / chunk table
TABLE_BUFFERS           = 5      # embedded buffer table

# CR2W export (chunk) entry — 24 bytes
#   +0  u16 className
#   +2  u16 objectFlags
#   +4  u32 parentID
#   +8  u32 dataOffset  ← absolute offset in file
#   +12 u32 dataSize
#   +16 u32 template
#   +20 u32 crc32
EXPORT_ENTRY_SIZE    = 24
EXPORT_DATAOFFSET_AT = 8     # byte offset of dataOffset field inside an export entry

# CR2W buffer entry — 24 bytes
#   +0  u32 flags
#   +4  u32 index
#   +8  u32 offset      ← absolute offset in file
#   +12 u32 diskSize
#   +16 u32 memSize
#   +20 u32 crc32
BUFFER_ENTRY_SIZE    = 24
BUFFER_OFFSET_AT     = 8

# Max string byte length (7-bit len_byte encoding: 0x80 | len, max = 0x7F = 127)
MAX_STRING_BYTES = 127


# ── low-level helpers ──────────────────────────────────────────────────────────

def ru16(data: bytes, pos: int):
    return struct.unpack_from('<H', data, pos)[0], pos + 2

def ru32(data: bytes, pos: int):
    return struct.unpack_from('<I', data, pos)[0], pos + 4

def ru64(data: bytes, pos: int):
    return struct.unpack_from('<Q', data, pos)[0], pos + 8


# ── serialization ──────────────────────────────────────────────────────────────

def _encode_str(s: str) -> bytes:
    """Encode a Python string to UTF-8, truncated to MAX_STRING_BYTES without splitting chars."""
    raw = s.encode('utf-8')
    if len(raw) <= MAX_STRING_BYTES:
        return raw
    raw = raw[:MAX_STRING_BYTES]
    # Don't cut in the middle of a multi-byte sequence
    while raw and (raw[-1] & 0xC0) == 0x80:
        raw = raw[:-1]
    return raw


def pack_string_prop(name_cname: int, type_cname: int, value: str) -> bytes:
    """Serialize: [name:u16][String_type:u16][size:u32][len_byte:u8][utf8…]"""
    utf8 = _encode_str(value)
    n = len(utf8)
    size = n + 5          # self-inclusive: 4 (size field) + 1 (len_byte) + n
    len_byte = 0x80 | n
    return (struct.pack('<HHI', name_cname, type_cname, size)
            + bytes([len_byte])
            + utf8)


def pack_uint64_prop(name_cname: int, type_cname: int, value: int) -> bytes:
    """Serialize: [name:u16][Uint64_type:u16][12:u32][value:u64]"""
    return struct.pack('<HHIQ', name_cname, type_cname, 12, value)


def pack_entry(entry: dict, idx: dict) -> bytes:
    """
    Serialize one entry using the file-specific CName indices in `idx`.

    `idx` maps logical names to per-file CName table indices, e.g.:
      {'primaryKey': 10, 'secondaryKey': 12, 'femaleVariant': 14, 'maleVariant': 15,
       'String': 13, 'Uint64': 11}

    Each entry dict has:
      - 'primaryKey', 'secondaryKey', 'femaleVariant', 'maleVariant'  (translated values)
      - '_props': list of (name_idx, raw_bytes | None)
          None  → use the current dict value for that field (translated or original)
          bytes → unknown property; emit verbatim
    If '_props' is absent the entry only has the 4 standard fields.
    """
    props = entry.get('_props')
    if props is None:
        # Simple path: no raw-property info stored
        return (
            pack_uint64_prop(idx['primaryKey'],    idx['Uint64'], entry.get('primaryKey', 0))
            + pack_string_prop(idx['secondaryKey'],  idx['String'], entry.get('secondaryKey', ''))
            + pack_string_prop(idx['femaleVariant'], idx['String'], entry.get('femaleVariant', ''))
            + pack_string_prop(idx['maleVariant'],   idx['String'], entry.get('maleVariant', ''))
            + b'\x00\x00'
        )

    out = b''
    for name_idx, raw in props:
        if raw is not None:
            out += raw   # unknown property — preserve verbatim
        elif name_idx == idx['primaryKey']:
            out += pack_uint64_prop(idx['primaryKey'], idx['Uint64'], entry.get('primaryKey', 0))
        elif name_idx == idx['secondaryKey']:
            out += pack_string_prop(idx['secondaryKey'],  idx['String'], entry.get('secondaryKey', ''))
        elif name_idx == idx['femaleVariant']:
            out += pack_string_prop(idx['femaleVariant'], idx['String'], entry.get('femaleVariant', ''))
        elif name_idx == idx['maleVariant']:
            out += pack_string_prop(idx['maleVariant'],   idx['String'], entry.get('maleVariant', ''))
    out += b'\x00\x00'
    return out


def parse_cname_table(data: bytes) -> dict:
    """
    Parse the file's CName (Names) table — table[0] in the CR2W tables array.

    Each entry is 8 bytes: {string_offset:u32, hash:u32}.
    string_offset points to a NUL-terminated UTF-8 string elsewhere in the file.

    Returns dict {name_string: index} or empty dict if parsing fails.
    """
    try:
        tbl_pos = HEADER_TABLES_OFFSET   # 0x28: first CR2WTable entry
        tbl_offset = struct.unpack_from('<I', data, tbl_pos)[0]
        tbl_count  = struct.unpack_from('<I', data, tbl_pos + 4)[0]

        if tbl_offset == 0 or tbl_count == 0 or tbl_offset >= len(data):
            return {}

        result = {}
        for i in range(tbl_count):
            entry_pos = tbl_offset + i * 8
            if entry_pos + 8 > len(data):
                break
            str_offset = struct.unpack_from('<I', data, entry_pos)[0]
            if str_offset == 0 or str_offset >= len(data):
                continue
            end = data.find(b'\x00', str_offset)
            if end < 0:
                continue
            name = data[str_offset:end].decode('utf-8', errors='replace')
            result[name] = i
        return result
    except Exception:
        return {}


def build_cname_indices(data: bytes) -> dict:
    """
    Build per-file CName index lookup, with fallback to module-level defaults
    if the file's CName table doesn't contain the expected names.
    """
    cn = parse_cname_table(data)
    return {
        'primaryKey':    cn.get('primaryKey',    CNAME_PRIMARY_KEY),
        'secondaryKey':  cn.get('secondaryKey',  CNAME_SECONDARY_KEY),
        'femaleVariant': cn.get('femaleVariant', CNAME_FEMALE_VARIANT),
        'maleVariant':   cn.get('maleVariant',   CNAME_MALE_VARIANT),
        'String':        cn.get('String',        CNAME_STRING),
        'Uint64':        cn.get('Uint64',        CNAME_UINT64),
    }


# ── binary parsing ─────────────────────────────────────────────────────────────

def find_entries_start(data: bytes, idx: dict = None) -> int:
    """First primaryKey field after the CR2W header area, using file-specific indices."""
    if idx is None:
        idx = build_cname_indices(data)
    sig = struct.pack('<HH', idx['primaryKey'], idx['Uint64'])
    pos = data.find(sig, 0x200)
    return pos


def _read_property(data: bytes, pos: int, idx: dict):
    """
    Read one CR2W property using file-specific type indices in `idx`.
    Returns (name_idx, type_idx, value, raw_bytes, next_pos) or None for end-of-entry.
    """
    name_idx = struct.unpack_from('<H', data, pos)[0]
    if name_idx == 0:
        return None

    type_idx   = struct.unpack_from('<H', data, pos + 2)[0]
    size       = struct.unpack_from('<I', data, pos + 4)[0]
    data_len   = size - 4
    data_start = pos + 8
    next_pos   = data_start + data_len
    raw        = bytes(data[pos:next_pos])   # snapshot of all bytes for this prop

    if type_idx == idx['Uint64']:
        value = struct.unpack_from('<Q', data, data_start)[0]
    elif type_idx == idx['String']:
        len_byte = data[data_start]
        str_len  = len_byte & 0x7F
        value = data[data_start + 1: data_start + 1 + str_len].decode('utf-8', errors='replace')
    else:
        value = None

    return name_idx, type_idx, value, raw, next_pos


def parse_all_entries_with_end(data: bytes, entries_start: int, idx: dict = None):
    """
    Parse every entry including unknown properties (sub-object refs etc.).

    `idx` is the file-specific CName index lookup. If None, uses module defaults.

    Each entry dict contains:
      primaryKey / secondaryKey / femaleVariant / maleVariant  — field values
      _props     — [(name_idx, None)] for known fields, [(name_idx, raw_bytes)] for unknown
      _orig_start / _orig_end — byte span in `data`

    Returns (entries_list, entries_end_pos).
    """
    if idx is None:
        idx = build_cname_indices(data)

    primary_idx = idx['primaryKey']
    secondary_idx = idx['secondaryKey']
    female_idx = idx['femaleVariant']
    male_idx = idx['maleVariant']

    entries    = []
    pos        = entries_start
    entries_end = entries_start

    while pos + 4 < len(data):
        peek = struct.unpack_from('<H', data, pos)[0]
        if peek == 0xFFFF:
            break

        entry = {
            'primaryKey': 0, 'secondaryKey': '', 'femaleVariant': '', 'maleVariant': '',
            '_props': [],
            '_orig_start': pos,
            '_orig_end':   pos,
        }
        found_entry = False

        # Match the entry-start signature dynamically: [primaryKey:u16][Uint64:u16]
        start_sig = struct.pack('<HH', primary_idx, idx['Uint64'])
        if data[pos:pos+4] != start_sig:
            scan = data.find(start_sig, pos, pos + 32)
            if scan < 0:
                break
            pos = scan
            entry['_orig_start'] = pos

        while pos + 2 < len(data):
            result = _read_property(data, pos, idx)
            if result is None:
                pos += 2
                entries_end        = pos
                entry['_orig_end'] = pos
                found_entry        = True
                break

            name_idx, type_idx, value, raw, next_pos = result

            if name_idx == primary_idx:
                entry['primaryKey'] = value
                entry['_props'].append((primary_idx, None))
            elif name_idx == secondary_idx:
                entry['secondaryKey'] = value or ''
                entry['_props'].append((secondary_idx, None))
            elif name_idx == female_idx:
                entry['femaleVariant'] = value or ''
                entry['_props'].append((female_idx, None))
            elif name_idx == male_idx:
                entry['maleVariant'] = value or ''
                entry['_props'].append((male_idx, None))
            else:
                # Unknown property (sub-object ref, extra field, etc.) — store raw bytes
                entry['_props'].append((name_idx, raw))

            pos = next_pos

        if found_entry:
            entries.append(entry)

    return entries, entries_end


# Keep old name as alias for verify re-parse
def parse_all_entries(data: bytes, entries_start: int, idx: dict = None) -> list:
    entries, _ = parse_all_entries_with_end(data, entries_start, idx)
    return entries


def fix_cr2w_header_offsets(new_data: bytearray, entries_start: int,
                             entries_end_orig: int, delta: int,
                             orig_entry_starts: list, new_entry_starts: list):
    """
    Fix all CR2W export.dataOffset and buffer.offset fields after modifying the
    entries section.

    Three cases for each stored offset value V:
      V < entries_start      → not affected (pointer is before our section)
      V >= entries_end_orig  → simple shift: new value = V + delta
      otherwise              → embedded: find which original entry contains V,
                               then remap using the corresponding new entry start

    orig_entry_starts / new_entry_starts must be parallel lists of the same length.
    """
    if delta == 0:
        return

    u32     = lambda p: struct.unpack_from('<I', new_data, p)[0]
    n_spans = len(orig_entry_starts)

    def remap(v: int) -> int:
        if v < entries_start:
            return v                     # before our section — unchanged
        if v >= entries_end_orig:
            return v + delta             # after our section — simple shift
        # Embedded: binary-search for the containing entry
        lo, hi = 0, n_spans - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if orig_entry_starts[mid] <= v:
                lo = mid
            else:
                hi = mid - 1
        # lo is the entry whose start <= v
        offset_within = v - orig_entry_starts[lo]
        return new_entry_starts[lo] + offset_within

    def fix_field(field_pos: int):
        val = u32(field_pos)
        new_val = remap(val)
        if new_val != val:
            struct.pack_into('<I', new_data, field_pos, new_val)

    # ── exports ───────────────────────────────────────────────────────────────
    exp_tbl   = HEADER_TABLES_OFFSET + TABLE_EXPORTS * TABLE_ENTRY_SIZE
    exp_base  = u32(exp_tbl)
    exp_count = u32(exp_tbl + 4)
    if exp_base > 0:
        for i in range(exp_count):
            fix_field(exp_base + i * EXPORT_ENTRY_SIZE + EXPORT_DATAOFFSET_AT)

    # ── buffers ───────────────────────────────────────────────────────────────
    buf_tbl   = HEADER_TABLES_OFFSET + TABLE_BUFFERS * TABLE_ENTRY_SIZE
    buf_base  = u32(buf_tbl)
    buf_count = u32(buf_tbl + 4)
    if buf_base > 0:
        for i in range(buf_count):
            fix_field(buf_base + i * BUFFER_ENTRY_SIZE + BUFFER_OFFSET_AT)


# ── per-file injection ─────────────────────────────────────────────────────────

def inject_file(filepath: Path, translated_entries: list,
                verify: bool = False, test_ascii: bool = False) -> bool:
    """
    Inject translated text into a CR2W localization file.

    Strategy:
      1. Parse ALL entries from the original binary (including ones with empty strings
         that cp2077_extract.py filtered out — the binary contains more entries than
         the translated JSON).
      2. Build a lookup {primaryKey → translated_entry}.
      3. Merge: for each original entry, use the translated text if available,
         otherwise keep the original text.
      4. Serialize the merged entries (same count as original → no index corruption).
      5. Patch fileSize and chunk dataSize in the header.
    """
    with open(filepath, 'rb') as f:
        original = f.read()

    if original[:4] != b'CR2W':
        print(f"    skip: not CR2W")
        return False

    # Build per-file CName index lookup — each file declares its own subset of
    # CNames, so 'femaleVariant' may live at index 14 in onscreens.json but at a
    # different index in subtitle files.
    idx = build_cname_indices(original)

    entries_start = find_entries_start(original, idx)
    if entries_start < 0:
        print(f"    skip: no entry start found (cnames: pk={idx['primaryKey']}, fv={idx['femaleVariant']}, mv={idx['maleVariant']})")
        return False

    # ── Step 1: parse ALL original entries ──────────────────────────────────
    # NOTE: In CP2077 localization CR2W files, export[1].dataOffset may point INTO
    # the middle of the entries section (not after it). Do NOT cap at that offset —
    # the parser's natural end is the true entries section boundary.
    all_orig, entries_end = parse_all_entries_with_end(original, entries_start, idx)

    if not all_orig:
        print(f"    skip: no entries parsed")
        return False
    if entries_end <= entries_start:
        print(f"    skip: could not locate entries end ({len(all_orig)} entries parsed)")
        return False

    # ── Step 2: build translation lookup keyed by primaryKey ────────────────
    trans_lookup = {e.get('primaryKey'): e for e in translated_entries}

    # ── Step 3: merge (keep _props / _orig_start / _orig_end from original) ──
    merged = []
    for orig in all_orig:
        pk = orig.get('primaryKey', 0)
        t  = trans_lookup.get(pk)
        if t:
            entry = dict(orig)   # copy including _props and _orig_* spans
            if test_ascii:
                # Inject a visible ASCII marker to confirm string packing works
                # before worrying about font support
                entry['femaleVariant'] = 'TEST_STRING'
                entry['maleVariant']   = 'TEST_STRING'
            else:
                entry['femaleVariant'] = t.get('femaleVariant') or orig.get('femaleVariant', '')
                entry['maleVariant']   = t.get('maleVariant')   or orig.get('maleVariant', '')
            merged.append(entry)
        else:
            merged.append(orig)

    # ── Step 4: serialize + build entry span tables ──────────────────────────
    serialized   = [pack_entry(e, idx) for e in merged]
    new_entries_bytes = b''.join(serialized)

    old_section_len = entries_end - entries_start
    new_section_len = len(new_entries_bytes)
    delta           = new_section_len - old_section_len

    # Parallel arrays of original and new absolute start positions per entry
    orig_entry_starts = [e['_orig_start'] for e in all_orig]
    new_entry_starts  = []
    cursor = entries_start
    for b in serialized:
        new_entry_starts.append(cursor)
        cursor += len(b)

    # ── Step 5: build new binary ─────────────────────────────────────────────
    new_data = bytearray(original[:entries_start])
    new_data += new_entries_bytes
    new_data += original[entries_end:]

    # Fix fileSize (always use actual length — CR2W may store 0 here).
    struct.pack_into('<I', new_data, HEADER_FILE_SIZE_OFFSET, len(new_data))

    # Fix the array property header (count + size fields) that precedes the entries section.
    # Layout at entries_start - 9:
    #   [name:u16][type:u16][size:u32][count:u32] then entries begin
    # Both size and count must be updated or the engine/WolvenKit reads the wrong byte range.
    count_field_pos = entries_start - 5   # u32 — number of entries
    size_field_pos  = entries_start - 9   # u32 — byte length of (count field + all items)

    if count_field_pos >= 0:
        struct.pack_into('<I', new_data, count_field_pos, len(merged))

    if size_field_pos >= 0:
        # size field encodes: distance from size field position to entries_end.
        # Derivation: orig_size = entries_end - size_field_pos
        #             new_size  = new_entries_end - size_field_pos
        #                       = (entries_start + new_section_len) - (entries_start - 9)
        #                       = new_section_len + 9
        # We compute the addend from the original values so this generalizes across files.
        orig_size = struct.unpack_from('<I', original, size_field_pos)[0]
        old_section_len_for_size = entries_end - entries_start
        size_addend = orig_size - old_section_len_for_size  # = 9 for onscreens.json
        new_size = new_section_len + size_addend
        struct.pack_into('<I', new_data, size_field_pos, new_size)

    # Fix all CR2W export and buffer offsets (handles before/after/embedded cases).
    fix_cr2w_header_offsets(new_data, entries_start, entries_end, delta,
                            orig_entry_starts, new_entry_starts)

    print(f"    {len(all_orig)} entries, delta={delta:+d} bytes "
          f"({len(original)} → {len(new_data)})")

    # ── Step 7: write ────────────────────────────────────────────────────────
    with open(filepath, 'wb') as f:
        f.write(new_data)

    # ── Step 8: verify (optional) ────────────────────────────────────────────
    if verify:
        re_data  = bytes(new_data)
        re_idx   = build_cname_indices(re_data)
        re_start = find_entries_start(re_data, re_idx)
        re_all, re_end = parse_all_entries_with_end(re_data, re_start, re_idx)

        if len(re_all) != len(all_orig):
            print(f"    VERIFY FAIL: original had {len(all_orig)} entries, "
                  f"re-read {len(re_all)}")
            return False

        # Check the actual data length matches expectation
        if re_end - re_start != new_section_len:
            print(f"    VERIFY FAIL: section size mismatch "
                  f"(expected {new_section_len}, got {re_end - re_start})")
            return False

    return True


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    translated_json_path = Path(sys.argv[1])
    dry_run    = '--dry-run'    in sys.argv
    verify     = '--verify'     in sys.argv
    test_ascii = '--test-ascii' in sys.argv
    if test_ascii:
        print("[!] TEST MODE: injecting 'TEST_STRING' for all translated entries")

    if not translated_json_path.exists():
        print(f"ERROR: {translated_json_path} not found")
        sys.exit(1)

    print(f"Loading translations from {translated_json_path} ...")
    with open(translated_json_path, 'r', encoding='utf-8') as f:
        all_translations: dict = json.load(f)

    print(f"  {len(all_translations)} files in translation JSON")
    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  Backups → {BACKUP_DIR}")
    print()

    ok = skipped = failed = 0

    for rel_path, entries in sorted(all_translations.items()):
        filepath = ARCHIVE_DIR / Path(rel_path.replace('/', os.sep))

        if not filepath.exists():
            print(f"MISS  {rel_path}")
            skipped += 1
            continue

        if dry_run:
            # Estimate new size without writing
            new_bytes = sum(len(pack_entry(e)) for e in entries)
            print(f"DRY   {rel_path}  ({len(entries)} entries, ~{new_bytes} B)")
            ok += 1
            continue

        # Backup (once, don't overwrite existing backup)
        backup = BACKUP_DIR / Path(rel_path.replace('/', os.sep))
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(filepath, backup)

        try:
            success = inject_file(filepath, entries, verify=verify, test_ascii=test_ascii)
        except Exception as e:
            print(f"ERR   {rel_path}: {e}")
            # Restore from backup
            shutil.copy2(backup, filepath)
            failed += 1
            continue

        if success:
            ok += 1
            if ok % 200 == 0:
                print(f"  ... {ok} files done")
        else:
            print(f"FAIL  {rel_path}")
            shutil.copy2(backup, filepath)
            failed += 1

    print()
    print(f"{'[DRY RUN] ' if dry_run else ''}Done: {ok} ok, {failed} failed, {skipped} missing")


if __name__ == '__main__':
    main()
