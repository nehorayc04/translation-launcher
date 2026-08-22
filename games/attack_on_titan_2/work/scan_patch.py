"""
Diagnose "still English in-game" — scan LINKDATA_PATCH_000.BIN (the sibling
"patch" archive at LINKDATA\PATCH\, per the base+patch shadowing trap: the
same content can exist in several archives and the engine resolves ONE by
load order — see universal Playbook §8e / the AC Shadows precedent) for:
  (a) any DataTable containing our EXACT pristine English source for entries
      2424/1056 (proves PATCH_000 shadows the base REGION_EU copy we edited)
  (b) any small DataTable that LOOKS like UI/menu chrome (short strings,
      title-case, words like "New Game"/"Continue"/"Options"/"Load"/"Save")
"""
from __future__ import annotations

import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, is_datatable, parse_datatable, read_cstring  # noqa: E402

PATCH = Path(r"F:\Games\Attack on Titan 2\LINKDATA\PATCH\LINKDATA_PATCH_000.BIN")
BACKUP = Path(r"F:\Games\Attack on Titan 2\LINKDATA\REGION\LINKDATA_REGION_EU.BIN.he_backup")

UI_WORDS = re.compile(
    r"\b(new game|continue|options|load|save|settings|start|start game|"
    r"title|exit|quit|back|select|language|sound|graphics|controls|"
    r"press\s|button|menu)\b",
    re.IGNORECASE,
)


def load_pristine_strings(entry_idx: int) -> list[str]:
    """Read the entry's ORIGINAL (pre-edit) strings from the .he_backup."""
    with open(BACKUP, "rb") as f:
        data = f.read()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    assert code == MAGIC
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + entry_idx * 16)
    start = eo * mult
    raw = data[start : start + csize]
    content = raw if dsize == 0 else zlib.decompress(raw[8:])
    blobs = parse_datatable(content)
    return [read_cstring(b) if b is not None else "" for b in blobs]


def main() -> None:
    print("Loading pristine (pre-edit) strings from backup for entries 2424, 1056 ...")
    story_strings = load_pristine_strings(2424)
    battle_strings = load_pristine_strings(1056)
    story_probe = set(s for s in story_strings[:30] if len(s) > 8)
    battle_probe = set(s for s in battle_strings[:30] if len(s) > 8)
    print(f"  story probe set ({len(story_probe)}): {list(story_probe)[:3]}")
    print(f"  battle probe set ({len(battle_probe)}): {list(battle_probe)[:3]}")

    print(f"\nScanning {PATCH.name} ({PATCH.stat().st_size / 1e9:.2f} GB) ...")
    with open(PATCH, "rb") as f:
        data = f.read()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    assert code == MAGIC
    print(f"  {files} entries, mult={mult}")

    shadow_hits = []
    ui_candidates = []

    for i in range(files):
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
        start = eo * mult
        raw = data[start : start + csize]
        if not raw:
            continue
        try:
            if dsize == 0:
                content = raw
            else:
                content = zlib.decompress(raw[8:])
        except Exception:
            continue
        if not is_datatable(content):
            continue
        blobs = parse_datatable(content)
        if len(blobs) == 0:
            continue
        strings = []
        for b in blobs[:60]:
            if b is None:
                continue
            s = read_cstring(b)
            if s:
                strings.append(s)
        sset = set(strings)

        if sset & story_probe:
            shadow_hits.append(("story", i, len(blobs), list(sset & story_probe)[:3]))
        if sset & battle_probe:
            shadow_hits.append(("battle", i, len(blobs), list(sset & battle_probe)[:3]))

        # UI-chrome heuristic: small table (5-120 strings), short strings,
        # several matching common menu vocabulary
        if 3 <= len(blobs) <= 120:
            ui_matches = sum(1 for s in strings if UI_WORDS.search(s))
            avg_len = sum(len(s) for s in strings) / max(1, len(strings))
            if ui_matches >= 2 and avg_len < 40:
                ui_candidates.append((i, len(blobs), ui_matches, strings[:8]))

    print(f"\nShadow-content hits (PATCH copies of our story/battle probe strings): {len(shadow_hits)}")
    for kind, idx, n, sample in shadow_hits[:20]:
        print(f"  [{kind}] entry {idx} ({n} strings): {sample}")

    print(f"\nUI-chrome candidate tables: {len(ui_candidates)}")
    for idx, n, matches, sample in ui_candidates[:30]:
        print(f"  entry {idx} ({n} strings, {matches} UI-word hits): {sample}")


if __name__ == "__main__":
    main()
