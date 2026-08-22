#!/usr/bin/env python3
"""Populate the Arabic UI loc package (rec1593, currently a 139B stub) with Hebrew menu
strings by reusing the English package structure + LOGICAL Hebrew edits, patching the
internal Language field to Arabic (20). Deploy AS TLocalizationPackage_Arabic (append-relocate).
Under Arabic locale the menu then reads Hebrew, rendered with the Arabic TTF (Shilia+Hebrew)."""
import sys, struct
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
sys.path.insert(0, r"C:\tmp\acuwork")
import acu_forge as F, acu_loc as L, acu_minbuild as MB, acu_deploy as D

FORGE = r"E:/Games/Assassin's Creed Unity/DataPC.forge"
ARABIC_LANG = 20
MARKER = 0xD28389B5

# LOGICAL Hebrew (Arabic locale applies bidi -> do NOT pre-reverse)
EDITS = {
    532106: "אפשרויות",
    558658: "חזור",
    456237: "כתוביות",
    520544: "תפריט ראשי",
    544279: "עברית עובד",
}


def build_as_arabic(orig_path, edits, out_path):
    orig, payload, maxIndex, fragCount, fr, fs = MB.load_orig(orig_path)
    orig_tables, code_by_id = MB.decode_capture(payload, maxIndex, fragCount)
    enc, extra_list = MB.make_encoder(fs, fragCount, maxIndex)
    for k, v in edits.items():
        code_by_id[k] = enc(v)
    newpay = MB.rebuild_payload(maxIndex, fragCount, fr, extra_list, orig_tables, code_by_id)
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
    newcontent = bytearray(content[:P] + struct.pack("<i", len(newpay)) + newpay + content[P + 4 + oc:])
    # field2 (content[4]) = len(content) - X
    field2_orig = struct.unpack_from("<i", content, 4)[0]
    X = len(content) - field2_orig
    struct.pack_into("<i", newcontent, 4, len(newcontent) - X)
    # patch Language: the u32 immediately BEFORE the 0xD28389B5 marker
    mk = newcontent.find(struct.pack("<I", MARKER))
    assert mk > 0, "marker not found"
    lang_off = mk - 4
    old_lang = struct.unpack_from("<I", newcontent, lang_off)[0]
    struct.pack_into("<I", newcontent, lang_off, ARABIC_LANG)
    print(f"payload {len(payload)}->{len(newpay)}  Language {old_lang}->{ARABIC_LANG} @content+{lang_off}")
    newdata = orig[:p1] + MB.make_cfd_lzo(bytes(newcontent), orig[p1 + 8:p1 + 15]) + sig
    open(out_path, "wb").write(newdata)
    return newdata


def main():
    fg = F.Forge(FORGE)
    en = fg.extract_index(fg.name_to_index["TLocalizationPackage_English"])
    fg.f.close()
    open(r"C:/tmp/acuwork/loc_en_pristine.data", "wb").write(en)
    newdata = build_as_arabic(r"C:/tmp/acuwork/loc_en_pristine.data", EDITS,
                              r"C:/tmp/acuwork/loc_arabic_HE.data")
    # verify decode
    d = L.decode_payload(L._payload_from_data(newdata)[1])
    for k, v in EDITS.items():
        print(f"   {k}: {'OK' if d.get(k)==v else 'MISMATCH'}  {d.get(k)!r}")
    print(f"new Arabic .data = {len(newdata):,} B")
    print("\n== deploy as TLocalizationPackage_Arabic (append-relocate) ==")
    D.apply(FORGE, "TLocalizationPackage_Arabic", newdata)
    print("\nDONE. Set in-game Text Language = Arabic (العربية), launch, check the main menu item 4.")


if __name__ == "__main__":
    main()
