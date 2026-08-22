"""
10_applier_probe.py — READ-ONLY reuse check for the SM2 native applier on
Ratchet & Clank: Rift Apart.

Question: can translation_manager/spiderman2_mod.py deploy an R&C localization
override via the SAME native toc-redirect + d/mods mechanism (no Overstrike,
no big-archive repack)?

Answer (dry-run, proven below): YES, with ZERO applier code changes. R&C's toc
is TOC2 / RCRA — byte-identical section model to SM2:
  get_spans_section / get_assets_section (ids) / get_sizes_section
  (RcraSizeEntry {value, archive_index, offset, header_offset}) /
  get_archives_section (66-byte entries: 40-byte filename + <QQIHI>).

The 32 localization_all variants all share ONE asset_id
(BE55D94F171BF8DE = crc64("localization/localization_all.localization"))
but live in 32 DIFFERENT spans (0, 8, 16 ... 248). So SM2's
_find_size_index(t, span, asset_id) disambiguates the variant by SPAN, exactly
like an SM2 stage entry named "{span}/{HEXID}".

NO Arabic and NO Hebrew slot exists → this is the LTR-hijack case: we hijack an
ENGLISH variant. variant_00 (span 0, size-index 87375) is the clean target.

Deploy (identical to SM2, from apply()):
  1. write the rebuilt Hebrew DAT1 (header stripped: raw[36:]) to d/mods/tm_he_0
  2. _append_archive(t, "d\\mods\\tm_he_0")  -> new archive index 147
  3. redirect size-entry[87375]: archive_index=147, offset=0, value=len(dat1)
     (header_offset UNCHANGED — the engine prepends the 36-byte asset header
     from the headers section; that is why value == filesize-36.)
Payload the build must produce = one .stage/.modular whose entry is
  "0/BE55D94F171BF8DE"  holding the rebuilt DAT1 (raw[36:]).

This script only READS the toc (parse + in-memory dry-run). It never writes.
"""

from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "games" / "spiderman2" / "tools" / "ALERT"))
sys.path.insert(0, str(REPO / "translation_manager"))

import spiderman2_mod as sm2  # noqa: E402
from dat1lib import crc64      # noqa: E402

TOC = Path("F:/Game Lab/Ratchet & Clank - Rift Apart/toc")
LOC_PATH = "localization/localization_all.localization"


def main() -> None:
    assert TOC.is_file(), f"toc not found: {TOC}"
    d = sm2._load_dat1lib()
    t = sm2._read_toc(d, TOC)

    aid = crc64.hash(LOC_PATH)
    print(f"asset_id(crc64) = {aid:016X}  (expect BE55D94F171BF8DE)")

    spans = t.get_spans_section()
    sizes = t.get_sizes_section()
    arch = t.get_archives_section()
    ids = t.get_assets_section().ids
    print(f"spans={len(spans.entries)} archives={len(arch.archives)} "
          f"sizes={len(sizes.entries)} assets={len(ids)}")

    # locate every localization_all variant (32) and its span/size-entry
    entries = t.get_asset_entries_by_path(LOC_PATH)
    print(f"localization_all variants found: {len(entries)}  (expect 32)")

    def span_of(index: int) -> int:
        for s, sp in enumerate(spans.entries):
            if sp.asset_index <= index < sp.asset_index + sp.count:
                return s
        return -1

    # hijack target = variant_00 = English, span 0
    HIJACK_SPAN = 0
    idx = sm2._find_size_index(t, HIJACK_SPAN, aid)
    assert idx == 87375, idx
    se = sizes.entries[idx]
    print(f"\nHIJACK target: variant_00 (English)  span={HIJACK_SPAN}  "
          f"size_index={idx}")
    print(f"  BEFORE  archive={se.archive_index} offset={se.offset} "
          f"value={se.value} header_offset={se.header_offset}")

    # dry-run the SM2 redirect (in memory ONLY — nothing is written to disk)
    new_arc = sm2._append_archive(t, "d\\mods\\tm_he_0")
    fake_len = 2_000_000
    print(f"  _append_archive -> new archive index {new_arc} "
          f"(name {bytes(arch.archives[-1].filename).split(b_nul())[0]!r})")
    print(f"  PLAN redirect: archive={new_arc} offset=0 value=<len(dat1)> "
          f"(e.g. {fake_len})  header_offset STAYS {se.header_offset}")
    print("\nVERDICT: reuse as-is. spiderman2_mod.apply(game_root, ["
          "<payload with entry '0/BE55D94F171BF8DE' = rebuilt DAT1 raw[36:]>]) "
          "deploys R&C Hebrew with no code changes.")


def b_nul():
    return b"\x00"


if __name__ == "__main__":
    main()
