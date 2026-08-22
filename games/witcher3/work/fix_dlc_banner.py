# -*- coding: utf-8 -*-
"""Make the DLC banners (Hearts of Stone / Blood and Wine) show ENGLISH instead of CHINESE.

THE BUG (vanilla CDPR, not caused by the mod): the main-menu expansion banners are IMAGES, loaded by
the menu Flash AT RUNTIME from `texture.cache` by a language-suffixed path:

    gameplay\\gui_new\\icons\\quests\\ep_logos\\ep1_logo_{ch,cz,en,pl,ru}.png     (Hearts of Stone)
    gameplay\\gui_new\\icons\\quests\\ep_logos\\ep2_logo_{ch,cz,en,pl,ru}.png     (Blood and Wine)

Only FIVE variants ship — and **there is no Arabic one**. The Arabic locale (added late, in the
next-gen patch) falls through to `_ch` (Chinese), which is exactly what the user sees while playing
the Hebrew mod (the Hebrew text under the banner renders fine; only the baked-in banner art is CJK).
These assets are NOT in any bundle — they live only inside `texture.cache` (magic `HCXT`, v6).

THE FIX — swap the two PATH STRINGS, not the pixels:
    entry that owns the Chinese art  -> renamed "..._en.png"
    entry that owns the English art  -> renamed "..._ch.png"
So when the game asks for `_ch.png` (what Arabic resolves to) the cache hands it the ENGLISH artwork.
`_ch` and `_en` are the same length, so this is an in-place 2-byte edit per path: no index rebuild,
no data move, no size change, and the 8.5 GB cache is otherwise untouched.

(If the cache looks resources up by a path HASH rather than the string, this is a no-op — harmless,
and we would then have to swap the entries' data pointers instead. Try this first: it is reversible
and costs 8 bytes.)

Revert data (original bytes + offsets) is saved to dlc_banner_patch.json — no 8.5 GB backup needed.

Usage:  py fix_dlc_banner.py            # dry-run: locate + show what would change
        py fix_dlc_banner.py --deploy   # patch (GAME MUST BE CLOSED)
        py fix_dlc_banner.py --revert
"""
import os, sys, json

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
CACHE = os.path.join(GAME, "content", "content0", "texture.cache")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "dlc_banner_patch.json")

PREFIX = rb"gameplay\gui_new\icons\quests\ep_logos"
PAIRS = [(b"ep1_logo_ch.png", b"ep1_logo_en.png"),      # Hearts of Stone
         (b"ep2_logo_ch.png", b"ep2_logo_en.png")]      # Blood and Wine
TAIL = 8 * 1024 * 1024                                   # the string table lives at the very end


def find_paths():
    """-> [(abs_offset, current_bytes, label), ...] for every ep{1,2}_logo_{ch,en} path."""
    size = os.path.getsize(CACHE)
    start = size - TAIL
    with open(CACHE, "rb") as f:
        f.seek(start); tail = f.read()
    out = []
    for ch_name, en_name in PAIRS:
        for name in (ch_name, en_name):
            full = PREFIX + b"\\" + name
            i = tail.find(full)
            if i < 0:
                raise SystemExit(f"path not found in texture.cache: {full.decode()}")
            if tail.find(full, i + 1) >= 0:
                raise SystemExit(f"path appears MORE THAN ONCE — aborting: {full.decode()}")
            # the 2 language letters sit right before ".png"
            lang_off = start + i + len(full) - len(b"ch.png")
            out.append((lang_off, tail[i + len(full) - len(b"ch.png"): i + len(full) - len(b".png")],
                        full.decode("latin1")))
    return out


def deploy():
    hits = find_paths()
    with open(CACHE, "rb") as f:
        for off, cur, label in hits:
            f.seek(off); got = f.read(2)
            assert got == cur, f"read mismatch at {off}"
    # swap: ch <-> en for each pair (ep1 then ep2 => hits are [ch,en, ch,en])
    edits = []
    for k in range(0, len(hits), 2):
        off_ch, cur_ch, lbl_ch = hits[k]
        off_en, cur_en, lbl_en = hits[k + 1]
        assert cur_ch == b"ch" and cur_en == b"en", (cur_ch, cur_en)
        edits.append({"offset": off_ch, "orig": "ch", "new": "en", "path": lbl_ch})
        edits.append({"offset": off_en, "orig": "en", "new": "ch", "path": lbl_en})

    if os.path.exists(STATE):
        print("already patched (dlc_banner_patch.json exists) — run --revert first"); return
    with open(CACHE, "r+b") as f:
        for e in edits:
            f.seek(e["offset"]); f.write(e["new"].encode())
    json.dump(edits, open(STATE, "w"), indent=1)
    print(f"patched {len(edits)} path strings in texture.cache:")
    for e in edits:
        print(f"   @{e['offset']:>12,}  {e['orig']} -> {e['new']}   ({os.path.basename(e['path'])})")
    # verify
    with open(CACHE, "rb") as f:
        for e in edits:
            f.seek(e["offset"])
            assert f.read(2) == e["new"].encode()
    print("verified. The banners should now show ENGLISH artwork in the Hebrew/Arabic locale.")
    print("Restart the game.")


def revert():
    if not os.path.exists(STATE):
        print("nothing to revert"); return
    edits = json.load(open(STATE))
    with open(CACHE, "r+b") as f:
        for e in edits:
            f.seek(e["offset"]); f.write(e["orig"].encode())
    os.remove(STATE)
    print(f"reverted {len(edits)} path strings")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        for off, cur, label in find_paths():
            print(f"  @{off:>12,}  lang={cur.decode()}  {label}")
        print("\n(dry-run) re-run with --deploy (GAME MUST BE CLOSED)")
