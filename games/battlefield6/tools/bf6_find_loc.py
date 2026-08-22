"""Scan every bundle in the given .toc files for a `res` entry whose resType matches
FMT.FileTools.ResourceType.LocalizedStringResource (1585851909) -- see bf6_bundle.py's
module docstring for how that resource-type value was found."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bf6_toc import TocFile, read_cas_bundle  # noqa: E402
from bf6_catalog import build_catalog_list, build_persistent_index_map, resolve_cas_path  # noqa: E402
from bf6_bundle import parse_bundle_meta, RESTYPE_LOCALIZED_STRING  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: bf6_find_loc.py <win32_root> <layout.toc> <file1.toc> [file2.toc ...]")
        return 1
    win32_root, layout_toc = argv[0], argv[1]
    toc_paths = argv[2:]

    catalogs = build_catalog_list(layout_toc)
    pidx_map = build_persistent_index_map(catalogs)
    open_files: dict[str, object] = {}
    hits = 0
    scanned = 0
    parse_fails = 0

    for toc_path in toc_paths:
        t = TocFile.read(toc_path)
        print(f"=== {t.summary()} ===")
        for b in t.bundles:
            try:
                entries = read_cas_bundle(t.data, b.offset)
            except Exception:  # noqa: BLE001
                continue
            if not entries:
                continue
            e0 = entries[0]
            ordv = pidx_map.get(e0.catalog_persistent_index)
            cat = catalogs[ordv] if ordv is not None else None
            if not cat:
                continue
            path = resolve_cas_path(win32_root, cat, e0.cas, e0.is_in_patch)
            key = str(path)
            if key not in open_files:
                if not path.exists():
                    open_files[key] = None
                else:
                    open_files[key] = open(path, "rb")
            f = open_files[key]
            if f is None:
                continue
            f.seek(e0.bundle_offset)
            meta_bytes = f.read(e0.bundle_size)
            scanned += 1
            try:
                info = parse_bundle_meta(meta_bytes)
            except Exception:  # noqa: BLE001
                parse_fails += 1
                continue
            for e in info.entries:
                if e.res_type == RESTYPE_LOCALIZED_STRING:
                    hits += 1
                    de = entries[e.data_index] if e.data_index < len(entries) else None
                    print(f"  HIT bundle[{b.index}] {b.name!r}: res name={e.name!r} "
                          f"size={e.original_size} data={de}")
    print(f"\nscanned={scanned} parse_fails={parse_fails} hits={hits}")
    for f in open_files.values():
        if f:
            f.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
