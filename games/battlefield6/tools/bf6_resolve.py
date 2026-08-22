"""
End-to-end resolver: .toc bundle -> CASBundle sub-header -> catalog name -> real
cas_NN.cas file + byte offset -> raw bundle bytes.

usage: bf6_resolve.py <win32_root> <layout.toc> <file.toc> <bundle_index_or_name_substr>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bf6_toc import TocFile, read_cas_bundle  # noqa: E402
from bf6_catalog import build_catalog_list, build_persistent_index_map, resolve_cas_path  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: bf6_resolve.py <win32_root> <layout.toc> <file.toc> <bundle_index_or_name_substr>")
        return 1
    win32_root, layout_toc, toc_path, sel = argv[:4]

    catalogs = build_catalog_list(layout_toc)
    pidx_map = build_persistent_index_map(catalogs)
    t = TocFile.read(toc_path)
    print(t.summary())

    if sel.isdigit():
        targets = [t.bundles[int(sel)]]
    else:
        needle = sel.lower()
        targets = [b for b in t.bundles if b.name and needle in b.name.lower()]
        if not targets:
            print(f"no bundle name contains '{sel}'")
            return 1

    for b in targets:
        print(f"\n=== bundle[{b.index}] {b.name!r} size={b.size} toc_offset={b.offset} ===")
        entries = read_cas_bundle(t.data, b.offset)
        for k, e in enumerate(entries):
            ordinal = pidx_map.get(e.catalog_persistent_index) if e.catalog_persistent_index is not None else None
            cat = catalogs[ordinal] if ordinal is not None else None
            cat_name = cat.name if cat else f"<unresolved pidx {e.catalog_persistent_index}>"
            cas_path = resolve_cas_path(win32_root, cat, e.cas, e.is_in_patch) if cat else None
            print(
                f"  entry[{k}] catalog={ordinal}({cat_name}) cas={e.cas} "
                f"offset={e.bundle_offset} size={e.bundle_size} patch={e.is_in_patch}"
            )
            if cas_path is None:
                continue
            print(f"    -> {cas_path}  exists={cas_path.exists()}")
            if cas_path.exists() and e.bundle_size > 0:
                with open(cas_path, "rb") as f:
                    f.seek(e.bundle_offset)
                    raw = f.read(min(e.bundle_size, 64))
                print(f"    first bytes: {raw.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
