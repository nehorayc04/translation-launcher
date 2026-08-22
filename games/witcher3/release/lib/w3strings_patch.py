# -*- coding: utf-8 -*-
"""SURGICAL single-string patch for an ENCRYPTED (non-Arabic) .w3strings — no full re-encode.

WHY THIS EXISTS (a bug that broke the game once — do not repeat it):
`w3strings.encode()` rebuilds the blob SEQUENTIALLY in block1 order. That reproduces `ar.w3strings`
BYTE-IDENTICALLY (its blob really is laid out in block1 order) — but in EVERY other language file the
blob order is DIFFERENT from block1 order (offsets are not sequential). So a full re-encode of, say,
`en.w3strings` silently rewrites every offset -> the game resolves nothing -> the whole UI falls back
to raw keys (`#PANEL_CONTINUE`, `#MENU_MAIN_QUIT`, ...). Symptom seen live 2026-07-14.

THE SAFE WAY — touch nothing that already exists:
  1. keep the original bytes verbatim (header, block1, block2, the entire blob),
  2. APPEND the new string (enciphered with the file's own language key) at the END of the blob,
  3. repoint ONLY the target entry's `offset`/`strlen` in block1, and bump `count3`.
Offsets are relative to the blob start, so even if the varint `count3` field changes length nothing
else shifts. Every other string keeps its exact original bytes and offset.

Verified by decoding the RESULT and asserting every entry is unchanged except the patched one.
"""
import struct
import w3strings as W


def _bit6_len(n):
    return len(W.emit_bit6(n))


def _read_header(data):
    """-> (block1_start, count1, count2_start, count3_field_start, count3, blob_start)"""
    assert data[:4] == b"RTSW"
    r = W._R(data); r.p = 10
    count1 = W.bit6(r)
    block1_start = r.p
    r.p = block1_start + count1 * 12
    count2_start = r.p
    count2 = W.bit6(r)
    r.p += count2 * 8
    count3_field_start = r.p
    count3 = W.bit6(r)
    blob_start = r.p
    return block1_start, count1, count2_start, count3_field_start, count3, blob_start


def encipher(text, enckey):
    """Apply the language's per-string XOR stream (symmetric — same routine decodes)."""
    u16 = text.encode("utf-16-le")
    strlen = len(u16) // 2
    if not enckey:
        return u16, strlen
    out = bytearray()
    string_key = (enckey >> 8) & 0xFFFF
    for j in range(strlen):
        b1, b2 = u16[j * 2], u16[j * 2 + 1]
        char_key = ((strlen + 1) * string_key) & 0xFFFF
        b1 ^= char_key & 0xFF
        b2 ^= (char_key >> 8) & 0xFF
        string_key = ((string_key << 1) | (string_key >> 15)) & 0xFFFF
        out += bytes((b1, b2))
    return bytes(out), strlen


def patch_string(raw, str_id, new_text):
    """Return new .w3strings bytes with `str_id`'s text replaced by `new_text`. Everything else
    (including every other string's bytes and offset) is preserved verbatim."""
    key1 = struct.unpack_from("<H", raw, 8)[0]
    key2 = struct.unpack_from("<H", raw, len(raw) - 2)[0]
    keyid = (key1 << 16) | key2
    enckey, _lang = W.get_key(keyid)

    b1_start, count1, _c2s, c3_field, count3, blob_start = _read_header(raw)
    blob_end = len(raw) - 2                       # key2 is the last 2 bytes
    blob = raw[blob_start:blob_end]

    # locate the entry in block1
    idx = None
    for i in range(count1):
        off = b1_start + i * 12
        sid = struct.unpack_from("<I", raw, off)[0] ^ enckey
        if sid == str_id:
            idx = i
            break
    if idx is None:
        raise KeyError(f"str_id {str_id} not in block1")

    enc, strlen = encipher(new_text, enckey)
    new_offset = len(blob) // 2                   # append at the blob end (in UTF-16 units)
    new_blob = blob + enc + b"\x00\x00"
    new_count3 = len(new_blob) // 2

    # rebuild: [header .. block2]  +  bit6(count3)  +  blob  +  key2
    head = bytearray(raw[:c3_field])
    e_off = b1_start + idx * 12
    struct.pack_into("<II", head, e_off + 4, new_offset, strlen)   # offset + strlen (str_id kept)
    out = bytes(head) + W.emit_bit6(new_count3) + new_blob + raw[-2:]
    return out


def verify(orig, patched, str_id, new_text):
    """Decode BOTH and assert only `str_id` changed."""
    a = W.decode(orig); b = W.decode(patched)
    if len(a["entries"]) != len(b["entries"]):
        return False, "entry count changed"
    if a["keyid"] != b["keyid"]:
        return False, "keyid changed"
    am = {e["str_id"]: e["text"] for e in a["entries"]}
    bm = {e["str_id"]: e["text"] for e in b["entries"]}
    if set(am) != set(bm):
        return False, "str_id set changed"
    diff = [k for k in am if am[k] != bm[k]]
    if diff != [str_id]:
        return False, f"unexpected changes: {diff[:5]} ({len(diff)} total)"
    if bm[str_id] != new_text:
        return False, f"target text is {bm[str_id]!r}, expected {new_text!r}"
    if a["block2"] != b["block2"]:
        return False, "block2 changed"
    return True, "ok"
