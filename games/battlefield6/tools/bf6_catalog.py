"""
Battlefield 6 (Frostbite) catalog resolver — the missing link between a `.toc`
bundle's CASBundle sub-header (Catalog byte + Cas byte + BundleOffset + BundleSize)
and a real byte range inside a specific `cas_NN.cas` file on disk.

Reverse-engineered by decompiling `FrostySdk.FileSystem.ProcessCatalogs` /
`FMT.ServicesManagers.FileSystemService.{ProcessLayouts,GetFilePath}` (see
bf6_toc.py / bf6_dbobject.py module docstrings for the general carving method).

THE key facts:
  - `Data/layout.toc` (one level above Data/Win32/) is a DbObject file (bf6_dbobject.py)
    whose top-level dict has `installManifest.installChunks[]` — one entry per physical
    catalog folder (e.g. "installation/commonbase/en", "installation/commonbase/ar" for
    the Arabic locale, "installation/san1installpackage/...", etc).
  - `Catalog.Name` = `installChunk["installBundle"]` if present, else `"win32/" +
    installChunk["name"]`. This is the folder name (with a "Win32/" prefix baked in
    that must be stripped to match our real on-disk Data/Win32/ layout).
  - `FMT.ServicesManagers.FileSystemService.GetFilePath(catalogIndex, cas, patch)`:
        Catalogs[catalogIndex].Name + "/cas_" + cas.ToString("D2") + ".cas"
    (prefixed logically by "native_data/" or "native_patch/", which in FMT's own
    ResolvePath maps onto our real Data/Win32/<name-without-Win32-prefix>/ tree).
  - **`catalogIndex` (the CASBundle.Catalog byte, 0-255) is a plain ORDINAL POSITION**
    in `installChunks`, assigned in iteration order, SKIPPING any chunk with
    `testDLC == True` (FMT.ServicesManagers.FileSystemService.ProcessCatalogs, same
    gate as FrostySdk.FileSystem.ProcessCatalogs).
  - **CORRECTION (found via `BF6Plugin.BF6TOCFile`, the BF6-specific override — see
    bf6_toc.py):** for the actual on-disk CASBundle bytes, the raw int32 the file stores
    is NOT that small ordinal directly — it's the chunk's own `persistentIndex` field (a
    large, possibly-negative signed int). `BF6TOCFile.FindCatalogCasPatch`/`ReadCasBundles`
    look it up via `CatalogsIndexed[persistentIndex]` first (to validate it exists), then
    re-derive the small ordinal via `CatalogObjects.FindIndex(x => x.PersistentIndex ==
    persistentIndex)` for internal storage. Net effect for us: build a
    `persistentIndex -> ordinal` map (`pidx_to_ordinal` here) and use THAT to resolve a
    raw on-disk catalog int32 to our ordinal `CatalogEntry` list.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bf6_dbobject import read_dbobject_file  # noqa: E402


@dataclass
class CatalogEntry:
    index: int
    name: str        # e.g. "win32/installation/commonbase/ar" (as FMT stores it)
    language: str | None
    always_installed: bool
    persistent_index: int | None = None

    def relative_dir(self) -> str:
        """Strip a leading 'win32/' (any case) so it maps onto our Data/Win32/ tree."""
        n = self.name.rstrip("\x00")
        low = n.lower()
        if low.startswith("win32/"):
            return n[len("win32/"):]
        return n


def build_catalog_list(layout_toc_path: str | Path) -> list[CatalogEntry]:
    obj = read_dbobject_file(layout_toc_path)
    chunks = obj["installManifest"]["installChunks"]
    catalogs: list[CatalogEntry] = []
    for chunk in chunks:
        if chunk.get("testDLC"):
            continue
        install_bundle = chunk.get("installBundle")
        name = chunk.get("name", "").rstrip("\x00")
        catalog_name = install_bundle.rstrip("\x00") if install_bundle else ("win32/" + name)
        catalogs.append(
            CatalogEntry(
                index=len(catalogs),
                name=catalog_name,
                language=(chunk.get("language") or "").rstrip("\x00") or None,
                always_installed=bool(chunk.get("alwaysInstalled")),
                persistent_index=chunk.get("persistentIndex"),
            )
        )
    return catalogs


def build_persistent_index_map(catalogs: list[CatalogEntry]) -> dict[int, int]:
    """persistentIndex -> ordinal position, for resolving the raw int32 catalog id
    that BF6TOCFile.ReadCasBundles actually stores on disk (see module docstring)."""
    return {c.persistent_index: c.index for c in catalogs if c.persistent_index is not None}


def resolve_cas_path(win32_root: str | Path, catalog: CatalogEntry, cas: int, patch: bool = False) -> Path:
    """Build the real on-disk path to a cas_NN.cas file for a given catalog+cas index."""
    sub = catalog.relative_dir()
    # our real tree has no separate native_patch/ mirror observed yet for the base
    # install chunks; patch archives (if present) live under a sibling "patch/" dir
    # in real Frostbite installs -- left as a TODO once we hit one.
    return Path(win32_root) / sub / f"cas_{cas:02d}.cas"


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: bf6_catalog.py <layout.toc> [grep_substring]")
        return 1
    catalogs = build_catalog_list(argv[0])
    needle = argv[1].lower() if len(argv) > 1 else None
    print(f"{len(catalogs)} catalogs (ordinal index == CASBundle.Catalog byte value)")
    for c in catalogs:
        if needle and needle not in c.name.lower() and (not c.language or needle not in c.language.lower()):
            continue
        print(f"  [{c.index:3d}] lang={c.language or '-':20s} always={c.always_installed!s:5s} {c.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
