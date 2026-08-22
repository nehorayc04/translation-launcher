#!/usr/bin/env python3
"""PROOF: replace every Arabic subtitle string (rec1594, 7663 real Arabic lines) with a
Hebrew marker (LOGICAL — the engine bidi-reverses the Arabic slot). Deploy in-place/relocate.
With Subtitles language = Arabic, ANY in-game dialogue then shows Hebrew, rendered via the
Arabic TTF (Shilia + injected Hebrew). Proves the subtitle translation path end-to-end."""
import sys, struct
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
sys.path.insert(0, r"C:\tmp\acuwork")
import acu_forge as F, acu_loc as L, acu_minbuild as MB, acu_deploy as D

FORGE = r"E:/Games/Assassin's Creed Unity/DataPC.forge"
PROOF = "עברית עובדת בכתוביות"   # logical; engine reverses for RTL


def main():
    fg = F.Forge(FORGE)
    i = fg.name_to_index["TLocalizationPackage_Arabic_Subtitles"]
    raw = fg.extract_index(i)
    fg.f.close()
    open(r"C:/tmp/acuwork/subs_ar_pristine.data", "wb").write(raw)
    lang, payload = L._payload_from_data(raw)
    ids = list(L.decode_payload(payload).keys())
    print(f"Arabic subtitles: {len(ids)} ids, replacing ALL with proof Hebrew (logical)")
    edits = {k: PROOF for k in ids}
    orig, newpay, newdata, oldlen = MB.build(r"C:/tmp/acuwork/subs_ar_pristine.data", edits,
                                             r"C:/tmp/acuwork/subs_ar_HE.data")
    print(f"payload {oldlen} -> {len(newpay)}   .data {len(orig)} -> {len(newdata)}")
    # verify a couple
    d = L.decode_payload(L._payload_from_data(newdata)[1])
    print("sample:", {k: d[k] for k in ids[:2]})
    print("\n== deploy Arabic subtitles (Hebrew proof) ==")
    D.apply(FORGE, "TLocalizationPackage_Arabic_Subtitles", newdata)
    print("\nDONE. Subtitles language must be Arabic (it is). CONTINUE your save and walk into "
          "any dialogue / cutscene — the subtitle should read Hebrew.")


if __name__ == "__main__":
    main()
