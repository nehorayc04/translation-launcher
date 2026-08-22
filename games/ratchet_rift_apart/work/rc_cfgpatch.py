"""Delta-0 patch of the shared launcher+pause-menu UI config-doc.

WHY THIS EXISTS
---------------
Three settings tabs (Display&Graphics / Key Mapping / Mouse) render their RAW ASCII KEY NAME
in-game, while the structurally-identical Controller tab renders our Hebrew. Everything that
could explain a localization miss was ruled out with evidence:

  * the keys DO exist in the shipped table, with real English values;
  * the engine looks strings up BY HASH (crc32.hash(key, normalize=False)), and the hash the
    config-doc carries for each broken key matches the localization table EXACTLY;
  * a full engine-lookup simulation resolves all 24k entries, these included;
  * crc64-probing the whole toc finds exactly ONE localization asset, so they cannot be
    reading some other table.

=> the lookup is not failing. Those widget classes (PageVisual / PageKeyBindings / TypeHeader,
vs PageControls which works) draw the config-doc's own string RAW instead of localizing it.
So the only surface that can carry their Hebrew is the config doc itself.

THE PATCH
---------
Each string reference in the doc is  [u32 len][u32 hash][u32][u32][bytes]\\0  — i.e. the length
sits 16 bytes before the string and its crc32 hash 12 bytes before (len EXCLUDES the NUL).
We overwrite the string bytes in place with UTF-8 Hebrew padded with spaces to the EXACT
original length, and leave `len` and `hash` untouched — so no offset in the document moves
and nothing else in the 129 KB doc changes. The asset then ships through the same proven
index-redirect path as the loc variants (header_offset != -1, value = len(blob)).

The bidi mode of that raw-draw path is unknown, so the three tabs are deliberately built as
an A/B: two VISUAL, one LOGICAL. Whichever group reads correctly names the mode, and either
way at least two of the three tabs stop showing an ASCII key name.
"""
import struct

CFG_AID = 0x8B875EC96CB13E41
LEN_OFF, HASH_OFF = 16, 12          # bytes before the string: u32 length, u32 crc32 hash


def find_records(doc: bytes, key: str, hash_of=None):
    """Locate EVERY record for `key` (a label can be referenced from more than one page list —
    e.g. the launcher's and the in-game menu's — and all of them must carry the same text).
    Each hit is validated three ways: NUL-terminated, the declared length matches, and (if
    given) the stored crc32 hash matches. Returns [str_off, …]."""
    kb = key.encode("ascii")
    hits = []
    p = doc.find(kb)
    while p >= 0:
        end_ok = p + len(kb) < len(doc) and doc[p + len(kb)] == 0
        len_ok = p >= LEN_OFF and struct.unpack_from("<I", doc, p - LEN_OFF)[0] == len(kb)
        h_ok = True
        if hash_of is not None and len_ok:
            h_ok = struct.unpack_from("<I", doc, p - HASH_OFF)[0] == hash_of(key)
        if end_ok and len_ok and h_ok:
            hits.append(p)
        p = doc.find(kb, p + 1)
    if not hits:
        raise KeyError(f"{key}: no valid record found in the config doc")
    return hits


def patch(doc: bytes, repl: dict, hash_of=None) -> tuple[bytes, list]:
    """repl = {key: utf8_bytes}. Overwrites in place, space-padded, same total length."""
    out = bytearray(doc)
    done = []
    for key, val in repl.items():
        offs = find_records(doc, key, hash_of)
        ln = len(key.encode("ascii"))
        if len(val) > ln:
            raise ValueError(f"{key}: replacement {len(val)}B exceeds slot {ln}B")
        for off in offs:
            out[off:off + ln] = val + b" " * (ln - len(val))
            done.append((key, off, ln, len(val)))
    assert len(out) == len(doc), "config-doc length changed — must stay delta-0"
    return bytes(out), done


def verify(orig: bytes, new: bytes, done: list):
    """Assert nothing outside the patched string slots changed."""
    assert len(orig) == len(new)
    allowed = set()
    for _, off, ln, _ in done:
        allowed.update(range(off, off + ln))
    diff = [i for i in range(len(orig)) if orig[i] != new[i]]
    stray = [i for i in diff if i not in allowed]
    assert not stray, f"{len(stray)} bytes changed OUTSIDE the patched slots (first {stray[:5]})"
    # every record's length + hash header must be untouched
    for _, off, ln, _ in done:
        assert orig[off - LEN_OFF:off] == new[off - LEN_OFF:off], "len/hash header was modified"
    return len(diff)
