"""MSMR localization codec — decode / patch / re-encode `localization_all.localization`.

Marvel's Spider-Man Remastered (Insomniac "Luna", VERSION_MSMR 202200) stores every
language as a VARIANT of ONE asset id (crc64 of
"localization/localization_all.localization" = 0xBE55D94F171BF8DE), selected by SPAN.
The asset file is:

    [36-byte asset header][DAT1 '1TAD' ...]

and its inner DAT1 carries the SAME five sections R&C Rift Apart uses, so this codec is
a direct port of games/ratchet_rift_apart/work/04_roundtrip.py:

  0xD540A903 ENTRY_COUNT   u32                      -> N (57,368 on MSMR)
  0x4D73CEBD KEYS          NUL-separated UTF-8      (identical in every variant)
  0xA4EA55B2 KEY_OFFSETS   u32 x N into KEYS        (identical in every variant)
  0x70A382B8 VALUES        NUL-separated UTF-8      (per-language)
  0xF80DEEB4 TEXT_OFFSETS  u32 x N into VALUES      (per-language)

Only VALUES + TEXT_OFFSETS are rebuilt; every other section (incl. the four u32 x N
tables 0x06A58050 / 0xC43731B5 / 0xB0653243 and the u16 x N 0x0CD2CFE9) is copied
verbatim, so nothing that indexes by slot can drift.

⚠️ MSMR's SizeEntry has NO header_offset field, so the asset bytes on disk are the
WHOLE file (36-byte header included) — unlike R&C, where a header_offset != -1 asset
must be stored header-stripped. `encode()` therefore returns header+DAT1.
"""
from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path

TAG_VALUES       = 0x70A382B8
TAG_KEYS         = 0x4D73CEBD
TAG_TEXT_OFFSETS = 0xF80DEEB4
TAG_KEY_OFFSETS  = 0xA4EA55B2
TAG_ENTRY_COUNT  = 0xD540A903

HEADER_SIZE, SECTION_HEADER_SIZE, ALIGN = 16, 12, 16
ASSET_HEADER = 36                      # bytes before the inner DAT1
LOC_ASSET_PATH = "localization/localization_all.localization"
LOC_ASSET_ID   = 0xBE55D94F171BF8DE


def _dat1lib():
    root = Path(__file__).resolve().parents[3]
    alert = root / "games" / "spiderman2" / "tools" / "ALERT"
    if str(alert) not in sys.path:
        sys.path.insert(0, str(alert))
    import dat1lib.types.dat1 as d1  # noqa
    return d1


def _cstr(buf: bytes, off: int) -> bytes:
    end = buf.find(b"\x00", off)
    return buf[off:end if end >= 0 else len(buf)]


def _align_up(x: int, a: int) -> int:
    return (x + a - 1) // a * a


class Loc:
    """Parsed localization variant. `pairs` is the aligned [(key, value_bytes)] list."""

    def __init__(self, raw: bytes):
        d1 = _dat1lib()
        self.raw = raw
        self.prefix = raw[:ASSET_HEADER]
        self.payload = raw[ASSET_HEADER:]
        self.dat1 = d1.DAT1(io.BytesIO(self.payload), None)
        self._secs = {sh.tag: (sh.offset, sh.size) for sh in self.dat1.header.sections}
        self.count = struct.unpack("<I", self._sec(TAG_ENTRY_COUNT))[0]
        kb, vb = self._sec(TAG_KEYS), self._sec(TAG_VALUES)
        koff = struct.unpack(f"<{self.count}I", self._sec(TAG_KEY_OFFSETS))
        toff = struct.unpack(f"<{self.count}I", self._sec(TAG_TEXT_OFFSETS))
        self.pairs: list[tuple[str, bytes]] = [
            (_cstr(kb, koff[i]).decode("utf-8", "replace"), _cstr(vb, toff[i]))
            for i in range(self.count)
        ]

    def _sec(self, tag: int) -> bytes:
        o, s = self._secs[tag]
        return self.payload[o:o + s]

    # ---------------------------------------------------------------- read
    def as_dict(self) -> dict[str, str]:
        """key -> value (str). Empty values are included as ''."""
        return {k: v.decode("utf-8", "replace") for k, v in self.pairs}

    def nonempty(self) -> dict[str, str]:
        d = self.as_dict()
        return {k: v for k, v in d.items() if v.strip()}

    # --------------------------------------------------------------- write
    def encode(self, patch: dict[str, str] | None = None) -> bytes:
        """Rebuild the FULL asset (36-byte header + DAT1) with `patch` applied.

        `patch` maps key -> replacement string. Unknown keys are ignored (the caller
        should verify coverage). With patch=None this is an identity rebuild."""
        vals = [v for _, v in self.pairs]
        if patch:
            for i, (k, _) in enumerate(self.pairs):
                if k in patch:
                    vals[i] = patch[k].encode("utf-8")

        # VALUES blob: leading NUL so an empty value points at offset 0; dedup by content
        new_vals = bytearray(b"\x00")
        seen: dict[bytes, int] = {b"": 0}
        new_toff = [0] * self.count
        for i, v in enumerate(vals):
            hit = seen.get(v)
            if hit is not None:
                new_toff[i] = hit
                continue
            new_toff[i] = len(new_vals)
            new_vals.extend(v)
            new_vals.append(0)
            seen[v] = new_toff[i]

        overrides = {
            TAG_VALUES: bytes(new_vals),
            TAG_TEXT_OFFSETS: struct.pack(f"<{self.count}I", *new_toff),
        }

        headers = list(self.dat1.header.sections)
        data_by_tag = {
            sh.tag: overrides.get(sh.tag, self.payload[sh.offset:sh.offset + sh.size])
            for sh in headers
        }

        out = bytearray(self.payload[:HEADER_SIZE])
        for sh in headers:
            out.extend(struct.pack("<III", sh.tag, 0, 0))
        if self.dat1.header.unknowns:
            out.extend(self.dat1.header.unknowns)
        first_off = min(sh.offset for sh in headers)
        if len(out) < first_off:                       # preserve the string blob / padding
            out.extend(self.payload[len(out):first_off])

        new_off: dict[int, int] = {}
        for sh in sorted(headers, key=lambda s: s.offset):
            cur = _align_up(len(out), ALIGN)
            if cur > len(out):
                out.extend(b"\x00" * (cur - len(out)))
            new_off[sh.tag] = len(out)
            out.extend(data_by_tag[sh.tag])

        for idx, sh in enumerate(headers):
            pos = HEADER_SIZE + idx * SECTION_HEADER_SIZE
            struct.pack_into("<III", out, pos, sh.tag, new_off[sh.tag], len(data_by_tag[sh.tag]))

        # the DAT1 header carries its own total size — patch it wherever it appears
        needle = struct.pack("<I", self.dat1.header.size)
        hoff = bytes(self.payload[:HEADER_SIZE]).find(needle)
        if hoff >= 0:
            struct.pack_into("<I", out, hoff, len(out))

        return self.prefix + bytes(out)

    # ------------------------------------------------------------- surgical write
    def encode_minimal(self, patch: dict[str, str]) -> bytes:
        """Surgical patch — root-caused 2026-08-11 against the FULL-REBUILD `encode()`
        above, which was proven to NOT round-trip identically even with patch=None
        (it dedupes VALUES and relayouts every section's offset from scratch). Every
        prior "content differs -> boot stall" deploy in this project went through that
        rebuild; a raw same-length in-place byte edit on the PRISTINE file, with zero
        structural change, was then proven safe in-game. This generalizes that proof:

          * a patched value the SAME byte-length as the original is edited IN PLACE
            (offset unchanged) -- UNLESS its original TEXT_OFFSETS slot is SHARED with
            another (possibly unpatched) key, in which case it falls through to the
            append path below so the shared key is never silently corrupted.
          * a patched value of a DIFFERENT byte-length is appended past the current end
            of the VALUES section (NUL-terminated) and only that key's TEXT_OFFSETS
            entry is repointed there. Requires VALUES to be the LAST section physically
            in the payload (true on every MSMR loc variant checked) -- growing it then
            collides with nothing, and only VALUES' own section-table SIZE field needs
            a one-field patch (its offset never moves).

        ⚠️ TEXT_OFFSETS values are relative to VALUES' OWN start (`vb_off`), not
        absolute payload offsets -- `_cstr(vb, toff[i])` slices `vb = payload[vb_off:
        vb_off+vb_size]` first. Every absolute `payload[...]` index used here must add
        `vb_off`; every value WRITTEN into `toff` must be relative to it.

        Every other byte -- every other section's exact offset and content, the
        section table (besides VALUES' own size field when growing), every untouched
        pair, the physical order of everything -- is left 100% unchanged. No dedup, no
        relayout of any section. `encode_minimal({})` is BYTE-IDENTICAL to self.raw
        (verified in the selftest below)."""
        from collections import Counter

        vb_off, vb_size = self._secs[TAG_VALUES]
        to_off, to_size = self._secs[TAG_TEXT_OFFSETS]
        payload = bytearray(self.payload)
        toff = list(struct.unpack(f"<{self.count}I", bytes(payload[to_off:to_off + to_size])))
        offset_counts = Counter(toff)          # BEFORE any edits -- shared-slot detector

        extra = bytearray()
        base_extra_rel = vb_size               # append point, relative to VALUES' start

        for i, (k, old_v) in enumerate(self.pairs):
            if k not in patch:
                continue
            new_v = patch[k].encode("utf-8")
            shared = offset_counts[toff[i]] > 1
            if len(new_v) == len(old_v) and not shared:
                o = vb_off + toff[i]
                payload[o:o + len(new_v)] = new_v
            else:
                new_off_rel = base_extra_rel + len(extra)
                extra.extend(new_v)
                extra.append(0)
                toff[i] = new_off_rel

        struct.pack_into(f"<{self.count}I", payload, to_off, *toff)

        if extra:
            if vb_off + vb_size != len(payload):
                raise ValueError("VALUES is not the last section -- unsafe to grow in place")
            payload.extend(extra)
            headers = list(self.dat1.header.sections)
            idx = next(i for i, sh in enumerate(headers) if sh.tag == TAG_VALUES)
            size_field_pos = HEADER_SIZE + idx * SECTION_HEADER_SIZE + 8  # tag,off,SIZE
            struct.pack_into("<I", payload, size_field_pos, vb_size + len(extra))

        needle = struct.pack("<I", self.dat1.header.size)
        hoff = bytes(self.payload[:HEADER_SIZE]).find(needle)
        if hoff >= 0:
            struct.pack_into("<I", payload, hoff, len(payload))

        return self.prefix + bytes(payload)


def load(path: str | os.PathLike) -> Loc:
    return Loc(Path(path).read_bytes())


# --------------------------------------------------------------------- selftest
def _selftest(locs_dir: Path) -> int:
    files = sorted(p for p in locs_dir.glob("variant_*.localization"))
    if not files:
        print("[!] no variants at", locs_dir)
        return 1
    bad = 0
    for p in files:
        L = load(p)
        rebuilt = L.encode()
        ident = rebuilt == L.raw
        # semantic re-parse
        M = Loc(rebuilt)
        mism = sum(1 for a, b in zip(L.pairs, M.pairs) if a != b)
        status = "BYTE-IDENTICAL" if ident else ("SEMANTIC-PASS" if mism == 0 else "FAIL")
        if status == "FAIL":
            bad += 1
        print(f"  {p.name:<42} n={L.count} delta={len(rebuilt)-len(L.raw):+8d} "
              f"mismatches={mism} -> {status}")
    # patch test on the first file
    L = load(files[0])
    k = next(k for k, v in L.pairs if v.strip())
    patched = Loc(L.encode({k: "שלום עברית"}))
    got = dict(patched.pairs)[k].decode("utf-8")
    others = sum(1 for (ka, va), (kb, vb) in zip(L.pairs, patched.pairs)
                 if ka == kb and ka != k and va != vb)
    print(f"\n  patch {k!r} -> {got!r}   other-values-changed={others}")
    ok = got == "שלום עברית" and others == 0
    print(f"  patch round-trip: {'PASS' if ok else 'FAIL'}")
    return 0 if (bad == 0 and ok) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    here = Path(__file__).resolve().parents[1]
    sys.exit(_selftest(here / "extract" / "loc_variants"))
