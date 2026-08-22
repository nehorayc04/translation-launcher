"""
Recover the FULL fixed keystream and decrypt de.moe end-to-end.

Approach (empirical, no layout assumptions):
  - de.moe and es.moe are byte-identical for [0:116840] and diverge after => SAME N/layout (aligned).
  - Anchors of known keystream:
      KS[0:8]  from gettext magic+rev
      KS[12:16] from O=28
      KS[metadata..] from the language-independent metadata crib
  - Everywhere else: for each aligned byte position, choose KS[i]=k so that BOTH de[i]^k and es[i]^k
    look like text (letters/space/digits/UTF-8 lead/NUL/newline). Two constraints => reliable.
    For the shared region [0:116840] de==es, so one constraint (English text) — bias toward
    English letter frequencies. Then dump the decrypted gettext .mo and validate the header.
"""
import os, struct, collections

HERE = os.path.dirname(__file__)
EXTRACT = os.path.join(HERE, "..", "extract")
load = lambda n: open(os.path.join(EXTRACT, n), "rb").read()

CRIB = b"MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n"

TEXT = set(range(0x20, 0x7f)) | {0x00, 0x09, 0x0a, 0x0d}
# UTF-8 continuation/lead bytes common in translations
UTF8 = set(range(0x80, 0xC0)) | set(range(0xC2, 0xF5))
GOOD = TEXT | UTF8

ENG_FREQ = {c: 1 for c in b"etaoinshrdlucmfwypvbgkjqxz ETAOINSHRDLU.,:/()\x00-0123456789"}

def main():
    de = load("de.moe")[16:]
    es = load("es.moe")[16:]
    n = min(len(de), len(es))
    ks = bytearray(n)
    known = bytearray(n)  # 1 where anchored

    def anchor(pos, kbytes):
        for i, k in enumerate(kbytes):
            if pos + i < n:
                ks[pos + i] = k; known[pos + i] = 1

    # anchor magic+rev
    gt = bytes.fromhex("de12049500000000")
    anchor(0, bytes(de[i] ^ gt[i] for i in range(8)))
    # anchor O=28 at plaintext[12:16]
    anchor(12, bytes(de[12 + i] ^ b"\x1c\x00\x00\x00"[i] for i in range(4)))
    # find + anchor the metadata crib in de
    L = len(CRIB)
    meta_pos = None
    for pos in range(300, len(de) - L):
        if bytes(de[pos + i] ^ CRIB[i] for i in range(L))[:0] == b"":
            dec = bytes(de[pos + i] ^ (de[pos] ^ CRIB[0]) for i in range(1))  # cheap skip
        # direct: does de^crib give a KS that when re-applied reproduces crib? trivially yes; need a check
    # simpler: crib-drag with a printable check on es beyond divergence
    for pos in range(300, len(de) - L):
        kseg = bytes(de[pos + i] ^ CRIB[i] for i in range(L))
        # es at same pos decrypts to mostly-text?
        if pos + L <= len(es):
            des = bytes(es[pos + i] ^ kseg[i] for i in range(L))
            if sum(1 for x in des if x in GOOD) >= L - 2:
                meta_pos = pos
                anchor(pos, kseg)
                break
    print("meta crib anchored at", meta_pos)

    # statistical fill
    for i in range(n):
        if known[i]:
            continue
        best_k, best_s = 0, -1
        cde, ces = de[i], es[i]
        same = (cde == ces)  # shared/english region
        for k in range(256):
            a = cde ^ k
            if a not in GOOD:
                continue
            if same:
                s = ENG_FREQ.get(a, 0) + (1 if a in GOOD else 0)
            else:
                b = ces ^ k
                if b not in GOOD:
                    continue
                s = 2 + ENG_FREQ.get(a, 0) + ENG_FREQ.get(b, 0)
            if s > best_s:
                best_s, best_k = s, k
        ks[i] = best_k

    pt = bytes(de[i] ^ ks[i] for i in range(n))
    magic, rev, N, O, T = struct.unpack("<IIIII", pt[:20])
    print(f"decrypted header: magic={magic:08x} rev={rev} N={N} O={O} T={T}")
    ok = (magic == 0x950412de and O == 28)
    print("gettext header valid?", ok, "| N sane?", 100 < N < 100000)
    # if header sane, parse strings via the tables (English msgids are trustworthy: shared region)
    if magic == 0x950412de and 100 < N < 200000 and O == 28 and T == 28 + 8 * N and T + 8 * N <= n:
        # msgid table
        msgids = []
        for k in range(N):
            ln, off = struct.unpack("<II", pt[O + 8 * k: O + 8 * k + 8])
            if off + ln <= n:
                msgids.append(pt[off:off + ln])
        eng = [m for m in msgids if m]
        print(f"parsed {len(eng)} non-empty English msgids")
        for m in eng[:25]:
            try:
                print("  EN:", m.decode("utf-8")[:80])
            except Exception:
                print("  EN(raw):", m[:60])
        # save full keystream + english corpus
        open(os.path.join(HERE, "keystream.bin"), "wb").write(bytes(ks))
        import json
        json.dump([m.decode("utf-8", "replace") for m in msgids],
                  open(os.path.join(HERE, "en_msgids.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        print("saved keystream.bin + en_msgids.json")
    else:
        # header not clean -> statistical KS is noisy in the low-constraint header; still dump text sample
        print("header not clean from statistical KS (expected: header has no text constraint).")
        print("sample decrypted text region [55000:56000]:")
        print(pt[55000:56000].decode("latin1"))

if __name__ == "__main__":
    main()
