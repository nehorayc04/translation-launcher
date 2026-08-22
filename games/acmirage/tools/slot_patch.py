#!/usr/bin/env python3
"""
slot_patch.py — in-place texture patching with a SLOT-level backup.

`mirage_deploy.py` backs up the whole forge, which is fine for a 2.5 GB file and
impractical for the 9.4 GB SharedGroup. An in-place write only ever touches the bytes
inside one resource's own slot, so the revert only needs those bytes: each patch saves
the original slot to `<forge>.he_slots.json` (offset + size + the original bytes,
base64) and `revert` writes them straight back. Nothing else in the forge can change,
so this is exactly as safe as a full-file backup for this operation and costs
kilobytes instead of gigabytes.

    python slot_patch.py <forge> white <resource_id> [...]   # solid-white test payload
    python slot_patch.py <forge> revert
    python slot_patch.py <forge> list
"""
import argparse
import base64
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from bc7_encode import encode  # noqa: E402
from mirage_texdump import find_dims  # noqa: E402
from mirage_texture import TextureRes  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def slots_path(forge):
    return forge + ".he_slots.json"


def _load_slots(forge):
    p = slots_path(forge)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def solid_payload(w, h, rgb=(255, 255, 255)):
    img = np.zeros((h, w, 4), np.uint8)
    img[:, :, 0], img[:, :, 1], img[:, :, 2] = rgb
    img[:, :, 3] = 255
    return encode(img)


def patch(forge, ids, rgb=(255, 255, 255)):
    fg = Forge(forge)
    od = acs_cfd._oodle()
    ents = {e.id: e for e in fg.entries}
    slots = _load_slots(forge)
    todo = []
    for rid in ids:
        rid = int(rid)
        e = ents.get(rid)
        if not e:
            print(f"  id={rid} not in {os.path.basename(forge)} — skipped")
            continue
        # Decode once and measure the texture BEFORE constructing TextureRes: header
        # lengths vary per class/texture (264, 270, 281, 325, 337, 351 all seen), so
        # constructing without a known payload length hits the 264/325 guess and
        # throws on everything else.
        blob0 = fg.read(e)
        try:
            cfds, _ = acs_cfd.decode_resource(blob0, od)
            content = cfds[-1][0]
        except Exception as ex:
            print(f"  id={rid} skipped (decode: {type(ex).__name__})")
            continue
        d = find_dims(content)
        if not d:
            print(f"  id={rid} skipped (no single-mip dims)")
            continue
        w, h, hdr = d
        try:
            res = TextureRes(blob0, od, payload_len=w * h)
        except SystemExit as ex:
            print(f"  id={rid} skipped ({ex})")
            continue
        blob = res.rebuild(solid_payload(w, h, rgb))
        if len(blob) > e.size:
            print(f"  id={rid} skipped (blob {len(blob):,} > slot {e.size:,})")
            continue
        todo.append((e, res.name, w, h, blob))
    fg.f.close()

    if not todo:
        print("nothing to do")
        return 1
    with open(forge, "r+b") as fh:
        for e, name, w, h, blob in todo:
            key = str(e.id)
            if key not in slots:                       # save the pristine slot ONCE
                fh.seek(e.offset)
                slots[key] = {"offset": e.offset, "size": e.size,
                              "orig": base64.b64encode(fh.read(e.size)).decode()}
            fh.seek(e.offset)
            fh.write(blob + b"\x00" * (e.size - len(blob)))
            print(f"  MARK  id={e.id:<16} {w}x{h:<5} {len(blob):>8,}B into {e.size:>9,}B  {name}")
        fh.flush()
        os.fsync(fh.fileno())
    json.dump(slots, open(slots_path(forge), "w", encoding="utf-8"))
    print(f"  saved {len(slots)} pristine slot(s) -> {os.path.basename(slots_path(forge))}")
    return 0


def revert(forge):
    slots = _load_slots(forge)
    if not slots:
        print("no slot backup — nothing to revert")
        return 1
    with open(forge, "r+b") as fh:
        for rid, s in slots.items():
            fh.seek(s["offset"])
            fh.write(base64.b64decode(s["orig"]))
        fh.flush()
        os.fsync(fh.fileno())
    os.remove(slots_path(forge))
    print(f"reverted {len(slots)} slot(s) in {os.path.basename(forge)} (byte-identical)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["white", "mark", "revert", "list"])
    ap.add_argument("--rgb", default="255,255,255",
                    help="marker colour for `mark`, e.g. 255,255,0")
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    if a.cmd == "revert":
        sys.exit(revert(a.forge))
    if a.cmd == "list":
        for rid, s in _load_slots(a.forge).items():
            print(f"  id={rid} off={s['offset']} size={s['size']:,}")
        sys.exit(0)
    rgb = tuple(int(x) for x in a.rgb.split(","))
    sys.exit(patch(a.forge, a.ids, rgb))
