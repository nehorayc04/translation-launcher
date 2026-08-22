"""Pure-Python reader/writer for Unreal Engine .locres (LocRes) files.

Format spec ported from akintos/UnrealLocres (LocresLib/LocresFile.cs),
MIT-style reference implementation. Supports all 4 versions; this game's
files use version 3 (Optimized_CityHash64_UTF16).

Usage:
    python ud_locres.py info <file.locres>
    python ud_locres.py dump <file.locres> [out.json]
"""
import json
import struct
import sys

MAGIC = bytes([0x0E, 0x14, 0x74, 0x75, 0x67, 0x4A, 0x03, 0xFC,
                0x4A, 0x15, 0x90, 0x9D, 0xC3, 0x37, 0x7F, 0x1B])

LEGACY = 0
COMPACT = 1
OPTIMIZED = 2
OPTIMIZED_CITYHASH64_UTF16 = 3


def _read_i32(buf, off):
    return struct.unpack_from('<i', buf, off)[0], off + 4


def _read_u32(buf, off):
    return struct.unpack_from('<I', buf, off)[0], off + 4


def _read_i64(buf, off):
    return struct.unpack_from('<q', buf, off)[0], off + 8


def _read_unreal_string(buf, off):
    length, off = _read_i32(buf, off)
    if length > 0:
        data = buf[off:off + length]
        off += length
        s = data.decode('ascii', errors='replace')
    elif length < 0:
        n = -length * 2
        data = buf[off:off + n]
        off += n
        s = data.decode('utf-16-le', errors='replace')
    else:
        return "", off
    return s.rstrip('\x00'), off


def load(path):
    """Returns dict: {version, namespaces: [{name, hash, entries:[{key,key_hash,value,source_hash,str_index}]}]}"""
    with open(path, 'rb') as f:
        buf = f.read()
    off = 0
    if buf[0:16] == MAGIC:
        off = 16
        version = buf[off]
        off += 1
    else:
        version = LEGACY

    localized_string_array = None
    if version >= COMPACT:
        arr_offset, off = _read_i64(buf, off)
        saved_off = off
        off2 = arr_offset
        count, off2 = _read_i32(buf, off2)
        localized_string_array = []
        if version >= OPTIMIZED:
            for _ in range(count):
                s, off2 = _read_unreal_string(buf, off2)
                _refcount, off2 = _read_i32(buf, off2)
                localized_string_array.append(s)
        else:
            for _ in range(count):
                s, off2 = _read_unreal_string(buf, off2)
                localized_string_array.append(s)
        off = saved_off

    if version >= OPTIMIZED:
        _entries_count, off = _read_i32(buf, off)

    namespace_count, off = _read_i32(buf, off)
    namespaces = []
    for _ in range(namespace_count):
        ns_hash = None
        if version >= OPTIMIZED:
            ns_hash, off = _read_u32(buf, off)
        ns_name, off = _read_unreal_string(buf, off)
        key_count, off = _read_i32(buf, off)
        entries = []
        for _ in range(key_count):
            key_hash = None
            if version >= OPTIMIZED:
                key_hash, off = _read_u32(buf, off)
            key, off = _read_unreal_string(buf, off)
            source_hash, off = _read_u32(buf, off)
            str_index = None
            if version >= COMPACT:
                str_index, off = _read_i32(buf, off)
                value = localized_string_array[str_index]
            else:
                value, off = _read_unreal_string(buf, off)
            entries.append({
                'key': key, 'key_hash': key_hash,
                'value': value, 'source_hash': source_hash,
                'str_index': str_index,
            })
        namespaces.append({'name': ns_name, 'hash': ns_hash, 'entries': entries})

    return {'version': version, 'namespaces': namespaces,
            'localized_string_array': localized_string_array}


def _write_i32(v):
    return struct.pack('<i', v)


def _write_u32(v):
    return struct.pack('<I', v)


def _write_i64(v):
    return struct.pack('<q', v)


def _write_unreal_string(s):
    # An EMPTY string is stored as length 0 with NO payload (not as a lone NUL).
    # Writing "\x00" with length 1 round-trips semantically but is NOT byte-identical
    # to what the engine's own cooker emits. (Found on Corsair Cove, same codec.)
    if s == "":
        return _write_i32(0)
    s = s + "\x00"
    if all(ord(c) <= 127 for c in s):
        data = s.encode('ascii')
        return _write_i32(len(data)) + data
    data = s.encode('utf-16-le')
    return _write_i32(-len(s)) + data


def save(parsed, path):
    """Rebuilds a version-3 (Optimized_CityHash64_UTF16) locres from the
    structure returned by load() (namespaces/entries mutated in place).
    Reuses the ORIGINAL ns_hash/key_hash bytes read from the source file —
    valid as long as namespace/key names are unchanged (only values differ).
    """
    version = OPTIMIZED_CITYHASH64_UTF16
    out = bytearray()
    out += MAGIC
    out += bytes([version])
    array_offset_pos = len(out)
    out += _write_i64(0)  # placeholder
    entry_count_pos = len(out)
    out += _write_i32(0)  # placeholder (localizedStringEntryCount)
    out += _write_i32(len(parsed['namespaces']))

    string_table = []  # ordered unique values (first-appearance order == the engine's own)
    string_index = {}  # value -> index
    ref_counts = []    # the engine stores the REAL reference count, not 1
    total_entries = 0

    for ns in parsed['namespaces']:
        ns_hash = ns['hash'] if ns['hash'] is not None else 0
        out += _write_u32(ns_hash)
        out += _write_unreal_string(ns['name'])
        out += _write_i32(len(ns['entries']))
        for e in ns['entries']:
            key_hash = e['key_hash'] if e['key_hash'] is not None else 0
            out += _write_u32(key_hash)
            out += _write_unreal_string(e['key'])
            out += _write_u32(e['source_hash'])
            val = e['value']
            idx = string_index.get(val)
            if idx is None:
                idx = len(string_table)
                string_table.append(val)
                string_index[val] = idx
                ref_counts.append(0)
            ref_counts[idx] += 1
            out += _write_i32(idx)
            total_entries += 1

    string_table_offset = len(out)
    out += _write_i32(len(string_table))
    for s, rc in zip(string_table, ref_counts):
        out += _write_unreal_string(s)
        out += _write_i32(rc)  # refCount == the real number of entries pointing here

    struct.pack_into('<q', out, array_offset_pos, string_table_offset)
    struct.pack_into('<i', out, entry_count_pos, total_entries)

    with open(path, 'wb') as f:
        f.write(out)
    return {'total_entries': total_entries, 'unique_strings': len(string_table)}


def stats(parsed):
    total = sum(len(ns['entries']) for ns in parsed['namespaces'])
    return {
        'version': parsed['version'],
        'namespace_count': len(parsed['namespaces']),
        'total_entries': total,
        'unique_strings': len(parsed['localized_string_array']) if parsed['localized_string_array'] is not None else None,
    }


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'info'
    path = sys.argv[2]
    parsed = load(path)
    if cmd == 'info':
        st = stats(parsed)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        print("\nnamespaces (first 40):")
        for ns in parsed['namespaces'][:40]:
            print(f"  [{ns['name'] or '(root)'}] {len(ns['entries'])} entries")
    elif cmd == 'dump':
        out = sys.argv[3] if len(sys.argv) > 3 else None
        flat = []
        for ns in parsed['namespaces']:
            for e in ns['entries']:
                flat.append({'ns': ns['name'], 'key': e['key'], 'en': e['value']})
        if out:
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(flat, f, ensure_ascii=False, indent=1)
            print(f"wrote {len(flat)} entries -> {out}")
        else:
            print(json.dumps(flat[:50], ensure_ascii=False, indent=1))
    elif cmd == 'roundtrip':
        out = sys.argv[3] if len(sys.argv) > 3 else path + '.rt'
        save(parsed, out)
        reparsed = load(out)
        a = [(e['key'], e['value']) for ns in parsed['namespaces'] for e in ns['entries']]
        b = [(e['key'], e['value']) for ns in reparsed['namespaces'] for e in ns['entries']]
        print('original entries:', len(a), 'rebuilt entries:', len(b))
        print('identical (key,value) sequence:', a == b)
        import hashlib
        orig_hash = hashlib.md5(open(path, 'rb').read()).hexdigest()
        new_hash = hashlib.md5(open(out, 'rb').read()).hexdigest()
        print('orig md5:', orig_hash)
        print('rebuilt md5:', new_hash)
        print('byte-identical:', orig_hash == new_hash)
