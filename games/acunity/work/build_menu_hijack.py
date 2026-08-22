#!/usr/bin/env python3
"""MENU HIJACK PROOF — the Language field, not the slot name, may drive font+bidi selection.
Take a MENU-SELECTABLE LTR language (Czech), put Hebrew in its menu strings, and patch its
internal Language field to Arabic (20). If the engine picks the font/bidi from that field, the
menu will render with the Arabic-capable TTF (Shilia + injected Hebrew) → Hebrew menus.

ONE build answers three questions at once (playbook §"one-build multi-mode menu proof"):
  * a pure-Latin marker  -> did the package load at all (font-independent)?
  * LOGICAL Hebrew items -> engine applies bidi?
  * VISUAL  Hebrew items -> engine draws storage order?
  * boxes everywhere     -> Language field does NOT drive font selection (menu truly dead).
"""
import sys, struct
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
sys.path.insert(0, r"C:\tmp\acuwork")
import acu_forge as F, acu_loc as L, acu_minbuild as MB, acu_deploy as D

FORGE = r"E:/Games/Assassin's Creed Unity/DataPC.forge"
TARGET = "TLocalizationPackage_Czech"
ARABIC_LANG = 20
MARKER = 0xD28389B5


def vis(s):
    return s[::-1]


EDITS = {
    521007:   "ZZ-CZ-OK-ZZ",        # CONTINUE -> Latin marker: proves the package loaded
    532102:   "אפשרויות",            # EStore   -> LOGICAL
    532097:   vis("אפשרויות"),       # Uplay    -> VISUAL
    532106:   "עברית",               # Options  -> LOGICAL (item 4, known visible)
    542673:   vis("עברית"),          # Initiates-> VISUAL
    60000099: "יציאה",               # Quit     -> LOGICAL
}


def main():
    fg = F.Forge(FORGE)
    idx = fg.name_to_index[TARGET]
    raw = fg.extract_index(idx)
    slot = fg.disk_size(idx)
    fg.f.close()
    src = r"C:/tmp/acuwork/cz_pristine.data"
    open(src, "wb").write(raw)

    orig, payload, maxIndex, fragCount, fr, fs = MB.load_orig(src)
    tables, code_by_id = MB.decode_capture(payload, maxIndex, fragCount)
    enc, extra = MB.make_encoder(fs, fragCount, maxIndex)
    present = {k: v for k, v in EDITS.items() if k in code_by_id}
    print(f"{TARGET}: maxIndex={maxIndex} frags={fragCount} slot={slot:,}")
    print(f"editing {len(present)}/{len(EDITS)} ids (missing: {sorted(set(EDITS)-set(present))})")
    for k, v in present.items():
        code_by_id[k] = enc(v)
    newpay = MB.rebuild_payload(maxIndex, fragCount, fr, extra, tables, code_by_id)

    p1, _ = L.cfd_decompress(orig, 0)
    p2, content = L.cfd_decompress(orig, p1)
    sig = orig[p2:]
    bo = 12 + struct.unpack_from("<i", content, 8)[0]
    P = oc = None
    for off in range(bo, bo + 96):
        v = struct.unpack_from("<i", content, off)[0]
        if 1000 < v < len(content) - off and content[off + 4] == 0 and 128 <= content[off + 5] <= 255:
            P, oc = off, v
            break
    new = bytearray(content[:P] + struct.pack("<i", len(newpay)) + newpay + content[P + 4 + oc:])
    f2 = struct.unpack_from("<i", content, 4)[0]
    struct.pack_into("<i", new, 4, len(new) - (len(content) - f2))
    mk = new.find(struct.pack("<I", MARKER))
    old_lang = struct.unpack_from("<I", new, mk - 4)[0]
    struct.pack_into("<I", new, mk - 4, ARABIC_LANG)
    print(f"payload {len(payload)}->{len(newpay)}   Language {old_lang} -> {ARABIC_LANG}")

    newdata = orig[:p1] + MB.make_cfd_lzo(bytes(new), orig[p1 + 8:p1 + 15]) + sig
    open(r"C:/tmp/acuwork/cz_HE.data", "wb").write(newdata)
    # verify via the marker (never the fragile heuristic finder)
    q1, _ = L.cfd_decompress(newdata, 0)
    _, c2 = L.cfd_decompress(newdata, q1)
    m2 = c2.find(struct.pack("<I", MARKER))
    cnt = struct.unpack_from("<I", c2, m2 + 4)[0]
    d = L.decode_payload(c2[m2 + 8:m2 + 8 + cnt])
    print(f"verify: {len(d)} strings, Language={struct.unpack_from('<I', c2, m2-4)[0]}")
    for k, v in present.items():
        print(f"   {k}: {'OK' if d.get(k)==v else 'MISMATCH'}  {d.get(k)!r}")
    print(f"\n.data {len(orig):,} -> {len(newdata):,} (slot {slot:,}, fits_inplace={len(newdata)<=slot})")
    if len(newdata) <= slot:
        D.apply_inplace(FORGE, TARGET, newdata)
    else:
        D.apply(FORGE, TARGET, newdata)
    print("\nDONE. In-game: Options -> Menu Language -> Čeština (Czech) -> RESTART the game.")


if __name__ == "__main__":
    main()
