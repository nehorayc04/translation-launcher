"""
CP2077 Localization Extractor
Reads binary CR2W localization files and extracts text entries to JSON.

Usage:
  python cp2077_extract.py

Output:
  source/resources/localization_export.json
"""

import struct
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים")
ARCHIVE_DIR  = PROJECT_ROOT / "source" / "archive" / "base" / "localization" / "en-us"
OUTPUT_FILE  = PROJECT_ROOT / "source" / "resources" / "localization_export.json"

# CR2W CName indices for localization files
CNAME_PRIMARY_KEY    = 10  # 'primaryKey'
CNAME_UINT64         = 11  # 'Uint64'
CNAME_SECONDARY_KEY  = 12  # 'secondaryKey'
CNAME_STRING         = 13  # 'String'
CNAME_FEMALE_VARIANT = 14  # 'femaleVariant'
CNAME_MALE_VARIANT   = 15  # 'maleVariant'

# Folders to skip (audio/lip sync, not translatable text)
SKIP_FOLDERS = {'lipsync', 'vo', 'vo_helmet', 'vo_holocall', 'vo_rewinded'}


def u16(data: bytes, pos: int):
    return struct.unpack_from('<H', data, pos)[0], pos + 2

def u32(data: bytes, pos: int):
    return struct.unpack_from('<I', data, pos)[0], pos + 4

def u64(data: bytes, pos: int):
    return struct.unpack_from('<Q', data, pos)[0], pos + 8


def read_property(data: bytes, pos: int):
    """Read one CR2W property. Returns (name_idx, type_idx, value, next_pos) or None for end marker."""
    name_idx, pos = u16(data, pos)
    if name_idx == 0:
        return None  # end of entry

    type_idx, pos = u16(data, pos)
    size, pos     = u32(data, pos)   # self-inclusive size (includes these 4 bytes)
    data_len      = size - 4
    data_start    = pos

    if type_idx == CNAME_UINT64:
        value, _ = u64(data, data_start)
    elif type_idx == CNAME_STRING:
        len_byte = data[data_start]
        str_len  = len_byte & 0x7F
        value    = data[data_start + 1 : data_start + 1 + str_len].decode('utf-8', errors='replace')
    else:
        value = None  # unsupported type, skip

    return name_idx, type_idx, value, data_start + data_len


def parse_entries(data: bytes, start_pos: int):
    """Parse all localization entries from binary data starting at start_pos."""
    entries = []
    pos = start_pos

    while pos + 4 < len(data):
        # Peek at next name_CName — if 0 it could be array end
        peek = struct.unpack_from('<H', data, pos)[0]
        if peek == 0xFFFF:  # some files use 0xFFFF as array end
            break

        entry = {'primaryKey': 0, 'secondaryKey': '', 'femaleVariant': '', 'maleVariant': ''}
        found_entry = False

        # Try to read primaryKey as entry start
        if data[pos:pos+4] != b'\x0a\x00\x0b\x00':
            # Not a primaryKey field — might be padding or end of array
            # Scan forward for next entry start
            scan = data.find(b'\x0a\x00\x0b\x00', pos, pos + 32)
            if scan < 0:
                break
            pos = scan

        # Read all properties of this entry
        while pos + 2 < len(data):
            result = read_property(data, pos)
            if result is None:
                pos += 2  # consumed the 00 00 end marker
                found_entry = True
                break

            name_idx, type_idx, value, next_pos = result

            if name_idx == CNAME_PRIMARY_KEY:
                entry['primaryKey'] = value
            elif name_idx == CNAME_SECONDARY_KEY:
                entry['secondaryKey'] = value or ''
            elif name_idx == CNAME_FEMALE_VARIANT:
                entry['femaleVariant'] = value or ''
            elif name_idx == CNAME_MALE_VARIANT:
                entry['maleVariant'] = value or ''

            pos = next_pos

        if found_entry and entry['secondaryKey']:
            entries.append(entry)

    return entries


def find_entries_start(data: bytes) -> int:
    """Find the start of the entries array in the binary data."""
    # Look for the first primaryKey field header: 0a 00 0b 00
    marker = b'\x0a\x00\x0b\x00'
    pos = data.find(marker, 0x200)  # skip header
    if pos < 0:
        return -1

    # Scan backwards for array header (sometimes entries are preceded by count/offset bytes)
    # Just return the first primaryKey position
    return pos


def extract_file(filepath: Path) -> list:
    """Extract entries from a single CR2W localization file."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"  ERROR reading {filepath.name}: {e}")
        return []

    # Verify CR2W magic
    if data[:4] != b'CR2W':
        return []

    start = find_entries_start(data)
    if start < 0:
        return []

    return parse_entries(data, start)


def should_skip(path: Path) -> bool:
    return any(skip in path.parts for skip in SKIP_FOLDERS)


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_files = {}
    json_files = sorted(ARCHIVE_DIR.rglob('*.json'))

    print(f"Found {len(json_files)} JSON files in archive")
    print(f"Skipping: {SKIP_FOLDERS}")
    print()

    processed = 0
    skipped   = 0
    total_entries = 0

    for filepath in json_files:
        rel = filepath.relative_to(ARCHIVE_DIR)

        if should_skip(rel):
            skipped += 1
            continue

        entries = extract_file(filepath)
        if not entries:
            continue

        key = str(rel).replace('\\', '/')
        all_files[key] = entries
        processed += 1
        total_entries += len(entries)

        if processed % 100 == 0:
            print(f"  Processed {processed} files, {total_entries} entries so far...")

    print()
    print(f"Done: {processed} files, {total_entries} entries extracted")
    print(f"Skipped: {skipped} files")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_files, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {OUTPUT_FILE}")
    size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print(f"File size: {size_mb:.1f} MB")


if __name__ == '__main__':
    main()
